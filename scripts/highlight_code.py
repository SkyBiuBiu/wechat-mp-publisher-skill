#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把代码围栏转成「按语言着色」的公众号代码块组件（通用库 1a 深色 / 1b 浅色）。

为什么单独做一个脚本
--------------------
手写高亮要逐 token 编色值，既费 token 又必然出现「这套主题用这个绿、下套主题
忘了改」的漂移。这里把**配色从当前主题的「设计变量速查表」推导**出来，
因此 6 套内置主题与任何自定义主题（theme-generator.md 产出的标准 theme-<id>.md）
都自动适配，不需要为每套主题维护一份高亮配色表。

顺带解决三件手写必然出错的事，三件都真出过：

一、缩进与对齐：行首空格、连续空格必须转成 &nbsp;
------------------------------------------------
默认 `white-space:normal` 会吃掉行首空格、把连续空格压成一个。后果不是"缩进浅了
一点"，而是：4 空格缩进**整层消失**（嵌套结构读不出来）、作者对齐在某一列的行尾
注释**全部挤到代码后面**、多行块注释左右不齐。全角空格　能保住缩进，但它比一个
半角字符宽约 1.67 倍（等宽字体 advance 约 0.6em），**对不齐列**——用来缩进可以，
用来对齐不行。所以这里把行首空格与连续空格转成 `&nbsp;`：宽度与空格完全相同、
且不被 HTML 折叠，对齐原样保住。
（不能改用 `white-space:pre`：源码里的缩进与换行会被原样渲染成大左缩进 + 空行，
理由见 references/common-components.md。）

二、长行横滑，不折行
--------------------
折行会把「# 预算护栏」这类行尾注释甩到下一行开头，读者分不清它属于哪一句，
而且同一段代码在不同手机上折在不同位置、对不齐。所以每行 `<p>` 内联
`white-space:nowrap`，外层 `section` 给 `overflow-x:auto`。内联样式是刻意的：
微信会往页面注入 `white-space:normal`，内联优先级高于它的任何选择器。
顶部栏只在**确实超宽时**才出现「左右滑动 →」提示——手机上横向滚动条是隐藏的，
不提示读者根本不知道能滑。

三、色彩更丰富，但仍是同一套主题
--------------------------------
早期版本把全部 token 压在主色相 ±24° 内、饱和度锁 0.30~0.42，结果整块糊成一个色。
现在换成**以主题色相为起点的色环**：关键词留在主色相本身（保住主题身份），
函数 / 数字 / 字符串 / 内置 / 类型依次取 +35° / +70° / +140° / +195° / +262°。
六个色相同处一个明度带（深色底 L≈0.68~0.78）与一个饱和度带（S≈0.45~0.62）——
**丰富来自色相，秩序来自明度与饱和度**，这是"色彩丰富但不突兀"的可核对定义。
关键词另加粗，让结构在彩色里依然立得住。
要回早期的单色克制版：`--scheme calm`。

主题主色的色相不可信时（墨黑 / 灰，如橄榄手记 #1e1f23、石墨极简 #52525B）
自动改取该主题登记的点睛强调色（#ed7b2f / #F97316）——判据是通道差而非
HSL 饱和度，后者会低估低明度深色。

用法
----
    # 抽取 Markdown 里所有围栏，逐个输出代码块组件
    python highlight_code.py article.md --theme moyu-green

    # 只要 python 的，写到文件
    python highlight_code.py article.md --theme moyu-green --lang python -o code.html

    # 单段代码（文件 / stdin）
    python highlight_code.py --code-file demo.py --lang python --theme moyu-green
    cat demo.sh | python highlight_code.py - --lang bash --theme moyu-green

    # 看配色 / 查语言 / 换回单色版
    python highlight_code.py --show-palette --all-themes
    python highlight_code.py --list-langs
    python highlight_code.py article.md --theme zen-whitespace --scheme calm

