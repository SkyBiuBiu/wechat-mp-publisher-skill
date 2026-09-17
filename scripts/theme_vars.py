#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主题库「设计变量速查表」的唯一解析入口。

**为什么要有这个文件**
--------------------
`render_mermaid.py`（插图）、`make_assets.py`（封面）、`highlight_code.py`（代码块）
原先是各写一份正则去读主题变量表。问题不在"写了几份"，而在**三份的标签清单
各不相同、且都读不出某些主题的真实颜色**，而且全都静默退回兜底色：

  实测 `references/theme-olive-journal.md` 的变量表写的是「主题墨色」而不是
  「主色 / 主色调」——
    · 封面侧：清单里其实有「主题墨色」，但兜底用的 avoid 词表含「深」，
      而该标签带括号说明「（强调/CTA/深底）」，于是被自己排掉 → 退回深色版式；
    · 插图侧：清单里没有「主题墨色」→ 退回内置兜底色，橄榄手记的插图
      长期用着**摸鱼绿的绿**。
  另一例：`theme-moyu-ticket.md` 的次要文字是 **3 位十六进制 `#888`**，
  两处正则都只认 6 位 → 取不到 → 又退回兜底灰，票据风少了它自己的灰。

所以这里统一三件事：
  1. 变量表的**解析**（取表、剥掉标签里的括号说明、支持 3/6 位十六进制）；
  2. **匹配规则**（先按归一化标签精确匹配，再前缀匹配并用 avoid 词表排除派生标签）；
  3. **缺失诊断**（`missing` 字段），让调用方明说"哪套主题的哪个变量没读到"，
     而不是悄悄用兜底色 —— 静默兜底正是上面两个 bug 藏了这么久的原因。

字段映射**按消费者分别声明**（`SCHEMAS`）：封面拿「次要文字」做副标题、
插图拿「辅助文字」做连线色，两者语义本就不同，硬统一会改坏既有配色。

零第三方依赖。改这一个文件，三个脚本同时生效。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFS = os.path.join(ROOT, "references")

# --------------------------------------------------------------- 版式常量
# 不是主题变量，但插图与代码块两个脚本都要用同一个数，所以放这里，避免各写一份
# 再慢慢漂开（本文件存在的原因就是这个）。
#
# 微信图文正文在**手机上**的内容区宽度（CSS px）。取最窄的常见机型当基准：
#   360dp Android：360 − 两侧留白 16×2 = 328
#   375pt iPhone ：375 − 两侧留白 16×2 = 343
# 取 328 是刻意保守 —— 判断"放不放得下"时宁可多提示一次，也不要漏。
#
# 别拿 677 来算这个：那是**桌面版网页**的 max-width。手机上正文只有 328 上下，
# 于是"按 677 算刚好放得下"的一段代码，在手机上会折成两行；
# 同理插图的"正文里字号"按 677 估会高估近一倍（详见 render_mermaid.apparent_pt）。
MOBILE_CONTENT_W = 328

# 剥掉「主色（石墨灰）」这类括号说明，只留标签主体
_PAREN_RE = re.compile(r"[(（\[【].*?[)）\]】]")
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")

# 消费者 → 字段 → (可接受标签[按优先级], 前缀匹配时要排除的词)
#
# 纪律：**只增不删**。每张表都是对应脚本原清单的超集（原顺序原样保留，
# 新标签追加在末尾）。删标签会让某套主题从"取到自己的色"退化成"取兜底色"，
# 且不报错 —— 实测踩过：漏掉「米黄纸感背景」，摸鱼票据的暖纸底会被换成中性灰。
SCHEMAS = {
    # 封面（make_assets.py）：副标题要「次要文字」档，日期要更浅的「辅助文字」档
    "cover": {
        "primary": (["主色调", "主色", "主题墨色", "主题色", "主颜色"],
                    ("深", "浅", "背景", "极")),
        "title":   (["标题色"], ()),
        "body":    (["次要文字", "次要文字色", "正文色", "正文", "弱化文字"], ()),
        "aux":     (["辅助文字", "辅助文字色", "弱化文字", "注释/标签",
                     "标签文字色", "标签色"], ()),
        "light":   (["极浅灰", "极浅灰底", "米白背景", "底色", "纯白底",
                     "浅灰背景", "米黄纸感背景", "主色调背景"], ("主色调",)),
    },
    # 插图（render_mermaid.py）：节点填充 / 线条 / 文字
    "diagram": {
        "primary":  (["主色调", "主色", "主颜色", "主题墨色", "主题色"],
                     ("深", "浅", "背景", "极")),
        "title":    (["标题色", "大标题"], ()),
        "body":     (["正文色", "次要文字色", "次要文字"], ()),
        "aux":      (["辅助文字", "注释/标签", "次要文字",
                      "辅助文字色", "次要文字色", "弱化文字", "标签文字色"], ()),
        "light":    (["极浅灰", "浅灰背景", "极浅灰底", "米白背景", "底色",
                      "纯白底", "米黄纸感背景", "主色调背景"], ()),
        "tint":     (["浅绿背景", "浅底", "浅色背景", "标签浅底", "标签底色",
                      "浅橄榄灰背景", "极浅灰底", "浅灰背景",
                      "主色调极浅"], ()),
    },
    # 代码块（highlight_code.py）：只需要主色，其余由主色推导
    #
    # accent 是「主色其实是墨黑/灰」时的备用色相来源：橄榄手记的主色是
    # 主题墨色 #1e1f23、石墨极简是 #52525B，两者都接近无彩色，色相是噪声，
    # 硬拿它推色只会得到一片灰蓝。而这两套主题各自都登记了点睛用的强调色
    # （#ed7b2f / #F97316），那才是它们的色彩身份所在。
    "code": {
        "primary": (["主色调", "主色", "主题墨色", "主题色", "主颜色", "强调色"],
                    ("深", "浅", "背景", "极")),
        "accent":  (["强调橙", "强调色", "点睛色", "下划线标记色", "荧光笔色"],
                    ("深", "浅", "背景", "底")),
    },
}


