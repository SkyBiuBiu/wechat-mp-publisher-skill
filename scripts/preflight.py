#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布前体检 —— 在调微信接口之前，把所有会因为「平台约束」翻车的地方先查一遍。

零第三方依赖，仅用 Python 标准库（Python 3.8+）。Windows / Linux 通用。

分三级：
    P0  阻断。发不出去，或发出去内容一定会坏。必须改。
    P1  警告。发得出去，但排版会塌 / 图片不显示 / 合规有风险。
    P2  建议。不影响发布，改了更好。

用法：
    python preflight.py -c work/config.json          # 体检（有 P0 则退出码 1）
    python preflight.py -c work/config.json --json   # 结构化输出，给 CI 用
    python preflight.py -c work/config.json --warn-only   # 有 P0 也返回 0
    python preflight.py -c work/config.json --no-compliance  # 跳过合规词库
    python preflight.py -c work/config.json --quiet  # 只打印问题清单

被 publish.py 的 draft 流程在发请求前自动调用（可用 --no-preflight 跳过）。
"""

import argparse
import io
import json
import os
import re
import sys

try:  # Windows 老终端是 GBK，输出中文/符号可能炸，统一转 utf-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLE_DIR = os.path.join(ROOT, "assets", "styles")

# ---------------------------------------------------------------- 官方硬上限
# 数值来源：developers.weixin.qq.com → 新增草稿 / 上传图文消息内的图片 接口文档
# 详见 references/wechat-api-reference.md 第二节
L_TITLE = 32             # 标题，总长度不超过 32 个字
L_AUTHOR = 16            # 作者，不超过 16 个字
L_DIGEST = 120           # 摘要，不超过 120 个字（留空则抓正文前 54 字）
L_DIGEST_AUTO = 54       # 摘要留空时的自动抓取字数
L_CONTENT_CHARS = 20000  # 正文必须少于 2 万字符
L_CONTENT_BYTES = 1024 * 1024      # 正文小于 1MB
L_SOURCE_URL_BYTES = 1024          # content_source_url 不超过 1KB
L_COVER_BYTES = 10 * 1024 * 1024   # 封面永久素材图片上限 10MB
L_INLINE_BYTES = 1024 * 1024       # uploadimg 单张 < 1MB
NEAR_RATIO = 0.95        # 正文字数达到上限的这个比例就预警

INLINE_IMG_EXT = (".jpg", ".jpeg", ".png")
COVER_IMG_EXT = (".bmp", ".png", ".jpeg", ".jpg", ".gif")

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r'\bsrc\s*=\s*["\']([^"\']*)["\']', re.I)
STYLE_ATTR_RE = re.compile(r'\bstyle\s*=\s*["\']([^"\']*)["\']', re.I)
TAG_RE = re.compile(r"<[^>]+>")
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.I)
LINE_HEIGHT_RE = re.compile(r"line-height\s*:\s*(\d+(?:\.\d+)?)\s*(?:;|\"|')", re.I)
PARA_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)

P0, P1, P2 = "P0", "P1", "P2"
LEVEL_NAME = {P0: "阻断", P1: "警告", P2: "建议"}

# ---------------------------------------------------------------- 合规词库
# 只做「提示」，不做拦截：命中即列出上下文，由人判断是不是技术术语。
# 全部归 P1。用 --no-compliance 可整体跳过。
COMPLIANCE_RULES = [
    ("广告法绝对化用语", P1, "《广告法》第九条禁用绝对化表述，公众号审核也会盯这类词",
     [r"国家级", r"世界级", r"最高级", r"最佳", r"最好", r"最强", r"最优",
      r"最便宜", r"最低价", r"顶级", r"极致", r"史上最",
      r"全国第一", r"全网第一", r"行业第一", r"销量第一", r"排名第一",
      r"第一品牌", r"第一名", r"唯一", r"独家", r"首个", r"首创",
      r"100%", r"绝对", r"永久有效", r"NO\.?\s*1"]),
    ("诱导分享 / 诱导关注", P1, "微信明令禁止诱导分享、集赞、关注类表述，可能被限制功能",
     [r"分享到朋友圈", r"发到朋友圈", r"转发本文", r"求转发", r"集赞", r"点赞过",
      r"扫码关注", r"长按.{0,4}关注", r"关注我(?:们)?(?:后|才能|即可)", r"点击蓝字关注"]),
    ("站外导流信息", P1, "公众号正文不得放微信号、QQ、手机号、二维码等站外引流信息",
     [r"微信号\s*[:：]", r"加(?:我|作者)?微信", r"个人微信号", r"QQ\s*群?\s*[:：]",
      r"加群", r"1[3-9]\d{9}"]),
    ("金融投资承诺性表述", P1, "保本、稳赚、零风险类承诺性表述属违规，金融保险类内容风险最高",
     [r"保本", r"保收益", r"稳赚", r"包赚", r"躺赚", r"零风险", r"无风险",
      r"承诺收益", r"稳赚不赔", r"年化收益\s*\d", r"高额回报"]),
    ("医疗疗效类表述", P1, "医疗健康类内容不得表述疗效，需资质",
     [r"治愈", r"根治", r"包治", r"抗癌", r"疗效", r"药效", r"药到病除"]),
]


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
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def strip_tags(html):
    text = TAG_RE.sub("", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()


def peek(text, start, end, width=14):
    """截取命中词前后一小段，输出里好定位。"""
    a = max(0, start - width)
    b = min(len(text), end + width)
    frag = text[a:b].replace("\n", " ")
    return ("…" if a > 0 else "") + frag + ("…" if b < len(text) else "")


def img_size(path):
    """读图片像素尺寸。只认 png / jpg / gif，失败返回 None（零依赖，手解文件头）。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                import struct
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:3] == b"GIF":
                import struct
                w, h = struct.unpack("<HH", head[6:10])
                return int(w), int(h)
            if head[:2] == b"\xff\xd8":  # JPEG：扫 SOF 段
                f.seek(2)
                import struct
                while True:
                    b = f.read(1)
                    while b and b != b"\xff":
                        b = f.read(1)
                    if not b:
                        return None
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if not marker:
                        return None
                    if 0xC0 <= marker[0] <= 0xCF and marker[0] not in (0xC4, 0xC8, 0xCC):
                        f.read(3)
                        h, w = struct.unpack(">HH", f.read(4))
                        return int(w), int(h)
                    seg = f.read(2)
                    if len(seg) < 2:
                        return None
                    f.seek(struct.unpack(">H", seg)[0] - 2, 1)
    except Exception:
        return None
    return None