零第三方依赖：只用标准库。语言识别是启发式的，目标是「读起来清楚」，
不是完整语法分析器。
"""
import argparse
import io
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFS = os.path.join(ROOT, "references")

import theme_vars          # 同目录；主题变量表的唯一解析入口

# 无主题时的兜底（与 make_assets.py 的内置橙调一致）
FALLBACK_PRIMARY = "#D94F22"

FENCE_RE = re.compile(r"^[ \t]*```[ \t]*([A-Za-z0-9_+-]*)[^\n]*\n(.*?)^[ \t]*```[ \t]*$",
                      re.S | re.M)

# 正文内容区宽度与代码字号。两个数决定「一行能放多少列」，进而决定要不要出
# 横滑提示 —— 改字号就得重算。宽度取手机基准（见 theme_vars.MOBILE_CONTENT_W）：
# 代码块是给手机看的，用桌面版网页的 677 算会得出"75 列也放得下"这种假结论。
CONTENT_W = theme_vars.MOBILE_CONTENT_W
CODE_FONT_PX = 13
BODY_PAD_X = 14
# 等宽字体 advance 约 0.6em（Consolas / SF Mono / Monaco 都在这个量级）
MONO_ADVANCE = 0.6


# ------------------------------------------------------------------ 颜色工具
# 颜色换算与主题解析都复用 theme_vars，本文件不再自带一份 —— 原先那份的标签
# 清单里没有「主题墨色」，橄榄手记这类主题的主色取不到就静默退回内置橙调，
# 代码块于是永远配不出主题色。一套工具一处实现，才有"改一次三个脚本同时生效"。
_rgb = theme_vars.rgb
_hex = theme_vars.hex_of
rgb2hsl = theme_vars.rgb2hsl
hsl2hex = theme_vars.hsl2hex


def theme_primary(theme_id):
    """从主题库的「设计变量速查表」里取主色调。取不到返回 None。"""
    return theme_vars.primary(theme_id)


# ------------------------------------------------------------------ 配色推导
# 主色彩度低于这个值就认为"它其实是黑/灰"，色相不可信，改用 accent 的色相。
# 15/255 ≈ 0.059：实测 #4A5D52（留白禅意的墨绿，差 19）算有色，
# #52525B（石墨灰，差 9）与 #1e1f23（橄榄手记墨色，差 5）算无色。
CHROMA_MIN = 0.059

# 主色不可信、又找不到 accent 时用的中性冷色相（石墨蓝灰那一类）
NEUTRAL_HUE = 210.0

# 各 token 类别的取色参数：色相偏移、(深色底 L, 深色底 S), (浅色底 L, 浅色底 S)
# 色相偏移按「离主色的远近」排序：越靠前的 token 在文章里出现得越多、越该带主题色。
# 明度/饱和度带刻意收窄 —— 这是"丰富但不突兀"的另一半，只放色相变，不放明暗变。
SCHEMES = {
    "rich": {
        "keyword": (0,   (0.74, 0.62), (0.34, 0.78)),
        "func":    (35,  (0.75, 0.55), (0.36, 0.68)),
        "number":  (70,  (0.76, 0.50), (0.38, 0.72)),
        "string":  (140, (0.74, 0.45), (0.34, 0.62)),
        "builtin": (195, (0.76, 0.48), (0.36, 0.64)),
        "type":    (262, (0.76, 0.50), (0.36, 0.60)),
    },
    # 早期版本：全部压在主色相附近、只留一个对比色。给"配色要克制"的温和主题用。
    "calm": {
        "keyword": (0,   (0.74, 0.42), (0.34, 0.55)),
        "func":    (24,  (0.73, 0.40), (0.36, 0.52)),
        "string":  (200, (0.76, 0.36), (0.42, 0.42)),
        "number":  (200, (0.82, 0.30), (0.34, 0.38)),
    },
}

# 加粗的 token：颜色只解决"认得出是哪类"，结构还得靠字重。只给关键词，
# 给多了等于没重点。
BOLD = ("keyword", "type")


def palette(theme_id, style="dark", scheme="rich"):
    """按主题推导一套高亮配色。返回 dict（键即 token 类别）。

    色相来源按可信度挑，全程只用主题**已有**的颜色，不自造：

      1. 主色本身有色（彩度 ≥ CHROMA_MIN）→ 直接用它的色相，
         这是摸鱼绿 / 红白雪 / 摸鱼票据这类"主色即身份"的主题；
      2. 主色是墨黑或灰（橄榄手记 #1e1f23、石墨极简 #52525B）→ 色相是噪声，
         改取主题登记的点睛强调色的色相（#ed7b2f / #F97316）；
      3. 连强调色也没有 → 落到中性冷色相，token 之间靠色相偏移区分。

    第 2 条是"自定义主题也能自动适配"的关键：自定义主题只要在变量表里
    登记了主色或强调色，代码块就自动带上它的色彩身份。
    """
    t = theme_vars.tokens(theme_id, "code")
    primary = t["primary"] or FALLBACK_PRIMARY
    source = "主色"

    if t["pairs"] is not None and theme_vars.chroma(primary) < CHROMA_MIN:
        accent = t["accent"]
        if accent and theme_vars.chroma(accent) >= CHROMA_MIN:
            source = "强调色 {}".format(accent)
            primary = accent
        else:
            return _palette_from(theme_id, NEUTRAL_HUE, style, primary,
                                 "中性兜底色相（主题里没有可用的彩色）", True, scheme)

    # 色相一律取自主题已有颜色，饱和度与明度由本脚本统一施加 ——
    # 所以像 #4A5D52（留白禅意的墨绿，彩度仅 0.075）这样的低饱和主题，
    # 也能得到"明确是墨绿、但不刺眼"的 token，而不是被误判成灰色丢掉色相。
    return _palette_from(theme_id, theme_vars.hue_of(primary), style, primary,
                         source, False, scheme)


def _palette_from(theme_id, h, style, primary, source, neutral_theme, scheme):
    """给定色相，按色环展开成整套 token 配色。

    改这里之前先读模块头部「三、色彩更丰富，但仍是同一套主题」：
    丰富只靠色相偏移，明度与饱和度带必须保持收窄，否则就会回到"满屏彩点"。
    """
    steps = SCHEMES.get(scheme) or SCHEMES["rich"]
    idx = 0 if style == "light" else 1
    pal = {
        "theme": theme_id or "(内置橙调)",
        "primary": primary,
        "source": source,
        "scheme": scheme if scheme in SCHEMES else "rich",
        "neutral_theme": neutral_theme,
    }
    for kind, spec in steps.items():
        off, dark_ls, light_ls = spec
        l, s = (light_ls if style == "light" else dark_ls)
        pal[kind] = hsl2hex(h + off, s, l)

    if style == "light":
        pal.update({
            "bg": "#F6F8FA",
            "header_bg": None,
            "header_fg": "#9CA3AF",
            "border": _hex(_rgb(primary)),
            "base": "#24292F",
            "comment": "#6E7781",
        })
    else:
        pal.update({
            # 顶栏底色往主题色相偏一点（低饱和深色），让整块有个主题回声，
            # 而不是所有主题共用一个 #0F172A。
            "bg": "#1E293B",
            "header_bg": hsl2hex(h, 0.30, 0.13) if not neutral_theme else "#0F172A",
            "header_fg": "#8496AE",
            "border": _hex(_rgb(primary)),
            "base": "#E2E8F0",
            "comment": "#8296B0",
        })
    return pal


# ------------------------------------------------------------------ 语言档案
# 每个档案给出 token 的匹配式；命中即不再往下试，顺序见 ORDER。
# 运算符与标点故意不列（不着色）——"丰富"靠 token 分类，不靠给标点上色。
# 未列入的类别写 (?!) 表示永不匹配。
_NEVER = r"(?!)"

_SH_COMMANDS = ("if|then|elif|else|fi|for|do|done|while|until|case|esac|function|"
                "in|return|export|local|readonly|source|set|unset|shift|trap|eval|"
                "sudo|apt|apt-get|yum|dnf|brew|systemctl|service|docker|kubectl|"
                "git|curl|wget|ssh|scp|rsync|tar|zip|unzip|make|npm|npx|pnpm|yarn|"
                "node|python|python3|pip|pip3|poetry|uv|go|cargo|mvn|gradle|java|"
                "echo|printf|cat|grep|egrep|sed|awk|find|xargs|sort|uniq|head|tail|"
                "wc|cut|tr|tee|less|more|touch|mkdir|rmdir|rm|cp|mv|ln|chmod|chown|"
                "ls|pwd|cd|exit|kill|ps|top|df|du|free|whoami|env|which|test|open|"
                "jq|yq|openssl|date|sleep|watch|time|alias")

# 顺序 = 优先级。decorator 在 string 之前（@a.b 不该被当字符串），
# builtin 在 type 之前（print 是内置、MyClass 是类，两者语义不同、配色也该不同）。
ORDER = ("comment", "decorator", "string", "keyword",
         "builtin", "type", "number", "func")

PROFILES = {
    "python": {
        "comment": r"#[^\n]*",
        "decorator": r"@[\w.]+",
        "string": r'"""(?:[^"]|"(?!""))*"""|\'\'\'(?:[^\']|\'(?!\'\'))*\'\'\'|'
                  r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        "keyword": r"\b(?:def|class|return|if|elif|else|for|while|in|not|and|or|"
                   r"import|from|as|with|try|except|finally|raise|yield|lambda|"
                   r"pass|break|continue|global|nonlocal|assert|del|is|None|True|"
                   r"False|self|cls|async|await|match|case)\b",
        # 小写内置：函数名/内置类型名。与"大写开头 = 类名"分开，语义不同配色才不同。
        "builtin": r"\b(?:print|len|range|enumerate|zip|map|filter|sum|min|max|"
                   r"abs|round|sorted|reversed|open|isinstance|issubclass|super|"
                   r"type|getattr|setattr|hasattr|repr|format|id|hash|iter|next|"
                   r"any|all|input|vars|dir|callable|divmod|pow)\b",
        "type": r"\b[A-Z][A-Za-z0-9_]*\b",
        "number": r"\b(?:0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][-+]?\d+)?)\b",
        "func": r"\b[A-Za-z_]\w*(?=\s*\()",
    },
    "bash": {
        "comment": r"#[^\n]*",
        "decorator": _NEVER,
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'',
        # 变量优先于命令名：$PATH 与 PATH 是两回事
        "builtin": r"\$\{?[A-Za-z_][\w]*\}?|\$\{[^}]*\}",
        "keyword": r"\b(?:{})\b".format(_SH_COMMANDS),
        "type": _NEVER,
        "number": r"(?<=\s)-{1,2}[A-Za-z][\w-]*|\b\d+(?:\.\d+)?\b",
        "func": r"(?<![\w.-])[A-Za-z_][\w.-]*(?=\s)",
    },
    "json": {
        "comment": r"//[^\n]*",
        "decorator": _NEVER,
        "string": r'"(?:\\.|[^"\\])*"',
        "keyword": _NEVER,
        "builtin": r"\b(?:true|false|null)\b",
        "type": _NEVER,
        "number": r"-?\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b",
        "func": _NEVER,
    },
    "javascript": {
        "comment": r"//[^\n]*|/\*.*?\*/",
        "decorator": _NEVER,
        "string": r"`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
        "keyword": r"\b(?:const|let|var|function|return|if|else|for|while|do|switch|"
                   r"case|break|continue|new|class|extends|super|this|import|export|"
                   r"from|default|async|await|try|catch|finally|throw|typeof|"
                   r"instanceof|in|of|delete|void|yield|static|get|set|"
                   r"interface|type|enum|implements|public|private|readonly|as|"
                   r"null|undefined|true|false|NaN)\b",
        # 小写全局函数 → builtin；大写构造器/全局对象 → type（与类名同色）
        "builtin": r"\b(?:parseInt|parseFloat|isNaN|isFinite|setTimeout|setInterval|"
                   r"clearTimeout|clearInterval|fetch|alert|confirm|prompt|require|"
                   r"encodeURIComponent|decodeURIComponent|structuredClone)\b",
        "type": r"\b(?:console|window|document|globalThis|process|module|exports|"
                r"Math|JSON|Object|Array|String|Number|Boolean|Promise|Map|Set|WeakMap|"
                r"WeakSet|Date|RegExp|Error|TypeError|RangeError|Symbol|Proxy|BigInt|"
                r"Reflect|Intl)\b|\b[A-Z][A-Za-z0-9_$]*\b",
        "number": r"\b(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?)\b",
        "func": r"\b[A-Za-z_$]\w*(?=\s*\()",
    },
    "yaml": {
        "comment": r"#[^\n]*",
        "decorator": _NEVER,
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'',
        "keyword": r"^[ \t-]*[\w.$/-]+(?=\s*:)",
        "builtin": r"\b(?:true|false|null|yes|no|on|off)\b",
        "type": _NEVER,
        "number": r"\b\d+(?:\.\d+)?\b",
        "func": _NEVER,
    },
    "sql": {
        "comment": r"--[^\n]*|/\*.*?\*/",
        "decorator": _NEVER,
        "string": r"'(?:''|[^'])*'",
        # 聚合/工具函数（COUNT/SUM/COALESCE…）不再列在这里 —— 让它们落到 func，
        # 与其它语言的"函数名一个色"保持一致。
        "keyword": r"\b(?:SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|"
                   r"GROUP|ORDER|BY|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|"
                   r"SET|DELETE|CREATE|TABLE|INDEX|VIEW|DROP|ALTER|ADD|COLUMN|AS|"
                   r"AND|OR|NOT|NULL|IS|IN|LIKE|BETWEEN|DISTINCT|CASE|WHEN|THEN|"
                   r"ELSE|END|UNION|ALL|EXISTS|PRIMARY|KEY|FOREIGN|REFERENCES|"
                   r"CONSTRAINT|DEFAULT|ASC|DESC|WITH|WINDOW|OVER|PARTITION)\b",
        "builtin": r"\b(?:COALESCE|NULLIF|GREATEST|LEAST|NOW|CURRENT_TIMESTAMP|"
                   r"INTERVAL)\b",
        "type": r"\b(?:INT|INTEGER|BIGINT|SMALLINT|SERIAL|BIGSERIAL|VARCHAR|CHAR|"
                r"TEXT|BOOLEAN|BOOL|DATE|TIME|TIMESTAMP|TIMESTAMPTZ|NUMERIC|DECIMAL|"
                r"REAL|DOUBLE|FLOAT|JSON|JSONB|UUID|BYTEA|BLOB)\b",
        "number": r"\b\d+(?:\.\d+)?\b",
        "func": r"\b[A-Za-z_]\w*(?=\s*\()",
    },
    "dockerfile": {
        "comment": r"#[^\n]*",
        "decorator": _NEVER,
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'',
        "keyword": r"^\s*(?:FROM|RUN|CMD|LABEL|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|"
                   r"VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL|"
                   r"AS)\b",
        "builtin": r"\b(?:alpine|debian|ubuntu|bookworm|bullseye|slim|latest|"
                   r"python|node|nginx|golang|openjdk|mysql|postgres|redis)\b",
        "type": _NEVER,
        "number": r"\b\d+(?:\.\d+)?\b",
        "func": _NEVER,
    },
    "clike": {   # go / rust / java / c / cpp / php / ruby / kotlin / swift …
        "comment": r"//[^\n]*|/\*.*?\*/|#[^\n]*",
        "decorator": r"@[A-Za-z_]\w*",
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'|`[^`]*`',
        "keyword": r"\b(?:func|fn|let|mut|const|var|val|return|if|else|for|while|"
                   r"switch|case|break|continue|new|class|struct|enum|interface|"
                   r"impl|trait|pub|use|mod|package|import|from|in|of|this|self|"
                   r"try|catch|finally|throw|throws|except|raise|defer|go|chan|"
                   r"range|type|map|void|int|float|double|bool|char|string|byte|"
                   r"long|short|unsigned|signed|static|final|public|private|"
                   r"protected|abstract|override|virtual|template|namespace|"
                   r"include|define|true|false|null|nil|None|undefined)\b",
        # 小写内置函数 / 常用包名（不含大写开头 —— 那是类名，归 type）
        "builtin": r"\b(?:printf|sprintf|snprintf|malloc|calloc|realloc|free|"
                   r"sizeof|len|cap|append|make|panic|recover|println|print|"
                   r"println|fmt|os|strconv|errors|strings|time|sync|io|log|"
                   r"require|assert|expect|puts|each|puts)\b",
        "type": r"\b[A-Z][A-Za-z0-9_]*\b",
        "number": r"\b(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?)\b",
        "func": r"\b[A-Za-z_]\w*(?=\s*\()",
    },
    "plain": {k: _NEVER for k in ORDER},
}

# 语言别名 → 档案名
ALIASES = {
    "py": "python", "python3": "python",
    "sh": "bash", "shell": "bash", "zsh": "bash", "console": "bash",
    "shell-session": "bash", "terminal": "bash", "cmd": "bash", "powershell": "bash",
    "js": "javascript", "jsx": "javascript", "ts": "javascript", "tsx": "javascript",
    "typescript": "javascript", "node": "javascript", "mjs": "javascript",
    "yml": "yaml",
    "docker": "dockerfile", "docker-file": "dockerfile",
    "go": "clike", "golang": "clike", "rust": "clike", "rs": "clike",
    "java": "clike", "c": "clike", "cpp": "clike", "c++": "clike", "cs": "clike",
    "csharp": "clike", "php": "clike", "ruby": "clike", "rb": "clike",
    "kotlin": "clike", "swift": "clike", "scala": "clike", "toml": "plain",
    "text": "plain", "txt": "plain", "log": "plain", "output": "plain",
    "prompt": "plain", "md": "plain", "markdown": "plain", "html": "plain",
    "xml": "plain", "csv": "plain", "env": "plain", "ini": "plain", "conf": "plain",
}


def profile_of(lang):
    key = (lang or "").strip().lower()
    key = ALIASES.get(key, key)
    return PROFILES.get(key, PROFILES["clike"])


def ordered_pattern(prof):
    """把档案拼成一个带命名组的正则，ORDER 即优先级。"""
    parts = [r"(?P<{}>{})".format(k, prof.get(k, _NEVER)) for k in ORDER]
    return re.compile("|".join(parts))


def tokenize_line(line, rx):
    """把一行切成 [(文本, 类别)]，类别 "plain" 表示不着色。"""
    out, pos = [], 0
    for m in rx.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], "plain"))
        out.append((m.group(0), m.lastgroup))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], "plain"))
    return [t for t in out if t[0]]


# ------------------------------------------------------------------ 版式度量
def _cols(line):
    """一行的显示列数：东亚全角字符算 2 列，其余 1 列。"""
    n = 0
    for ch in line.replace("\t", "    "):
        n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n


def max_cols(lines):
    return max((_cols(ln) for ln in lines), default=0)


def fits_cols(content_w=None, font_px=None):
    """正文里一行最多能放多少列（超了就得横滑）。"""
    content_w = content_w or CONTENT_W
    font_px = font_px or CODE_FONT_PX
    return int((content_w - 2 * BODY_PAD_X) / (font_px * MONO_ADVANCE))


# ------------------------------------------------------------------ 组件装配
MONO = "'SF Mono',Consolas,Monaco,monospace"

# 行首空格 / 连续空格：必须转 &nbsp;，否则被 HTML 折叠（见模块头部「一」）。
_LEAD_RE = re.compile(r"^[ \t]+")
_RUN_RE = re.compile(r"[ \t]{2,}")


def esc(s):
    """代码里的 < > & 必须转义，否则会把 HTML 结构冲掉。
    必须在 preserve_spaces 之前跑：否则会把 nbsp 的 & 转成 &amp;nbsp;。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def preserve_spaces(s, at_line_start=False):
    """把会被 HTML 折叠掉的空格转成 &nbsp;（宽度与空格相同、不被折叠）。

    只动"真的会被折叠"的那部分，免得 HTML 无谓膨胀：
      · 行首空格（at_line_start，只有整行的第一段才可能命中）；
      · 连续 2 个以上的空格 —— 作者用它把行尾注释对齐到某一列，
        折叠成一个就全挤到代码后面了。
    单个词间空格保持原样：`white-space:nowrap` 已经保证它不会被用来折行。
    """
    s = s.replace("\t", "    ")
    if at_line_start:
        s = _LEAD_RE.sub(lambda m: "&nbsp;" * len(m.group(0)), s)
    return _RUN_RE.sub(lambda m: "&nbsp;" * len(m.group(0)), s)


def code_line_html(line, rx, pal, nowrap=True):
    style = ("margin:0;font-family:{};font-size:{}px;line-height:1.6;color:{};"
             .format(MONO, pal.get("font_px", CODE_FONT_PX), pal["base"]))
    if nowrap:
        style += "white-space:nowrap;"
    if not line.strip():
        # 空行也要占位，否则段落间距会被压掉
        return ('    <p style="{}"><span leaf="">　</span></p>'.format(style))
    chunks = []
    for i, (text, kind) in enumerate(tokenize_line(line, rx)):
        # 只有整行的第一段才可能是"行首空格"
        body = preserve_spaces(esc(text), at_line_start=(i == 0))
        if kind == "plain" or not pal.get(kind):
            chunks.append('<span leaf="">{}</span>'.format(body))
        else:
            weight = "font-weight:bold;" if kind in BOLD else ""
            chunks.append('<span style="color:{};{}"><span leaf="">{}</span></span>'
                          .format(pal[kind], weight, body))
    return '    <p style="{}">{}</p>'.format(style, "".join(chunks))


def build_block(code, lang, pal, style="dark", wrap=False, hint=True,
                content_w=None, font_px=None):
    """按通用库 1a/1b 的结构装配一个代码块。

    wrap=True  退回折行版（读者不用横滑，但行尾注释会被折到下一行）
    hint=False 关掉「左右滑动」提示
    """
    label = (lang or "").strip() or "text"
    lines = [ln.rstrip() for ln in code.rstrip("\n").split("\n")]
    content_w = content_w or CONTENT_W
    font_px = font_px or CODE_FONT_PX
    pal = dict(pal, font_px=font_px)

    rx = ordered_pattern(profile_of(lang))
    nowrap = not wrap
    body = "\n".join(code_line_html(ln, rx, pal, nowrap) for ln in lines)

    widest = max_cols(lines)
    overflow = nowrap and widest >= fits_cols(content_w, font_px)
    # 外层给 overflow-x:auto，内层每行 nowrap —— 两边都要，缺一边都不滚。
    scroller = "padding:11px 14px;overflow-x:auto;-webkit-overflow-scrolling:touch;"
    if nowrap:
        scroller += "white-space:nowrap;"

    tip = ""
    if overflow and hint:
        # 提示语跟主题库自己的横滑卡组保持一致（「👉 滑动」），
        # 读者在两个地方看到的是同一套说法。
        tip = ('<span style="margin-left:auto;font-size:11px;color:{};'
               'white-space:nowrap;"><span leaf="">👉 左右滑动</span></span>'
               .format(pal["header_fg"]))

    if style == "light":
        head = ('  <section style="padding:7px 14px;border-bottom:1px solid #E5E7EB;">\n'
                '    <span style="font-size:12px;color:{};font-family:Consolas,Monaco,'
                'monospace;letter-spacing:1px;"><span leaf="">{}</span></span>\n'
                '{}  </section>'.format(
                    pal["header_fg"], esc(label),
                    ("    " + tip + "\n") if tip else ""))
        # 浅色版顶栏是块级，要让提示落在右侧得先把它排成一行
        if tip:
            head = ('  <section style="display:flex;align-items:center;padding:7px 14px;'
                    'border-bottom:1px solid #E5E7EB;">\n'
                    '    <span style="font-size:12px;color:{};font-family:Consolas,'
                    'Monaco,monospace;letter-spacing:1px;"><span leaf="">{}</span>'
                    '</span>\n    {}\n  </section>'.format(
                        pal["header_fg"], esc(label), tip))
        return ('<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;'
                'background:{};border:1px solid #E5E7EB;border-left:3px solid {};">\n'
                '{}\n'
                '  <section style="{}">\n{}\n  </section>\n'
                '</section>'.format(pal["bg"], pal["border"], head, scroller, body))

    dots = "".join(
        '    <span style="display:inline-block;width:10px;height:10px;border-radius:'
        '50%;background:{};{}font-size:0;line-height:0;overflow:hidden;">.</span>\n'
        .format(c, "" if i == 2 else "margin-right:7px;")
        for i, c in enumerate(("#FF5F56", "#FFBD2E", "#27C93F")))
    head = ('  <section style="display:flex;align-items:center;padding:9px 14px;'
            'background:{};">\n'
            '{}'
            '    <span style="margin-left:12px;font-size:12px;color:{};font-family:'
            'Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">{}</span>'
            '</span>\n'
            '{}</section>'.format(
                pal["header_bg"], dots, pal["header_fg"], esc(label),
                ("    " + tip + "\n") if tip else ""))
    # 左侧 3px 主题色竖条：和 1b 同一处理，让"这块是哪个主题的代码"一眼可辨
    return ('<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;'
            'background:{};border-left:3px solid {};'
            'box-shadow:0 4px 16px -8px rgba(15,23,42,0.4);">\n'
            '{}\n  <section style="{}">\n{}\n  </section>\n'
            '</section>'.format(pal["bg"], pal["border"], head, scroller, body))


# ------------------------------------------------------------------ 输入解析
def blocks_from_markdown(text, want_lang=None):
    out = []
    for m in FENCE_RE.finditer(text):
        lang, code = m.group(1), m.group(2)
        if (lang or "").lower() in ("mermaid", ""):
            continue
        if want_lang and (lang or "").lower() != want_lang.lower():
            continue
        out.append((lang, code))
    return out


def read_text(path):
    if path in (None, "-"):
        return io.open(sys.stdin.fileno(), encoding="utf-8", errors="replace").read()
    return io.open(path, encoding="utf-8").read()


# ------------------------------------------------------------------ 输出
def show_palette(theme_ids, style, scheme):
    for tid in theme_ids:
        pal = palette(tid, style, scheme)
        print("=" * 66)
        print("主题 {}   色相来源 {}   主色 {}   方案 {}".format(
            pal["theme"], pal["source"], pal["primary"], pal["scheme"]))
        if pal["neutral_theme"]:
            print("  （主色近中性，已改用中性冷色相）")
        toks = [k for k in ORDER if pal.get(k)]
        for k in toks + ["base"]:
            mark = "  *粗" if k in BOLD else ""
            print("  {:<9} {}{}".format(k, pal[k], mark))
        print("  底色      {}   顶栏 {}   竖条 {}".format(
            pal["bg"], pal["header_bg"] or "—", pal["border"]))
        ph, _ps, _pl = rgb2hsl(_rgb(pal["primary"]))
        print("  主色彩度 {:.3f}（阈值 {}）".format(
            theme_vars.chroma(pal["primary"]), CHROMA_MIN))
        # 各 token 相对主色的偏移，一眼看出色环张得开不开、还在不在同一明度带
        offs = []
        for k in toks:
            kh, _ks, kl = rgb2hsl(_rgb(pal[k]))
            offs.append("{} {:+.0f}°/L{:.2f}".format(k, (kh - ph + 180) % 360 - 180, kl))
        print("  " + "  ".join(offs))


def main():
    ap = argparse.ArgumentParser(
        description="把代码围栏转成按语言着色的公众号代码块（零依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="配色由 --theme 指定的主题库推导，6 套内置主题与自定义主题同样适用。")
    ap.add_argument("input", nargs="?", help="Markdown 文件；用 - 读 stdin")
    ap.add_argument("--code-file", help="只处理一段纯代码（不解析围栏）")
    ap.add_argument("--lang", default=None,
                    help="只处理该语言的围栏 / 指定单段代码的语言")
    ap.add_argument("--theme", default=None,
                    help="主题标识（如 moyu-green），配色从该主题库推导")
    ap.add_argument("--style", choices=["dark", "light"], default="dark",
                    help="dark=通用库 1a（默认） / light=通用库 1b")
    ap.add_argument("--scheme", choices=sorted(SCHEMES), default="rich",
                    help="rich=色环配色（默认，色彩丰富） / calm=单色克制版")
    ap.add_argument("--wrap", action="store_true",
                    help="长行折行，不出横向滚动（默认横滑，保住行尾对齐）")
    ap.add_argument("--no-hint", action="store_true",
                    help="关掉超宽时的「左右滑动」提示")
    ap.add_argument("--content-width", type=int, default=None,
                    help="正文内容区宽度 px，默认 {}".format(CONTENT_W)
                         + "（用来判断会不会超宽）")
    ap.add_argument("--code-font-size", type=int, default=None,
                    help="代码字号 px，默认 {}".format(CODE_FONT_PX))
    ap.add_argument("--check-widths", action="store_true",
                    help="只报告每块代码最宽一行多少列、会不会横滑，不出 HTML")
    ap.add_argument("-o", "--out", default=None, help="输出文件，默认 stdout")
    ap.add_argument("--show-palette", action="store_true",
                    help="打印配色表后退出（排查颜色问题用）")
    ap.add_argument("--all-themes", action="store_true",
                    help="配合 --show-palette：列出全部内置主题")
    ap.add_argument("--list-langs", action="store_true", help="列出支持的语言标识")
    args = ap.parse_args()

    if args.list_langs:
        print("语言标识：" + ", ".join(sorted(set(list(PROFILES) + list(ALIASES)))))
        print("其它标识按 C 系语言处理；text / prompt / md 等不着色。")
        return

    if args.show_palette:
        if args.all_themes:
            ids = sorted(set(re.findall(r"theme-([A-Za-z0-9_-]+)\.md",
                                        io.open(os.path.join(REFS, "theme-index.md"),
                                                encoding="utf-8").read()))
                         - {"generator"})
        else:
            ids = [args.theme]
        show_palette(ids, args.style, args.scheme)
        return

    theme = args.theme
    if theme is None:
        # 跟工作目录的 config.json 走，省得两边不一致
        for cand in (os.path.join(os.getcwd(), "config.json"),):
            if os.path.isfile(cand):
                try:
                    theme = (json.load(io.open(cand, encoding="utf-8")) or {}).get("theme")
                except Exception:                    # noqa: BLE001
                    pass
    pal = palette(theme, args.style, args.scheme)
    if theme and not theme_primary(theme):
        print("[!] 读不到主题配色（references/theme-{}.md 缺失或无变量表），"
              "改用内置橙调".format(theme), file=sys.stderr)
    print("[i] 配色取自主题：{}  主色 {}  {} / {}".format(
        pal["theme"], pal["primary"], args.style, pal["scheme"]), file=sys.stderr)

    if args.code_file or args.input == "-" and args.lang:
        src = read_text(args.code_file or "-")
        pairs = [(args.lang or "text", src)]
    else:
        if not args.input:
            ap.error("需要给 Markdown 文件，或用 --code-file / --lang 处理单段代码")
        pairs = blocks_from_markdown(read_text(args.input), args.lang)

    if not pairs:
        print("[!] 没有匹配到代码围栏" +
              ("（--lang {}）".format(args.lang) if args.lang else ""), file=sys.stderr)
        sys.exit(1)

    if args.check_widths:
        cap = fits_cols(args.content_width, args.code_font_size)
        print("正文一行可放 {} 列（内容区 {}px，代码 {}px）".format(
            cap, args.content_width or CONTENT_W,
            args.code_font_size or CODE_FONT_PX))
        for lang, code in pairs:
            lines = [ln.rstrip() for ln in code.rstrip("\n").split("\n")]
            w = max_cols(lines)
            print("  {:<10} 最宽 {} 列  {}".format(
                lang or "text", w,
                "→ 超宽，会横滑（顶部出提示）" if w >= cap else "→ 放得下"))
        return

    chunks = []
    for lang, code in pairs:
        chunks.append("<!-- 代码块：{} → 通用库 {} -->".format(
            (lang or "text"), "1b 浅色" if args.style == "light" else "1a 深色"))
        chunks.append(build_block(code, lang, pal, args.style, wrap=args.wrap,
                                  hint=not args.no_hint,
                                  content_w=args.content_width,
                                  font_px=args.code_font_size))
    html = "\n\n".join(chunks) + "\n"

    if args.out:
        io.open(args.out, "w", encoding="utf-8", newline="\n").write(html)
        print("[i] 已写入 {}（{} 块 / {} 字符）".format(
            args.out, len(pairs), len(html)), file=sys.stderr)
    else:
        sys.stdout.write(html)


if __name__ == "__main__":
    main()
