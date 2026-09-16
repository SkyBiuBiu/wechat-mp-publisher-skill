#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格渲染器 —— 把风格预设套进正文模板，生成可直接投递的 article.html。

零第三方依赖，仅用 Python 标准库（Python 3.8+）。Windows / Linux 通用。

设计：模板里写 {{token}} 占位符，本脚本按预设的 token 值替换。
正文的视觉风格由「预设 + 覆盖」决定，写作口吻由 references/style-presets.md 约束（给人/AI 看）。

用法：
    python apply_style.py --list                       # 列出全部内置预设
    python apply_style.py                              # 用 config.json 里的 style（或默认预设）渲染
    python apply_style.py --preset minimal-paper       # 指定预设，输出到 ./article.html
    python apply_style.py --preset business-blue -o work/article.html
    python apply_style.py --preset engineering-orange --set primary=#1f4e8c
    python apply_style.py --preset engineering-orange --set font_size=17px --set radius=6px
    python apply_style.py --style-file my-style.json   # 用自定义预设
    python apply_style.py --preset magazine-warm --dump my-style.json   # 导出后改
    python apply_style.py --preset terminal-green --show-tokens         # 只看 token，不写文件
    python apply_style.py --preset terminal-green --out -               # 输出到标准输出
    python apply_style.py --no-config --preset minimal-paper            # 不读 config.json 的 style

取值优先级（后者覆盖前者）：
    内置预设 → config.json 的 style.preset → config.json 的 style.overrides → 命令行 --set
