#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成公众号素材图（封面 + 正文插图）。辅助脚本，发布主流程 publish.py 不依赖它。

依赖：pip install pillow
用法：
    python make_assets.py -c ../config.json                 # 跟着 config 的 theme 走
    python make_assets.py --theme moyu-green -o assets      # 指定主题
    python make_assets.py --title "标题" --subtitle "副标题" --brand "署名"
    python make_assets.py --dark                            # 忽略主题，用内置深色版式
    python make_assets.py --motif ring --motif-caption "7 STEPS"   # 封面右侧画「循环」意象
    python make_assets.py --only cover                      # 只要封面，别生成插图
产出：
    cover.png        1800x766（公众号封面 2.35:1，2x 高清）
    diagram.png      1800x840（正文插图，链路示意，2x 高清）

主题驱动：配色从 references/theme-<id>.md 的「设计变量速查表」里取
（主色调 / 标题色 / 正文色 / 辅助文字 / 极浅底），保证封面与正文成套。
取不到就退回内置深色橙调版式（--dark 同效果）。

2x 高清说明：公众号封面按 900px 宽展示、正文区约 677px 宽，
2 倍超采样输出保证手机 2x/3x 屏上文字锐利不糊。
"""
import argparse
import io
import json
import math
import os
import sys
from PIL import Image, ImageDraw, ImageFont

import theme_vars          # 同目录；主题变量表的唯一解析入口

# 2x 高清倍率：全部坐标与字号按此缩放（设计稿以 1x 为单位）
S = 2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---- 内置深色版式（无主题 / --dark 时使用）
ORANGE = (217, 79, 34)
BG = (22, 24, 29)
PANEL = (32, 35, 42)
BORDER = (54, 59, 68)
FG = (238, 240, 244)
MUTED = (150, 158, 170)
DIM = (108, 114, 126)


# ---------------------------------------------------------------- 主题配色
# 变量表的解析与匹配统一在 theme_vars.py（三个脚本共用一份，见其文件头注释）。
# 放在这里会出问题：清单里少一个标签，主题就静默退回兜底色 —— 封面会退回
# 深色版式、插图会串成别的主题的颜色。统一之后改一处三处生效。
def load_theme(theme_id):
    """从主题组件库抽配色。返回 dict 或 None（取不到就退回内置深色版式）。"""
    return theme_vars.asset_theme(theme_id)


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


def split_title(title, title_size, draw, max_w, soft_w):
    """标题折行，返回 1~2 行。

    - 含显式换行（\\n）时原样尊重，不再自动断
    - 英文标题在空格处断，避免断在词中间（旧版按字符数对半切，会把 Harness 切成 Harn / ess）
    - 中文标题按视觉宽度从中点向两侧找断点
    - max_w 是硬上限（超出会溢出画布），soft_w 是软上限（超过就倾向折两行）
    """
    if "\n" in title:
        return [s.strip() for s in title.split("\n") if s.strip()]

    f = font(title_size, True)

    def width(t):
        return draw.textlength(t, font=f)

    if width(title) <= soft_w:
        return [title]

    mid = len(title) / 2.0
    latin = sum(1 for ch in title if ch.isascii()) / max(1, len(title))
    if latin > 0.5:
        spaces = [i for i, ch in enumerate(title) if ch == " "]
        if spaces:
            cut = min(spaces, key=lambda i: abs(i - mid))
            head, tail = title[:cut].rstrip(), title[cut + 1:].lstrip()
            if head and tail and width(head) <= max_w and width(tail) <= max_w:
                return [head, tail]

    cut = int(mid)
    while cut > 1 and width(title[:cut]) > max_w:
        cut -= 1
    if cut <= 1:
        return [title]
    return [title[:cut], title[cut:]]


def _wash(img, box, color, alpha, radius):
    """在给定区域叠一层低透明度色块（PIL 的 RGB 画布不支持 alpha，走 RGBA 合成）。"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius,
                                            fill=color + (alpha,))
    img.alpha_composite(layer)


