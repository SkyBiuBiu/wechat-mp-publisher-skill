#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推文封面的**版式规格**与**主题质感皮肤**（单一来源）。

**为什么要有这个文件**
--------------------
封面原先的几何全写死在 `make_assets.make_cover()` 里：画布 `900*S, 383*S`、
竖条 `7*S`、品牌行 `(56*S,48*S)`、标题两套基线 `126*S / (96+i*64)*S`、
分隔线 `(57*S,236*S)-(151*S,236*S)`、环形意象圆心 `762,197` 半径 `90`……
"风格统一"靠的是这段代码恰好只有一份，而不是一份**写下来的规格**。
后果有两个：

  1. 想调一处（比如分隔线太短、环太淡）要改绘制逻辑，改多了就慢慢漂开；
  2. 没有地方能回答"这套封面到底规定了什么"，自检也无从断言。

所以几何收进 `SPEC`，绘制方只负责"按规格画"。**比例 900:383（2.35:1）是
微信列表页裁切的硬约束**（`preflight.py` 的 WX108 会校验），动几何时别碰它。

**皮肤（skin）是什么**
--------------------
同一套几何下，"主题气质"由一组质感参数决定，而不是各写一套版式：
底色倾向、竖条宽度与颜色、外框描边（票据的黑硬边）、圆角倍率、
底纹（票据的撕票虚线、禅意的极细线）、字型（禅意用衬线）。

这一层是**为"同色主题"准备的**：摸鱼绿与摸鱼票据风的主色同为 `#059669`，
留白禅意与石墨极简都偏无彩 —— 光靠主色分不开。有了皮肤之后，票据是
"米黄纸底 + 2px 黑硬边 + 12px 黑竖条 + 撕票虚线 + 直角"，摸鱼绿是
"近白底 + 8px 绿竖条 + 大圆角"，**在不改主题库任何色值的前提下**一眼可分。

未登记皮肤的主题走 `skin_of()` 的自动推导（按主色彩度判断"是否近无彩"），
所以新增主题不会重蹈"封面整张没有颜色"的覆辙。

