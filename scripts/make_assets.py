#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成公众号素材图（封面 + 正文插图）。辅助脚本，发布主流程 publish.py 不依赖它。

依赖：pip install pillow
用法：
    python make_assets.py -c ../config.json                 # 跟着 config 的 theme 与 cover 段走
    python make_assets.py --theme moyu-green -o assets      # 指定主题
    python make_assets.py --title "标题" --subtitle "副标题" --brand "署名"
    python make_assets.py --dark                            # 忽略主题，用内置深色版式
    python make_assets.py --motif ring --motif-caption "7 STEPS"   # 封面右侧画「循环」意象
    python make_assets.py --only cover                      # 只要封面，别生成插图
产出：
    cover.png        1800x766（公众号封面 2.35:1，2x 高清）
    diagram.png      1800x840（正文插图，链路示意，2x 高清）

主题驱动：配色从 references/theme-<id>.md 的「设计变量速查表」里取
（主色调 / 标题色 / 正文色 / 辅助文字 / 极浅底 / 点睛色），保证封面与正文成套。
取不到就退回内置深色橙调版式（--dark 同效果）。

**版式与皮肤**：封面的几何规格在 `cover_spec.SPEC`（单一来源，别再往本文件写坐标），
主题气质由 `cover_spec.THEME_SKINS` 的皮肤决定 —— 底色倾向、竖条宽度与颜色、
外框描边、圆角、底纹、字型。同一套几何下"摸鱼绿 vs 摸鱼票据风""石墨极简 vs 留白禅意"
靠皮肤区分，不靠改主题库色值。改版式请改 cover_spec.py，并跑 cover_spec.py 自检。

**文案来源**：`config.json` 的 `cover` 段（brand/title/subtitle/date/motif…），
命令行参数只做覆盖（优先级 CLI > config.cover > config.article.title > 内置默认）。

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
import cover_spec          # 同目录；封面几何规格与主题皮肤的唯一来源

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


_SERIF_MISSING = []


def font(size, bold=False, serif=False):
    """挑一个可用的中文字体，按优先级回退。

    `serif=True` 给"禅意"类主题用衬线标题（皮肤参数 `serif`）。衬线字体比黑体
    难找，取不到时**退回黑体并在 stderr 说一句** —— 静默退化会让"禅意风"这个
    皮肤偷偷失效，而那正是它和石墨极简区分开的主要手段之一。
    """
    size = int(size * S)
    candidates = []
    if serif:
        candidates += [r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\msyh.ttc",
                       "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
                       "/usr/share/fonts/truetype/arphic/uming.ttc"]
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
    if serif and "serif" not in _SERIF_MISSING:
        _SERIF_MISSING.append("serif")
        print("[!] 本机没有可用衬线中文字体，标题退化为黑体（禅意风的字型区分会变弱）",
              file=sys.stderr)
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


def _ring_motif(img, spec, color, nodes=7, label="LOOP", caption="", dim=1.0):
    """封面右下角画一个「循环」意象：环形导轨 + N 个节点 + 顺时针箭头 + 圆心文字。

    单独开一层 RGBA 再 alpha_composite —— PIL 的 ImageDraw 画在 RGBA 画布上是
    直接写像素、不做混色，低透明度图形必须走图层合成（同 _wash 的理由）。

    版式上这块落在封面右侧的极淡主色块里（x > 600），与左侧标题/副标题不重叠；
    节点数与箭头方向按「一圈走 N 步、顺时针推进」表达循环。

    颜色由调用方决定（主题用**点睛色**，不是主色）：主色是墨黑/石墨灰的主题，
    用它画环等于没画 —— 橄榄手记的封面长期就是这么灰掉的。
    `dim` 是整体调淡倍率，给"禅意"这类要极度克制的主题用。
    """
    r = spec["ring"]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx, cy, R = r["cx"] * S, r["cy"] * S, r["r"] * S
    step = 360.0 / max(1, nodes)

    def al(v):
        return max(0, min(255, int(round(v * dim))))

    def pt(deg):
        a = math.radians(deg)
        return cx + R * math.cos(a), cy + R * math.sin(a)

    # 导轨圆（很淡，只是把节点串成环）
    d.ellipse([cx - R, cy - R, cx + R, cy + R],
              outline=color + (al(r["rail_alpha"]),), width=2 * S)

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
        d.polygon([tip, b1, b2], fill=color + (al(r["arrow_alpha"]),))

    # 节点：起始节点实心加大（当前这一轮的入口），其余半透明
    for i in range(nodes):
        x, y = pt(-90 + i * step)
        rr = (r["node_first_r"] if i == 0 else r["node_r"]) * S
        alpha = 255 if i == 0 else al(r["node_alpha"])
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=color + (alpha,))
    x, y = pt(-90)
    d.ellipse([x - 13 * S, y - 13 * S, x + 13 * S, y + 13 * S],
              outline=color + (al(r["rail_alpha"] + 18),), width=2 * S)

    # 圆心文字（anchor="mm" 让文字正中对齐到圆心，省得自己量基线偏移）
    if label:
        d.text((cx, cy + r["label_dy"] * S), label,
               font=font(r["label_size"], True), fill=color + (al(235),), anchor="mm")
    if caption:
        d.text((cx, cy + r["caption_dy"] * S), caption,
               font=font(r["caption_size"]), fill=color + (al(150),), anchor="mm")

    img.alpha_composite(layer)


