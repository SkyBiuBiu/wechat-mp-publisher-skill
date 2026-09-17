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
顺带解决两件手写必然出错的事：代码里的 < > & 转义（不转义会把 HTML 结构冲掉）、
以及每行必须用 <p style="margin:0"> 而绝不能用 white-space:pre。

配色为什么「不突兀」
--------------------
三条硬约束，全部落在代码里可核对：
  1. **同族**：关键词取主题主色的同色相，函数取主色相邻 +24°，所以整块代码的
     主旋律就是主题色本身；
  2. **统一明度**：深色底上所有 token 的明度锁在 L≈73~82%，饱和度压到 30~42%。
     全篇只有「亮度一致」这一种变化，不会出现某个 token 扎眼；
  3. **只留一个暖色**：字符串/数字用主色 +200°（近似互补）的低饱和暖色，全文
     仅此一处对比色。运算符与标点**不着色**，避免满屏彩点。
主题主色若是低饱和中性色（如石墨极简 #52525B），色相无意义，改用中性冷色相，
token 之间靠明度与冷暖区分。

用法
----
    # 抽取 Markdown 里所有围栏，逐个输出代码块组件
    python highlight_code.py article.md --theme moyu-green

    # 只要 python 的，写到文件
    python highlight_code.py article.md --theme moyu-green --lang python -o code.html

    # 单段代码（文件 / stdin）
    python highlight_code.py --code-file demo.py --lang python --theme moyu-green
    cat demo.sh | python highlight_code.py - --lang bash --theme moyu-green

    # 看配色（排查「颜色突兀」时先看这个）
    python highlight_code.py --show-palette --theme moyu-green
    python highlight_code.py --show-palette --all-themes

零第三方依赖：只用标准库。语言识别是启发式的，目标是「读起来清楚」，
不是完整语法分析器。
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFS = os.path.join(ROOT, "references")

import theme_vars          # 同目录；主题变量表的唯一解析入口

# 无主题时的兜底（与 make_assets.py 的内置橙调一致）
FALLBACK_PRIMARY = "#D94F22"

FENCE_RE = re.compile(r"^[ \t]*```[ \t]*([A-Za-z0-9_+-]*)[^\n]*\n(.*?)^[ \t]*```[ \t]*$",
                      re.S | re.M)


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


