#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把同一篇文章排成**全部内置主题各一版**，用于在草稿箱里横向对比主题效果。

为什么需要它：主题库有 6 套，靠读 theme-index 的表格想象不出"我这篇文章用
红白系长什么样"。这个脚本拿一篇已排好的稿子（含 mermaid 流程图、表格、引用卡、
着色代码块）当基准，把**主题真正不同的三样东西**换掉，其余原样保留：

  1. 配色 —— 主题变量表的色板（主色/下划线/浅底/文字层级）
  2. 结构质感 —— 圆角倍率、卡片描边、阴影气质（票据=硬阴影黑描边，
     禅意/石墨/橄榄=细线无影，红白=淡红描边）
  3. 字体与代码块 —— 字体栈、标题衬线与否、深色/浅色代码块

换的是"主题身份"，不换版式骨架 —— 所以每一版都必然过窄屏体检
（骨架已经按 288px 加固过），不会出现"某个主题的样张在手机上炸了"。

用法：
    python scripts/build_theme_showcase.py --src ../wechat-publish --out ../wechat-publish/showcase
    python scripts/build_theme_showcase.py --src ... --out ... --themes moyu-green,red-white
    python scripts/build_theme_showcase.py --src ... --out ... --push        # 逐版推草稿箱
    python scripts/build_theme_showcase.py --src ... --out ... --no-cover    # 跳过封面（省时间）

