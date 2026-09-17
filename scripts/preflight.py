#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布前体检 —— 只查「微信接口会不会拒」这一类问题。

职责边界（2026-09 收紧）：
    排版与合规  →  validate_gzh_html.py + component_lint.py（双关卡）
    接口硬约束  →  本文件

之所以这么切：排版规则属于主题组件库的范畴，改主题时不该动到这里；
本文件只保留「就算排版完美，微信照样会报错」的那些限制——标题/摘要长度、
正文 2 万字符、图片体积与格式、外链图会被静默过滤、残留的 mermaid 源码。

三级：
    P0  阻断。微信直接报错，或发出去内容一定坏。
    P1  警告。发得出去，但图片不显示 / 版式塌。
    P2  建议。不影响发布。

用法：
    python preflight.py -c work/config.json
    python preflight.py -c work/config.json --json
    python preflight.py -c work/config.json --warn-only
    python preflight.py -c work/config.json --quiet

被 publish.py 的 draft 流程在发请求前自动调用（--no-preflight 可跳过）。
零第三方依赖，Python 3.8+ / Windows / Linux 通用。
"""

import argparse
import io
import json
import os
import re
import sys

try:  # Windows 老终端 GBK，输出中文/符号可能炸
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
THEME_INDEX = os.path.join(ROOT, "references", "theme-index.md")

# ---------------------------------------------------------------- 官方硬上限
# 数值来源：developers.weixin.qq.com → 新增草稿 / 上传图文消息内的图片
# 详见 references/wechat-api-reference.md 第二节
L_TITLE = 32                       # 标题 ≤ 32 字
L_AUTHOR = 16                      # 作者 ≤ 16 字
L_DIGEST = 120                     # 摘要 ≤ 120 字（留空自动抓正文前 54 字）
L_CONTENT_CHARS = 20000            # 正文 < 2 万字符
L_CONTENT_BYTES = 1024 * 1024      # 正文 < 1MB
L_SOURCE_URL_BYTES = 1024          # content_source_url ≤ 1KB
L_COVER_BYTES = 10 * 1024 * 1024   # 封面永久素材 ≤ 10MB
L_INLINE_BYTES = 1024 * 1024       # uploadimg 单张 < 1MB
INLINE_IMG_EXT = (".jpg", ".jpeg", ".png")
COVER_IMG_EXT = (".bmp", ".png", ".jpeg", ".jpg", ".gif")
COVER_RATIO = 2.35                 # 微信推荐 900x383
IMG_WARN_WIDTH = 600               # 正文图低于这个宽度会在手机上糊

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']*)["']""", re.I)
SCRIPT_RE = re.compile(r"<script[\s>]", re.I)
EVENT_ATTR_RE = re.compile(r"""\son[a-z]+\s*=\s*["']""", re.I)
ANCHOR_RE = re.compile(r"""href\s*=\s*["']#""", re.I)
H1H6_TAG_RE = re.compile(r"<h[1-6]\b[^>]*>", re.I)
INLINE_FONTSIZE_RE = re.compile(r"""style\s*=\s*["'][^"']*font-size""", re.I)
FENCE_RE = re.compile(r"^\s*```", re.M)
MERMAID_SRC_RE = re.compile(r"\b(flowchart|graph\s+(?:LR|TD|TB|RL|BT)|sequenceDiagram"
                            r"|classDiagram|stateDiagram|erDiagram|gantt|pie)\b")
EDITOR_ATTR_RE = re.compile(
    r"""\s+data-(?:page-node|node|block|element|editor)[a-z-]*=(?:"[^"]*"|'[^']*')""",
    re.I)

P0, P1, P2 = "P0", "P1", "P2"
LEVEL_NAME = {P0: "阻断", P1: "警告", P2: "建议"}


def out(msg=""):
    print(msg, flush=True)


class Finding(object):
    def __init__(self, level, code, title, detail="", fix="", context=""):
        self.level = level
        self.code = code
        self.title = title
        self.detail = detail
        self.fix = fix
        self.context = context

    def to_dict(self):
        return {"level": self.level, "code": self.code, "title": self.title,
                "detail": self.detail, "fix": self.fix, "context": self.context}


def add(findings, level, code, title, detail="", fix="", context=""):
    findings.append(Finding(level, code, title, detail, fix, context))