def palette(theme_id, style="dark"):
    """按主题推导一套高亮配色。返回 dict（键即 token 类别）。

    色相来源按可信度挑，全程只用主题**已有**的颜色，不自造：

      1. 主色本身有色（彩度 ≥ CHROMA_MIN）→ 直接用它的色相，
         这是摸鱼绿 / 红白雪 / 摸鱼票据这类"主色即身份"的主题；
      2. 主色是墨黑或灰（橄榄手记 #1e1f23、石墨极简 #52525B）→ 色相是噪声，
         改取主题登记的点睛强调色的色相（#ed7b2f / #F97316）；
      3. 连强调色也没有 → 落到中性冷色相，token 之间靠明度与冷暖区分。

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
                                 "中性兜底色相（主题里没有可用的彩色）", True)

    # 色相一律取自主题已有颜色，饱和度与明度由本脚本统一施加 ——
    # 所以像 #4A5D52（留白禅意的墨绿，彩度仅 0.075）这样的低饱和主题，
    # 也能得到"明确是墨绿、但不刺眼"的 token，而不是被误判成灰色丢掉色相。
    return _palette_from(theme_id, theme_vars.hue_of(primary), style, primary,
                         source, False)


def _palette_from(theme_id, h, style, primary, source, neutral_theme):
    """给定色相，展开成整套 token 配色。

    三条硬约束（改这里要先看模块头部的说明）：
      · 关键词与函数是主色相的邻居（+0° / +24°），全块的主旋律就是主题色；
      · 深色底上所有 token 明度锁在 0.73~0.82、饱和度 0.30~0.42，
        全篇只有"亮度一致"这一种变化；
      · 只有字符串/数字用 +200° 的低饱和暖色，运算符与标点不着色。
    """
    if style == "light":
        return {
            "theme": theme_id or "(内置橙调)",
            "primary": primary,
            "source": source,
            "neutral_theme": neutral_theme,
            "bg": "#F6F8FA",
            "header_bg": None,
            "header_fg": "#9CA3AF",
            "border": _hex(_rgb(primary)),
            "base": "#24292F",
            "comment": "#6E7781",
            "keyword": hsl2hex(h, 0.55, 0.34),
            "func": hsl2hex(h + 24, 0.52, 0.36),
            "string": hsl2hex(h + 200, 0.42, 0.42),
            "number": hsl2hex(h + 200, 0.38, 0.34),
        }
    return {
        "theme": theme_id or "(内置橙调)",
        "primary": primary,
        "source": source,
        "neutral_theme": neutral_theme,
        "bg": "#1E293B",
        "header_bg": "#0F172A",
        "header_fg": "#64748B",
        "border": None,
        "base": "#E2E8F0",
        "comment": "#8B9BB0",
        "keyword": hsl2hex(h, 0.42, 0.74),
        "func": hsl2hex(h + 24, 0.40, 0.73),
        "string": hsl2hex(h + 200, 0.36, 0.76),
        "number": hsl2hex(h + 200, 0.30, 0.82),
    }


# ------------------------------------------------------------------ 语言档案
# 每个档案给出 token 的匹配式，按「注释 → 字符串 → 关键字 → 数字 → 函数」优先，
# 命中即不再往下试。运算符与标点故意不列（不着色）。
_SH_COMMANDS = ("if|then|elif|else|fi|for|do|done|while|until|case|esac|function|"
                "in|return|export|local|readonly|source|set|unset|shift|trap|eval|"
                "sudo|apt|apt-get|yum|dnf|brew|systemctl|service|docker|kubectl|"
                "git|curl|wget|ssh|scp|rsync|tar|zip|unzip|make|npm|npx|pnpm|yarn|"
                "node|python|python3|pip|pip3|poetry|uv|go|cargo|mvn|gradle|java|"
                "echo|printf|cat|grep|egrep|sed|awk|find|xargs|sort|uniq|head|tail|"
                "wc|cut|tr|tee|less|more|touch|mkdir|rmdir|rm|cp|mv|ln|chmod|chown|"
                "ls|pwd|cd|exit|kill|ps|top|df|du|free|whoami|env|which|test|open|"
                "jq|yq|openssl|date|sleep|watch|time|alias")

PROFILES = {
    "python": {
        "comment": r"#[^\n]*",
        "string": r'"""(?:[^"]|"(?!""))*"""|\'\'\'(?:[^\']|\'(?!\'\'))*\'\'\'|'
                  r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        "keyword": r"\b(?:def|class|return|if|elif|else|for|while|in|not|and|or|"
                   r"import|from|as|with|try|except|finally|raise|yield|lambda|"
                   r"pass|break|continue|global|nonlocal|assert|del|is|None|True|"
                   r"False|self|cls|async|await|match|case)\b",
        "number": r"\b(?:0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][-+]?\d+)?)\b",
        "func": r"\b[A-Za-z_]\w*(?=\s*\()",
    },
    "bash": {
        "comment": r"#[^\n]*",
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'',
        "number": r"(?<=\s)-{1,2}[A-Za-z][\w-]*|\b\d+(?:\.\d+)?\b",
        "keyword": r"\b(?:{})\b".format(_SH_COMMANDS),
        "func": r"(?<![\w.-])[A-Za-z_][\w.-]*(?=\s)",
    },
    "json": {
        "comment": r"//[^\n]*",
        "string": r'"(?:\\.|[^"\\])*"',
        "keyword": r"\b(?:true|false|null)\b",
        "number": r"-?\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b",
        "func": r"(?!)",
    },
    "javascript": {
        "comment": r"//[^\n]*|/\*.*?\*/",
        "string": r"`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
        "keyword": r"\b(?:const|let|var|function|return|if|else|for|while|do|switch|"
                   r"case|break|continue|new|class|extends|super|this|import|export|"
                   r"from|default|async|await|try|catch|finally|throw|typeof|"
                   r"instanceof|in|of|delete|void|yield|static|get|set|"
                   r"interface|type|enum|implements|public|private|readonly|as|"
                   r"null|undefined|true|false|NaN)\b",
        "number": r"\b(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?)\b",
        "func": r"\b[A-Za-z_$]\w*(?=\s*\()",
    },
    "yaml": {
        "comment": r"#[^\n]*",
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'',
        "keyword": r"^\s*[-\s]*[\w.$-]+(?=\s*:)|(?<=:\s)\S+$",
        "number": r"\b(?:true|false|null|yes|no|\d+(?:\.\d+)?)\b",
        "func": r"(?!)",
    },
    "sql": {
        "comment": r"--[^\n]*|/\*.*?\*/",
        "string": r"'(?:''|[^'])*'",
        "keyword": r"\b(?:SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|"
                   r"GROUP|ORDER|BY|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|"
                   r"SET|DELETE|CREATE|TABLE|INDEX|VIEW|DROP|ALTER|ADD|COLUMN|AS|"
                   r"AND|OR|NOT|NULL|IS|IN|LIKE|BETWEEN|DISTINCT|COUNT|SUM|AVG|"
                   r"MIN|MAX|CASE|WHEN|THEN|ELSE|END|UNION|ALL|EXISTS|PRIMARY|KEY|"
                   r"FOREIGN|REFERENCES|CONSTRAINT|DEFAULT|ASC|DESC)\b",
        "number": r"\b\d+(?:\.\d+)?\b",
        "func": r"\b[A-Za-z_]\w*(?=\s*\()",
    },
    "dockerfile": {
        "comment": r"#[^\n]*",
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'',
        "keyword": r"^\s*(?:FROM|RUN|CMD|LABEL|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|"
                   r"VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL|"
                   r"AS)\b",
        "number": r"\b\d+(?:\.\d+)?\b",
        "func": r"(?!)",
    },
    "clike": {   # go / rust / java / c / cpp / php / ruby / kotlin / swift …
        "comment": r"//[^\n]*|/\*.*?\*/|#[^\n]*",
        "string": r'"(?:\\.|[^"\\])*"|\'[^\']*\'|`[^`]*`',
        "keyword": r"\b(?:func|fn|let|mut|const|var|val|return|if|else|for|while|"
                   r"switch|case|break|continue|new|class|struct|enum|interface|"
                   r"impl|trait|pub|use|mod|package|import|from|in|of|this|self|"
                   r"try|catch|finally|throw|throws|except|raise|defer|go|chan|"
                   r"range|type|map|void|int|float|double|bool|char|string|byte|"
                   r"long|short|unsigned|signed|static|final|public|private|"
                   r"protected|abstract|override|virtual|template|namespace|"
                   r"include|define|true|false|null|nil|None|undefined)\b",
        "number": r"\b(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?)\b",
        "func": r"\b[A-Za-z_]\w*(?=\s*\()",
    },
    "plain": {
        "comment": r"(?!)",
        "string": r"(?!)",
        "keyword": r"(?!)",
        "number": r"(?!)",
        "func": r"(?!)",
    },
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
    """把档案拼成一个带命名组的正则，顺序即优先级。"""
    order = ("comment", "string", "keyword", "number", "func")
    parts = [r"(?P<{}>{})".format(k, prof[k]) for k in order]
    return re.compile("|".join(parts))


def tokenize_line(line, rx):
    """把一行切成 [(文本, 类别)]，类别 "plain" 表示不着色。"""
    out, pos = [], 0
    for m in rx.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], "plain"))
        kind = m.lastgroup
        out.append((m.group(0), kind))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], "plain"))
    return [t for t in out if t[0]]


# ------------------------------------------------------------------ 组件装配
MONO = "'SF Mono',Consolas,Monaco,monospace"


def esc(s):
    """代码里的 < > & 必须转义，否则会把 HTML 结构冲掉。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def code_line_html(line, rx, pal):
    if not line.strip():
        # 空行也要占位，否则段落间距会被压掉
        return ('    <p style="margin:0;font-family:{};font-size:13px;'
                'line-height:1.6;color:{};"><span leaf="">　</span></p>'
                .format(MONO, pal["base"]))
    chunks = []
    for text, kind in tokenize_line(line, rx):
        body = esc(text)
        if kind == "plain":
            chunks.append('<span leaf="">{}</span>'.format(body))
        else:
            chunks.append('<span style="color:{};"><span leaf="">{}</span></span>'
                          .format(pal[kind], body))
    return ('    <p style="margin:0;font-family:{};font-size:13px;line-height:1.6;'
            'color:{};">{}</p>'.format(MONO, pal["base"], "".join(chunks)))


def build_block(code, lang, pal, style="dark"):
    """按通用库 1a/1b 的结构装配一个代码块。"""
    label = (lang or "").strip() or "text"
    lines = [ln.rstrip() for ln in code.rstrip("\n").split("\n")]
    rx = ordered_pattern(profile_of(lang))
    body = "\n".join(code_line_html(ln, rx, pal) for ln in lines)

    if style == "light":
        head = ('  <section style="padding:7px 14px;border-bottom:1px solid #E5E7EB;">\n'
                '    <span style="font-size:12px;color:{};font-family:Consolas,Monaco,'
                'monospace;letter-spacing:1px;"><span leaf="">{}</span></span>\n'
                '  </section>'.format(pal["header_fg"], esc(label)))
        return ('<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;'
                'background:{};border:1px solid #E5E7EB;border-left:3px solid {};">\n'
                '{}\n'
                '  <section style="padding:11px 14px;">\n{}\n  </section>\n'
                '</section>'.format(pal["bg"], pal["border"], head, body))

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
            '  </section>'.format(pal["header_bg"], dots, pal["header_fg"], esc(label)))
    return ('<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;'
            'background:{};box-shadow:0 4px 16px -8px rgba(15,23,42,0.4);">\n'
            '{}\n  <section style="padding:11px 14px;">\n{}\n  </section>\n'
            '</section>'.format(pal["bg"], head, body))


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
def show_palette(theme_ids, style):
    for tid in theme_ids:
        pal = palette(tid, style)
        print("=" * 62)
        print("主题 {}   色相来源 {}   主色 {}".format(
            pal["theme"], pal["source"], pal["primary"]))
        if pal["neutral_theme"]:
            print("  （主色近中性，已改用中性冷色相）")
        order = ["base", "comment", "keyword", "func", "string", "number"]
        for k in order:
            print("  {:<9} {}".format(k, pal[k]))
        print("  底色      {}   顶栏 {}".format(
            pal["bg"], pal["header_bg"] or "—"))
        # 主色到关键词色的色相偏移，便于判断「是否同族」
        ph, ps, _ = rgb2hsl(_rgb(pal["primary"]))
        kh, _, _ = rgb2hsl(_rgb(pal["keyword"]))
        print("  主色彩度 {:.3f}（阈值 {}）".format(theme_vars.chroma(pal["primary"]),
                                              CHROMA_MIN))
        print("  色相：主色 {:.0f}° → 关键词 {:.0f}°（偏移 {:.0f}°）".format(
            ph, kh, (kh - ph + 180) % 360 - 180))


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
        show_palette(ids, args.style)
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
    pal = palette(theme, args.style)
    if theme and not theme_primary(theme):
        print("[!] 读不到主题配色（references/theme-{}.md 缺失或无变量表），"
              "改用内置橙调".format(theme), file=sys.stderr)
    print("[i] 配色取自主题：{}  主色 {}  样式 {}".format(
        pal["theme"], pal["primary"], args.style), file=sys.stderr)

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

    chunks = []
    for lang, code in pairs:
        chunks.append("<!-- 代码块：{} → 通用库 {} -->".format(
            (lang or "text"), "1b 浅色" if args.style == "light" else "1a 深色"))
        chunks.append(build_block(code, lang, pal, args.style))
    html = "\n\n".join(chunks) + "\n"

    if args.out:
        io.open(args.out, "w", encoding="utf-8", newline="\n").write(html)
        print("[i] 已写入 {}（{} 块 / {} 字符）".format(
            args.out, len(pairs), len(html)), file=sys.stderr)
    else:
        sys.stdout.write(html)


if __name__ == "__main__":
    main()