def load_config_soft(path):
    """读配置但不因缺凭证中断：体检应该在没凭证时也能跑。"""
    problems = []
    cfg = {}
    if not os.path.isfile(path):
        problems.append("配置文件不存在：{}".format(path))
        return cfg, problems, os.getcwd()
    try:
        cfg = json.loads(read_text(path))
    except ValueError as e:
        problems.append("{} 不是合法 JSON：{}".format(path, e))
        return {}, problems, os.path.dirname(os.path.abspath(path))
    for k in ("appid", "appsecret"):
        v = str(cfg.get(k) or os.environ.get(
            "WECHAT_MP_" + ("APPID" if k == "appid" else "APPSECRET")) or "").strip()
        if not v:
            problems.append("缺少 {}（不影响本次体检，但发布时会失败）".format(k))
    return cfg, problems, os.path.dirname(os.path.abspath(path))


def resolve(base_dir, p):
    if not p:
        return None
    return p if os.path.isabs(p) else os.path.join(base_dir, p)


# ---------------------------------------------------------------- 各项检查
def check_meta(cfg, findings):
    art = cfg.get("article") or {}
    title = (art.get("title") or "").strip()
    if not title:
        add(findings, P0, "WX001", "缺少文章标题",
            "article.title 为空，微信必填", "在 config.json 里填 title")
    elif len(title) > L_TITLE:
        add(findings, P0, "WX002", "标题超过 {} 字".format(L_TITLE),
            "当前 {} 字，超 {} 字".format(len(title), len(title) - L_TITLE),
            "砍到 {} 字以内，微信按字符数硬校验".format(L_TITLE))

    author = (art.get("author") or cfg.get("author") or "").strip()
    if len(author) > L_AUTHOR:
        add(findings, P0, "WX003", "作者名超过 {} 字".format(L_AUTHOR),
            "当前 {} 字".format(len(author)), "精简到 {} 字以内".format(L_AUTHOR))

    digest = (art.get("digest") or "").strip()
    if not digest:
        add(findings, P2, "WX201", "摘要留空",
            "微信会自动抓取正文前 {} 字，可能抓到半句话".format(L_DIGEST_AUTO),
            "建议手写 60-120 字的摘要，信息量比自动截断大")
    elif len(digest) > L_DIGEST:
        add(findings, P0, "WX004", "摘要超过 {} 字".format(L_DIGEST),
            "当前 {} 字".format(len(digest)), "删到 {} 字以内".format(L_DIGEST))

    url = (art.get("content_source_url") or "").strip()
    n_url = len(url.encode("utf-8"))
    if not url:
        add(findings, P2, "WX202", "未配置原文链接",
            "content_source_url 为空，文末不会有「阅读原文」",
            "有对应仓库/文档就填上，转化和溯源都靠它")
    elif n_url > L_SOURCE_URL_BYTES:
        add(findings, P0, "WX005", "原文链接超过 1KB",
            "当前 {} 字节".format(n_url), "换短链，或去掉多余的 UTM 参数")

    if not int(cfg.get("need_open_comment", 0) or 0):
        add(findings, P2, "WX203", "评论未开启",
            "need_open_comment=0", "想收反馈就把 need_open_comment 改成 1")