# ---------------------------------------------------------------- 工具
def read_text(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def strip_tags(html):
    text = re.sub(r"<[^>]+>", "", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def img_size(path):
    """读图片像素尺寸（零依赖，手解文件头）。失败返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                import struct
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:3] == b"GIF":
                import struct
                w, h = struct.unpack("<HH", head[6:10])
                return int(w), int(h)
            if head[:2] == b"\xff\xd8":     # JPEG：扫 SOF 段
                f.seek(2)
                data = f.read()
                i = 0
                while i < len(data) - 9:
                    if data[i] != 0xFF:
                        i += 1
                        continue
                    marker = data[i + 1]
                    if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6,
                                  0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        h = (data[i + 5] << 8) | data[i + 6]
                        w = (data[i + 7] << 8) | data[i + 8]
                        return int(w), int(h)
                    if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                        i += 2
                        continue
                    seg = (data[i + 2] << 8) | data[i + 3]
                    i += 2 + seg
    except Exception:
        return None
    return None


def registered_themes():
    """从 references/theme-index.md 读已注册主题标识（排除 theme-generator.md）。"""
    if not os.path.isfile(THEME_INDEX):
        return set()
    ids = set(re.findall(r"theme-([A-Za-z0-9_-]+)\.md", read_text(THEME_INDEX)))
    return ids - {"generator"}


def render_bar(n, total, width=14):
    filled = int(round(width * min(float(n) / total, 1.0)))
    return "[" + "#" * filled + "." * (width - filled) + "]"


# ---------------------------------------------------------------- 检查项
def check_config(cfg, cfg_path, findings):
    """凭证/主题这些「配置本身」的问题。"""
    for k in ("appid", "appsecret"):
        v = str(cfg.get(k) or "")
        if not v:
            add(findings, P0, "WX001", "缺少 {}".format(k),
                detail="config.json 与环境变量都没有提供 {}".format(k),
                fix="填进 config.json，或设环境变量 WECHAT_MP_{}".format(
                    "APPID" if k == "appid" else "APPSECRET"))
        elif v.lower().startswith("wx000") or v.startswith("你的"):
            add(findings, P0, "WX002", "{} 还是占位值".format(k), fix="填真实数据")

    theme = cfg.get("theme")
    if not theme:
        add(findings, P1, "WX003", "没记录主题标识（config.theme）",
            detail="排版用的是哪套主题组件库没有落到配置里",
            fix="填 theme 字段，取值见 references/theme-index.md")
    else:
        ids = registered_themes()
        if ids and theme not in ids:
            add(findings, P0, "WX004", "主题标识未注册：{}".format(theme),
                detail="已注册：{}".format("、".join(sorted(ids))),
                fix="改成已注册的主题标识，或按 references/theme-generator.md 登记新主题")


def check_article_meta(cfg, findings):
    art = cfg.get("article") or {}
    title = (art.get("title") or "").strip()
    if not title:
        add(findings, P0, "WX010", "缺少文章标题", fix="填 article.title")
    elif len(title) > L_TITLE:
        add(findings, P0, "WX011", "标题超过 {} 字".format(L_TITLE),
            detail="当前 {} 字".format(len(title)),
            fix="微信公众号硬限制，超了接口直接报错")

    author = (art.get("author") or cfg.get("author") or "").strip()
    if len(author) > L_AUTHOR:
        add(findings, P0, "WX012", "作者名超过 {} 字".format(L_AUTHOR),
            detail="当前 {} 字".format(len(author)))

    digest = (art.get("digest") or "").strip()
    if not digest:
        add(findings, P2, "WX201", "摘要留空",
            fix="留空会自动抓正文前 54 字，想要更精准建议手写")
    elif len(digest) > L_DIGEST:
        add(findings, P0, "WX013", "摘要超过 {} 字".format(L_DIGEST),
            detail="当前 {} 字".format(len(digest)))

    url = art.get("content_source_url") or ""
    if not url:
        add(findings, P2, "WX202", "未配置原文链接",
            fix="留空则文末不显示「阅读原文」；发布链路跳不通时建议留空")
    elif len(url.encode("utf-8")) > L_SOURCE_URL_BYTES:
        add(findings, P0, "WX014", "原文链接超过 1KB")

    if not cfg.get("need_open_comment"):
        add(findings, P2, "WX203", "评论未开启", fix="需要互动时设 need_open_comment=1")


def check_content(cfg, base_dir, findings, stats):
    art = cfg.get("article") or {}
    cf = art.get("content_file")
    if not cf:
        add(findings, P0, "WX020", "未配置正文文件", fix="填 article.content_file")
        return None
    path = cf if os.path.isabs(cf) else os.path.join(base_dir, cf)
    if not os.path.isfile(path):
        add(findings, P0, "WX021", "正文文件不存在", detail=path,
            fix="先按主题组件库装配出正文 HTML")
        return None

    raw = read_text(path)
    # 注释与编辑器注入的记账属性不属于正文，不占 2 万字符额度
    content, n_cmt = COMMENT_RE.subn("", raw)
    content, n_attr = EDITOR_ATTR_RE.subn("", content)
    if n_cmt:
        out("[i] 剥离 {} 段 HTML 注释（微信也会过滤）".format(n_cmt))
    if n_attr:
        out("[i] 剥离 {} 处编辑器注入属性（微信也会过滤）".format(n_attr))

    n_chars = len(content)
    stats["content_chars"] = n_chars
    stats["text_chars"] = len(strip_tags(content))
    stats["content_path"] = path

    # 2 万字符：官方文档口径，但实测（2026-09-17，draft/add）45258 字符被接受，
    # 回查 draft/get 得 45390 字符、尾部一致，即完整落库未截断。所以降为提示不阻断，
    # 真正的硬约束是 1MB 字节数。判定依据见 references/wechat-api-reference.md 第六节。
    if n_chars > L_CONTENT_CHARS:
        add(findings, P1, "WX022", "正文超过 2 万字符（文档口径，实测未强制）",
            detail="当前 {} 字符，超出 {} 字".format(n_chars, n_chars - L_CONTENT_CHARS),
            fix="接口目前接受且不截断，可直接发；若接口回字数类错误，"
                "再按主题库的精简组件重排，或把长代码/长表格转成图片、拆篇")
    if len(content.encode("utf-8")) > L_CONTENT_BYTES:
        add(findings, P0, "WX023", "正文超过 1MB")
    if n_chars < 200:
        add(findings, P1, "WX102", "正文过短", detail="仅 {} 字符".format(n_chars))

    if SCRIPT_RE.search(content):
        add(findings, P0, "WX024", "<script> 会被微信过滤",
            fix="删掉；交互一律不做")
    if EVENT_ATTR_RE.search(content):
        add(findings, P1, "WX103", "内联事件属性（onclick 等）会被剥离")
    # 标题标签：主题组件库（如摸鱼绿的步骤卡）本来就用 <h4>，不是问题本身。
    # 真正的风险是没写内联 font-size —— 那样平台默认标题样式会顶上来。
    h_tags = H1H6_TAG_RE.findall(content)
    if h_tags:
        naked = [h for h in h_tags if not INLINE_FONTSIZE_RE.search(h)]
        if naked:
            add(findings, P2, "WX104",
                "{} 个 h1~h6 没写内联 font-size".format(len(naked)),
                detail=naked[0][:90],
                fix="标题标签有平台默认字号/间距；主题库的 h 组件都显式写了 "
                    "font-size/color/margin，照抄即可消掉这条")
    if ANCHOR_RE.search(content):
        add(findings, P1, "WX105", "正文含站内锚点链接",
            fix="公众号不支持页内跳转，锚点会变成死链")

    # 残留的 Markdown 围栏 / mermaid 源码 —— 排版前没处理干净的话会当正文发出去
    fences = FENCE_RE.findall(content)
    if fences:
        add(findings, P0, "WX025", "正文残留 Markdown 围栏（```）",
            detail="共 {} 处".format(len(fences)),
            fix="代码块要用 references/common-components.md 的 1a/1b 组件，"
                "不要留着围栏")
    if re.search(r"```\s*mermaid", content, re.I) or \
            (MERMAID_SRC_RE.search(content) and "<img" not in content[:2000]):
        add(findings, P0, "WX026", "正文残留 mermaid 源码",
            fix="先跑 scripts/render_mermaid.py 渲染成 PNG，再按图片组件引用")

    # 图片
    imgs = IMG_RE.findall(content)
    stats["images"] = len(imgs)
    for i, tag in enumerate(imgs, 1):
        m = SRC_RE.search(tag)
        if not m:
            add(findings, P1, "WX106", "第 {} 张图缺 src".format(i))
            continue
        src = m.group(1).strip()
        if src.startswith("data:"):
            add(findings, P0, "WX027", "第 {} 张图是 base64 内嵌".format(i),
                fix="公众号不接受 data: URI，存成文件走自动上传")
            continue
        if re.match(r"^(https?:)?//", src):
            if not re.search(r"(mmbiz\.qpic\.cn|mmbiz\.qlogo\.cn)", src, re.I):
                add(findings, P0, "WX028", "第 {} 张图是外链图，会被静默过滤".format(i),
                    detail=src[:80],
                    fix="改成相对路径，发布时自动上传换链")
            continue
        abs_path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if not os.path.isfile(abs_path):
            add(findings, P0, "WX029", "第 {} 张图文件不存在".format(i),
                detail=abs_path)
            continue
        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in INLINE_IMG_EXT:
            add(findings, P0, "WX030", "第 {} 张图格式不支持（{}）".format(i, ext),
                fix="uploadimg 只收 jpg/jpeg/png")
        size = os.path.getsize(abs_path)
        if size > L_INLINE_BYTES:
            add(findings, P0, "WX031", "第 {} 张图超过 1MB".format(i),
                detail="{:.2f} MB".format(size / 1048576.0),
                fix="压缩后再放进来（uploadimg 硬限制）")
        if not re.search(r"\bstyle\s*=", tag):
            add(findings, P1, "WX107", "第 {} 张图没有内联样式".format(i),
                fix="用主题库图片组件的 max-width:100%;height:auto 写法")

    if len(imgs) > 8:
        add(findings, P2, "WX204", "正文图片较多（{} 张）".format(len(imgs)),
            fix="图多会拖慢加载，考虑合并或做信息图")
    return content


def check_cover(cfg, base_dir, findings, stats):
    art = cfg.get("article") or {}
    cov = art.get("cover_file")
    if not cov:
        add(findings, P0, "WX040", "未配置封面图",
            detail="图文消息的 thumb_media_id 必填，缺封面微信报 40007",
            fix="跑 scripts/make_assets.py 生成，或自己给一张 900x383")
        return
    path = cov if os.path.isabs(cov) else os.path.join(base_dir, cov)
    if not os.path.isfile(path):
        add(findings, P0, "WX041", "封面文件不存在", detail=path)
        return
    ext = os.path.splitext(path)[1].lower()
    if ext not in COVER_IMG_EXT:
        add(findings, P0, "WX042", "封面格式不支持（{}）".format(ext),
            fix="支持 bmp/png/jpeg/jpg/gif")
    size = os.path.getsize(path)
    stats["cover_size"] = "{:.0f} KB".format(size / 1024.0)
    if size > L_COVER_BYTES:
        add(findings, P0, "WX043", "封面超过 10MB")

    wh = img_size(path)
    if not wh:
        add(findings, P2, "WX205", "读不出封面像素尺寸",
            fix="纯标准库解析，个别 JPEG 变体读不到，肉眼确认一下比例即可")
    else:
        w, h = wh
        stats["cover_wh"] = "{}x{}".format(w, h)
        ratio = float(w) / h if h else 0
        if abs(ratio - COVER_RATIO) > 0.25:
            add(findings, P1, "WX108", "封面比例偏离 2.35:1",
                detail="当前 {}x{}（{:.2f}:1），推荐 900x383".format(w, h, ratio),
                fix="列表页会被裁切，重出一张")
        if w < 900:
            add(findings, P1, "WX109", "封面分辨率偏低，会糊",
                detail="宽 {} px，推荐 900".format(w))


# ---------------------------------------------------------------- 报告
def build_report(cfg_path):
    cfg = {}
    if os.path.isfile(cfg_path):
        try:
            cfg = json.load(io.open(cfg_path, encoding="utf-8"))
        except ValueError as e:
            findings = []
            add(findings, P0, "WX000", "config.json 不是合法 JSON", detail=str(e))
            return cfg, findings, {}, os.path.dirname(os.path.abspath(cfg_path))
    base_dir = os.path.dirname(os.path.abspath(cfg_path))
    findings, stats = [], {}
    check_config(cfg, cfg_path, findings)
    check_article_meta(cfg, findings)
    check_content(cfg, base_dir, findings, stats)
    check_cover(cfg, base_dir, findings, stats)
    return cfg, findings, stats, base_dir


def print_report(findings, stats):
    counts = {P0: 0, P1: 0, P2: 0}
    for f in findings:
        counts[f.level] = counts.get(f.level, 0) + 1

    for lvl in (P0, P1, P2):
        group = [f for f in findings if f.level == lvl]
        if not group:
            continue
        out("")
        out("{} · {} · {} 项".format(lvl, LEVEL_NAME[lvl], len(group)))
        out("-" * 66)
        for f in group:
            out("  [{}] {}".format(f.code, f.title))
            if f.detail:
                out("        现象：{}".format(f.detail))
            if f.fix:
                out("        处理：{}".format(f.fix))
    out("")

    n = stats.get("content_chars", 0)
    if n:
        over = "（超出文档口径 {} 字，见 WX022）".format(n - L_CONTENT_CHARS) \
            if n > L_CONTENT_CHARS else ""
        out("      正文 {} 字符 {} {}/{}{}".format(
            n, render_bar(n, max(L_CONTENT_CHARS, n)), n, L_CONTENT_CHARS, over))
    bits = []
    if stats.get("text_chars"):
        bits.append("纯文本 {} 字".format(stats["text_chars"]))
    if stats.get("images"):
        bits.append("图片 {} 张".format(stats["images"]))
    if stats.get("cover_size"):
        bits.append("封面 {}{}".format(
            stats["cover_size"],
            "（{}）".format(stats["cover_wh"]) if stats.get("cover_wh") else ""))
    if bits:
        out("      " + " | ".join(bits))
    out("-" * 66)
    out("统计：P0×{}  P1×{}  P2×{}".format(counts[P0], counts[P1], counts[P2]))
    if counts[P0]:
        out("结果：不可发布 —— 先修 P0。{} 项阻断会让微信直接报错或内容残缺。"
            .format(counts[P0]))
        out("      排版类问题不在这里查：跑 scripts/validate_gzh_html.py <正文.html>")
    else:
        out("结果：接口侧可以发布{}。".format(
            "（{} 项警告建议顺手改掉）".format(counts[P1]) if counts[P1] else ""))
        out("      别忘了排版关：scripts/validate_gzh_html.py <正文.html>")


def run(cfg_path, warn_only=False, as_json=False, quiet=False):
    """给 publish.py 也用的入口。返回退出码（有 P0 则 1）。"""
    cfg, findings, stats, base_dir = build_report(cfg_path)
    counts = {P0: 0, P1: 0, P2: 0}
    for f in findings:
        counts[f.level] = counts.get(f.level, 0) + 1

    if as_json:
        out(json.dumps({"config": cfg_path,
                        "theme": cfg.get("theme"),
                        "findings": [f.to_dict() for f in findings],
                        "stats": stats,
                        "counts": counts}, ensure_ascii=False, indent=2))
    elif not quiet:
        out("== 发布前体检（接口侧硬约束）==")
        print_report(findings, stats)
    else:
        for f in findings:
            out("[{}] {}".format(f.code, f.title))

    return 0 if (warn_only or not counts[P0]) else 1


def main():
    p = argparse.ArgumentParser(description="发布前体检（只查微信接口硬约束）")
    p.add_argument("-c", "--config", default=None, help="config.json 路径")
    p.add_argument("--json", dest="as_json", action="store_true", help="JSON 输出")
    p.add_argument("--warn-only", action="store_true", help="有 P0 也返回 0")
    p.add_argument("--quiet", action="store_true", help="只打印问题清单")
    args = p.parse_args()

    cfg_path = args.config
    if not cfg_path:
        p.error("缺少 -c/--config")
    if not os.path.isfile(cfg_path):
        out("[X] 配置文件不存在：{}".format(cfg_path))
        sys.exit(1)

    sys.exit(run(cfg_path, warn_only=args.warn_only, as_json=args.as_json,
                 quiet=args.quiet))


if __name__ == "__main__":
    main()
