#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出「同一篇文章 × 全部主题」的封面墙，用来验收封面观感。

**为什么要有它**
------------
封面色值表看不出"扎不扎眼"，更看不出"两套主题的封面是不是长得一样"——
而后者恰恰是真出过的问题：摸鱼绿与摸鱼票据风的主色同为 `#059669`，
改之前两张封面几乎无法分辨。一张墙排开所有主题，差异（或雷同）一眼可见。

这也是**新增主题的验收口**：主题登记进 `references/theme-index.md` 后重跑，
它会自动出现在墙里；没出现就说明登记漏了。

依赖：pip install pillow（与 make_assets 同）
用法：
    python cover_wall.py --title "Agent Loop 七环节" --subtitle "一次循环的七个环节" \\
        --date 2026.09 --motif ring --motif-nodes 7 --motif-caption "7 STEPS" -o wall
    python cover_wall.py --themes moyu-green,moyu-ticket -o wall      # 只比其中两套
    python cover_wall.py -c work/config.json -o wall                  # 文案取自 config.cover
产出：
    <out>/cover-wall.png       所有主题的封面墙（每格标注主题名 / 主色 / 点睛色 / 皮肤）
    <out>/<theme>/cover.png    各主题的封面原图（1800x766）
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[X] 需要 pillow：pip install pillow", file=sys.stderr)
    sys.exit(1)

import make_assets        # noqa: E402  封面绘制（几何取自 cover_spec）
import cover_spec         # noqa: E402  皮肤与主题名
import theme_vars         # noqa: E402  主题配色解析

INDEX = os.path.join(ROOT, "references", "theme-index.md")

# 与 validate_skill.check_themes 同一口径：从索引表里认主题，别另立一份名单
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|[^|]*?`?(#[0-9A-Fa-f]{6})`?[^|]*\|"
                    r"[^|]*\|\s*`references/theme-([A-Za-z0-9_-]+)\.md`", re.M)


def registered_themes():
    """读 theme-index.md，返回 [(主题 id, 中文名, 主色)]，保持表内顺序。"""
    if not os.path.isfile(INDEX):
        return []
    text = io.open(INDEX, encoding="utf-8").read()
    out = []
    for m in ROW_RE.finditer(text):
        name, color, tid = m.group(1).strip(), m.group(2), m.group(3)
        if tid != "generator":
            out.append((tid, name, color))
    return out


def font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def skin_summary(theme, skin):
    """一格墙下方那行小字：让"为什么这两张看起来不同"变成可读的事实。"""
    bits = ["竖条 {}px".format(skin["rail_w"])]
    bits.append("点睛 {}".format(
        "#%02X%02X%02X" % tuple(theme["accent"]) if theme["accent_own"] else "用主色"))
    bits.append("圆角 {}".format(skin["radius"]) if skin["radius"] else "直角")
    if skin["frame_w"]:
        bits.append("{}px 硬边".format(skin["frame_w"]))
    if skin["paper"] != "none":
        bits.append("底纹 {}".format(skin["paper"]))
    if skin["serif"]:
        bits.append("衬线标题")
    return " · ".join(bits)