"""

import argparse
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLE_DIR = os.path.join(ROOT, "assets", "styles")
TEMPLATE = os.path.join(ROOT, "assets", "templates", "article.template.html")

# ---- token 白名单：写错键名会直接报错，避免"改了没生效"的哑巴问题 -------------
COLOR_KEYS = [
    "primary", "primary_soft", "text", "text_strong", "muted", "border",
    "card_bg", "code_bg", "code_text", "table_head_bg", "table_head_text",
]
SIZE_KEYS = ["font_size", "line_height", "radius", "para_margin", "letter_spacing",
             "heading_size"]
TOKEN_KEYS = COLOR_KEYS + SIZE_KEYS

COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# 尺寸类：数字 + 单位（px / em / rem / %），line_height 允许纯数字
SIZE_RE = re.compile(r"^\d+(?:\.\d+)?(?:px|em|rem|%)?$")

# 打印 token 表时的中文标签
LABEL = {
    "primary": "主题色", "primary_soft": "主题浅底", "text": "正文色",
    "text_strong": "强调色", "muted": "次要文字", "border": "分隔线",
    "card_bg": "卡片底", "code_bg": "代码块底", "code_text": "代码文字",
    "table_head_bg": "表头底", "table_head_text": "表头文字",
    "font_size": "正文字号", "line_height": "行高", "radius": "圆角",
    "para_margin": "段间距", "letter_spacing": "字间距", "heading_size": "小标题字号",
}


def out(msg=""):
    print(msg, flush=True)


def die(msg):
    print("\n[X] " + msg, file=sys.stderr, flush=True)
    sys.exit(1)


# ---------------------------------------------------------------- 预设装载
def list_presets():
    """返回 [(id, path), ...]，按 id 排序。"""
    items = []
    for path in sorted(glob.glob(os.path.join(STYLE_DIR, "*.json"))):
        try:
            with io.open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, IOError):
            continue
        pid = data.get("id") or os.path.splitext(os.path.basename(path))[0]
        items.append((pid, path, data))
    return items


def find_preset(preset_id):
    for pid, path, data in list_presets():
        if pid == preset_id:
            return path, data
    return None, None


def load_preset(preset_id, style_file=None):
    """装载预设。style_file 优先；两者都为空则报错。"""
    if style_file:
        if not os.path.isfile(style_file):
            die("自定义风格文件不存在：{}".format(style_file))
        try:
            with io.open(style_file, encoding="utf-8") as f:
                data = json.load(f)
        except ValueError as e:
            die("{} 不是合法 JSON：{}".format(style_file, e))
        return data, os.path.abspath(style_file)

    path, data = find_preset(preset_id)
    if not data:
        ids = [p[0] for p in list_presets()]
        die("找不到预设「{}」。可选：{}".format(preset_id, "、".join(ids) or "（styles 目录为空）"))
    return data, path


def validate_tokens(tokens, where):
    """校验 token 键名与取值。返回清洗后的 dict。"""
    unknown = [k for k in tokens if k not in TOKEN_KEYS]
    if unknown:
        die("{} 里有无法识别的 token：{}\n    可用 token：{}".format(
            where, "、".join(unknown), "、".join(TOKEN_KEYS)))
    clean = {}
    bad = []
    for k, v in tokens.items():
        v = str(v).strip()
        if k in COLOR_KEYS:
            if not COLOR_RE.match(v):
                bad.append("{}={}（需要 #rgb 或 #rrggbb 形式）".format(k, v))
                continue
        elif k in SIZE_KEYS:
            if not SIZE_RE.match(v):
                bad.append("{}={}（需要数字 + px/em/rem/% 单位）".format(k, v))
                continue
        clean[k] = v
    if bad:
        die("{} 的 token 取值不合法：\n    - {}".format(where, "\n    - ".join(bad)))
    return clean


def load_style_from_config(cfg_path):
    """从 config.json 读 style 段。返回 (preset, overrides_dict)，读不到就是 (None, {})。"""
    if not cfg_path or not os.path.isfile(cfg_path):
        return None, {}
    try:
        with io.open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, IOError):
        return None, {}
    st = data.get("style")
    if not isinstance(st, dict):
        return None, {}
    preset = st.get("preset")
    ov = st.get("overrides")
    if not isinstance(ov, dict):
        ov = {}
    # 下划线开头的是给人看的注释键（config 里常这么写），跳过
    ov = dict((k, v) for k, v in ov.items() if not str(k).startswith("_"))
    return (str(preset) if preset else None), ov


def find_default_config():
    for cand in (os.path.join(os.getcwd(), "config.json"),
                 os.path.join(ROOT, "config.json")):
        if os.path.isfile(cand):
            return cand
    return None


def resolve_tokens(preset_id, style_file, overrides, config_overrides=None):
    """合并顺序：内置预设 → config.style.overrides → --set 覆盖（后者优先）。"""
    data, src = load_preset(preset_id, style_file)
    tokens = validate_tokens(
        dict((k, v) for k, v in (data.get("tokens") or {}).items()
             if not str(k).startswith("_")), src)

    if config_overrides:
        tokens.update(validate_tokens(config_overrides, "config.json 的 style.overrides"))

    if overrides:
        ov = {}
        for item in overrides:
            if "=" not in item:
                die("--set 的格式是 key=value，收到：{}".format(item))
            k, v = item.split("=", 1)
            k = k.strip()
            if k not in TOKEN_KEYS:
                die("--set 里有无法识别的 token：{}\n    可用 token：{}".format(k, "、".join(TOKEN_KEYS)))
            ov[k] = v.strip()
        tokens.update(validate_tokens(ov, "--set"))

    # 缺项用内置默认补齐（自定义文件只写想改的几项也能用）
    _, default_data = find_preset("engineering-orange")
    base = (default_data or {}).get("tokens") or {}
    merged = dict(base)
    merged.update(tokens)

    missing = [k for k in TOKEN_KEYS if k not in merged]
    if missing:
        die("模板需要这些 token 但没有值：{}".format("、".join(missing)))
    return merged, data, src


# ---------------------------------------------------------------- 渲染
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def render(tokens):
    if not os.path.isfile(TEMPLATE):
        die("模板不存在：{}".format(TEMPLATE))
    with io.open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()

    # HTML 注释里的 {{xxx}} 是给人看的说明文字，不参与替换
    # （公众号本来就会剥掉注释，publish.py 也会先剥离，留着不影响成稿）
    stash = []

    def hide(m):
        stash.append(m.group(0))
        return "\x00CMT{}\x00".format(len(stash) - 1)

    body = COMMENT_RE.sub(hide, tpl)

    def repl(m):
        key = m.group(1)
        if key not in tokens:
            die("模板里的占位符 {{{{{}}}}} 没有对应 token".format(key))
        return tokens[key]

    body = PLACEHOLDER_RE.sub(repl, body)

    leftover = sorted(set(PLACEHOLDER_RE.findall(body)))
    if leftover:
        die("渲染后仍有未替换的占位符：{}".format("、".join(leftover)))

    return re.sub(r"\x00CMT(\d+)\x00", lambda m: stash[int(m.group(1))], body)


# ---------------------------------------------------------------- 子功能
def cmd_list():
    presets = list_presets()
    if not presets:
        die("{} 下没有任何风格预设".format(STYLE_DIR))
    out("可用风格预设（{} 个）：".format(len(presets)))
    out("")
    for pid, path, data in presets:
        mark = " *" if pid == "engineering-orange" else "  "
        out("{}({})  {}".format(mark, pid, data.get("name") or ""))
        if data.get("tagline"):
            out("      {}".format(data["tagline"]))
        if data.get("best_for"):
            out("      常配题材：{}（参考，不限制你写什么）".format("、".join(data["best_for"])))
        out("")
    out("带 * 的是默认预设。用法：python apply_style.py --preset <id>")
    out("自定义：--set primary=#1f4e8c 局部覆盖，或 --dump my.json 导出后整份改。")


def print_tokens(tokens, name):
    out("预设：{}".format(name))
    out("-" * 52)
    for k in TOKEN_KEYS:
        out("  {:<18} {:<12} {}".format(k, tokens[k], LABEL.get(k, "")))
    out("-" * 52)


def cmd_dump(preset_id, style_file, out_path):
    data, src = load_preset(preset_id, style_file)
    data.pop("_说明", None)
    data["_说明"] = ("自定义风格。id 与服务端的无关，随便起；tokens 里只写想改的项也行，"
                     "没写的会继承 engineering-orange 的默认值。")
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    out("[OK] 已导出：{}".format(out_path))
    out("     改完用它渲染：python apply_style.py --style-file {}".format(
        os.path.basename(out_path)))


def main():
    p = argparse.ArgumentParser(
        description="按风格预设渲染公众号正文模板（零依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="内置预设说明见 references/style-presets.md")
    p.add_argument("--list", action="store_true", help="列出全部内置预设后退出")
    p.add_argument("--preset", default=None,
                   help="预设 id。不填则用 config.json 的 style.preset，再退回 engineering-orange")
    p.add_argument("-c", "--config", default=None,
                   help="config.json 路径，用于读取 style.preset / style.overrides")
    p.add_argument("--no-config", action="store_true",
                   help="不读 config.json 的 style 段，只用命令行参数")
    p.add_argument("--style-file", default=None,
                   help="自定义预设 JSON 路径。给了它就忽略 --preset")
    p.add_argument("--set", dest="overrides", action="append", default=[],
                   metavar="K=V", help="覆盖单个 token，可重复，如 --set primary=#1f4e8c")
    p.add_argument("-o", "--out", default=None,
                   help="输出文件路径，默认 当前目录/article.html；用 - 输出到标准输出")
    p.add_argument("--dump", default=None, metavar="PATH",
                   help="把当前预设导出成可编辑的自定义 JSON，不渲染")
    p.add_argument("--show-tokens", action="store_true", help="只打印 token 表，不写文件")
    args = p.parse_args()

    if args.list:
        cmd_list()
        return 0

    # 解析风格来源：命令行 --preset > config.json 的 style.preset > 默认预设
    cfg_overrides = {}
    if not args.no_config:
        cfg_path = args.config or find_default_config()
        cfg_preset, cfg_overrides = load_style_from_config(cfg_path)
        if not args.preset and cfg_preset:
            args.preset = cfg_preset
            out("[i] 风格取自 {}：{}".format(cfg_path, cfg_preset))
    if not args.preset:
        args.preset = "engineering-orange"

    if args.dump:
        cmd_dump(args.preset, args.style_file, args.dump)
        return 0

    tokens, data, src = resolve_tokens(args.preset, args.style_file, args.overrides,
                                       config_overrides=cfg_overrides)
    name = data.get("name") or args.preset

    if args.show_tokens:
        print_tokens(tokens, name)
        return 0

    html = render(tokens)

    out_path = args.out
    if out_path == "-":
        sys.stdout.write(html)
        return 0
    if not out_path:
        out_path = os.path.join(os.getcwd(), "article.html")
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    out("[OK] 已渲染：{}".format(out_path))
    out("     风格：{}（{}）".format(name, src))
    if args.overrides or cfg_overrides:
        notes = []
        if cfg_overrides:
            notes.append("config.json {} 项".format(len(cfg_overrides)))
        if args.overrides:
            notes.append("命令行 {}".format("、".join(args.overrides)))
        out("     覆盖：{}".format(" + ".join(notes)))
    out("     下一步：把内容改成自己的 → python scripts/preflight.py -c config.json → draft")
    out("     提示：模板第 8 块引用了 assets/diagram.png。没有这张图体检会报 WX012，"
        "删掉那一块或放上自己的图。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