def norm_label(label):
    """把标签归一化：去括号说明、去反引号与空白。"""
    return _PAREN_RE.sub("", label).strip().strip("`").strip()


def read_vars(theme_id, refs_dir=None):
    """读主题库的变量表，返回 [(原始标签, 归一化标签, 色值)]，保持文件顺序。

    找不到主题库或没有变量表时返回 None（调用方自行决定兜底还是报错）。
    """
    if not theme_id:
        return None
    path = os.path.join(refs_dir or REFS, "theme-{}.md".format(theme_id))
    if not os.path.isfile(path):
        return None
    text = io.open(path, encoding="utf-8").read()
    m = re.search(r"##\s*设计变量速查表\s*```(.*?)```", text, re.S)
    block = m.group(1) if m else text

    pairs = []
    for line in block.splitlines():
        line = line.strip()
        if "：" not in line and ":" not in line:
            continue
        label, val = re.split(r"[：:]", line, maxsplit=1)
        hexes = _HEX_RE.findall(val)
        if hexes:
            pairs.append((label.strip(), norm_label(label), hexes[0]))
    return pairs


def pick(pairs, wanted, avoid=()):
    """先按归一化标签精确匹配（按 wanted 顺序），再前缀匹配（排掉 avoid 词）。"""
    for want in wanted:
        for _raw, norm, val in pairs:
            if norm == want:
                return val
    for want in wanted:
        for _raw, norm, val in pairs:
            if norm.startswith(want) and not any(a in norm for a in avoid):
                return val
    return None


def tokens(theme_id, schema="diagram"):
    """按指定消费者的字段表解析主题色值。

    返回 dict：各字段的色值（**取不到就是 None，不在这里兜底** —— 三个脚本的
    兜底色本来就不一样，统一兜底等于替它们做错决定），外加
      pairs   原始变量对（None 表示主题库缺失 / 没有变量表）
      found   命中的字段
      missing 未命中的字段（调用方应据此给出提示，不要静默兜底）
    """
    fields = SCHEMAS[schema]
    pairs = read_vars(theme_id)
    res = {"id": theme_id, "schema": schema, "pairs": pairs,
           "found": [], "missing": []}
    for name, (wanted, avoid) in fields.items():
        val = pick(pairs, wanted, avoid) if pairs else None
        res[name] = val
        (res["found"] if val else res["missing"]).append(name)
    res["missing"].sort()
    return res


# ------------------------------------------------------------------ 颜色工具
def rgb(h):
    """#RGB / #RRGGBB → (r, g, b)"""
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hex_of(triple):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in triple)


def rgb2hsl(triple):
    r, g, b = [v / 255.0 for v in triple]
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        hue = (g - b) / d + (6.0 if g < b else 0.0)
    elif mx == g:
        hue = (b - r) / d + 2.0
    else:
        hue = (r - g) / d + 4.0
    return hue * 60.0, s, l


def hsl2hex(hue, s, l):
    hue = (hue % 360.0) / 60.0
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    c = (1.0 - abs(2.0 * l - 1.0)) * s
    x = c * (1.0 - abs(hue % 2 - 1.0))
    m = l - c / 2.0
    seg = int(hue) % 6
    part = [(c, x, 0.0), (x, c, 0.0), (0.0, c, x),
            (0.0, x, c), (x, 0.0, c), (c, 0.0, x)][seg]
    return hex_of([(v + m) * 255.0 for v in part])


def primary(theme_id):
    """主色（封面/插图/代码块都要用）。取不到返回 None。"""
    return tokens(theme_id, "code")["primary"]


def chroma(color):
    """颜色的**绝对**彩度：max-min 通道差，0~255 归一。

    用它判断"这个色的色相是否可信"，比 HSL 饱和度稳：`#1e1f23`（橄榄手记的
    墨色）HSL 饱和度有 0.077，看数字像"有一点彩"，实际通道差只有 5/255 ——
    那点色相纯属舍入噪声，拿它推色会得到一片和主题无关的灰蓝。
    HSL 饱和度会低估这类低明度深色，通道差不会。
    """
    r, g, b = rgb(color)
    return (max(r, g, b) - min(r, g, b)) / 255.0


def hue_of(color):
    """颜色的色相（0~360°）。"""
    return rgb2hsl(rgb(color))[0]


def asset_theme(theme_id):
    """make_assets.py 需要的形式：色值转成 rgb 三元组。

    主色与标题色是封面排版的必需项，二者任一取不到就返回 None，
    让调用方退回内置深色版式（这是既有契约，别改成静默兜底）。
    """
    t = tokens(theme_id, "cover")
    if t["pairs"] is None or not (t["primary"] and t["title"]):
        return None
    return {
        "id": theme_id,
        "primary": rgb(t["primary"]),
        "title": rgb(t["title"]),
        "body": rgb(t["body"] or t["title"]),
        "aux": rgb(t["aux"] or t["body"] or t["title"]),
        "light": rgb(t["light"] or "#FFFFFF"),
        "is_light": True,
        "missing": t["missing"],
    }