def check_cover(cfg, base_dir, findings, stats):
    """封面：图文消息的 thumb_media_id 必填，走永久素材接口，上限 10MB。"""
    art = cfg.get("article") or {}
    cf = art.get("cover_file")
    if not cf:
        add(findings, P0, "WX016", "未配置封面图",
            "图文消息的 thumb_media_id 是必填项，缺了微信会报 40007",
            "补 article.cover_file；没有素材就先用 make_assets.py 生成 900x383")
        return
    p = resolve(base_dir, cf)
    if not os.path.isfile(p):
        add(findings, P0, "WX017", "封面图文件不存在",
            "{}（{})".format(cf, p), "检查路径拼写")
        return
    size = os.path.getsize(p)
    stats["cover_bytes"] = size
    ext = os.path.splitext(p)[1].lower()
    if ext not in COVER_IMG_EXT:
        add(findings, P0, "WX019", "封面图格式不支持",
            "{} 是 {}".format(cf, ext),
            "永久素材支持 bmp/png/jpeg/jpg/gif，建议用 png")
    if size > L_COVER_BYTES:
        add(findings, P0, "WX018", "封面图超过 10MB",
            "{} 有 {:.2f} MB".format(cf, size / 1048576.0),
            "压缩后再传，或用 make_assets.py 重新生成")

    wh = img_size(p)
    if wh:
        w, h = wh
        stats["cover_size"] = "{}x{}".format(w, h)
        ratio = w / float(h) if h else 0
        if abs(ratio - 2.35) > 0.35:
            add(findings, P1, "WX115", "封面比例偏离 2.35:1",
                "当前 {}x{}（{:.2f}:1），公众号首图按 2.35:1 展示".format(w, h, ratio),
                "重做成 900x383 最稳，或在 config 里用 cover_info.crop_percent_list 指定裁剪")
        if w < 600:
            add(findings, P2, "WX212", "封面分辨率偏低",
                "宽 {}px".format(w), "封面建议 900x383（宽不小于 600px），小图会被拉糊")


