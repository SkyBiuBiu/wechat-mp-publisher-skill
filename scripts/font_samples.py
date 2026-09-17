#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字体对比样张：同一版封面 + 同一张流程图，用各字体预设各出一遍，拼成一张图。

为什么需要它：字体好不好看，文字描述不出来 —— "楷体温润、宋体正式"这种话
谁都会说，但贴到自己那篇文章的标题上是什么感觉，只能看。这个脚本把
「封面 + 流程图」两处受字体影响最大的产物并排渲染，一眼就能挑。

用法：
    python scripts/font_samples.py --src ../wechat-publish --out ../wechat-publish/showcase/_fonts
    python scripts/font_samples.py --src ... --out ... --presets system,wenkai
    python scripts/font_samples.py --src ... --out ... --no-diagram   # 只比封面（快）

--src 目录需要含 article.md 与 config.json（与 build_theme_showcase.py 同源）。
产出：<out>/font-samples.png（对比图）、<out>/<preset>/（各预设的封面与流程图）。
"""

import argparse
import io
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import fonts                      # noqa: E402  字体预设的唯一来源

PY = sys.executable

BG = (244, 245, 247)
CARD = (255, 255, 255)
INK = (17, 24, 39)
DIM = (107, 114, 128)
LINE = (229, 231, 235)
LABEL_W = 232
COVER_W = 700
PAD = 26
ROW_GAP = 22
MAX_DIAG_H = 470
# 图内字号比正文默认（16px）大一档：对比样张是拿来看字形的，字号太小就白比了
DIAG_FONT_PX = 18


def out(msg=""):
    print(msg, flush=True)


def die(msg):
    print("[x] " + msg, file=sys.stderr)
    sys.exit(1)


def run(cmd, quiet=True):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and not quiet:
        out("    " + (r.stdout or "").strip())
        out("    " + (r.stderr or "").strip())
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def pick_font(size, bold=False):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:                     # noqa: BLE001
                continue
    return ImageFont.load_default()


def fit(img, max_w=None, max_h=None):
    """等比缩放到限制框内。"""
    w, h = img.size
    k = 1.0
    if max_w:
        k = min(k, float(max_w) / w)
    if max_h:
        k = min(k, float(max_h) / h)
    if k == 1.0:
        return img
    return img.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description="字体预设对比样张")
    ap.add_argument("--src", required=True, help="基准稿目录（含 article.md / config.json）")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--presets", default=None,
                    help="逗号分隔的预设，默认全部可用预设")
    ap.add_argument("--theme", default=None, help="主题标识，默认取 config.json 的 theme")
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--no-diagram", action="store_true")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    root = os.path.abspath(args.out)
    os.makedirs(root, exist_ok=True)

    cfg = {}
    cfg_path = os.path.join(src, "config.json")
    if os.path.isfile(cfg_path):
        cfg = json.load(io.open(cfg_path, encoding="utf-8")) or {}
    theme = args.theme or cfg.get("theme") or "moyu-green"

    ids = [x.strip() for x in args.presets.split(",")] if args.presets else list(fonts.PRESETS)
    rows, skipped = [], []
    for pid in ids:
        if pid not in fonts.PRESETS:
            die("未登记的字体预设：{}（可选：{}）".format(pid, "/".join(fonts.PRESETS)))
        if not fonts.available(pid):
            skipped.append(pid)
            continue
        tdir = os.path.join(root, pid)
        os.makedirs(tdir, exist_ok=True)
        out("=== {}（{}）===".format(pid, fonts.PRESETS[pid]["label"]))

        cover_png = None
        if not args.no_cover:
            rc, log = run([PY, os.path.join(HERE, "make_assets.py"),
                           "-c", cfg_path, "-o", tdir, "--only", "cover",
                           "--font-preset", pid], quiet=False)
            cand = os.path.join(tdir, "cover.png")
            if rc == 0 and os.path.isfile(cand):
                cover_png = cand
                out("    封面 OK")
            else:
                out("    [!] 封面失败")

        diag_png = None
        if not args.no_diagram:
            rc, log = run([PY, os.path.join(HERE, "render_mermaid.py"),
                           os.path.join(src, "article.md"), "--theme", theme,
                           "--font-preset", pid,
                           "--font-size", str(DIAG_FONT_PX),
                           "-o", os.path.join(tdir, "article.mermaid.md"),
                           "--out-dir", tdir], quiet=False)
            cand = os.path.join(tdir, "mermaid-1.png")
            if rc == 0 and os.path.isfile(cand):
                diag_png = cand
                out("    流程图 OK")
            else:
                out("    [!] 流程图失败（本地渲染不可用？）")

        if cover_png or diag_png:
            f = fonts.preset_files(pid)
            rows.append(dict(
                pid=pid, label=fonts.PRESETS[pid]["label"],
                files=os.path.basename(f["title"] or ""), cover=cover_png,
                diag=diag_png))

    if skipped:
        out("[i] 跳过（字体文件没配齐）：{}".format("、".join(skipped)))
    if not rows:
        die("没有任何预设出图成功 —— 先跑 scripts/fonts.py 看字体在哪")

    # ---------------- 拼图
    cover_imgs = [fit(Image.open(r["cover"]).convert("RGB"), max_w=COVER_W)
                  for r in rows] if rows[0]["cover"] else [None] * len(rows)
    diag_imgs = [fit(Image.open(r["diag"]).convert("RGB"), max_h=MAX_DIAG_H)
                 for r in rows] if rows[0]["diag"] else [None] * len(rows)

    row_h = 0
    for ci, di in zip(cover_imgs, diag_imgs):
        row_h = max(row_h, ci.size[1] if ci else 0, di.size[1] if di else 0)
    diag_w = max([d.size[0] for d in diag_imgs if d] or [0])

    W = LABEL_W + (COVER_W if cover_imgs[0] else 0) + (diag_w + 30 if diag_imgs[0] else 0)
    W += PAD * 2
    title_h = 96
    H = title_h + len(rows) * (row_h + ROW_GAP) + PAD + 20

    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    f_h1 = pick_font(30, True)
    f_h2 = pick_font(16)
    f_name = pick_font(26, True)
    f_meta = pick_font(15)
    f_tag = pick_font(13)

    d.text((PAD, 30), "字体对比样张", font=f_h1, fill=INK)
    d.text((PAD, 68), "同一版封面（Agent Loop 七环节）× 同一张流程图，只换字体预设；"
                      "封面为 2x 高清缩略，流程图按正文宽度渲染", font=f_h2, fill=DIM)

    y = title_h
    for i, r in enumerate(rows):
        d.rounded_rectangle([PAD - 10, y - 8, W - PAD + 10, y + row_h + 10],
                            radius=12, fill=CARD, outline=LINE)
        x = PAD
        d.text((x, y + 6), r["pid"], font=f_name, fill=INK)
        d.text((x, y + 42), r["label"], font=f_meta, fill=DIM)
        # 文件名也写上：同一套字体换个字重，观感差得不小
        d.text((x, y + 66), r["files"][:26], font=f_tag, fill=(156, 163, 175))
        x += LABEL_W

        if r["cover"] and cover_imgs[i]:
            canvas.paste(cover_imgs[i], (x, y))
            d.rectangle([x, y, x + cover_imgs[i].size[0] - 1, y + cover_imgs[i].size[1] - 1],
                        outline=LINE)
            x += COVER_W + 30
        if r["diag"] and diag_imgs[i]:
            dy = y + max(0, (row_h - diag_imgs[i].size[1]) // 2)
            canvas.paste(diag_imgs[i], (x, dy))
            d.rectangle([x, dy, x + diag_imgs[i].size[0] - 1, dy + diag_imgs[i].size[1] - 1],
                        outline=LINE)
        y += row_h + ROW_GAP

    png = os.path.join(root, "font-samples.png")
    canvas.save(png)
    out("\n[OK] 对比图：{}（{} 套预设，{}）".format(
        png, len(rows), "封面 + 流程图" if rows[0]["diag"] else "仅封面"))


if __name__ == "__main__":
    main()
