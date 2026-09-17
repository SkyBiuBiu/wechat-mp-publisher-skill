#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mermaid → PNG 预渲染。

为什么需要这一步：公众号会剥掉 <script> 与 SVG 里的文字，mermaid 源码直接
粘进去是一堆乱码。所以排版前先把 ```mermaid 围栏渲染成 PNG，产物里只留
<img>，图片走发布链路自动上传换链。

在流程里的位置：**排版之前**。渲染完得到一个"图片已就位"的 Markdown 工作
副本，再按主题组件库装配 HTML。

用法：
    python scripts/render_mermaid.py article.md
    python scripts/render_mermaid.py article.md --theme moyu-green
    python scripts/render_mermaid.py article.md --check        # 只列出图，不渲染
    python scripts/render_mermaid.py --list-themes             # 看有哪些主题可用

默认输出：
    <输入去扩展名>.mermaid<扩展名>    工作副本（围栏已换成图片引用）
    <out-dir>/mermaid-<n>.png         渲染产物，默认 assets/

渲染通道（自动选）：
    1. 本地 mmdc（npm i -g @mermaid-js/mermaid-cli）—— 离线、不泄露内容
    2. mermaid.ink 在线服务 —— 免安装，但图表内容会发给该第三方
    config.json 的 mermaid.remote=false 可禁用在线通道。
"""

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
REFS = os.path.join(SKILL_ROOT, "references")
THEME_INDEX = os.path.join(REFS, "theme-index.md")

# ```mermaid ... ``` 围栏（允许前后有空白与其它语言标记）
FENCE_RE = re.compile(
    r"^[ \t]*```[ \t]*(?P<lang>[A-Za-z0-9_+-]*)[ \t]*\r?\n"
    r"(?P<code>.*?)^[ \t]*```[ \t]*$",
    re.S | re.M)

# <pre class="mermaid"> ... </pre> / <section class="mermaid"> ... </section>
HTML_BLOCK_RE = re.compile(
    r"<(?P<tag>pre|section)\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bmermaid\b[^\"']*[\"'][^>]*>"
    r"(?P<code>.*?)</(?P=tag)>",
    re.S | re.I)

import theme_vars          # 同目录；主题变量表的唯一解析入口

# 微信图文正文的内容区宽度。出图宽度按它来 —— 配合 scale=3 正好是显示尺寸的
# 3 倍（视网膜够用），既不糊也不浪费体积。
#
# 注意：这个值**不改变字看起来多大**。mermaid.ink 会把 SVG 缩放到你请求的
# width，最终观感 = 字号 × 正文宽度 ÷ 图形"原始版式宽度"（见 apparent_pt）。
# 所以指望调大 width 让字变大是白费劲，真正的杠杆是原始宽度（换方向 / 拆图）。
CONTENT_W = 677

# 图内字号。mermaid 默认 14px 偏小，正文里再一缩就更吃力，提到 16px。
FONT_PX = 16

# 正文里实际字号低于这个值就基本读不出了（实测 7.8px 那种就是废图）
MIN_APPARENT_PT = 11.0

# 期望的图内字号。公众号正文惯用 16px 上下，图里的字贴着它最自然 ——
# 比正文大一点便于扫读，又不至于大得突兀。
TARGET_PT = 17.0

# 图最小显示宽度。窄图拉太小时会像块孤立的小贴片，给个下限兜住。
MIN_DISPLAY_W = 240

# 出图底色。**必须是实色**：mermaid.ink 默认返回透明背景的 PNG，而微信点开
# 大图是黑底查看器 —— 深色文字压在黑底上等于没画。实测 bgColor=FFFFFF 能让
# 它返回 RGB 不透明图，体积反而更小。
PNG_BG = "FFFFFF"

USER_AGENT = "wechat-mp-publisher-skill"

DEFAULT_TOKENS = {
    "primary": "#059669",
    "title": "#111827",
    "text": "#374151",
    "card_bg": "#F9FAFB",
    "primary_soft": "#ECFDF5",
    "muted": "#9CA3AF",
    "radius": "8px",
    "para_margin": "20px",
}


def out(msg=""):
    print(msg)