def check_content(cfg, base_dir, findings, stats):
    art = cfg.get("article") or {}
    content_file = art.get("content_file")
    if not content_file:
        add(findings, P0, "WX006", "未配置正文文件",
            "article.content_file 为空", "指向你的 article.html")
        return None, None

    path = resolve(base_dir, content_file)
    if not os.path.isfile(path):
        add(findings, P0, "WX007", "正文文件不存在",
            path, "检查路径，注意相对路径是相对 config.json 所在目录")
        return None, path

    raw = read_text(path)
    content, n_cmt = COMMENT_RE.subn("", raw)
    if n_cmt:
        out("[i] 已剥离 {} 段 HTML 注释（公众号也会过滤，不计入校验）".format(n_cmt))

    # ---- 字符数与体积：微信按 content 字段的 HTML 长度算
    n_chars = len(content)
    n_bytes = len(content.encode("utf-8"))
    stats["content_chars"] = n_chars
    stats["content_bytes"] = n_bytes
    stats["text_chars"] = len(strip_tags(content))

    if n_chars > L_CONTENT_CHARS:
        add(findings, P0, "WX008", "正文超过 2 万字符",
            "当前 {} 字符，超 {} 字符（按 HTML 长度计，不是纯文本字数）".format(
                n_chars, n_chars - L_CONTENT_CHARS),
            "把代码块用 enhance_content.py 重建（内联样式卡片比裸 HTML 省大量字符）、"
            "mermaid 渲染成 PNG，或按章节拆成系列")
    elif n_chars >= L_CONTENT_CHARS * NEAR_RATIO:
        add(findings, P1, "WX101", "正文接近 2 万字符上限",
            "当前 {} 字符（{:.0f}%），再补内容就会超".format(
                n_chars, n_chars * 100.0 / L_CONTENT_CHARS),
            "留出余量，或提前规划拆篇")

    if n_bytes > L_CONTENT_BYTES:
        add(findings, P0, "WX009", "正文超过 1MB",
            "当前 {:.2f} MB".format(n_bytes / 1048576.0),
            "通常是 base64 内嵌图片导致的，改成本地图片文件")

    if n_chars < 300:
        add(findings, P1, "WX102", "正文过短",
            "剥离标签后只有 {} 字".format(stats["text_chars"]),
            "确认是不是漏贴内容；公众号对过短内容的推荐权重也低")

    # ---- 会被公众号剥掉的写法
    if re.search(r"<style\b", content, re.I):
        add(findings, P1, "WX103", "<style> 块会被剥离",
            "公众号编辑器不保留 style 标签", "把样式全部内联到标签的 style 属性上")
    n_class = len(re.findall(r'\bclass\s*=', content, re.I))
    if n_class:
        add(findings, P1, "WX104", "class 属性会被剥离",
            "发现 {} 处 class=".format(n_class), "改成内联 style，class 写了等于没写")
    n_on = len(re.findall(r'\son[a-z]+\s*=', content, re.I))
    if n_on:
        add(findings, P1, "WX105", "内联事件属性会被剥离",
            "发现 {} 处 on*= （如 onclick）".format(n_on), "删掉，公众号不执行 JS")
    for tag in ("script", "iframe", "form", "input", "video", "audio", "canvas"):
        if re.search(r"<" + tag + r"\b", content, re.I):
            lvl = P0 if tag == "script" else P1
            code = "WX010" if tag == "script" else "WX106"
            add(findings, lvl, code, "正文含 <{}> 标签".format(tag),
                "该标签在公众号里会被剥离，内容会缺一块",
                "删掉，或改成静态截图")

    # ---- 锚点与链接
    anchors = re.findall(r'<a\b[^>]*href\s*=\s*["\']#([^"\']*)["\']', content, re.I)
    if anchors:
        add(findings, P1, "WX107", "正文含站内锚点链接",
            "发现 {} 处 href=\"#...\"".format(len(anchors)),
            "公众号不支持页内跳转，把 <a href=\"#x\"> 降级成 <span> 或纯文本")
    ext = [u for u in re.findall(r'<a\b[^>]*href\s*=\s*["\'](https?://[^"\']+)["\']', content, re.I)]
    if ext:
        add(findings, P2, "WX204", "正文含站外超链接",
            "发现 {} 处外链".format(len(ext)),
            "公众号里外链不可直接跳转（只提示复制），重要的放 content_source_url")

    # ---- 图片
    check_images(content, base_dir, findings, stats)

    # ---- 排版
    check_layout(content, findings, stats)

    # ---- 代码块与 mermaid
    check_code_blocks(content, findings)

    # ---- 摘要与「阅读原文」的一致性
    if not (art.get("content_source_url") or "").strip():
        plain = strip_tags(content)
        if "阅读原文" in plain:
            add(findings, P1, "WX108", "正文提到「阅读原文」但没配链接",
                "content_source_url 为空，读者点了没反应",
                "填上 content_source_url，或删掉这句引导")

    return content, path


