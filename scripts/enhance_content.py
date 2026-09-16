#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容增强器 —— 发布前把两类「公众号原生不支持」的内容预处理成兼容形态。

零第三方依赖，仅用 Python 标准库（Python 3.8+）。Windows / Linux 通用。

两件事：

1. mermaid 渲染（子命令 mermaid）
   正文里的 ```mermaid 围栏 或 <div class="mermaid"> 块 → 渲染成 PNG，
   替换成 <img src="assets/mermaid-N.png">（本地相对路径，publish.py 会自动上传换链）。
   为什么是 PNG 不是 SVG：公众号会剥 <style> 与 <foreignObject>，SVG 里
   的文字必丢；PNG 是唯一稳妥形态。

   渲染通道按优先级：
     a) 本地 mmdc（mermaid-cli）：需 node，npm i -g @mermaid-js/mermaid-cli
        可用 config 的 mermaid.mmdc 指定可执行文件路径。
     b) mermaid.ink 远程渲染：零安装兜底。注意这会把图表内容发给第三方服务，
        涉密内容请在 config 设 "mermaid": {"remote": false} 关掉，或装 mmdc。
   两个通道都不可用时，mermaid 源码原样保留，preflight 会报 WX216 拦下。

2. 代码块重建（子命令 code）
   正文里的 ```lang 围栏 与 <pre><code> 块 → 重建为全内联样式的代码卡片：
   深底 + 语言徽标 + 离线语法高亮（零依赖正则着色器）+ 「长按复制」提示。
   缩进用 &nbsp;、换行用 <br> 双保险，不怕公众号折叠空白。
   不转图片：文字可选中，手机上长按代码即可复制——公众号剥 <script>，
   JS 一键复制按钮活不下来，「长按复制」是唯一可靠路径。

用法：
    python enhance_content.py -c work/config.json            # 全部（mermaid → code），就地更新
    python enhance_content.py mermaid -c work/config.json    # 只渲染 mermaid
    python enhance_content.py code -c work/config.json       # 只重建代码块
    python enhance_content.py -c work/config.json --dry-run  # 只报告会改什么，不写文件
    python enhance_content.py -c work/config.json -o out.html  # 结果写到别处，不动原文件

就地更新前会自动留同名 .bak 备份（首次修改时）。

config.json 相关段（都可选）：
    "code":    {"highlight": true, "copy_hint": true},
    "mermaid": {"remote": true, "scale": 2, "width": 800, "dir": "assets", "mmdc": null}

代码高亮配色：预设 JSON 顶层可加 "code_highlight": {"keyword": "#ff7b72", ...} 覆盖，
没写就按 code_bg 明暗自动选深/浅两套默认色板。
"""

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from apply_style import (  # noqa: E402  复用 token 体系，保证与渲染器同一套口径
    COLOR_KEYS,
    load_preset,
    load_style_from_config,
    validate_tokens,
)


def out(msg=""):
    print(msg, flush=True)


def die(msg):
    print("\n[X] " + msg, file=sys.stderr, flush=True)
    sys.exit(1)


def esc(s):
    """HTML 转义（保留引号原样，用于文本节点）。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ================================================================ 通用工具
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FENCE_RE = re.compile(
    r"(?m)^[ \t]*```(?P<lang>[A-Za-z0-9_+#.\-]*)(?P<meta>[^\n]*)\n"
    r"(?P<code>.*?)"
    r"^[ \t]*```[ \t]*$", re.S)
MERMAID_BLOCK_RE = re.compile(
    r'<(div|pre|p)\b[^>]*class\s*=\s*["\'][^"\']*mermaid[^"\']*["\'][^>]*>'
    r"(.*?)</\1\s*>", re.S | re.I)
PRE_RE = re.compile(r"<pre\b[^>]*>(.*?)</pre\s*>", re.S | re.I)
CODE_INNER_RE = re.compile(r"<code\b([^>]*)>(.*?)</code\s*>", re.S | re.I)

ENTITIES = [("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"),
            ("&nbsp;", " "), ("&amp;", "&")]


def unescape_entities(s):
    for ent, ch in ENTITIES:
        s = s.replace(ent, ch)
    return s


def stash_comments(html):
    """把 HTML 注释藏起来，避免处理到说明性内容。返回 (正文, 注释列表)。"""
    stash = []

    def hide(m):
        stash.append(m.group(0))
        return "\x00CMT{}\x00".format(len(stash) - 1)

    return COMMENT_RE.sub(hide, html), stash