def die(msg, code=1):
    print("[X] " + msg, file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------ 主题取色
def list_themes():
    """从 references/theme-index.md 解析已注册主题：[(中文名, 标识, 主色), ...]"""
    if not os.path.isfile(THEME_INDEX):
        return []
    text = io.open(THEME_INDEX, encoding="utf-8").read()
    rows = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        name, primary, _, lib = cells[0], cells[1], cells[2], cells[3]
        m = re.search(r"#([0-9A-Fa-f]{6})", primary)
        f = re.search(r"theme-([A-Za-z0-9_-]+)\.md", lib)
        if not (m and f and name and name != "主题"):
            continue
        if set(name) <= set("-: "):      # 表头分隔行
            continue
        rows.append((name, f.group(1), "#" + m.group(1)))
    return rows


def theme_tokens(theme_id):
    """读主题组件库的「设计变量速查表」，取出渲染要用的几个颜色。

    解析与匹配统一走 theme_vars（三个脚本共用一份）。原先这里自带一份正则，
    清单里没有「主题墨色」，于是橄榄手记取不到主色、静默退回兜底色 ——
    它的插图长期是摸鱼绿的绿。统一之后这类问题一次修掉。
    缺失的变量会写进 toks["missing"]，由 main 提示出来，不再无声兜底。
    """
    toks = dict(DEFAULT_TOKENS)
    if not theme_id:
        toks["theme_id"] = None
        toks["missing"] = []
        return toks

    t = theme_vars.tokens(theme_id, "diagram")
    if t["pairs"] is None:
        out("[!] 找不到主题库 references/theme-{}.md，用中性默认色渲染".format(theme_id))
        toks["theme_id"] = theme_id
        toks["missing"] = t["missing"]
        return toks

    mapping = {"primary": "primary", "title": "title", "text": "body",
               "card_bg": "light", "primary_soft": "tint", "muted": "aux"}
    for key, field in mapping.items():
        if t[field]:
            toks[key] = t[field]
    toks["theme_id"] = theme_id
    toks["missing"] = t["missing"]
    return toks


# ------------------------------------------------------------------ 渲染
def mermaid_config(toks):
    return {
        "theme": "base",
        "themeVariables": {
            "primaryColor": toks["card_bg"],
            "primaryTextColor": toks["title"],
            "primaryBorderColor": toks["primary"],
            "lineColor": toks["muted"],
            "secondaryColor": toks["primary_soft"],
            "tertiaryColor": toks["card_bg"],
            "fontFamily": "PingFang SC,Microsoft YaHei,sans-serif",
            "fontSize": "{}px".format(toks.get("font_px") or FONT_PX),
        },
        "htmlLabels": False,
        "flowchart": {"htmlLabels": False},
    }


# -------------------------------------------------------------- 可读性体检
_VIEWBOX_RE = re.compile(
    r'viewBox\s*=\s*["\']\s*([\d.eE+-]+)[\s,]+([\d.eE+-]+)[\s,]+'
    r'([\d.eE+-]+)[\s,]+([\d.eE+-]+)')
_DIR_RE = re.compile(r"\b(?:flowchart|graph)\s+(LR|RL|TB|TD|BT)\b", re.I)
_OPPOSITE = {"LR": "TD", "RL": "TD", "TD": "LR", "TB": "LR", "BT": "LR"}


def apparent_pt(natural_w, font_px=FONT_PX, content_w=CONTENT_W):
    """估算这张图在正文里的实际字号（px）。

    mermaid.ink 会把 SVG 缩放到请求的 width，再按 scale 栅格化；浏览器又把
    位图缩到正文宽度。两次缩放相乘后请求的 width 被抵消，只剩：

        正文里实际字号 = 图内字号 × 正文宽度 ÷ 图形原始宽度

    实测：原始宽 1389px 的横排图配 16px 字号 → 正文里 7.8px（手机上一团灰）；
    原始宽 423px 的竖排图 → 25.7px（很清楚）。所以"图看不清"的根因是
    原始宽度，不是位图像素不够。
    """
    return float(font_px) * float(content_w) / max(1.0, float(natural_w))


def display_width(natural_w, font_px=FONT_PX, content_w=CONTENT_W,
                  target_pt=TARGET_PT):
    """按"让图内字号落到正文惯用字号附近"来定这张图的显示宽度。

    有两种坏法，方向相反：

    - 宽图（横排、节点多）：原始宽度远大于正文宽度，满宽显示时字被压扁
      → 交给上面那套自动换方向 / 拆图去治，这里只能给满宽。
    - 窄图（竖排、节点少）：原始宽度本来就小，满宽一拉字就变成 40px 巨字，
      图还长到两三屏 —— 同样难用。这时反过来把显示宽度收窄。

    收窄到多少：让实际字号正好等于 target_pt。解出来
    `显示宽度 = target_pt × 原始宽度 ÷ 图内字号`。上限是正文宽度（不能溢出），
    下限是个够体面的小宽度。收窄后"实际字号 = target_pt"恒定，图也不会虚胖。
    """
    if not natural_w:
        return content_w
    want = float(target_pt) * float(natural_w) / max(1.0, float(font_px))
    return int(max(MIN_DISPLAY_W, min(float(content_w), round(want))))


def parse_viewbox(svg_text):
    """从 SVG 根节点取原始版式尺寸。"""
    m = _VIEWBOX_RE.search(svg_text)
    if not m:
        return None
    w, h = float(m.group(3)), float(m.group(4))
    return (w, h) if w > 0 and h > 0 else None


def flip_direction(src):
    """把 flowchart 方向换成正交的那个（LR↔TD）；换不了就原样返回。"""
    def rep(m):
        return "{} {}".format(m.group(0).split()[0], _OPPOSITE[m.group(1).upper()])
    return _DIR_RE.sub(rep, src)


def svg_payload(src, toks):
    """构造 mermaid.ink /svg/<b64> 的请求体。"""
    state = {"code": src,
             "mermaid": {"theme": "base",
                         "themeVariables": mermaid_config(toks)["themeVariables"],
                         "htmlLabels": False}}
    raw = json.dumps(state, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def probe_natural_size(src, toks, opts):
    """取图形原始版式尺寸 (w, h)，拿不到返回 None。

    remote 走 mermaid.ink 的 /svg 端点（只解析 viewBox，不栅格化，很便宜）；
    mmdc 走一次本地 svg 渲染。这一步是可读性体检与自动换方向的前提 ——
    没有它就只能等图发出去才发现在手机上读不出。
    """
    mmdc = opts.get("mmdc") or shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if mmdc:
        with tempfile.TemporaryDirectory(prefix="wmp-svg-") as td:
            mmd = os.path.join(td, "diagram.mmd")
            svg = os.path.join(td, "diagram.svg")
            conf = os.path.join(td, "mermaid-config.json")
            io.open(mmd, "w", encoding="utf-8").write(src)
            io.open(conf, "w", encoding="utf-8").write(
                json.dumps(mermaid_config(toks), ensure_ascii=False))
            try:
                subprocess.run([mmdc, "-i", mmd, "-o", svg, "-c", conf],
                               capture_output=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired):
                return None
            if not os.path.isfile(svg):
                return None
            return parse_viewbox(io.open(svg, encoding="utf-8", errors="replace").read())

    if not opts.get("remote"):
        return None
    url = "https://mermaid.ink/svg/{}".format(svg_payload(src, toks))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return parse_viewbox(resp.read().decode("utf-8", "replace"))
    except Exception:                                # noqa: BLE001
        return None


def render_one(src, idx, out_dir, toks, opts, width=None):
    """渲染单张图，返回 (png 绝对路径, 通道名)。失败抛 RuntimeError。

    width 是**这张图**的显示宽度（由 display_width 算好传进来）。位图按
    width × scale 出，正好是显示尺寸的 scale 倍 —— 窄图也就不会傻乎乎地
    按满宽出 3600px 的巨图。
    """
    out_path = os.path.join(out_dir, "mermaid-{}.png".format(idx))
    scale = int(opts["scale"])
    width = int(width or opts["width"])
    cfg_json = json.dumps(mermaid_config(toks), ensure_ascii=False)

    mmdc = opts.get("mmdc") or shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if mmdc:
        with tempfile.TemporaryDirectory(prefix="wmp-mmd-") as td:
            mmd = os.path.join(td, "diagram.mmd")
            conf = os.path.join(td, "mermaid-config.json")
            io.open(mmd, "w", encoding="utf-8").write(src)
            io.open(conf, "w", encoding="utf-8").write(cfg_json)
            cmd = [mmdc, "-i", mmd, "-o", out_path, "-b", "white",
                   "-w", str(width), "-s", str(scale), "-c", conf]
            try:
                p = subprocess.run(cmd, capture_output=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise RuntimeError("mmdc 调用失败：{}".format(e))
            if p.returncode != 0 or not os.path.isfile(out_path) \
                    or os.path.getsize(out_path) == 0:
                err = (p.stderr or b"").decode("utf-8", "replace").strip()
                raise RuntimeError("mmdc 渲染失败：{}".format(err[-300:] or "未知错误"))
        return out_path, "mmdc"

    if opts["remote"]:
        state = {"code": src,
                 "mermaid": {"theme": "base",
                             "themeVariables": mermaid_config(toks)["themeVariables"],
                             "htmlLabels": False}}
        raw = json.dumps(state, ensure_ascii=False).encode("utf-8")
        b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        # width 取正文宽度（见 CONTENT_W 注释）：位图正好是显示尺寸的 scale 倍。
        # bgColor 必带 —— 不带的话 ink 返回透明背景 PNG，微信点开大图是黑底，
        # 深色文字直接糊掉。
        url = ("https://mermaid.ink/img/{}?type=png&scale={}&width={}&bgColor={}"
               .format(b64, scale, width, PNG_BG))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = resp.read()
        except Exception as e:                      # noqa: BLE001
            raise RuntimeError("mermaid.ink 请求失败：{}".format(e))
        if not data.startswith(b"\x89PNG") or len(data) < 200:
            raise RuntimeError("mermaid.ink 返回的不是有效 PNG")
        io.open(out_path, "wb").write(data)
        return out_path, "mermaid.ink"

    raise RuntimeError("本地 mmdc 不可用且 remote=false")


# ------------------------------------------------------------------ 主流程
def collect_blocks(text):
    """返回 [(命名组起始位置, 结束位置, 源码, 原始片段)]，按出现顺序。"""
    found = []

    def fence_repl(m):
        if (m.group("lang") or "").lower() != "mermaid":
            return m.group(0)
        found.append((m.start(), m.end(), m.group("code"), m.group(0)))
        return m.group(0)

    FENCE_RE.sub(fence_repl, text)

    def html_repl(m):
        found.append((m.start(), m.end(), m.group("code"), m.group(0)))
        return m.group(0)

    HTML_BLOCK_RE.sub(html_repl, text)

    found.sort(key=lambda x: x[0])
    return found


def load_config_defaults(cfg_path):
    """从 config.json 读 mermaid / theme 段，作为命令行默认值。"""
    d = {"theme": None, "dir": "assets", "scale": 3, "width": CONTENT_W,
         "remote": True, "font_px": FONT_PX}
    if not cfg_path or not os.path.isfile(cfg_path):
        return d
    try:
        cfg = json.load(io.open(cfg_path, encoding="utf-8"))
    except (ValueError, OSError):
        return d
    if cfg.get("theme"):
        d["theme"] = cfg["theme"]
    for k in ("dir", "scale", "width", "remote", "mmdc"):
        if k in (cfg.get("mermaid") or {}):
            d[k] = cfg["mermaid"][k]
    return d


def main():
    ap = argparse.ArgumentParser(
        description="把 Markdown/HTML 里的 ```mermaid 围栏预渲染成 PNG")
    ap.add_argument("file", nargs="?", help="输入文件（.md 为主要场景，也吃 .html）")
    ap.add_argument("-c", "--config", default=None,
                    help="config.json 路径：读取其中的 theme / mermaid 段作为默认值")
    ap.add_argument("--theme", default=None,
                    help="主题标识（摸鱼绿=moyu-green），决定图表配色；--list-themes 可查")
    ap.add_argument("--list-themes", action="store_true", help="列出已注册主题后退出")
    ap.add_argument("--check", action="store_true", help="只列出待渲染的图，不实际渲染")
    ap.add_argument("-o", "--out", default=None, help="工作副本输出路径")
    ap.add_argument("--in-place", action="store_true",
                    help="直接覆盖源文件（自动备份 .bak）")
    ap.add_argument("--out-dir", default=None, help="PNG 输出目录，默认 assets/")
    ap.add_argument("--width", type=int, default=None,
                    help="兜底显示宽度，默认 {}（微信正文内容区宽度）。只在量不到"
                         "图形原始宽度时用得上 —— 正常情况宽度由 display_width "
                         "按图逐张算".format(CONTENT_W))
    ap.add_argument("--scale", type=int, default=None,
                    help="位图倍率（默认 3），配合 --width 决定清晰度")
    ap.add_argument("--font-size", type=int, default=None,
                    help="图内字号 px，默认 {}".format(FONT_PX))
    ap.add_argument("--target-size", type=float, default=None,
                    help="期望在正文里看到的字号 px，默认 {}（窄图按它收窄显示宽度）"
                         .format(TARGET_PT))
    ap.add_argument("--keep-direction", action="store_true",
                    help="不自动换 flowchart 方向（默认发现横排太扁时改竖排）")
    ap.add_argument("--no-size-check", action="store_true",
                    help="跳过可读性体检（省一次请求，也就看不到「字太小」的提示）")
    ap.add_argument("--mmdc", default=None, help="本地 mmdc 可执行文件路径")
    ap.add_argument("--no-remote", action="store_true", help="禁用 mermaid.ink 在线渲染")
    ap.add_argument("--json", action="store_true", help="额外输出 manifest JSON")
    args = ap.parse_args()

    if args.list_themes:
        rows = list_themes()
        if not rows:
            die("读不到主题注册表：{}".format(THEME_INDEX))
        out("已注册主题（{} 套）：".format(len(rows)))
        for name, tid, primary in rows:
            out("  {:<10} {:<22} {}".format(name, tid, primary))
        return 0

    if not args.file:
        ap.error("缺少输入文件（或用 --list-themes）")
    if not os.path.isfile(args.file):
        die("输入文件不存在：{}".format(args.file))

    d = load_config_defaults(args.config)
    theme = args.theme or d["theme"]
    out_dir_rel = args.out_dir or d["dir"] or "assets"
    opts = {
        "scale": args.scale if args.scale is not None else d["scale"],
        "width": args.width if args.width is not None else d["width"],
        "remote": False if args.no_remote else bool(d["remote"]),
        "mmdc": args.mmdc or d.get("mmdc"),
        "size_check": not args.no_size_check,
        "keep_direction": args.keep_direction,
        "font_px": args.font_size or d.get("font_px") or FONT_PX,
        "target_pt": args.target_size or TARGET_PT,
    }

    text = io.open(args.file, encoding="utf-8").read()
    blocks = collect_blocks(text)

    if not blocks:
        out("[i] 没找到 ```mermaid 围栏，无需渲染")
        return 0

    out("发现 {} 张 mermaid 图（主题 {}）".format(len(blocks), theme or "默认中性色"))
    if args.check:
        for i, (_, _, src, _) in enumerate(blocks, 1):
            first = (src.strip().splitlines() or [""])[0][:60]
            out("  [{}] {}".format(i, first))
        return 0

    base = os.path.dirname(os.path.abspath(args.file))
    out_dir = out_dir_rel if os.path.isabs(out_dir_rel) \
        else os.path.join(base, out_dir_rel)
    os.makedirs(out_dir, exist_ok=True)
    toks = theme_tokens(theme)
    toks["font_px"] = opts["font_px"]
    if toks.get("missing"):
        out("[!] 主题 {} 的变量表里没读到：{} —— 这几项会用中性默认色，"
            "建议补齐主题库（见 references/theme-generator.md）"
            .format(theme, "、".join(toks["missing"])))

    manifest, ok, fail, notes = [], 0, 0, []
    result = text
    for i, (start, end, src, original) in enumerate(blocks, 1):
        src = src.strip()
        if not src:
            continue

        # ---- 可读性体检（顺带决定要不要换方向）
        natural = probe_natural_size(src, toks, opts) if opts["size_check"] else None
        if natural:
            pt = apparent_pt(natural[0], opts["font_px"])
            flipped = flip_direction(src)
            if pt < MIN_APPARENT_PT and not opts["keep_direction"] and flipped != src:
                alt = probe_natural_size(flipped, toks, opts)
                if alt:
                    alt_pt = apparent_pt(alt[0], opts["font_px"])
                    # 明显更好才换（1.25 倍以上），免得为一点点差别来回折腾
                    if alt_pt > pt * 1.25:
                        out("  [i] 第 {} 张在正文里太扁（仅 {:.1f}px），"
                            "自动换个方向 → {:.1f}px".format(i, pt, alt_pt))
                        src, natural, pt = flipped, alt, alt_pt
            # 定显示宽度，再看"实际"字号 —— 窄图被收窄后字号就是 TARGET_PT，
            # 不能再拿满宽的老数字吓人
            disp_w = display_width(natural[0], opts["font_px"],
                                   target_pt=opts["target_pt"])
            real_pt = apparent_pt(natural[0], opts["font_px"], disp_w)
            if real_pt < MIN_APPARENT_PT:
                notes.append(
                    "第 {} 张：正文里字号仅 {:.1f}px（图形原始宽度 {:.0f}px，"
                    "正文内容区 {}px）。手机上基本读不清 —— 缩短节点文字、"
                    "拆成两张，或换方向重渲。".format(i, real_pt, natural[0], CONTENT_W))
        else:
            disp_w = opts["width"]

        try:
            png, channel = render_one(src, i, out_dir, toks, opts, disp_w)
        except RuntimeError as e:
            fail += 1
            out("  [!] 第 {} 张渲染失败：{}".format(i, e))
            continue

        ok += 1
        rel = "{}/{}".format(out_dir_rel.replace("\\", "/"), os.path.basename(png)) \
            if not os.path.isabs(out_dir_rel) else png
        kb = os.path.getsize(png) / 1024.0
        size_note = ""
        if natural:
            size_note = "，原始 {:.0f}x{:.0f}，显示宽 {}px，正文里字号约 {:.1f}px".format(
                natural[0], natural[1], disp_w, real_pt)
        else:
            real_pt = None
        out("  [OK] 第 {} 张 → {}（{} 通道，{:.1f} KB{}）".format(
            i, rel, channel, kb, size_note))
        manifest.append({"index": i, "path": rel, "abs": png,
                         "channel": channel, "bytes": os.path.getsize(png),
                         "natural": list(natural) if natural else None,
                         "display_w": disp_w,
                         "apparent_pt": round(real_pt, 1) if real_pt else None})

        if args.file.lower().endswith((".html", ".htm")):
            repl = ('<img src="{}" style="width:{}px;max-width:100%;height:auto;'
                    'display:block;margin:0 auto;">'.format(rel, disp_w))
        else:
            repl = "![mermaid 图 {}]({})".format(i, rel)
        result = result[:start] + repl + result[end:]

    if notes:
        out("")
        out("[!] 有 {} 张图在正文里会偏小，建议处理后再排版：".format(len(notes)))
        for n in notes:
            out("    · " + n)
        out("    （--keep-direction 可关掉自动换方向，--no-size-check 跳过体检）")

    if args.json:
        out(json.dumps({"theme": theme, "images": manifest,
                        "ok": ok, "fail": fail}, ensure_ascii=False, indent=2))

    if fail and not ok:
        die("全部渲染失败：产物没变。可 npm i -g @mermaid-js/mermaid-cli 后重试")
    if fail:
        out("[!] {} 张失败，对应围栏原样保留（排版前请修掉，否则会当正文发出去）"
            .format(fail))

    if args.in_place:
        if not os.path.exists(args.file + ".bak"):
            io.open(args.file + ".bak", "w", encoding="utf-8").write(text)
            out("[i] 已备份原文件 → {}.bak".format(args.file))
        target = args.file
    else:
        stem, ext = os.path.splitext(args.file)
        target = args.out or "{}.mermaid{}".format(stem, ext)
    io.open(target, "w", encoding="utf-8").write(result)
    out("[OK] 工作副本已写出：{}".format(target))
    out("     → 排版时按主题库的图片组件引用这些 PNG，别再保留 ```mermaid 源码")
    return 0 if not fail else 2


if __name__ == "__main__":
    sys.exit(main())