def _paper_texture(img, spec, kind, color, bg):
    """封面底纹：让"质感"成为可辨的主题特征，而不只是换颜色。

    dotted   票据的撕票虚线：底部一条虚线 + 两端打孔圆（票根）
    hairline 禅意的极细底线：底部一条 1px 细线，白底上几乎只是"呼吸感"
    """
    if kind in (None, "none"):
        return
    c = spec["canvas"]
    W, H = c["w"] * S, c["h"] * S
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1 = 56 * S, W - 56 * S

    if kind == "dotted":
        y = 350 * S
        dash, gap = 16 * S, 10 * S
        x = x0
        while x < x1:
            d.line([(x, y), (min(x + dash, x1), y)], fill=color + (255,), width=2 * S)
            x += dash + gap
        for cx in (30 * S, W - 30 * S):
            d.ellipse([cx - 7 * S, y - 7 * S, cx + 7 * S, y + 7 * S],
                      fill=bg + (255,), outline=color + (255,), width=2 * S)
    elif kind == "hairline":
        y = 336 * S
        d.line([(x0, y), (x1, y)], fill=color + (255,), width=1 * S)

    img.alpha_composite(layer)


def make_cover(out_dir, brand, title, subtitle, date_str, theme=None,
               motif=None, motif_nodes=7, motif_label="LOOP", motif_caption=""):
    """按 cover_spec.SPEC 的几何画封面；主题决定配色与"皮肤"（底色/描边/圆角/底纹/字型）。

    几何全部来自 SPEC，本函数不写字面坐标 —— 想调版式请改 cover_spec.py。
    """
    spec = cover_spec.SPEC
    c, rl, br, ti, ru = (spec["canvas"], spec["rail"], spec["brand"],
                         spec["title"], spec["rule"])
    W, H = c["w"] * c["scale"], c["h"] * c["scale"]

    if theme:
        skin = cover_spec.skin_of(theme.get("id"), theme)
        bg = theme_vars.rgb(skin["bg"]) if skin.get("bg") else theme["light"]
        img = Image.new("RGBA", (W, H), bg + (255,))
        primary = theme["primary"]
        accent = theme["accent"]
        fg = theme["title"]
        muted = theme["body"]
        # 日期比副标题再浅一档。摸鱼票据风只有「次要文字」一个灰档位
        # （aux 与 body 取到同色），靠这一步拉开层次，不用主题库为封面多登记色值。
        dim = theme_vars.mix(theme["aux"], bg, 0.35, triples=True)
        if skin["rail_color"] == "primary":
            rail = primary
        elif skin["rail_color"]:
            rail = theme_vars.rgb(skin["rail_color"])
        else:
            rail = accent
        # 右下角一块极淡的主色，做出杂志感的层次（alpha 由皮肤决定）
        w = spec["wash"]
        _wash(img, [W + w["dx"] * S, H + w["dy"] * S,
                    W + (w["dx"] + w["dw"]) * S, H + (w["dy"] + w["dh"]) * S],
              primary, skin["wash_alpha"] or w["alpha"], skin["radius"] * S)
        if skin["frame_w"]:
            fw = skin["frame_w"] * S
            d0 = ImageDraw.Draw(img)
            d0.rectangle([fw // 2, fw // 2, W - 1 - fw // 2, H - 1 - fw // 2],
                         outline=theme_vars.rgb(skin["frame_color"]), width=fw)
        _paper_texture(img, spec, skin["paper"],
                       theme_vars.rgb(skin["paper_color"]) if skin.get("paper_color")
                       else theme_vars.mix(accent, bg, 0.72, triples=True), bg)
        ring_color, ring_dim = accent, skin["ring_dim"]
        serif = skin["serif"]
    else:
        # 内置深色版式（无主题 / --dark）：只借 SPEC 的几何，不参与皮肤与底纹
        skin = None
        img = Image.new("RGBA", (W, H), BG + (255,))
        primary = rail = accent = ORANGE
        fg, muted, dim = FG, MUTED, DIM
        ring_color, ring_dim, serif = ORANGE, 1.0, False

    d = ImageDraw.Draw(img)

    # 左侧主题色竖条（贯穿上下，是封面上最"重"的一块主题色）
    rail_w = skin["rail_w"] if skin else rl["w"]
    d.rectangle([rl["x"] * S, 0, (rl["x"] + rail_w) * S, H], fill=rail)

    # 品牌行：点睛色小方块 + 署名（方块让品牌行也带上主题色，不再只是一行灰字）
    dot = br["dot"] * S
    d.rectangle([br["x"] * S, br["y"] * S + (br["size"] * S - dot) // 2,
                 br["x"] * S + dot, br["y"] * S + (br["size"] * S + dot) // 2],
                fill=accent)
    d.text(((br["x"] + br["dot"] + br["dot_gap"]) * S, br["y"] * S), brand,
           font=font(br["size"]), fill=accent)

    # 标题折成 1~2 行；两行时缩一档字号，保证长标题不溢出
    lines = split_title(title, ti["two_size"], d,
                        ti["max_w"] * S, ti["soft_w"] * S)[:ti["max_lines"]]
    if len(lines) == 1:
        d.text((ti["x"] * S, ti["one_y"] * S), lines[0],
               font=font(ti["one_size"], True, serif), fill=fg)
    else:
        tf = font(ti["two_size"], True, serif)
        for i, line in enumerate(lines):
            d.text((ti["x"] * S, (ti["two_y"] + i * ti["leading"]) * S), line,
                   font=tf, fill=fg)

    # 分隔线：用点睛色，够长才立得住"栏目感"
    rule_w = (skin["rule_w"] if skin and skin.get("rule_w") else ru["w"])
    d.line([(ru["x"] * S, ru["y"] * S), ((ru["x"] + rule_w) * S, ru["y"] * S)],
           fill=accent, width=ru["thick"] * S)
    d.text((spec["subtitle"]["x"] * S, spec["subtitle"]["y"] * S), subtitle,
           font=font(spec["subtitle"]["size"]), fill=muted)
    d.text((spec["date"]["x"] * S, spec["date"]["y"] * S), date_str,
           font=font(spec["date"]["size"]), fill=dim)

    # 右侧空白处点一个意象。圆心取极淡色块的可视中心（色块右边被画布裁掉，
    # 可视区是 x∈[600,900]，中心 750），半径让最右节点离画布边留 ~35px
    if motif == "ring":
        _ring_motif(img, spec, ring_color, nodes=motif_nodes,
                    label=motif_label, caption=motif_caption, dim=ring_dim)

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


COVER_DEFAULTS = {
    "brand": "公众号 · 工程笔记",
    "title": "文章标题",
    "subtitle": "副标题 / 一句话摘要",
    "date": "",
    "motif": "none", "motif_nodes": 7, "motif_label": "LOOP", "motif_caption": "",
}


def resolve_cover_texts(cfg, args):
    """决定封面文案：**CLI（显式传入）> config.cover > config.article.title > 内置默认**。

    config 只带 `cover` 段时优先用它；没有该段时老配置照常工作（等同旧行为：
    CLI 参数说了算，没说的用内置默认）。title 额外支持从 `article.title` 复用 ——
    绝大多数封面主标题就是文章标题，没必要让人抄两遍。
    """
    cov = (cfg or {}).get("cover") or {}
    art = (cfg or {}).get("article") or {}
    cli = vars(args)
    out, source = {}, set()
    for key, default in COVER_DEFAULTS.items():
        cli_key = "motif_" + key.split("_", 1)[1] if key.startswith("motif_") else key
        val = cli.get(cli_key)
        if val is not None:
            out[key] = val
            source.add("命令")
            continue
        if key in cov and cov[key] not in (None, ""):
            out[key] = cov[key]
            source.add("config.cover")
            continue
        if key == "title" and art.get("title"):
            out[key] = art["title"]
            source.add("config.article")
            continue
        out[key] = default
    if cov:
        print("[i] 封面文案来源：{}".format(" + ".join(sorted(source)) or "内置默认"))
    return out


def main():
    p = argparse.ArgumentParser(description="生成公众号封面与正文插图（需 pillow）")
    p.add_argument("-o", "--out", default=os.path.join(os.getcwd(), "assets"),
                   help="输出目录，默认 当前目录/assets")
    p.add_argument("-c", "--config", default=None,
                   help="config.json 路径；给了就读里面的 theme 与 cover 段"
                        "（brand/title/subtitle/date/motif…），省得两边不一致")
    p.add_argument("--theme", default=None,
                   help="主题标识（如 moyu-green），对应 references/theme-<id>.md；"
                        "不给且 config 里也没有，就用内置深色橙调版式")
    p.add_argument("--dark", action="store_true",
                   help="忽略主题，强制用内置深色橙调版式")
    p.add_argument("--brand", default=None, help="封面左上角署名（默认取 config.cover.brand）")
    p.add_argument("--title", default=None,
                   help="封面主标题。过长自动折两行：英文断在空格处、中文按宽度断；"
                        "想自己控制换行就在参数里写 \\n（默认取 config.cover.title / article.title）")
    p.add_argument("--subtitle", default=None, help="封面副标题（默认取 config.cover.subtitle）")
    p.add_argument("--date", default=None, help="封面日期，留空不显示（默认取 config.cover.date）")
    p.add_argument("--motif", choices=["none", "ring"], default=None,
                   help="封面右侧的意象图：ring=环形节点+顺时针箭头（讲循环/流程的文章用）")
    p.add_argument("--motif-nodes", type=int, default=None,
                   help="ring 意象的节点数，默认 7（对应「几个环节」就填几）")
    p.add_argument("--motif-label", default=None, help="ring 圆心主文字，默认 LOOP")
    p.add_argument("--motif-caption", default=None,
                   help="ring 圆心副文字（小字），如 \"7 STEPS\"，留空不画")
    p.add_argument("--only", choices=["all", "cover", "diagram"], default="all",
                   help="只生成其中一张；默认 all（两张都出）")
    args = p.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("[X] 需要 pillow：pip install pillow", file=sys.stderr)
        sys.exit(1)

    cfg = None
    if args.config and os.path.isfile(args.config):
        with io.open(args.config, encoding="utf-8") as f:
            cfg = json.load(f) or {}

    theme_id = args.theme or (cfg or {}).get("theme")

    theme = None
    if not args.dark:
        theme = load_theme(theme_id)
        if theme_id and not theme:
            print("[!] 读不到主题配色（references/theme-{}.md 缺失或没有变量表），"
                  "退回内置深色版式".format(theme_id), file=sys.stderr)
        elif theme:
            skin = cover_spec.skin_of(theme["id"], theme)
            print("[i] 配色取自主题：{}  primary={}  accent={}{}".format(
                theme["id"], "#%02X%02X%02X" % theme["primary"],
                "#%02X%02X%02X" % theme["accent"],
                "" if theme["accent_own"] else "（该主题未登记点睛色，回退主色）"))
            if args.only in ("all", "cover"):
                print("[i] 封面皮肤：竖条 {}px  圆角 {}  底纹 {}{}{}".format(
                    skin["rail_w"], skin["radius"], skin["paper"],
                    "  衬线标题" if skin["serif"] else "",
                    "  黑硬边" if skin["frame_w"] else ""))

    cov = resolve_cover_texts(cfg, args)

    os.makedirs(args.out, exist_ok=True)
    if args.only in ("all", "cover"):
        make_cover(args.out, cov["brand"], cov["title"], cov["subtitle"], cov["date"],
                   theme, motif=cov["motif"], motif_nodes=int(cov["motif_nodes"]),
                   motif_label=cov["motif_label"], motif_caption=cov["motif_caption"])
    if args.only in ("all", "diagram"):
        make_flow(args.out, theme)


if __name__ == "__main__":
    main()