def unstash_comments(html, stash):
    return re.sub(r"\x00CMT(\d+)\x00",
                  lambda m: stash[int(m.group(1))], html)


def is_dark(hex_color):
    h = (hex_color or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return True
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 128


# ================================================================ 语法高亮
# 家族式正则着色器：每种语言家族一套 master 正则，命中片段按 kind 上色。
DARK_PALETTE = {
    "keyword": "#ff7b72", "string": "#a5d6ff", "comment": "#8b949e",
    "number": "#79c0ff", "function": "#d2a8ff", "variable": "#ffa657",
    "ins": "#56d364", "del": "#f85149",
}
LIGHT_PALETTE = {
    "keyword": "#cf222e", "string": "#0a3069", "comment": "#6e7781",
    "number": "#0550ae", "function": "#8250df", "variable": "#953800",
    "ins": "#1a7f37", "del": "#cf222e",
}

KW_C = set("""abstract as async await bool break byte case catch char class const
constexpr continue debugger def default delegate delete do double else enum event
explicit export extends extern false final finally fn float for foreach func function
go goto if impl implements import in inline instanceof int interface internal is let
long match mut namespace new nil noexcept null nullptr operator override package
private protected pub public readonly record ref return sealed short sizeof static
string struct super switch synchronized template this throw throws trait transient
true try type typedef typeof union unsafe use using val var virtual void volatile
when where while with yield""".split())
KW_PY = set("""and as assert async await break class continue def del elif else
except False finally for from global if import in is lambda None nonlocal not or
pass print raise return True try while with yield match case self""".split())
KW_SH = set("""if then else elif fi for while until do done case esac in function
select time return exit break continue local export readonly declare set unset
shift source alias echo cd eval exec kill printf read test trap ulimit wait""".split())
KW_SQL = set("""select from where insert into values update set delete create table
alter drop add column index view trigger procedure begin end commit rollback
transaction join inner left right outer full on as and or not null is like in
between exists union all group by order having limit offset distinct case when
then else primary key foreign references default unique check constraint
auto_increment serial int integer varchar char text boolean timestamp date
numeric decimal float double""".split())
KW_YAML = {"true", "false", "null", "yes", "no", "on", "off", "~"}

FAMILY_SPEC = {
    "c-like": {
        "flags": re.S,
        "parts": [
            ("comment", r"//[^\n]*|/\*.*?\*/"),
            ("string", r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`'),
            ("number", r"\b\d[\w.]*"),
            ("word", r"[A-Za-z_$][A-Za-z0-9_$]*"),
        ],
        "keywords": KW_C,
    },
    "python": {
        "flags": re.S,
        "parts": [
            ("comment", r"#[^\n]*"),
            ("string", r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''
                       r'|[frb]?"(?:\\.|[^"\\\n])*"|[frb]?\'(?:\\.|[^\'\\\n])*\''),
            ("number", r"\b\d[\w.]*"),
            ("word", r"[A-Za-z_][A-Za-z0-9_]*"),
        ],
        "keywords": KW_PY,
    },
    "bash": {
        "flags": re.S,
        "parts": [
            ("comment", r"(?<!\$)#[^\n]*"),
            ("string", r'"(?:\\.|[^"\\])*"|\'[^\']*\''),
            ("variable", r"\$\{[^}\n]*\}|\$[A-Za-z_]\w*|\$[@#?$!0-9]"),
            ("number", r"\b\d[\w.]*"),
            ("word", r"[A-Za-z_][A-Za-z0-9_]*"),
        ],
        "keywords": KW_SH,
    },
    "json": {
        "flags": re.S,
        "parts": [
            ("string", r'"(?:\\.|[^"\\])*"'),
            ("number", r"-?\b\d[\w.]*"),
            ("word", r"[A-Za-z_][A-Za-z0-9_]*"),
        ],
        "keywords": {"true", "false", "null"},
    },
    "yaml": {
        "flags": re.M | re.S,
        "parts": [
            ("comment", r"#[^\n]*"),
            ("key", r"^[ \t]*(?:-[ \t]+)?[\w.\-\"']+(?=:(?:\s|$))"),
            ("string", r'"(?:\\.|[^"\\\n])*"|\'[^\']*\''),
            ("number", r"\b\d[\w.]*"),
            ("word", r"[A-Za-z_][A-Za-z0-9_]*"),
        ],
        "keywords": KW_YAML,
    },
    "sql": {
        "flags": re.S,
        "parts": [
            ("comment", r"--[^\n]*|/\*.*?\*/"),
            ("string", r"'(?:''|[^'])*'"),
            ("number", r"\b\d[\w.]*"),
            ("word", r"[A-Za-z_][A-Za-z0-9_]*"),
        ],
        "keywords": KW_SQL,
    },
    "html": {
        "flags": re.S,
        "parts": [
            ("comment", r"<!--[\s\S]*?-->|<!DOCTYPE[^>]*>"),
            ("string", r'"[^"]*"|\'[^\']*\''),
            ("tag", r"</?[A-Za-z][\w:-]*|/?>"),
            ("attr", r"[A-Za-z_][\w:.-]*(?=\s*=)"),
        ],
        "keywords": set(),
    },
    "css": {
        "flags": re.S,
        "parts": [
            ("comment", r"/\*.*?\*/"),
            ("string", r'"[^"\n]*"|\'[^\'\n]*\''),
            ("keyword", r"@[\w-]+"),
            ("function", r"[A-Za-z-]+(?=\s*:)"),
            ("number", r"\b\d[\w.%]*"),
            ("word", r"[A-Za-z_-][\w-]*"),
        ],
        "keywords": set(),
    },
    "diff": {
        "flags": re.M,
        "parts": [
            ("comment", r"^@@[^\n]*|^(?:diff |index |old mode |new mode |--- |\+\+\+ )[^\n]*"),
            ("ins", r"^\+[^\n]*"),
            ("del", r"^-[^\n]*"),
        ],
        "keywords": set(),
    },
}

FAMILY_OF = {}
for _l in ("py python python3".split()):
    FAMILY_OF[_l] = "python"
for _l in ("bash sh shell zsh console".split()):
    FAMILY_OF[_l] = "bash"
for _l in ("js javascript jsx ts tsx typescript java go golang c cpp c++ csharp cs "
           "kotlin kt rust rs swift php scala dart objc m h".split()):
    FAMILY_OF[_l] = "c-like"
for _l in ("json jsonc json5".split()):
    FAMILY_OF[_l] = "json"
for _l in ("yaml yml toml ini".split()):
    FAMILY_OF[_l] = "yaml"
for _l in ("sql psql mysql".split()):
    FAMILY_OF[_l] = "sql"
for _l in ("html xml svg vue".split()):
    FAMILY_OF[_l] = "html"
for _l in ("css scss less".split()):
    FAMILY_OF[_l] = "css"
for _l in ("diff patch".split()):
    FAMILY_OF[_l] = "diff"

_MASTER_CACHE = {}


def _master(family):
    if family not in _MASTER_CACHE:
        spec = FAMILY_SPEC[family]
        parts = "|".join("(?P<{}>{})".format(n, p) for n, p in spec["parts"])
        _MASTER_CACHE[family] = re.compile(parts, spec["flags"])
    return _MASTER_CACHE[family]


def _classify(family, m, source):
    kind = m.lastgroup
    spec = FAMILY_SPEC[family]
    # key/tag 归 keyword 色、attr 归 function 色，保证 emit 的 kind 都在色板里
    if kind in ("key", "tag"):
        return "keyword"
    if kind == "attr":
        return "function"
    if kind in ("variable", "ins", "del", "comment"):
        return kind
    if kind == "string":
        if family == "json":
            tail = re.match(r"\s*:", source[m.end():m.end() + 8])
            if tail:
                return "keyword"
        return "string"
    if kind == "word":
        w = m.group(0)
        if w.lower() in spec["keywords"]:
            return "keyword"
        if re.match(r"[\s]*\(", source[m.end():m.end() + 24]):
            return "function"
        return "plain"
    if kind == "number":
        return "number"
    if kind == "keyword":
        return "keyword"
    if kind == "function":
        return "function"
    return "plain"


def highlight(code, lang, colors, enabled=True):
    """返回上色后的 HTML 文本（含 &nbsp;/<br> 化）。code 需已做 \x01 前导空格标记。"""
    if not enabled:
        return _emit_plain(code)
    family = FAMILY_OF.get((lang or "").lower())
    if not family:
        return _emit_plain(code)
    rx = _master(family)
    pieces = []
    pos = 0
    for m in rx.finditer(code):
        if m.start() > pos:
            pieces.append(("plain", code[pos:m.start()]))
        pieces.append((_classify(family, m, code), m.group(0)))
        pos = m.end()
    if pos < len(code):
        pieces.append(("plain", code[pos:]))
    buf = []
    for kind, text in pieces:
        t = esc(text).replace("\x01", "&nbsp;").replace("\n", "<br>")
        if kind != "plain" and t:
            buf.append('<span style="color:{};">{}</span>'.format(
                colors.get(kind) or "", t))
        else:
            buf.append(t)
    return "".join(buf)


def _emit_plain(code):
    return esc(code).replace("\x01", "&nbsp;").replace("\n", "<br>")


def mark_indent(code):
    """Tab 归一为 4 空格；行首空格打上 \x01 标记（emit 时转 &nbsp;）。"""
    code = code.replace("\t", "    ")
    return re.sub(r"(?m)^[ ]+", lambda m: "\x01" * len(m.group(0)), code)


# ================================================================ 卡片生成
def build_code_section(lang, label, code, st, opts):
    """生成代码卡片。

    结构刻意保持「编辑器抗清洗」：
    - 不用 display:flex / rgba() / white-space:pre-wrap / overflow:hidden ——
      公众号编辑器（mp 后台打开草稿并保存时）会重新序列化正文，
      这些属性会被剥掉，导致深色卡片变回白底纯文本。
    - 背景直接写在单个 <section> 上（background 简写），
      语言徽标 + 「长按复制」合并为单行，不依赖 flex 并排。
    - 代码行用 <br> + &nbsp; 保换行与缩进，word-break:break-all 兜底长行折行。
    """
    toks = st["tokens"]
    body = highlight(mark_indent(code), lang, st["colors"],
                     opts.get("highlight", True))
    head = ""
    if label or opts.get("copy_hint", True):
        left = esc(label) if label else (lang.upper() if lang else "CODE")
        hint = " · 长按复制" if opts.get("copy_hint", True) else ""
        head = (
            '<p style="margin:0 0 6px;font-family:Consolas,Menlo,monospace;'
            "font-size:12px;line-height:1.5;color:{badge};\">"
            "{left}{hint}</p>"
        ).format(badge=toks["primary"], left=left, hint=hint)
    return (
        '<section style="margin:0 0 {pm};background:{bg};'
        'border-radius:{r};padding:12px 14px;">{head}'
        '<p style="margin:0;font-family:Consolas,Menlo,monospace;'
        "font-size:13px;line-height:1.7;color:{ct};"
        'word-break:break-all;">{body}'
        "</p></section>"
    ).format(pm=toks["para_margin"], bg=toks["code_bg"], r=toks["radius"],
             head=head, ct=toks["code_text"], body=body)


def build_mermaid_section(rel, n, st):
    toks = st["tokens"]
    return (
        '<section style="margin:0 0 {pm};text-align:center;">'
        '<img src="{rel}" alt="mermaid 图 {n}" '
        'style="width:100%;display:block;border-radius:{r};">'
        "</section>"
    ).format(pm=toks["para_margin"], rel=esc(rel), n=n, r=toks["radius"])


# ================================================================ mermaid 渲染
def theme_variables(tokens):
    return {
        "primaryColor": tokens.get("card_bg", "#f7f8fa"),
        "primaryTextColor": tokens.get("text_strong", "#222222"),
        "primaryBorderColor": tokens.get("primary", "#d94f22"),
        "lineColor": tokens.get("muted", "#8a8a8a"),
        "secondaryColor": tokens.get("card_bg", "#f7f8fa"),
        "tertiaryColor": tokens.get("primary_soft", "#faf7f4"),
        "fontFamily": "PingFang SC,Microsoft YaHei,sans-serif",
        "fontSize": "14px",
    }


def render_mermaid(src, idx, out_dir, st, mcfg):
    """渲染单个 mermaid 图。返回 (png 绝对路径, 通道名)。失败抛 RuntimeError。"""
    out_path = os.path.join(out_dir, "mermaid-{}.png".format(idx))
    scale = int(mcfg.get("scale", 2) or 2)
    width = int(mcfg.get("width", 800) or 800)
    tvars = theme_variables(st["tokens"])
    mermaid_cfg = json.dumps({
        "theme": "base",
        "themeVariables": tvars,
        "htmlLabels": False,
        "flowchart": {"htmlLabels": False},
    }, ensure_ascii=False)

    mmdc = mcfg.get("mmdc") or shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if mmdc:
        with tempfile.TemporaryDirectory(prefix="wmp-mmd-") as td:
            mmd = os.path.join(td, "diagram.mmd")
            conf = os.path.join(td, "mermaid-config.json")
            with io.open(mmd, "w", encoding="utf-8") as f:
                f.write(src)
            with io.open(conf, "w", encoding="utf-8") as f:
                f.write(mermaid_cfg)
            cmd = [mmdc, "-i", mmd, "-o", out_path, "-b", "white",
                   "-w", str(width), "-s", str(scale), "-c", conf]
            try:
                p = subprocess.run(cmd, capture_output=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise RuntimeError("mmdc 调用失败：{}".format(e))
            if p.returncode != 0 or not os.path.isfile(out_path) \
                    or os.path.getsize(out_path) == 0:
                err = (p.stderr or b"").decode("utf-8", "replace").strip()
                raise RuntimeError("mmdc 渲染失败：{}".format(err[-300:] or "未知错误"))
        return out_path, "mmdc"

    if mcfg.get("remote", True):
        state = {"code": src,
                 "mermaid": {"theme": "base", "themeVariables": tvars,
                             "htmlLabels": False}}
        raw = json.dumps(state, ensure_ascii=False).encode("utf-8")
        b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        # scale/width 决定输出像素分辨率：mermaid.ink 默认图偏小，
        # 手机上按 100% 宽显示会被放大变糊，这里显式放大渲染
        url = "https://mermaid.ink/img/{}?type=png&scale={}&width={}".format(
            b64, scale, width)
        req = urllib.request.Request(url, headers={
            "User-Agent": "wechat-mp-publisher-skill/0.3"})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = resp.read()
        except Exception as e:  # noqa: BLE001  网络异常统一转 RuntimeError
            raise RuntimeError("mermaid.ink 请求失败：{}".format(e))
        if not data.startswith(b"\x89PNG") or len(data) < 200:
            raise RuntimeError("mermaid.ink 返回的不是有效 PNG")
        with io.open(out_path, "wb") as f:
            f.write(data)
        return out_path, "mermaid.ink"

    raise RuntimeError("本地 mmdc 不可用且 remote=false")


# ================================================================ 变换主体
def transform_mermaid(html, st, cfg, base_dir, report, dry):
    mcfg = cfg.get("mermaid") or {}
    blocks = []

    def fence_repl(m):
        if (m.group("lang") or "").lower() != "mermaid":
            return m.group(0)
        blocks.append([m.group("code"), m.group(0)])
        return "\x00MMK{}\x00".format(len(blocks) - 1)

    html = FENCE_RE.sub(fence_repl, html)

    def block_repl(m):
        blocks.append([unescape_entities(m.group(2)).strip(), m.group(0)])
        return "\x00MMK{}\x00".format(len(blocks) - 1)

    html = MERMAID_BLOCK_RE.sub(block_repl, html)

    if not blocks:
        return html, 0, 0

    rel_dir = str(mcfg.get("dir") or "assets")
    out_dir = rel_dir if os.path.isabs(rel_dir) else os.path.join(base_dir, rel_dir)
    os.makedirs(out_dir, exist_ok=True)

    ok = fail = 0
    for i, (src, original) in enumerate(blocks, 1):
        if not src.strip():
            continue
        try:
            png, channel = render_mermaid(src, i, out_dir, st, mcfg)
        except RuntimeError as e:
            fail += 1
            report.append("[!] mermaid 图 {} 渲染失败：{}".format(i, e))
            html = html.replace("\x00MMK{}\x00".format(i - 1), original)
            continue
        ok += 1
        rel = "{}/{}".format(rel_dir.replace("\\", "/"), os.path.basename(png)) \
            if not os.path.isabs(rel_dir) else png
        sec = build_mermaid_section(rel, i, st)
        html = html.replace("\x00MMK{}\x00".format(i - 1), sec)
        report.append("[OK] mermaid 图 {} → {}（{} 通道，{:.1f} KB）".format(
            i, rel, channel, os.path.getsize(png) / 1024.0))
    return html, ok, fail


def transform_code(html, st, cfg, report, dry):
    copts = {
        "highlight": (cfg.get("code") or {}).get("highlight", True),
        "copy_hint": (cfg.get("code") or {}).get("copy_hint", True),
    }
    if dry:
        n = 0
        for m in FENCE_RE.finditer(html):
            if (m.group("lang") or "").lower() != "mermaid":
                n += 1
        n += len(PRE_RE.findall(html))
        if n:
            report.append("[i] 发现 {} 个代码块待重建（dry-run，未写入）".format(n))
        return html, 0, 0

    n_built = 0
    langs = []

    # ---- 1) ``` 围栏（mermaid 的留给 transform_mermaid）
    stash = []

    def fence_repl(m):
        lang = (m.group("lang") or "").lower()
        if lang == "mermaid":
            return m.group(0)
        meta = (m.group("meta") or "").strip()
        label = meta.lstrip(":").strip()
        if label.lower().startswith("title="):
            label = label[6:].strip().strip('"').strip("'")
        code = m.group("code").strip("\n")
        if not code.strip():
            return m.group(0)
        stash.append(build_code_section(lang, label, code, st, copts))
        langs.append(lang or "plain")
        return "\x00CBK{}\x00".format(len(stash) - 1)

    html = FENCE_RE.sub(fence_repl, html)

    # 围栏若被 <p> 包着，把外层 <p> 一并吃掉
    html = re.sub(
        r"<p\b[^>]*>\s*(?:<br\s*/?>\s*)?\x00CBK(\d+)\x00(?:\s*(?:<br\s*/?>)?\s*)</p\s*>",
        lambda m: "\x00CBK{}\x00".format(m.group(1)), html, flags=re.I)

    # ---- 2) <pre>(<code>)</code></pre>（markdown 渲染产物）
    def pre_repl(m):
        inner = m.group(1)
        attrs, code = "", inner
        cm = CODE_INNER_RE.search(inner)
        if cm:
            attrs, code = cm.group(1), cm.group(2)
        code = unescape_entities(code)
        if code.startswith("\n"):
            code = code[1:]
        code = code.rstrip("\n")
        if not code.strip():
            return m.group(0)
        lm = re.search(r"(?:language-|lang-)([\w+#.-]+)", attrs or "")
        lang = lm.group(1).lower() if lm else ""
        stash.append(build_code_section(lang, "", code, st, copts))
        langs.append(lang or "plain")
        return "\x00CBK{}\x00".format(len(stash) - 1)

    html = PRE_RE.sub(pre_repl, html)

    # ---- 3) 放回卡片
    def put(m):
        idx = int(m.group(1))
        return stash[idx] if idx < len(stash) else m.group(0)

    if stash:
        html = re.sub(r"\x00CBK(\d+)\x00", put, html)
        n_built = len(stash)
        cnt = {}
        for l in langs:
            cnt[l] = cnt.get(l, 0) + 1
        detail = "、".join("{}×{}".format(k, v) for k, v in sorted(cnt.items()))
        report.append("[OK] 重建 {} 个代码块（{}）".format(n_built, detail))
    return html, n_built, 0


# ================================================================ 入口
def load_style_tokens(cfg, cfg_path):
    preset_id, overrides = load_style_from_config(cfg_path)
    preset_id = preset_id or "engineering-orange"
    try:
        data, src = load_preset(preset_id)
    except SystemExit:
        data, src = load_preset("engineering-orange")
    raw = dict((k, v) for k, v in (data.get("tokens") or {}).items()
               if not str(k).startswith("_"))
    tokens = validate_tokens(raw, src)
    if overrides:
        tokens.update(validate_tokens(overrides, "config.json 的 style.overrides"))
    dark = is_dark(tokens.get("code_bg", "#16181d"))
    palette = dict(DARK_PALETTE if dark else LIGHT_PALETTE)
    ch = data.get("code_highlight") or {}
    if isinstance(ch, dict):
        for k in list(palette):
            if isinstance(ch.get(k), str) and ch[k].startswith("#"):
                palette[k] = ch[k]
    return {"tokens": tokens, "colors": palette, "dark": dark,
            "preset": data.get("name") or preset_id}


def resolve(cfg_path):
    if not os.path.isfile(cfg_path):
        die("配置文件不存在：{}".format(cfg_path))
    try:
        with io.open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except ValueError as e:
        die("{} 不是合法 JSON：{}".format(cfg_path, e))
    art = cfg.get("article") or {}
    cf = art.get("content_file")
    if not cf:
        die("config.json 缺 article.content_file")
    path = cf if os.path.isabs(cf) else os.path.join(
        os.path.dirname(os.path.abspath(cfg_path)), cf)
    if not os.path.isfile(path):
        die("正文文件不存在：{}".format(path))
    return cfg, path



def run(cfg_path, mode="auto", dry=False, out_path=None, no_highlight=None,
        no_copy_hint=None):
    """返回值：0=无事发生或全部成功；2=有内容未能处理（残留源码）。"""
    cfg, path = resolve(cfg_path)
    base_dir = os.path.dirname(os.path.abspath(cfg_path))
    with io.open(path, encoding="utf-8") as f:
        raw = f.read()
    st = load_style_tokens(cfg, cfg_path)

    if no_highlight is not None:
        cfg.setdefault("code", {})["highlight"] = not no_highlight
    if no_copy_hint is not None:
        cfg.setdefault("code", {})["copy_hint"] = not no_copy_hint

    body, stash = stash_comments(raw)
    report = []
    rc = 0
    changed = False

    # auto 模式：什么都没有就不动手，publish 流程可放心调用
    if mode == "auto":
        has_mmd = bool(FENCE_RE.search(body)
                       and re.search(r"```mermaid", body)) \
            or bool(MERMAID_BLOCK_RE.search(body))
        has_code = False
        for m in FENCE_RE.finditer(body):
            if (m.group("lang") or "").lower() != "mermaid":
                has_code = True
        has_code = has_code or bool(PRE_RE.search(body))
        if not (has_mmd or has_code):
            return 0
        mode = "all"

    if mode in ("all", "mermaid"):
        body, ok, fail = transform_mermaid(body, st, cfg, base_dir, report, dry)
        if ok:
            changed = True
        if fail:
            rc = 2
    if mode in ("all", "code"):
        body, n, _ = transform_code(body, st, cfg, report, dry)
        if n:
            changed = True

    body = unstash_comments(body, stash)

    if report:
        out("== 内容增强（{}）==".format(st["preset"]))
        for line in report:
            out("  " + line)

    if dry:
        out("[i] dry-run：未写任何文件")
        return rc
    if not changed:
        out("[i] 没有需要增强的内容")
        return rc

    target = out_path or path
    if not out_path and not os.path.exists(path + ".bak"):
        with io.open(path + ".bak", "w", encoding="utf-8") as f:
            f.write(raw)
        out("[i] 已备份原文件 → {}.bak".format(path))
    parent = os.path.dirname(os.path.abspath(target))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with io.open(target, "w", encoding="utf-8") as f:
        f.write(body)
    out("[OK] 已更新：{}".format(target))
    if rc == 2:
        out("[!] 有渲染失败的 mermaid 源码原样保留，preflight 会以 WX216 拦截")
    return rc


def main():
    p = argparse.ArgumentParser(
        description="mermaid 渲染 + 代码块重建（零依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", nargs="?", default="all",
                   choices=["all", "mermaid", "code"],
                   help="all=全部（默认）/ mermaid=只渲染图表 / code=只重建代码块")
    p.add_argument("-c", "--config", default=None, help="config.json 路径")
    p.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    p.add_argument("-o", "--out", default=None,
                   help="结果写到别处（默认就地更新 content_file）")
    p.add_argument("--no-highlight", action="store_true",
                   help="关闭语法高亮（纯色代码）")
    p.add_argument("--no-copy-hint", action="store_true",
                   help="去掉代码块头部的「长按复制」提示")
    args = p.parse_args()

    cfg_path = args.config
    if not cfg_path:
        for cand in (os.path.join(os.getcwd(), "config.json"),
                     os.path.join(ROOT, "config.json")):
            if os.path.isfile(cand):
                cfg_path = cand
                break
    if not cfg_path:
        die("找不到 config.json，用 -c 指定")
    sys.exit(run(cfg_path, mode=args.mode, dry=args.dry_run, out_path=args.out,
                 no_highlight=True if args.no_highlight else None,
                 no_copy_hint=True if args.no_copy_hint else None))


if __name__ == "__main__":
    main()
