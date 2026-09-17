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
    """读主题组件库的「设计变量速查表」，取出渲染要用的几个颜色。"""
    toks = dict(DEFAULT_TOKENS)
    if not theme_id:
        return toks
    path = os.path.join(REFS, "theme-{}.md".format(theme_id))
    if not os.path.isfile(path):
        out("[!] 找不到主题库 {}，用中性默认色渲染".format(path))
        return toks

    text = io.open(path, encoding="utf-8").read()
    m = re.search(r"##\s*设计变量速查表\s*```(.*?)```", text, re.S)
    block = m.group(1) if m else text

    def pick(*labels):
        """按标签顺序找第一个命中的色值。"""
        for label in labels:
            rx = re.compile(re.escape(label) + r"[^\n#]*?(#[0-9A-Fa-f]{6})")
            hit = rx.search(block)
            if hit:
                return hit.group(1)
        return None

    pairs = {
        "primary": pick("主色调", "主色", "主颜色"),
        "title": pick("标题色", "大标题"),
        "text": pick("正文色"),
        "card_bg": pick("极浅灰", "浅灰背景"),
        "primary_soft": pick("浅绿背景", "浅底", "浅色背景"),
        "muted": pick("辅助文字", "注释/标签", "次要文字"),
    }
    for k, v in pairs.items():
        if v:
            toks[k] = v
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
            "fontSize": "14px",
        },
        "htmlLabels": False,
        "flowchart": {"htmlLabels": False},
    }


def render_one(src, idx, out_dir, toks, opts):
    """渲染单张图，返回 (png 绝对路径, 通道名)。失败抛 RuntimeError。"""
    out_path = os.path.join(out_dir, "mermaid-{}.png".format(idx))
    scale = int(opts["scale"])
    width = int(opts["width"])
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
        # mermaid.ink 默认出图偏小，手机上按 100% 宽显示会糊，显式放大渲染
        url = "https://mermaid.ink/img/{}?type=png&scale={}&width={}".format(
            b64, scale, width)
        req = urllib.request.Request(url, headers={
            "User-Agent": "wechat-mp-publisher-skill/0.5"})
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
    d = {"theme": None, "dir": "assets", "scale": 3, "width": 1200, "remote": True}
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
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--scale", type=int, default=None)
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

    manifest, ok, fail = [], 0, 0
    result = text
    for i, (start, end, src, original) in enumerate(blocks, 1):
        src = src.strip()
        if not src:
            continue
        try:
            png, channel = render_one(src, i, out_dir, toks, opts)
        except RuntimeError as e:
            fail += 1
            out("  [!] 第 {} 张渲染失败：{}".format(i, e))
            continue

        ok += 1
        rel = "{}/{}".format(out_dir_rel.replace("\\", "/"), os.path.basename(png)) \
            if not os.path.isabs(out_dir_rel) else png
        kb = os.path.getsize(png) / 1024.0
        out("  [OK] 第 {} 张 → {}（{} 通道，{:.1f} KB）".format(i, rel, channel, kb))
        manifest.append({"index": i, "path": rel, "abs": png,
                         "channel": channel, "bytes": os.path.getsize(png)})

        if args.file.lower().endswith((".html", ".htm")):
            repl = ('<img src="{}" style="max-width:100%;height:auto;'
                    'display:block;margin:0 auto;">'.format(rel))
        else:
            repl = "![mermaid 图 {}]({})".format(i, rel)
        result = result[:start] + repl + result[end:]

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