零第三方依赖（纯数据 + 一个推导函数）。
"""

# --------------------------------------------------------------- 版式规格
# 坐标与字号都是 1x 设计稿单位，绘制时统一乘 SPEC["canvas"]["scale"]。
# 改这里之前先看 preflight.py 的 COVER_RATIO —— 比例是红线。
SPEC = {
    # 画布：900*2 x 383*2 = 1800x766，比例 2.35:1（微信列表页按此裁切）
    "canvas":   {"w": 900, "h": 383, "scale": 2},

    # 左侧主色竖条：整条贯穿上下，是封面上最"重"的一块主题色
    "rail":     {"x": 0, "w": 7},

    # 品牌行（署名 / 栏目名）：左侧一个点睛色小方块 + 文字
    "brand":    {"x": 56, "y": 48, "size": 19, "dot": 8, "dot_gap": 10},

    # 主标题：一行时不缩字号、基线较低；两行时缩一档、整体上移，避免压到分隔线
    "title":    {"x": 56, "one_y": 126, "one_size": 56,
                 "two_y": 96, "two_size": 50, "leading": 64,
                 "max_w": 788, "soft_w": 520, "max_lines": 2},

    # 分隔线（点缀在副标题上方）：用点睛色，够长才有"栏目感"
    "rule":     {"x": 57, "y": 236, "w": 140, "thick": 3},

    "subtitle": {"x": 56, "y": 256, "size": 21},
    "date":     {"x": 56, "y": 306, "size": 17},

    # 右下角那一抹极淡的主色块（杂志感的层次）：相对画布右下角的偏移与尺寸
    # 右边/下边刻意画到画布外，形成"色块从角落漫进来"的效果
    "wash":     {"dx": -300, "dy": -300, "dw": 380, "dh": 380,
                 "alpha": 34, "radius": 60},

    # 环形意象（讲循环/分步的文章用）：圆心落在可见色块区（x>600）的中心
    "ring":     {"cx": 762, "cy": 197, "r": 90,
                 "rail_alpha": 92, "node_alpha": 132,
                 "node_first_r": 7, "node_r": 5.5, "arrow_alpha": 135,
                 "label_size": 19, "caption_size": 12,
                 "label_dy": -9, "caption_dy": 14},
}

# 主题中文名（封面墙的标注用；中文名的权威来源仍是 references/theme-index.md）
THEME_NAMES = {
    "moyu-green": "摸鱼绿",
    "red-white": "红白色系",
    "graphite-minimal": "石墨极简风",
    "zen-whitespace": "留白禅意风",
    "moyu-ticket": "摸鱼票据风",
    "olive-journal": "橄榄手记",
}

# --------------------------------------------------------------- 主题皮肤
# 字段说明：
#   bg          覆盖底色；None = 用主题的 light（极浅底色）
#   rail_w      左侧竖条宽度；None = 用 SPEC.rail.w
#   rail_color  None = 用点睛色（accent）；给了 hex 就用它
#   frame_w     外框描边宽度，0 = 无（票据的"黑硬边"就靠它）
#   radius      右下色块圆角倍率；0 = 直角
#   wash_alpha  右下色块的透明度；None = 用 SPEC.wash.alpha（越高主色越明显）
#   paper       底纹：none / dotted（撕票虚线）/ hairline（一条极细底线）
#   paper_color 底纹颜色；None = 用主题 tint 或细线不足时留空
#   serif       标题用衬线字体（禅意）
#   rule_w      分隔线长度；None = 用 SPEC.rule.w
#   ring_dim    环形意象整体调淡（禅意要克制）
#
# 设计意图（每套都对着一个具体的"辨识度问题"）：
#   moyu-green       基准；绿竖条 + 大圆角 + 极淡绿底块
#   red-white        正红竖条 + 中圆角；底色本来就是极淡红
#   graphite-minimal 5px 深灰竖条（不抢）、小圆角、无底纹；橙色只出现在
#                    环/品牌方块/分隔线共 3 处，正好是它"全篇 ≤3 处橙"的配额
#   zen-whitespace   3px 墨绿竖条 + 直角 + 一条极细底线 + 衬线标题 + 纯白底；
#                    与石墨极简的差别全在"留白与线条"，不在颜色
#   moyu-ticket      12px 黑竖条 + 米黄纸底 + 2px 黑硬边 + 撕票虚线 + 直角；
#                    主色绿退为环与色块的点缀，与摸鱼绿彻底分开
#   olive-journal    橙竖条 + 橙环 + 米白底 + 小圆角；墨黑主色只管文字，
#                    色彩身份交给它登记了却一直没上场的强调橙
THEME_SKINS = {
    "moyu-green": {
        "rail_w": 8, "radius": 60, "wash_alpha": 34,
    },
    "red-white": {
        "rail_w": 8, "radius": 40, "wash_alpha": 34,
    },
    "graphite-minimal": {
        "rail_w": 5, "rail_color": "primary", "radius": 24, "wash_alpha": 30,
    },
    "zen-whitespace": {
        # 底色是纯白（主题速查表的「底色」），色块透明度太低会看成"一块歪着的白"，
        # 26 刚好是"淡墨绿块"而不是"白块"，仍然是六套里最克制的
        "rail_w": 3, "radius": 0, "wash_alpha": 26, "ring_dim": 0.62,
        "paper": "hairline", "serif": True,
    },
    "moyu-ticket": {
        "rail_w": 12, "rail_color": "#1a1a1a", "bg": "#fffef8",
        "frame_w": 2, "frame_color": "#1a1a1a", "radius": 0, "wash_alpha": 30,
        "paper": "dotted", "paper_color": "#A7F3D0",
    },
    "olive-journal": {
        "rail_w": 8, "radius": 6, "wash_alpha": 30,
    },
}

# 未登记皮肤的主题（含用户自己新增、还没进 THEME_SKINS 的）：按主色彩度推导
DEFAULT_SKIN = {
    "rail_w": 8, "radius": 40, "wash_alpha": 34,
}

# 判"近无彩"的彩度阈值（theme_vars.chroma：max-min 通道差 / 255）
#   墨黑 #1e1f23 → 0.020、石墨灰 #52525B → 0.035、墨绿 #4A5D52 → 0.075 都落在这里面；
#   正红 0.71、emerald 0.57 远高于它。
LOW_CHROMA = 0.12


def skin_of(theme_id, theme=None):
    """取某主题的封面皮肤。未登记的主题按主色彩度自动推导。

    `theme` 传 theme_vars.asset_theme() 的结果（可选）。近无彩主题
    （主色是墨黑/石墨灰）必须有点睛色来承担色彩身份，否则封面会整张灰掉 ——
    这正是橄榄手记长期"灰白封面"的成因，所以这里把它变成自动规则：
    近无彩 → 竖条用点睛色、色块透明度拉高。
    """
    skin = dict(DEFAULT_SKIN)
    skin.update({"bg": None, "rail_color": None, "frame_w": 0, "frame_color": "#1a1a1a",
                 "wash_alpha": None, "paper": "none", "paper_color": None,
                 "serif": False, "rule_w": None, "ring_dim": 1.0, "derived": False})
    if theme_id in THEME_SKINS:
        skin.update(THEME_SKINS[theme_id])
        return skin

    # 未登记：按主色彩度推导（没有 theme 就按"有彩"处理，保守不改变观感）
    skin["derived"] = True
    if theme and theme.get("primary") is not None:
        import theme_vars
        if theme_vars.chroma("#%02X%02X%02X" % tuple(theme["primary"])) < LOW_CHROMA:
            skin["rail_color"] = "accent"      # 点睛色上场，别让封面没有颜色
            skin["wash_alpha"] = 42
            skin["radius"] = 24
    return skin


# --------------------------------------------------------------- 规格自检
def spec_problems():
    """返回规格里的自相矛盾项（空列表 = 没问题）。供 validate_skill.py 调用。

    只查"能自动判定的硬事实"：元素有没有出画布、比例对不对。审美判断不在这里。
    """
    c = SPEC["canvas"]
    W, H = c["w"], c["h"]
    bad = []

    if abs(float(W) / H - 2.35) > 0.02:
        bad.append("画布比例 {:.3f}:1 偏离 2.35:1（微信列表页按此裁切，见 preflight WX108）"
                   .format(float(W) / H))

    def inside(name, x, y, w=0, h=0):
        if x < 0 or y < 0 or x + w > W or y + h > H:
            bad.append("{} 超出画布：x={} y={} w={} h={}（画布 {}x{}）"
                       .format(name, x, y, w, h, W, H))

    r = SPEC["rail"]
    inside("左侧竖条", r["x"], 0, r["w"], H)
    # 竖条宽到压住文字列就不是"竖条"了：文字从 brand.x 起，中间要留出气口
    if r["w"] >= SPEC["brand"]["x"] - 10:
        bad.append("左侧竖条宽 {} 会压到文字列（文字从 x={} 起）"
                   .format(r["w"], SPEC["brand"]["x"]))
    b = SPEC["brand"]
    inside("品牌行", b["x"], b["y"], 0, b["size"])
    t = SPEC["title"]
    inside("主标题（单行）", t["x"], t["one_y"], 0, t["one_size"])
    inside("主标题（双行末行）",
           t["x"], t["two_y"] + (t["max_lines"] - 1) * t["leading"], 0, t["two_size"])
    if t["x"] + t["max_w"] > W:
        bad.append("主标题折行硬上限 {} + x {} 超出画布宽 {}".format(t["max_w"], t["x"], W))
    ru = SPEC["rule"]
    inside("分隔线", ru["x"], ru["y"], ru["w"], ru["thick"])
    for key in ("subtitle", "date"):
        e = SPEC[key]
        inside(key, e["x"], e["y"], 0, e["size"])
    if SPEC["subtitle"]["y"] < SPEC["rule"]["y"]:
        bad.append("副标题基线在分隔线上方，视觉顺序反了")
    if SPEC["date"]["y"] < SPEC["subtitle"]["y"]:
        bad.append("日期基线在副标题上方，视觉顺序反了")

    ri = SPEC["ring"]
    # 环形意象要落进右下色块的可见区域（x > 600 那块），且不许压到左侧文字列
    if ri["cx"] - ri["r"] < t["x"] + 300:
        bad.append("环形意象左缘 {} 侵入了文字区域".format(ri["cx"] - ri["r"]))
    if ri["cx"] + ri["r"] > W:
        bad.append("环形意象右缘 {} 超出画布".format(ri["cx"] + ri["r"]))
    if ri["cy"] + ri["r"] > H or ri["cy"] - ri["r"] < 0:
        bad.append("环形意象纵向超出画布")

    for tid, sk in THEME_SKINS.items():
        if sk.get("rail_w", SPEC["rail"]["w"]) > 30:
            bad.append("{} 的竖条宽度 {} 过大，会盖住文字列".format(tid, sk["rail_w"]))
        if sk.get("frame_w", 0) and not sk.get("frame_color"):
            bad.append("{} 配了描边宽度但没给描边色".format(tid))
    return bad


if __name__ == "__main__":
    import sys
    probs = spec_problems()
    if probs:
        for p in probs:
            print("[x] " + p)
        sys.exit(1)
    print("[OK] 封面规格自检通过（画布 {}x{} @{}x，六主题皮肤齐全）".format(
        SPEC["canvas"]["w"], SPEC["canvas"]["h"], SPEC["canvas"]["scale"]))