def _ring_motif(img, cx, cy, radius, accent, nodes=7, label="LOOP", caption=""):
    """封面右下角画一个「循环」意象：环形导轨 + N 个节点 + 顺时针箭头 + 圆心文字。

    单独开一层 RGBA 再 alpha_composite —— PIL 的 ImageDraw 画在 RGBA 画布上是
    直接写像素、不做混色，低透明度图形必须走图层合成（同 _wash 的理由）。

    版式上这块落在封面右侧的极淡主色块里（x > 600），与左侧标题/副标题不重叠；
    节点数与箭头方向按「一圈走 N 步、顺时针推进」表达循环。
    """
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx, cy, R = cx * S, cy * S, radius * S
    step = 360.0 / max(1, nodes)

    def pt(deg):
        a = math.radians(deg)
        return cx + R * math.cos(a), cy + R * math.sin(a)

    # 导轨圆（很淡，只是把节点串成环）
    d.ellipse([cx - R, cy - R, cx + R, cy + R],
              outline=accent + (60,), width=2 * S)

    # 相邻节点之间的中点上放箭头，方向 = 顺时针切向（角度增大即屏幕上顺时针）
    for i in range(nodes):
        deg = -90 + (i + 0.5) * step
        px, py = pt(deg)
        a = math.radians(deg)
        tx, ty = -math.sin(a), math.cos(a)   # 切向 = 前进方向
        nx, ny = math.cos(a), math.sin(a)    # 法向 = 用于撑开箭头底边
        tip = (px + tx * 5 * S, py + ty * 5 * S)
        b1 = (px - tx * 3.5 * S + nx * 4 * S, py - ty * 3.5 * S + ny * 4 * S)
        b2 = (px - tx * 3.5 * S - nx * 4 * S, py - ty * 3.5 * S - ny * 4 * S)
        d.polygon([tip, b1, b2], fill=accent + (135,))

    # 节点：起始节点实心加大（当前这一轮的入口），其余半透明
    for i in range(nodes):
        x, y = pt(-90 + i * step)
        r = (7 if i == 0 else 5.5) * S
        alpha = 255 if i == 0 else 96
        d.ellipse([x - r, y - r, x + r, y + r], fill=accent + (alpha,))
    x, y = pt(-90)
    d.ellipse([x - 13 * S, y - 13 * S, x + 13 * S, y + 13 * S],
              outline=accent + (110,), width=2 * S)

    # 圆心文字（anchor="mm" 让文字正中对齐到圆心，省得自己量基线偏移）
    if label:
        d.text((cx, cy - 9 * S), label, font=font(19, True),
               fill=accent + (235,), anchor="mm")
    if caption:
        d.text((cx, cy + 14 * S), caption, font=font(12),
               fill=accent + (150,), anchor="mm")

    img.alpha_composite(layer)


def make_cover(out_dir, brand, title, subtitle, date_str, theme=None,
               motif=None, motif_nodes=7, motif_label="LOOP", motif_caption=""):
    W, H = 900 * S, 383 * S
    if theme:
        img = Image.new("RGBA", (W, H), theme["light"] + (255,))
        accent = theme["primary"]
        fg = theme["title"]
        muted = theme["body"]
        dim = theme["aux"]
        # 右下角一块极淡的主色，做出杂志感的层次
        _wash(img, [W - 300 * S, H - 300 * S, W + 80 * S, H + 80 * S],
              accent, 26, 60 * S)
    else:
        img = Image.new("RGBA", (W, H), BG + (255,))
        accent = ORANGE
        fg = FG
        muted = MUTED
        dim = DIM

    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, 7 * S, H], fill=accent)
    d.text((56 * S, 48 * S), brand, font=font(19), fill=accent)

    # 标题折成 1~2 行；两行时缩一档字号，保证长标题不溢出
    lines = split_title(title, 50, d, (900 - 112) * S, 520 * S)[:2]
    if len(lines) == 1:
        d.text((56 * S, 126 * S), lines[0], font=font(56, True), fill=fg)
    else:
        tf = font(50, True)
        for i, line in enumerate(lines):
            d.text((56 * S, (96 + i * 64) * S), line, font=tf, fill=fg)

    d.line([(57 * S, 236 * S), (151 * S, 236 * S)], fill=accent, width=2 * S)
    d.text((56 * S, 256 * S), subtitle, font=font(21), fill=muted)
    d.text((56 * S, 306 * S), date_str, font=font(17), fill=dim)

    # 右侧空白处点一个意象。圆心取极淡色块的可视中心（色块右边被画布裁掉，
    # 可视区是 x∈[600,900]，中心 750），半径让最右节点离画布边留 ~35px
    if motif == "ring":
        _ring_motif(img, 762, 197, 90, accent,
                    nodes=motif_nodes, label=motif_label, caption=motif_caption)

    img = img.convert("RGB")
    path = os.path.join(out_dir, "cover.png")
    img.save(path)
    print("封面已生成: {}  ({}x{})".format(path, W, H))



