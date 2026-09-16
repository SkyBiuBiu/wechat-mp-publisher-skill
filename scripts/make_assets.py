#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成公众号素材图（封面 + 正文插图）。辅助脚本，发布主流程 publish.py 不依赖它。

依赖：pip install pillow
用法：
    python make_assets.py                                  # 输出到 ./assets
    python make_assets.py -o /path/to/proj/assets          # 指定输出目录
    python make_assets.py --title "标题" --subtitle "副标题" --brand "署名"
产出：
    cover.png        1800x766（公众号封面 2.35:1，2x 高清）
    diagram.png      1800x840（正文插图，链路示意，2x 高清）

2x 高清说明：公众号封面按 900px 宽展示、正文区约 677px 宽，
2 倍超采样输出保证手机 2x/3x 屏上文字锐利不糊。
改文案用命令行参数；要改版式直接改下面的 make_cover / make_flow。
"""
import argparse
import os
import sys
from PIL import Image, ImageDraw, ImageFont

# 2x 高清倍率：全部坐标与字号按此缩放（设计稿以 1x 为单位）
S = 2

ORANGE = (217, 79, 34)
BG = (22, 24, 29)
PANEL = (32, 35, 42)
BORDER = (54, 59, 68)
FG = (238, 240, 244)
MUTED = (150, 158, 170)
DIM = (108, 114, 126)


def font(size, bold=False):
    """挑一个可用的中文字体，按优先级回退。"""
    size = int(size * S)
    candidates = []
    if bold:
        candidates += [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
                       "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                       "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]
    else:
        candidates += [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                       "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                       "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    candidates += [r"C:\Windows\Fonts\simsun.ttc"]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_cover(out_dir, brand, title, subtitle, date_str):
    W, H = 900 * S, 383 * S
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, 7 * S, H], fill=ORANGE)
    d.text((56 * S, 48 * S), brand, font=font(19), fill=ORANGE)

    # 标题超长自动折成两行
    if len(title) > 9:
        cut = (len(title) + 1) // 2
        d.text((56 * S, 96 * S), title[:cut], font=font(50, True), fill=FG)
        d.text((56 * S, 160 * S), title[cut:], font=font(50, True), fill=FG)
    else:
        d.text((56 * S, 126 * S), title, font=font(56, True), fill=FG)

    d.line([(57 * S, 236 * S), (151 * S, 236 * S)], fill=ORANGE, width=2 * S)
    d.text((56 * S, 256 * S), subtitle, font=font(21), fill=MUTED)
    d.text((56 * S, 306 * S), date_str, font=font(17), fill=DIM)

    path = os.path.join(out_dir, "cover.png")
    img.save(path)
    print("封面已生成: {}  ({}x{})".format(path, W, H))


def make_flow(out_dir):
    W, H = 900 * S, 420 * S
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((44 * S, 36 * S), "发布链路三步", font=font(25, True), fill=FG)
    d.text((44 * S, 74 * S), "任一环节失败，草稿箱里都不会出现文章", font=font(17), fill=MUTED)

    bw, bh, gap = 240 * S, 148 * S, 44 * S
    x0, y0 = 44 * S, 132 * S
    steps = [
        ("01", "access_token", "/cgi-bin/token", "验 AppID / AppSecret\n+ IP 白名单"),
        ("02", "素材上传", "uploadimg / add_material", "正文图换链\n封面拿 media_id"),
        ("03", "草稿创建", "/cgi-bin/draft/add", "图文落库\n草稿箱可见"),
    ]

    for i, (num, title, api, desc) in enumerate(steps):
        x = x0 + i * (bw + gap)
        d.rounded_rectangle([x, y0, x + bw, y0 + bh], radius=10 * S,
                            fill=PANEL, outline=BORDER, width=1 * S)
        d.rounded_rectangle([x, y0, x + 3 * S, y0 + bh], radius=2 * S, fill=ORANGE)
        d.text((x + 20 * S, y0 + 16 * S), num, font=font(15, True), fill=ORANGE)
        d.text((x + 20 * S, y0 + 44 * S), title, font=font(21, True), fill=FG)
        d.text((x + 20 * S, y0 + 78 * S), api, font=font(13), fill=DIM)
        d.multiline_text((x + 20 * S, y0 + 102 * S), desc, font=font(15),
                         fill=MUTED, spacing=6 * S)

        if i < len(steps) - 1:
            ax = x + bw + 8 * S
            ay = y0 + bh // 2
            d.line([(ax, ay), (ax + gap - 18 * S, ay)], fill=BORDER, width=2 * S)
            d.polygon([(ax + gap - 18 * S, ay - 5 * S), (ax + gap - 8 * S, ay),
                       (ax + gap - 18 * S, ay + 5 * S)],
                      fill=ORANGE)

    d.text((44 * S, 330 * S), "共同前提：账号类型与认证状态决定接口权限", font=font(16), fill=DIM)
    d.text((44 * S, 358 * S), "未认证账号调用发布接口会返回 48001 api unauthorized",
           font=font(16), fill=DIM)

    path = os.path.join(out_dir, "diagram.png")
    img.save(path)
    print("正文插图已生成: {}  ({}x{})".format(path, W, H))


def main():
    p = argparse.ArgumentParser(description="生成公众号封面与正文插图（需 pillow）")
    p.add_argument("-o", "--out", default=os.path.join(os.getcwd(), "assets"),
                   help="输出目录，默认 当前目录/assets")
    p.add_argument("--brand", default="公众号 · 工程笔记", help="封面左上角署名")
    p.add_argument("--title", default="文章标题", help="封面主标题（超 9 字自动折两行）")
    p.add_argument("--subtitle", default="副标题 / 一句话摘要", help="封面副标题")
    p.add_argument("--date", default="", help="封面日期，留空不显示")
    args = p.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("[X] 需要 pillow：pip install pillow", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    make_cover(args.out, args.brand, args.title, args.subtitle, args.date)
    make_flow(args.out)


if __name__ == "__main__":
    main()