def check_images(content, base_dir, findings, stats):
    tags = IMG_RE.findall(content)
    stats["images"] = len(tags)
    local, external, inline = [], [], []

    for tag in tags:
        m = SRC_RE.search(tag)
        src = (m.group(1) if m else "").strip()
        if not src:
            continue
        if src.startswith("data:"):
            inline.append(src[:40])
            continue
        if re.match(r"^(https?:)?//", src):
            if "mmbiz.qpic.cn" in src or "mmbiz.qlogo.cn" in src:
                pass  # 已经是微信图床，正常
            else:
                external.append(src)
            continue
        local.append(src)

    for src in inline:
        add(findings, P0, "WX013", "正文含 base64 内嵌图片",
            src + "…", "内嵌图会让正文迅速超过 1MB 上限，改成本地图片文件")
    for src in external:
        add(findings, P0, "WX011", "正文含外链图（会被静默过滤）",
            src[:80],
            "改成本地相对路径，如 <img src=\"assets/xxx.png\">，脚本会自动上传换微信图床")
    oversized = []
    for src in local:
        p = resolve(base_dir, src)
        if not os.path.isfile(p):
            add(findings, P0, "WX012", "正文图片文件不存在",
                "{}（{})".format(src, p), "检查路径拼写，或删掉这个 <img>")
            continue
        size = os.path.getsize(p)
        ext = os.path.splitext(p)[1].lower()
        if ext not in INLINE_IMG_EXT:
            add(findings, P0, "WX014", "正文图片格式不支持",
                "{} 是 {}".format(src, ext), "uploadimg 只收 jpg/png，先转格式")
        if size > L_INLINE_BYTES:
            add(findings, P0, "WX015", "正文图片超过 1MB",
                "{} 有 {:.2f} MB".format(src, size / 1048576.0),
                "压缩到 1MB 以下；截图建议 deviceScaleFactor 设 2 就够")
        wh = img_size(p)
        if wh and wh[0] > 2000:
            oversized.append("{}（{}x{}）".format(src, wh[0], wh[1]))

    if oversized:
        add(findings, P2, "WX213", "正文图分辨率过大",
            "、".join(oversized[:3]),
            "正文区宽约 677px，图片宽 1080-1500px 足够，过宽只会白占体积")

    if stats["images"] > 20:
        add(findings, P2, "WX205", "正文图片较多",
            "共 {} 张".format(stats["images"]),
            "单篇 20 张以内阅读体验更好，也少触发加载失败")

    for tag in tags:
        m = STYLE_ATTR_RE.search(tag)
        style = (m.group(1) if m else "")
        if "width" not in style.lower():
            add(findings, P1, "WX109", "有图片没设宽度",
                tag[:60] + "…", "加 style=\"width:100%;display:block;\"，微信不会自动做响应式")
            break