--src 目录需要含：article.html（基准稿）、article.md（取代码围栏）、config.json（取凭证与文章元信息）。
"""

import argparse
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)

import highlight_code as hc          # noqa: E402  复用着色器，不重写一套

PY = sys.executable

# --------------------------------------------------------------- 主题档案
# palette：基准稿（摸鱼绿）用到的颜色 → 本主题的颜色。只映射"主题身份色"，
#          代码块内部的 token 色不在此列（代码块整块重生成）。
# radius ：圆角倍率。同一份骨架缩放到各主题的圆角语言（禅意 2px、票据 12px 硬边）。
# shadow ：卡片阴影。None = 保留基准稿的柔和阴影。
# border ：卡片描边（替换基准稿的淡绿描边与 1px 灰描边）。
THEMES = {
    "moyu-green": dict(
        name="摸鱼绿", code_style="dark", radius=1.0, shadow=None, border=None,
        font=None, serif=False,
        primary="#059669", aux="#9CA3AF", line="#E5E7EB", title="#111827",
        label_bg="#F9FAFB", label_border="1px solid #E5E7EB",
        swatches=("#059669", "#10B981", "#A7F3D0", "#ECFDF5"),
        palette={},
    ),
    "red-white": dict(
        name="红白色系", code_style="dark", radius=0.25,
        shadow="0 2px 8px rgba(220,38,38,0.06)",
        border="1px solid #FECACA", font=None, serif=False,
        primary="#DC2626", aux="#9CA3AF", line="#E5E7EB", title="#1C1917",
        label_bg="#FEF2F2", label_border="1px solid #FECACA",
        swatches=("#DC2626", "#991B1B", "#FCA5A5", "#FEF2F2"),
        palette={
            "#059669": "#DC2626",   # 主色 → 正红
            "#10b981": "#EF4444",
            "#34d399": "#FCA5A5",
            "#a7f3d0": "#FECACA",   # 下划线/淡标记 → 淡粉
            "#bbf7d0": "#FECACA",
            "#ecfdf5": "#FEF2F2",   # 浅底 → 极淡红
            "#f0fdf4": "#FEF2F2",
            "#fde68a": "#FEE2E2",   # 黄色高亮 → 粉白
            "#111827": "#1C1917",
        }),
    "graphite-minimal": dict(
        name="石墨极简风", code_style="light", radius=0.3, shadow="none",
        border="1px solid #E4E4E7", font=None, serif=False,
        primary="#52525B", aux="#A1A1AA", line="#E4E4E7", title="#27272A",
        label_bg="#FAFAFA", label_border="1px solid #E4E4E7",
        swatches=("#52525B", "#3F3F46", "#A1A1AA", "#F4F4F5"),
        palette={
            "#059669": "#52525B",   # 主色 → 石墨灰（全篇去绿）
            "#10b981": "#3F3F46",
            "#34d399": "#71717A",
            "#a7f3d0": "#52525B",   # 下划线 → 石墨灰
            "#bbf7d0": "#E4E4E7",
            "#ecfdf5": "#FAFAFA",
            "#f0fdf4": "#F4F4F5",
            "#fde68a": "#F4F4F5",
            "#111827": "#27272A",
            "#4b5563": "#71717A",
            "#6b7280": "#71717A",
            "#9ca3af": "#A1A1AA",
            "#d1d5db": "#E4E4E7",
            "#e5e7eb": "#E4E4E7",
            "#f3f4f6": "#F4F4F5",
            "#f9fafb": "#FAFAFA",
        }),
    "zen-whitespace": dict(
        name="留白禅意风", code_style="light", radius=0.15, shadow="none",
        border="1px solid #E8E8E8", font=None, serif=True,
        primary="#4A5D52", aux="#A3A3A3", line="#E8E8E8", title="#2B2B2B",
        label_bg="#EEF3F0", label_border="1px solid #E8E8E8",
        swatches=("#4A5D52", "#3D5046", "#B5C8BC", "#EEF3F0"),
        palette={
            "#059669": "#4A5D52",   # 主色 → 墨绿（低饱和）
            "#10b981": "#3D5046",
            "#34d399": "#B5C8BC",
            "#a7f3d0": "#B5C8BC",   # 下划线 → 低饱和墨绿
            "#bbf7d0": "#E8E8E8",
            "#ecfdf5": "#EEF3F0",
            "#f0fdf4": "#EEF3F0",
            "#fde68a": "#D6E4DC",   # 荧光笔色
            "#111827": "#2B2B2B",
            "#374151": "#525252",
            "#4b5563": "#525252",
            "#6b7280": "#A3A3A3",
            "#9ca3af": "#A3A3A3",
            "#d1d5db": "#E8E8E8",
            "#e5e7eb": "#E8E8E8",
            "#f3f4f6": "#EEF3F0",
            "#f9fafb": "#FFFFFF",
        }),
    "moyu-ticket": dict(
        name="摸鱼票据风", code_style="light", radius=1.0,
        shadow="4px 4px 0 #1a1a1a", border="2px solid #1a1a1a",
        font=None, serif=False,
        primary="#059669", aux="#999999", line="#E5E7EB", title="#1a1a1a",
        label_bg="#fffef8", label_border="2px solid #1a1a1a",
        swatches=("#059669", "#A7F3D0", "#1a1a1a", "#fffef8"),
        palette={
            "#111827": "#1a1a1a",
            "#374151": "#555555",
            "#4b5563": "#888888",
            "#6b7280": "#888888",
            "#9ca3af": "#999999",
            "#ecfdf5": "#F0FDF4",
            "#f9fafb": "#fffef8",   # 米黄纸感底
            "#f3f4f6": "#F3F4F6",
        }),
    "olive-journal": dict(
        name="橄榄手记", code_style="dark", radius=0.4, shadow="none",
        border="1px solid #bfc1b7",
        font=("'IBM Plex Sans',-apple-system,system-ui,'PingFang SC',"
              "'Hiragino Sans GB','Microsoft YaHei',sans-serif"),
        serif=False,
        primary="#1e1f23", accent="#ed7b2f",
        aux="#9ea096", line="#bfc1b7", title="#23251d",
        label_bg="#fdfdf8", label_border="1px solid #bfc1b7",
        swatches=("#1e1f23", "#ed7b2f", "#bfc1b7", "#eeefe9"),
        palette={
            # 主色是墨黑，点睛色才是橙 —— 下划线/强调一律走橙
            "#059669": "#ed7b2f",
            "#10b981": "#d4c9b8",
            "#34d399": "#d4c9b8",
            "#a7f3d0": "#bfc1b7",   # 下划线 → 橄榄灰线（重点词用橙，见下）
            "#bbf7d0": "#bfc1b7",
            "#ecfdf5": "#eeefe9",
            "#f0fdf4": "#eeefe9",
            "#fde68a": "#e5e7e0",
            "#111827": "#23251d",
            "#374151": "#4d4f46",
            "#4b5563": "#65675e",
            "#6b7280": "#65675e",
            "#9ca3af": "#9ea096",
            "#d1d5db": "#bfc1b7",
            "#e5e7eb": "#bfc1b7",
            "#f3f4f6": "#eeefe9",
            "#f9fafb": "#fdfdf8",
        }),
}

TID_RE = re.compile(r"theme-([A-Za-z0-9_-]+)\.md$")

PAGE_NODE = re.compile(r'\s*data-page-node-id="[^"]*"')
COMMENT = re.compile(r"[ \t]*<!--.*?-->")
HEX = re.compile(r"#[0-9A-Fa-f]{6}")
RADIUS = re.compile(r"border-radius:(\d+(?:\.\d+)?)px")
SHADOW = re.compile(r"box-shadow:[^;\"]+")
FENCE_PY = re.compile(r"```python\s*\n(.*?)```", re.S)


def out(msg):
    print(msg, flush=True)


def die(msg):
    print("[x] " + msg, file=sys.stderr)
    sys.exit(1)


def section_span(html, start):
    """start 指向某个 '<section'，返回它配对的 </section> 之后的位置。"""
    depth = 0
    for m in re.finditer(r"<section\b|</section\s*>", html[start:]):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return start + m.end()
        else:
            depth += 1
    raise ValueError("section 标签不配对")


def build_code_block(theme_id, style, code):
    pal = hc.palette(theme_id, style, "rich")
    return hc.build_block(code, "python", pal, style=style, wrap=False, hint=True)


def label_card(t, theme_id):
    """主题标识卡：一眼看清这一版是哪个主题、色板长什么样。"""
    sw = "".join(
        '      <section style="flex:1;min-width:0;">\n'
        '        <section style="height:20px;border-radius:3px;background:{c};'
        'border:1px solid rgba(0,0,0,0.06);">'
        '<span leaf=""><br></span></section>\n'
        '        <p style="margin:4px 0 0;font-size:8px;color:{aux};'
        'white-space:nowrap;letter-spacing:0;">'
        '<span leaf="">{c}</span></p>\n'
        '      </section>\n'.format(c=c, aux=t["aux"])
        for c in t["swatches"])
    return (
        '<!-- 主题标识卡（样张专用，正式稿删掉） -->\n'
        '  <section style="margin:0 20px 28px;background:{bg};'
        'border:{lb};border-radius:10px;padding:14px 16px;">\n'
        '    <p style="margin:0 0 6px;font-size:10px;font-weight:700;color:{aux};'
        'letter-spacing:1.5px;white-space:nowrap;">'
        '<span leaf="">THEME SAMPLE · 主题样张</span></p>\n'
        '    <p style="margin:0 0 12px;font-size:16px;font-weight:800;color:{title};'
        'line-height:1.35;">'
        '<span leaf="">{name}</span>'
        '<span style="color:{primary};font-size:11px;font-weight:600;">'
        '<span leaf="">　{ident}</span></span></p>\n'
        '    <section style="display:flex;gap:6px;align-items:flex-start;">\n'
        '{sw}'
        '    </section>\n'
        '  </section>\n\n  '.format(
            bg=t["label_bg"], lb=t["label_border"], aux=t["aux"], title=t["title"],
            name=t["name"], primary=t["primary"], ident=theme_id, sw=sw))


def build_html(base_html, t, theme_id, code_html):
    html = base_html

    # ---- 1. 代码块整块换成该主题配色的新块（基准稿只有一处围栏代码）
    marker = "<!-- 通用库 1a 深色代码块 -->"
    i = html.find(marker)
    if i >= 0:
        s = html.find("<section", i)
        e = section_span(html, s)
        html = html[:i] + "<!-- 代码块 -->\n    " + code_html + "\n" + html[e:]
    else:
        out("  [!] 没找到基准稿的代码块注释标记，代码块未替换")

    # ---- 2. 去掉编辑器记账属性与注释（公众号本来也会剥）
    html = PAGE_NODE.sub("", html)
    html = COMMENT.sub("", html)

    # ---- 3. 结构质感：圆角 / 阴影 / 卡片描边
    if t["radius"] != 1.0:
        html = RADIUS.sub(
            lambda m: "border-radius:{}px".format(
                max(1, round(float(m.group(1)) * t["radius"]))), html)
    if t["shadow"] is not None:
        html = SHADOW.sub("box-shadow:" + t["shadow"], html)
    if t["border"] is not None:
        html = html.replace("border:1.5px solid rgba(5,150,105,0.15)", t["border"])
        html = html.replace("border:1px solid #E5E7EB;border-radius:12px",
                            t["border"] + ";border-radius:12px")
    if t.get("font"):
        html = html.replace(
            "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
            "'Microsoft YaHei',sans-serif", t["font"])
    if t.get("serif"):
        # 标题（font-weight:900 的大字）换衬线，正文保持黑体 —— 禅意风的排版语言
        html = html.replace(
            "font-weight:900;",
            "font-family:'Noto Serif SC',Georgia,'Times New Roman',serif;"
            "font-weight:900;")

    # ---- 4. 配色：主题色板 + 主色带透明度的描边/发光
    hexmap = {k.lower(): v for k, v in t["palette"].items()}
    if hexmap:
        html = HEX.sub(lambda m: hexmap.get(m.group(0).lower(), m.group(0)), html)
    prim = t["primary"].lstrip("#")
    rgb = ",".join(str(int(prim[j:j + 2], 16)) for j in (0, 2, 4))
    html = re.sub(r"rgba\(\s*5\s*,\s*150\s*,\s*105\s*,", "rgba({},".format(rgb), html)

    # ---- 5. 插主题标识卡（目录之前）
    anchor = '<section style="margin:0 20px 32px;'
    if anchor in html:
        html = html.replace(anchor, label_card(t, theme_id) + anchor, 1)
    else:
        out("  [!] 没找到目录锚点，主题标识卡未插入")

    return html


def write_index(out_root, built, title):
    """横向对比页：六版并排，一眼看完配色与卡片质感。"""
    cells = []
    for theme_id, name, tdir in built:
        t = THEMES[theme_id]
        sw = "".join(
            '<span style="display:inline-block;width:14px;height:14px;border-radius:3px;'
            'background:{};border:1px solid rgba(0,0,0,0.08);margin-right:4px;'
            'vertical-align:middle;"></span>'.format(c) for c in t["swatches"])
        cells.append(
            '<section style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;'
            'padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">\n'
            '  <p style="margin:0 0 6px;font-size:15px;font-weight:700;color:#111827;">{name}'
            '<span style="font-size:11px;color:#9CA3AF;font-weight:400;">　{ident}</span></p>\n'
            '  <p style="margin:0 0 10px;">{sw}</p>\n'
            '  <iframe src="{ident}/article.html" style="width:390px;height:1200px;'
            'border:1px solid #E5E7EB;border-radius:6px;background:#fff;" '
            'loading="lazy"></iframe>\n'
            '  <p style="margin:8px 0 0;font-size:11px;"><a href="{ident}/article.html" '
            'style="color:#2563EB;">打开整篇 →</a></p>\n'
            '</section>'.format(name=name, ident=theme_id, sw=sw))
    html = (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
        '<title>{title}</title>\n'
        '<style>body{{margin:0;padding:28px 24px 60px;background:#F4F5F7;'
        "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',"
        'sans-serif;color:#111827;}}\n'
        'h1{{font-size:20px;margin:0 0 6px;}}\n'
        'p.lead{{margin:0 0 22px;font-size:13px;color:#6B7280;line-height:1.7;}}\n'
        '.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));'
        'gap:18px;}}\n'
        'iframe{{display:block;}}\n</style></head>\n<body>\n'
        '<h1>{title}</h1>\n'
        '<p class="lead">同一篇文章（含 mermaid 流程图、着色代码块、对比表格、引用卡）× '
        '六套预设主题。每格的窄屏预览按 390px 手机宽度渲染，滚动可看全文；'
        '配色、圆角、描边、阴影与代码块明暗都按各主题的设计变量表生成。</p>\n'
        '<section class="grid">\n{cells}\n</section>\n</body></html>\n'
    ).format(title=title, cells="\n".join(cells))
    path = os.path.join(out_root, "index.html")
    io.open(path, "w", encoding="utf-8").write(html)
    return path


def patch_config(cfg, t, theme_id, src_dir, tdir, title_prefix):
    cfg = json.loads(json.dumps(cfg))
    art = cfg.setdefault("article", {})
    art["title"] = "{}Agent Loop 运行原理 · {}".format(title_prefix, t["name"])
    art["digest"] = ("同一篇文章用「{}」主题（{}）排版：七环节流程图、着色代码块、"
                     "对比表格与卡片组件，用来横向对比六套预设的呈现效果。"
                     ).format(t["name"], theme_id)
    art["content_file"] = "article.html"
    art["cover_file"] = os.path.join("assets", "cover.png")
    cfg["theme"] = theme_id
    # 封面文案收口进 config 的 cover 段：make_assets 直接读这里，
    # 调用方不必再拼一长串 --brand/--title/--subtitle/--date/--motif…
    # （同一份文案写在两处就一定会漂；这里只有"每版不同的副标题"是变量）
    cfg["cover"] = {
        "brand": "公众号 · 工程笔记",
        "title": "Agent Loop 七环节",
        "subtitle": "主题样张 · " + t["name"],
        "date": "2026.09",
        "motif": "ring", "motif_nodes": 7,
        "motif_label": "LOOP", "motif_caption": "7 STEPS",
    }
    return cfg


def run(cmd, cwd=None, quiet=False):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not quiet:
        for line in (r.stdout or "").rstrip().splitlines():
            out("    " + line)
        for line in (r.stderr or "").rstrip().splitlines():
            out("    " + line)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="基准稿目录（含 article.html/md/config.json）")
    ap.add_argument("--out", required=True, help="样张输出根目录")
    ap.add_argument("--themes", default=None, help="逗号分隔主题标识，默认全部")
    ap.add_argument("--title-prefix", default="【主题样张】", help="草稿标题前缀")
    ap.add_argument("--no-cover", action="store_true", help="跳过封面生成")
    ap.add_argument("--push", action="store_true", help="逐版推送草稿箱")
    ap.add_argument("--sleep", type=float, default=3.0, help="推送间隔秒数")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    out_root = os.path.abspath(args.out)
    base_html = io.open(os.path.join(src, "article.html"), encoding="utf-8").read()
    md = io.open(os.path.join(src, "article.md"), encoding="utf-8").read()
    cfg0 = json.load(io.open(os.path.join(src, "config.json"), encoding="utf-8"))

    m = FENCE_PY.search(md)
    if not m:
        die("基准稿 article.md 里没有 ```python 围栏，无法重生成代码块")
    code = m.group(1)

    ids = [x.strip() for x in args.themes.split(",")] if args.themes else list(THEMES)
    bad = [x for x in ids if x not in THEMES]
    if bad:
        die("未登记的主题档案：{}（可选：{}）".format(", ".join(bad), ", ".join(THEMES)))

    os.makedirs(out_root, exist_ok=True)
    built = []

    for theme_id in ids:
        t = THEMES[theme_id]
        tdir = os.path.join(out_root, theme_id)
        adir = os.path.join(tdir, "assets")
        os.makedirs(adir, exist_ok=True)
        out("\n=== {} ({}) ===".format(t["name"], theme_id))

        # 1) mermaid：按主题配色重渲（每套主题的流程图颜色都跟着主题走）
        rc, log = run([PY, os.path.join(SCRIPTS, "render_mermaid.py"),
                       os.path.join(src, "article.md"), "--theme", theme_id,
                       "-o", os.path.join(tdir, "article.mermaid.md"),
                       "--out-dir", adir])
        if rc != 0:
            out("  [!] mermaid 渲染失败（沿用基准稿的图）")

        # 2) 正文
        html = build_html(base_html, t, theme_id, build_code_block(theme_id, t["code_style"], code))
        io.open(os.path.join(tdir, "article.html"), "w", encoding="utf-8").write(html)

        # 3) 配置
        cfg = patch_config(cfg0, t, theme_id, src, tdir, args.title_prefix)
        io.open(os.path.join(tdir, "config.json"), "w", encoding="utf-8").write(
            json.dumps(cfg, ensure_ascii=False, indent=2))

        # 4) 封面（配色与皮肤跟着主题走；文案取自 config 的 cover 段）
        if not args.no_cover:
            rc, log = run([PY, os.path.join(SCRIPTS, "make_assets.py"),
                           "-c", os.path.join(tdir, "config.json"), "-o", adir,
                           "--only", "cover"])
            if rc != 0:
                out("  [!] 封面生成失败（可用 --no-cover 跳过）")

        # 5) 产物关：ERROR 必须清零
        rc, log = run([PY, os.path.join(SCRIPTS, "validate_gzh_html.py"),
                       os.path.join(tdir, "article.html")])
        tail = [l for l in log.splitlines() if l.strip()][-1:] or [""]
        out("  校验：{}".format(tail[0].strip()))
        built.append((theme_id, t["name"], tdir))

    out("\n[OK] 生成 {} 版：{}".format(
        len(built), ", ".join(os.path.relpath(d, out_root) for _, _, d in built)))
    idx = write_index(out_root, built, "公众号主题样张对比 · {} 版".format(len(built)))
    out("    对比页：{}".format(idx))

    if not args.push:
        out("    加 --push 可逐版推送到草稿箱")
        return

    # 各主题目录各自持有一份 .token_cache.json（publish.py 是按 config.json 所在目录找缓存的）。
    # 而公众号的 access_token 是**单点有效**的：逐版各自去换 token，后换的会让先换的失效，
    # 于是"推第一版成功、推第二版 40001"。所以先为基准目录取一次，再把这份缓存分发给每一版，
    # 全程不再重复换 token。
    src_cache = os.path.join(src, ".token_cache.json")
    rc, _ = run([PY, os.path.join(SCRIPTS, "publish.py"), "token", "-f",
                 "-c", os.path.join(src, "config.json")])
    if rc == 0 and os.path.exists(src_cache):
        shared = io.open(src_cache, encoding="utf-8").read()
        out("\n[i] 已取一份 access_token，{} 版共用（避免逐版换 token 互相失效）".format(len(built)))
    else:
        shared = None
        out("\n[!] 预先取 token 失败，逐版将各自取 token（可能遇到 40001）")

    for i, (theme_id, name, tdir) in enumerate(built, 1):
        out("\n--- 推送 {}/{}  {} ---".format(i, len(built), name))
        if shared:
            io.open(os.path.join(tdir, ".token_cache.json"), "w", encoding="utf-8").write(shared)
        rc, log = run([PY, os.path.join(SCRIPTS, "publish.py"), "draft",
                       "-c", os.path.join(tdir, "config.json")])
        for line in log.splitlines():
            if "media_id" in line or "错误" in line or "errcode" in line:
                out("    " + line.strip())
        if i < len(built):
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