def make_flow(out_dir, theme=None):
    W, H = 900 * S, 420 * S
    if theme:
        bg, panel, border = theme["light"], None, None
        img = Image.new("RGBA", (W, H), bg + (255,))
        accent, fg, muted, dim = (theme["primary"], theme["title"],
                                  theme["body"], theme["aux"])
        _wash(img, [W - 260 * S, 0, W + 80 * S, H], accent, 22, 0)
        panel = theme["light"]
        border = tuple(int(c * 0.88) for c in accent)
    else:
        img = Image.new("RGBA", (W, H), BG + (255,))
        panel, border = PANEL, BORDER
        accent, fg, muted, dim = ORANGE, FG, MUTED, DIM

    d = ImageDraw.Draw(img)
    d.text((44 * S, 36 * S), "发布链路三步", font=font(25, True), fill=fg)
    d.text((44 * S, 74 * S), "任一环节失败，草稿箱里都不会出现文章",
           font=font(17), fill=muted)

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
                            fill=panel, outline=border, width=1 * S)
        d.rounded_rectangle([x, y0, x + 3 * S, y0 + bh], radius=2 * S, fill=accent)
        d.text((x + 20 * S, y0 + 16 * S), num, font=font(15, True), fill=accent)
        d.text((x + 20 * S, y0 + 44 * S), title, font=font(21, True), fill=fg)
        d.text((x + 20 * S, y0 + 78 * S), api, font=font(13), fill=dim)
        d.multiline_text((x + 20 * S, y0 + 102 * S), desc, font=font(15),
                         fill=muted, spacing=6 * S)

        if i < len(steps) - 1:
            ax = x + bw + 8 * S
            ay = y0 + bh // 2
            d.line([(ax, ay), (ax + gap - 18 * S, ay)], fill=border, width=2 * S)
            d.polygon([(ax + gap - 18 * S, ay - 5 * S), (ax + gap - 8 * S, ay),
                       (ax + gap - 18 * S, ay + 5 * S)], fill=accent)

    d.text((44 * S, 330 * S), "共同前提：账号类型与认证状态决定接口权限",
           font=font(16), fill=dim)
    d.text((44 * S, 358 * S), "未认证账号调用发布接口会返回 48001 api unauthorized",
           font=font(16), fill=dim)

    img = img.convert("RGB")
    path = os.path.join(out_dir, "diagram.png")
    img.save(path)
    print("正文插图已生成: {}  ({}x{})".format(path, W, H))


def main():
    p = argparse.ArgumentParser(description="生成公众号封面与正文插图（需 pillow）")
    p.add_argument("-o", "--out", default=os.path.join(os.getcwd(), "assets"),
                   help="输出目录，默认 当前目录/assets")
    p.add_argument("-c", "--config", default=None,
                   help="config.json 路径；给了就读里面的 theme，省得两边不一致")
    p.add_argument("--theme", default=None,
                   help="主题标识（如 moyu-green），对应 references/theme-<id>.md；"
                        "不给且 config 里也没有，就用内置深色橙调版式")
    p.add_argument("--dark", action="store_true",
                   help="忽略主题，强制用内置深色橙调版式")
    p.add_argument("--brand", default="公众号 · 工程笔记", help="封面左上角署名")
    p.add_argument("--title", default="文章标题",
                   help="封面主标题。过长自动折两行：英文断在空格处、中文按宽度断；"
                        "想自己控制换行就在参数里写 \\n")
    p.add_argument("--subtitle", default="副标题 / 一句话摘要", help="封面副标题")
    p.add_argument("--date", default="", help="封面日期，留空不显示")
    p.add_argument("--motif", choices=["none", "ring"], default="none",
                   help="封面右侧的意象图：ring=环形节点+顺时针箭头（讲循环/流程的文章用）")
    p.add_argument("--motif-nodes", type=int, default=7,
                   help="ring 意象的节点数，默认 7（对应「几个环节」就填几）")
    p.add_argument("--motif-label", default="LOOP", help="ring 圆心主文字，默认 LOOP")
    p.add_argument("--motif-caption", default="",
                   help="ring 圆心副文字（小字），如 \"7 STEPS\"，留空不画")
    p.add_argument("--only", choices=["all", "cover", "diagram"], default="all",
                   help="只生成其中一张；默认 all（两张都出）")
    args = p.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("[X] 需要 pillow：pip install pillow", file=sys.stderr)
        sys.exit(1)

    theme_id = args.theme
    if not theme_id and args.config and os.path.isfile(args.config):
        with io.open(args.config, encoding="utf-8") as f:
            theme_id = (json.load(f) or {}).get("theme")

    theme = None
    if not args.dark:
        theme = load_theme(theme_id)
        if theme_id and not theme:
            print("[!] 读不到主题配色（references/theme-{}.md 缺失或没有变量表），"
                  "退回内置深色版式".format(theme_id), file=sys.stderr)
        elif theme:
            print("[i] 配色取自主题：{}  primary={}".format(
                theme["id"], "#%02X%02X%02X" % theme["primary"]))

    os.makedirs(args.out, exist_ok=True)
    if args.only in ("all", "cover"):
        make_cover(args.out, args.brand, args.title, args.subtitle, args.date, theme,
                   motif=args.motif, motif_nodes=args.motif_nodes,
                   motif_label=args.motif_label, motif_caption=args.motif_caption)
    if args.only in ("all", "diagram"):
        make_flow(args.out, theme)


if __name__ == "__main__":
    main()