def check_layout(content, findings, stats):
    # 表格
    for tm in re.finditer(r"<table\b[^>]*>", content, re.I):
        if "border-collapse" not in tm.group(0).lower():
            add(findings, P1, "WX110", "表格缺 border-collapse",
                tm.group(0)[:60],
                "写成 style=\"width:100%;border-collapse:collapse;\"，否则手机上单元格会散")
            break
    cells = re.findall(r"<t[dh]\b[^>]*>", content, re.I)
    if cells and not any("padding" in c.lower() for c in cells):
        add(findings, P1, "WX111", "表格单元格缺内边距",
            "发现 {} 个 <td>/<th> 都没写 padding".format(len(cells)),
            "给每个 <td>/<th> 加 style=\"padding:9px 10px;\"，不然文字贴边")
    stats["tables"] = len(re.findall(r"<table\b", content, re.I))

    # 段落长度
    long_paras = 0
    for pm in PARA_RE.finditer(content):
        plain = strip_tags(pm.group(1))
        if len(plain) > 250:
            long_paras += 1
    if long_paras:
        add(findings, P1, "WX112", "有超长段落",
            "{} 个段落超过 250 字".format(long_paras),
            "手机上一屏只看 3 行左右，长段拆开或改成表格/清单")

    # 充数写法
    if re.search(r"<p\b[^>]*>(?:\s|&nbsp;|<br\s*/?>)*</p>", content, re.I):
        add(findings, P2, "WX206", "存在空段落",
            "用空 <p> 撑间距", "改用段落的 margin 控制间距，空段落会被微信吃掉")
    if re.search(r"(<br\s*/?>\s*){3,}", content, re.I):
        add(findings, P2, "WX207", "存在连续换行",
            "3 个以上连续 <br>", "同样改用 margin，连续 br 在不同设备上高度不一致")

    # 标题标签
    h_tags = re.findall(r"<h[1-6]\b", content, re.I)
    if h_tags:
        add(findings, P1, "WX113", "正文用了 h1~h6 标签",
            "发现 {} 处".format(len(h_tags)),
            "公众号会覆盖标题标签样式，改用 <p style=\"font-weight:bold;\"> 更可控")

    # 字号行高
    sizes = [float(x) for x in FONT_SIZE_RE.findall(content)]
    if sizes:
        main = sizes[0]
        stats["font_size"] = main
        if main < 14:
            add(findings, P2, "WX208", "正文字号偏小",
                "首个 font-size 是 {}px".format(main), "手机阅读推荐 15-16px")
        elif main > 18:
            add(findings, P2, "WX209", "正文字号偏大",
                "首个 font-size 是 {}px".format(main), "超过 18px 一屏放不下几行")
    lh = LINE_HEIGHT_RE.search(content)
    if lh:
        v = float(lh.group(1))
        stats["line_height"] = v
        if v < 1.6:
            add(findings, P2, "WX210", "行高偏紧",
                "line-height: {}".format(v), "正文行高 1.75-1.9 在手机上最舒服")


def check_code_blocks(content, findings):
    """未渲染的 mermaid / markdown 围栏 + 代码块内联样式完整性。"""
    fences = re.findall(r"(?m)^[ \t]*```", content)
    mmd_blocks = re.findall(r'class\s*=\s*["\'][^"\']*mermaid[^"\']*["\']', content)
    if fences or mmd_blocks:
        add(findings, P1, "WX216", "正文残留 Markdown 围栏或 mermaid 源码",
            "发现 {} 处 ``` 围栏、{} 处 mermaid 块，原样发出去就是一段乱码".format(
                len(fences), len(mmd_blocks)),
            "跑 python scripts/enhance_content.py -c config.json："
            "mermaid 渲染成 PNG，代码块重建为内联样式卡片")

    bad_ws = 0
    for m in re.finditer(r"<(pre|code)\b[^>]*>", content, re.I):
        if "white-space" not in m.group(0).lower():
            bad_ws += 1
    if bad_ws:
        add(findings, P1, "WX217", "代码块缺 white-space 内联样式",
            "发现 {} 个 <pre>/<code> 没写 white-space:pre-wrap，"
            "公众号会折叠空白，缩进和换行全丢".format(bad_ws),
            "用 enhance_content.py 重建代码块（含语法高亮与长按复制支持），"
            "或给每个 pre/code 补内联样式")