def build_wall(rows, cov, out_dir, cols=2, scale=620):
    """把各主题封面拼成一张墙，每格上方写主题名、下方写色值与皮肤摘要。"""
    cell_h = 0
    tiles = []
    for tid, name, cover_path, theme, skin in rows:
        im = Image.open(cover_path).convert("RGB")
        im = im.resize((scale, int(im.height * scale / im.width)))
        tiles.append((tid, name, im, theme, skin))
        cell_h = max(cell_h, im.height)

    pad, head, foot, gap = 14, 34, 30, 16
    cw = scale + pad * 2
    ch = head + cell_h + foot + pad
    W = cw * cols + gap * (cols - 1)
    H = ch * ((len(tiles) + cols - 1) // cols) + gap * (((len(tiles) + cols - 1) // cols) - 1)
    canvas = Image.new("RGB", (W, H), "#EDEFF2")
    d = ImageDraw.Draw(canvas)
    f_name, f_meta = font(22), font(15)

    for i, (tid, name, im, theme, skin) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = c * (cw + gap), r * (ch + gap)
        d.rectangle([x, y, x + cw, y + ch], fill="white")
        d.text((x + pad, y + 8), "{} ({})".format(name, tid), fill="#111827", font=f_name)
        canvas.paste(im, (x + pad, y + head))
        primary = "#%02X%02X%02X" % tuple(theme["primary"])
        accent = "#%02X%02X%02X" % tuple(theme["accent"])
        d.text((x + pad, y + head + cell_h + 6),
               "主色 {}  点睛 {}  |  {}".format(primary, accent, skin_summary(theme, skin)),
               fill="#4B5563", font=f_meta)

    path = os.path.join(out_dir, "cover-wall.png")
    canvas.save(path)
    return path


def main():
    p = argparse.ArgumentParser(description="出「同一篇文章 × 全部主题」的封面墙（需 pillow）")
    p.add_argument("-o", "--out", default=os.path.join(os.getcwd(), "cover-wall"),
                   help="输出目录，默认 当前目录/cover-wall")
    p.add_argument("-c", "--config", default=None,
                   help="config.json 路径；给了就读里面的 theme 与 cover 段作为默认文案")
    p.add_argument("--themes", default=None,
                   help="只画这几套主题（逗号分隔，如 moyu-green,moyu-ticket）；默认全部已注册主题")
    p.add_argument("--cols", type=int, default=2, help="每行几格，默认 2")
    p.add_argument("--scale", type=int, default=620, help="每格封面宽度（px），默认 620")
    # 文案参数与 make_assets 同名同义（默认 None，交给 config.cover / 内置默认兜底）
    p.add_argument("--brand", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--subtitle", default=None)
    p.add_argument("--date", default=None)
    p.add_argument("--motif", choices=["none", "ring"], default=None)
    p.add_argument("--motif-nodes", type=int, default=None)
    p.add_argument("--motif-label", default=None)
    p.add_argument("--motif-caption", default=None)
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)

    cfg = None
    if args.config and os.path.isfile(args.config):
        import json
        with io.open(args.config, encoding="utf-8") as f:
            cfg = json.load(f) or {}
    cov = make_assets.resolve_cover_texts(cfg, args)

    all_themes = registered_themes()
    if not all_themes:
        print("[X] 读不到 references/theme-index.md 的已注册主题表", file=sys.stderr)
        sys.exit(1)
    want = [t.strip() for t in args.themes.split(",")] if args.themes else None

    rows = []
    for tid, name, _color in all_themes:
        if want and tid not in want:
            continue
        theme = theme_vars.asset_theme(tid)
        if not theme:
            print("[!] 跳过 {}：读不到主题配色（theme-{}.md 缺变量表？）".format(tid, tid),
                  file=sys.stderr)
            continue
        tdir = os.path.join(args.out, tid)
        os.makedirs(tdir, exist_ok=True)
        make_assets.make_cover(tdir, cov["brand"], cov["title"], cov["subtitle"],
                               cov["date"], theme, motif=cov["motif"],
                               motif_nodes=int(cov["motif_nodes"]),
                               motif_label=cov["motif_label"],
                               motif_caption=cov["motif_caption"])
        rows.append((tid, name or cover_spec.THEME_NAMES.get(tid, tid),
                     os.path.join(tdir, "cover.png"), theme,
                     cover_spec.skin_of(tid, theme)))

    if not rows:
        print("[X] 没有可生成的主题", file=sys.stderr)
        sys.exit(1)

    wall = build_wall(rows, cov, args.out, cols=max(1, args.cols), scale=args.scale)
    print("\n封面墙已生成: {}  （{} 套主题，{}x{}）".format(
        wall, len(rows), *Image.open(wall).size))
    print("逐张原图在各主题子目录：{}/<theme>/cover.png".format(args.out))
    print("怎么看：①同色主题（摸鱼绿/摸鱼票据风）是否一眼可分 "
          "②近无彩主题（石墨极简/留白禅意）有没有色彩身份 ③点睛色是否真的上了封面")


if __name__ == "__main__":
    main()