def check_compliance(content, findings):
    plain = strip_tags(content)
    for name, level, why, patterns in COMPLIANCE_RULES:
        snippets, words = [], []
        for pat in patterns:
            for m in re.finditer(pat, plain, re.I):
                snip = peek(plain, m.start(), m.end())
                if snip not in snippets:
                    snippets.append(snip)
                    words.append(m.group(0))
                if len(snippets) >= 3:
                    break
            if len(snippets) >= 3:
                break
        if snippets:
            add(findings, level, "WX114", "疑似{}".format(name),
                "命中「{}」；上下文：{}".format(
                    "、".join(words[:3]), " | ".join(snippets[:2])),
                why + "。若属技术术语（如「唯一标识」）可忽略",
                context="、".join(sorted(set(words))))


def check_style(cfg, findings, stats):
    st = cfg.get("style") or {}
    preset = st.get("preset")
    if not preset:
        add(findings, P2, "WX211", "未选择风格预设",
            "config.json 里没有 style.preset，正文风格完全取决于模板本身",
            "用 python scripts/apply_style.py --list 看可选路线，"
            "再 apply_style.py --preset <id> 渲染正文")
        return
    path = os.path.join(STYLE_DIR, str(preset) + ".json")
    if not os.path.isfile(path):
        add(findings, P1, "WX212", "风格预设不存在",
            "style.preset = {}".format(preset),
            "用 python scripts/apply_style.py --list 查看可用 id")
        return
    try:
        data = json.loads(read_text(path))
    except ValueError:
        add(findings, P1, "WX213", "风格预设文件不是合法 JSON", path, "检查该文件")
        return
    stats["style"] = data.get("name") or preset

    ov = st.get("overrides") or {}
    if not isinstance(ov, dict):
        add(findings, P1, "WX214", "style.overrides 必须是对象",
            "当前类型 {}".format(type(ov).__name__),
            "写成 {\"primary\": \"#1f4e8c\"} 这样的键值对")
    else:
        valid = set((data.get("tokens") or {}).keys())
        real = dict((k, v) for k, v in ov.items() if not str(k).startswith("_"))
        bad = [k for k in real if k not in valid]
        if bad:
            add(findings, P1, "WX214", "style.overrides 里有未知 token",
                "无法识别：{}".format("、".join(sorted(bad))),
                "可用的 token 以预设文件里的 tokens 为准，写错等于没生效")
        if real:
            stats["style_overrides"] = len(real)

    # 风格与正文的实际写法是否对得上（emoji 是最容易跑偏的一项）
    policy = ((data.get("writing") or {}).get("emoji") or "")
    if "禁止" in policy:
        stats["emoji_banned"] = True


def check_emoji(content, findings, stats):
    if not stats.get("emoji_banned"):
        return
    plain = strip_tags(content)
    emo = re.findall(
        "[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", plain)
    if emo:
        add(findings, P2, "WX215", "所选风格禁用 emoji，但正文里有",
            "发现 {} 个：{}".format(len(emo), "".join(sorted(set(emo))[:8])),
            "该风格的写作约束写明禁用 emoji，删掉或换风格（--preset magazine-warm 允许少量）")


# ---------------------------------------------------------------- 报告
def build_report(cfg, base_dir, with_compliance=True):
    findings = []
    stats = {"content_chars": 0, "text_chars": 0, "images": 0, "tables": 0}
    check_meta(cfg, findings)
    check_cover(cfg, base_dir, findings, stats)
    content, _ = check_content(cfg, base_dir, findings, stats)
    if content:
        if with_compliance:
            check_compliance(content, findings)
        check_emoji(content, findings, stats)
    check_style(cfg, findings, stats)

    order = {P0: 0, P1: 1, P2: 2}
    findings.sort(key=lambda f: (order[f.level], f.code))
    return findings, stats


def render_bar(cur, total, width=28):
    filled = int(round(cur * width / float(total))) if total else 0
    filled = max(0, min(width, filled))
    return "[{}{}]".format("#" * filled, "-" * (width - filled))


def print_report(findings, stats, cfg_path, quiet=False):
    counts = {P0: 0, P1: 0, P2: 0}
    for f in findings:
        counts[f.level] += 1

    if not quiet:
        out("=" * 66)
        out("  wechat-mp-publisher · 发布前体检")
        out("  配置：{}".format(cfg_path))
        out("=" * 66)

    if not findings:
        out("[OK] 没有发现问题，可以发。")
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

    n_chars = stats.get("content_chars", 0)
    bits = []
    bits.append("正文 {} 字符 {} {}/{}".format(
        n_chars, render_bar(n_chars, L_CONTENT_CHARS), n_chars, L_CONTENT_CHARS))
    bits.append("纯文本 {} 字".format(stats.get("text_chars", 0)))
    bits.append("图片 {} 张".format(stats.get("images", 0)))
    if stats.get("tables"):
        bits.append("表格 {} 个".format(stats["tables"]))
    if stats.get("cover_size"):
        bits.append("封面 {}".format(stats["cover_size"]))
    if stats.get("style"):
        bits.append("风格 {}".format(stats["style"]))
    if stats.get("style_overrides"):
        bits.append("自定义 {} 项".format(stats["style_overrides"]))
    out("-" * 66)
    out("统计：P0×{}  P1×{}  P2×{}".format(counts[P0], counts[P1], counts[P2]))
    out("      " + " | ".join(bits))
    if counts[P0]:
        out("结果：不可发布 —— 先修 P0。{} 项阻断会让微信直接报错或内容残缺。".format(counts[P0]))
    else:
        out("结果：可以发布{}。".format(
            "（{} 项警告建议顺手改掉）".format(counts[P1]) if counts[P1] else ""))


def run(cfg_path, with_compliance=True, warn_only=False, as_json=False,
        quiet=False, config_problems=None, findings=None, stats=None):
    """给 publish.py 也用的入口。返回退出码。"""
    if findings is None:
        cfg, problems, base_dir = load_config_soft(cfg_path)
        config_problems = problems
        if not quiet:
            for p in problems:
                out("[i] {}".format(p))
        findings, stats = build_report(cfg, base_dir, with_compliance)

    if as_json:
        out(json.dumps({
            "config": cfg_path,
            "config_problems": config_problems or [],
            "findings": [f.to_dict() for f in findings],
            "stats": stats,
        }, ensure_ascii=False, indent=2))
    else:
        print_report(findings, stats, cfg_path, quiet=quiet)

    if warn_only:
        return 0
    return 1 if any(f.level == P0 for f in findings) else 0


def main():
    p = argparse.ArgumentParser(
        description="公众号发布前体检：约束 / 排版 / 合规三级检查（零依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("-c", "--config", default=None,
                   help="配置文件路径，默认 当前目录/config.json")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="输出 JSON（CI 友好）")
    p.add_argument("--warn-only", action="store_true",
                   help="即使有 P0 也返回 0（只报告不拦截）")
    p.add_argument("--no-compliance", action="store_true",
                   help="跳过广告法/导流/金融等合规词扫描")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="不打印表头与说明")
    args = p.parse_args()

    cfg_path = args.config
    if not cfg_path:
        cand = os.path.join(os.getcwd(), "config.json")
        cfg_path = cand if os.path.isfile(cand) else os.path.join(HERE, "config.json")

    rc = run(cfg_path, with_compliance=not args.no_compliance,
             warn_only=args.warn_only, as_json=args.as_json, quiet=args.quiet)
    sys.exit(rc)


if __name__ == "__main__":
    main()
