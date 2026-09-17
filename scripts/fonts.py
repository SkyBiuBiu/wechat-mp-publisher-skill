#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字体来源的**唯一**入口：封面（Pillow 按文件加载）与流程图（Chromium 按字体名
+ @font-face）必须描述同一套字体，否则会出现"封面换了字、图没换"或者反过来。

为什么单列一个模块：
- 封面走 Pillow：`ImageFont.truetype(<文件路径>, size)` —— 认文件，不认字体名。
- 流程图走浏览器：认 `font-family` 名字 —— 必须再喂一份 `@font-face` 指向同一个文件。
两边各写一份字体清单 = 必然漂。这里给两边发同一份答案。

字体文件**不随 skill 分发**（一套中文 17~26MB，塞进 zip 没道理）。查找顺序：

    1. 环境变量 WMP_FONT_DIR        —— 想指定任意目录时用
    2. <skill>/assets/fonts/        —— 想让字体跟着仓库走时用（记得 .gitignore）
    3. ~/.workbuddy/fonts/          —— 本机共享目录，多项目通用（推荐）
    4. C:\\Windows\\Fonts             —— 系统字体兜底

预设（preset）只有"逻辑角色"，不绑死某个文件 —— 缺文件就退回系统字体并在
stderr 说一句，绝不静默变丑：

    system  系统默认：微软雅黑 / 微软雅黑粗体（现状，零依赖）
    wenkai  霞鹜文楷 LXGW WenKai：楷体骨架，温润、辨识度高
    serif   思源宋体 Noto Serif SC 标题 + 思源黑体 Noto Sans SC 正文
    sans    思源黑体 Noto Sans SC：现代黑体，小字号最清晰
    rounded MiSans：圆润科技风（标题 Demibold / 正文 Regular）

用法：
    python scripts/fonts.py                 # 列出可用预设与命中情况
    python scripts/fonts.py --preset wenkai # 看这一套解析到了哪些文件
"""

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

# 逻辑角色 → 候选文件名（glob 通配，按顺序取第一个命中的）
PRESETS = {
    "system": {
        "label": "系统默认（微软雅黑）",
        "title": ["msyhbd.ttc", "msyh.ttc", "simhei.ttf"],
        "body": ["msyh.ttc", "simhei.ttf"],
    },
    "wenkai": {
        "label": "霞鹜文楷 LXGW WenKai",
        "title": ["LXGWWenKai-Medium.ttf", "LXGWWenKai-Bold.ttf",
                  "LXGWWenKai-Regular.ttf"],
        "body": ["LXGWWenKai-Regular.ttf", "LXGWWenKai-Light.ttf"],
    },
    "serif": {
        "label": "思源宋体 + 思源黑体",
        "title": ["NotoSerifSC*.ttf", "NotoSerifSC*.otf", "SourceHanSerifSC-*.otf"],
        "body": ["NotoSansSC*.ttf", "NotoSansSC*.otf", "SourceHanSansSC-*.otf"],
    },
    "sans": {
        "label": "思源黑体 Noto Sans SC",
        "title": ["NotoSansSC*.ttf", "NotoSansSC*.otf"],
        "body": ["NotoSansSC*.ttf", "NotoSansSC*.otf"],
    },
    "rounded": {
        "label": "MiSans（小米，圆润科技风）",
        "title": ["MiSans-Demibold.ttf", "MiSans-Bold.ttf", "MiSans-Medium.ttf"],
        "body": ["MiSans-Regular.ttf", "MiSans-Medium.ttf", "MiSans-Normal.ttf"],
    },
}

DEFAULT_PRESET = "system"

# CSS 里的字体族名：带 WMP 前缀，避免和用户系统里同名字体打架
FAMILY_TPL = "WMP-{preset}-{role}"


def font_dirs():
    dirs = []
    env = os.environ.get("WMP_FONT_DIR")
    if env:
        dirs.append(env)
    dirs.append(os.path.join(SKILL, "assets", "fonts"))
    home = os.path.expanduser("~")
    dirs.append(os.path.join(home, ".workbuddy", "fonts"))
    sys_dir = os.environ.get("SystemRoot", r"C:\Windows")
    dirs.append(os.path.join(sys_dir, "Fonts"))
    out = []
    for d in dirs:
        if d and os.path.isdir(d) and d not in out:
            out.append(d)
    return out


_CHECKABLE_EXT = (".ttf", ".ttc", ".otf", ".otc")
_SFNT_TAGS = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1")


def sfnt_ok(path):
    """字体文件的表目录是否完整落在文件长度内。

    为什么需要这么一道：**Pillow 的 truetype 是惰性加载的** —— 只读开头就能
    "成功打开"，于是下载到一半的字体也会被当成可用，渲染时才缺字（封面出现
    豆腐块或空白），而且全程不报错。这里按 sfnt 表目录把每个表的
    `offset + length` 与文件长度比对，半截文件会被判为不可用，自动落到下一个
    候选（如 Medium 没下完就用 Regular），而不是整体退回系统字体。
    """
    import struct
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(12)
            if len(head) < 12:
                return False
            if head[:4] == b"ttcf":                  # TrueType Collection
                num = struct.unpack(">I", head[8:12])[0]
                if not 0 < num <= 64:
                    return False
                offs = struct.unpack(">{}I".format(num), f.read(4 * num))
                f.seek(offs[0])
                head = f.read(12)
                if len(head) < 12:
                    return False
            if head[:4] not in _SFNT_TAGS:
                return False
            num_tables = struct.unpack(">H", head[4:6])[0]
            if not 0 < num_tables <= 512:
                return False
            recs = f.read(16 * num_tables)
            if len(recs) < 16 * num_tables:
                return False
            for i in range(num_tables):
                off, length = struct.unpack(">II", recs[i * 16 + 8:i * 16 + 16])
                if off + length > size:
                    return False
        return True
    except Exception:                                # noqa: BLE001
        return False


def loadable(path):
    """文件能不能真的拿来渲染。

    两道关：表目录完整（sfnt_ok，治半截文件）+ Pillow 能打开（治格式/权限）。
    非 Pillow 认得的格式（woff2）跳过校验，交给浏览器自己判断。
    """
    if not path.lower().endswith(_CHECKABLE_EXT):
        return True
    if not sfnt_ok(path):
        return False
    try:
        from PIL import ImageFont
        ImageFont.truetype(path, 12)
        return True
    except Exception:                                # noqa: BLE001
        return False


def resolve(patterns):
    """按目录顺序找**第一个能用的**字体文件，返回绝对路径或 None。

    候选按优先级依次尝试，坏文件跳过继续往下找 —— 所以"Medium 是半截的"
    会自动落到 Regular，而不是整体退回系统字体。
    """
    hits = []
    for d in font_dirs():
        for pat in patterns:
            for hit in sorted(glob.glob(os.path.join(d, pat))):
                if os.path.isfile(hit):
                    p = os.path.abspath(hit)
                    if p not in hits:
                        hits.append(p)
    for p in hits:
        if loadable(p):
            return p
    return None


_PRESET_CACHE = {}


def preset_files(preset):
    """返回 {role: 绝对路径|None}。缺哪个角色，哪个就是 None。"""
    if preset in _PRESET_CACHE:
        return _PRESET_CACHE[preset]
    spec = PRESETS.get(preset) or PRESETS[DEFAULT_PRESET]
    got = {role: resolve(spec[role]) for role in ("title", "body")}
    got["label"] = spec["label"]
    got["preset"] = preset
    _PRESET_CACHE[preset] = got
    return got


def available(preset):
    """这套预设能不能真的用上（title 与 body 都得有文件）。"""
    f = preset_files(preset)
    return bool(f["title"] and f["body"])


_WARNED = set()


def pick(preset, role, quiet=False):
    """取字体文件路径；取不到退回系统字体并提示一次（不静默变丑）。

    `role` 只有 title / body 两种：封面标题、图内强调文字走 title，
    其余（副标题、日期、正文、图内节点文字）走 body。
    """
    f = preset_files(preset).get(role)
    if f:
        return f
    key = (preset, role)
    if not quiet and key not in _WARNED:
        _WARNED.add(key)
        print("[!] 字体预设 {!r} 的 {} 文件没找到（查过：{}），退回系统字体".format(
            preset, role, ", ".join(font_dirs())[:120]), file=sys.stderr)
    return resolve(PRESETS["system"][role])


# ------------------------------------------------------------------ Pillow 侧
_WEIGHT_AXIS = ("weight", "wght")


def _axis_name(ax):
    """轴名统一成小写 str。Pillow 某些版本返回 bytes（b'Weight'），
    直接 str() 会得到 "b'weight'"，与 "weight" 匹配不上 —— 字重就静默失效。"""
    name = ax.get("name", "")
    if isinstance(name, bytes):
        name = name.decode("utf-8", "replace")
    return str(name).strip().lower()


def load(preset, role, size, weight=400, quiet=False):
    """给 Pillow 用的字体对象。可变字体（思源）按 weight 轴取实例。

    非可变字体（霞鹜文楷 Regular）无法真的加粗 —— 需要"粗"而字体没有粗体时，
    调用方可以靠 `stroke_width` 描边补一点视觉重量（见 make_assets 的用法）。
    """
    from PIL import ImageFont
    path = pick(preset, role, quiet=quiet)
    if not path:
        return ImageFont.load_default()
    try:
        f = ImageFont.truetype(path, int(size))
    except Exception:                                # noqa: BLE001
        return ImageFont.load_default()
    return _apply_weight(f, weight)


def _apply_weight(f, weight):
    try:
        axes = f.get_variation_axes() or []
    except Exception:                                # noqa: BLE001
        return f
    if not axes:
        return f
    vals = []
    for ax in axes:
        if _axis_name(ax) in _WEIGHT_AXIS:
            vals.append(max(ax.get("minimum", 400),
                            min(ax.get("maximum", 900), weight)))
        else:
            vals.append(ax.get("default", 0))
    try:
        f.set_variation_by_axes(vals)
    except Exception:                                # noqa: BLE001
        pass
    return f


# ---------------------------------------------------------------- 浏览器侧
def _url(path):
    return "file:///" + os.path.abspath(path).replace("\\", "/").lstrip("/")


def _weight_range(path):
    """可变字体给一个字重区间，静态字体给固定值。猜错不致命，浏览器会回退。"""
    low, high = 400, 700
    try:
        from PIL import ImageFont
        f = ImageFont.truetype(path, 12)
        for ax in (f.get_variation_axes() or []):
            if _axis_name(ax) in _WEIGHT_AXIS:
                low = int(ax.get("minimum", 400))
                high = int(ax.get("maximum", 900))
    except Exception:                                # noqa: BLE001
        pass
    return low, high


def families(preset):
    """返回 (title 字体族名, body 字体族名)。"""
    return (FAMILY_TPL.format(preset=preset, role="title"),
            FAMILY_TPL.format(preset=preset, role="body"))


def face_css(preset, roles=("title", "body")):
    """给浏览器用的 @font-face 文本。

    字体文件用 file:// 绝对路径引用 —— 渲染页是临时目录里的 file:// 文档，
    复制 20MB 字体过去不划算，直接指过来，配合 `--allow-file-access-from-files`。
    """
    blocks = []
    for role in roles:
        path = pick(preset, role, quiet=True)
        if not path:
            continue
        lo, hi = _weight_range(path)
        fmt = "woff2" if path.lower().endswith(".woff2") else (
            "opentype" if path.lower().endswith((".otf", ".otc"))
            else "truetype")
        blocks.append(
            "@font-face{{font-family:'{fam}';src:url('{url}') format('{fmt}');"
            "font-weight:{lo} {hi};font-display:block;}}".format(
                fam=FAMILY_TPL.format(preset=preset, role=role),
                url=_url(path), fmt=fmt, lo=lo, hi=hi))
    return "\n".join(blocks)


def css_stack(preset, role="body", fallback=None):
    """完整的 font-family 声明值（含兜底）。"""
    fam = families(preset)[0 if role == "title" else 1]
    tail = fallback or ("'PingFang SC','Microsoft YaHei',sans-serif")
    return "'{}',{}".format(fam, tail)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="字体预设自检")
    ap.add_argument("--preset", default=None, help="只看某一套")
    args = ap.parse_args()
    ids = [args.preset] if args.preset else list(PRESETS)
    print("字体查找目录：")
    for d in font_dirs():
        print("  - " + d)
    print()
    for pid in ids:
        spec = PRESETS.get(pid)
        if not spec:
            print("[x] 未登记的预设：{}".format(pid))
            continue
        f = preset_files(pid)
        mark = "OK " if (f["title"] and f["body"]) else "-- "
        print("{}{:<8} {}".format(mark, pid, spec["label"]))
        for role in ("title", "body"):
            print("      {:<5} {}".format(role, f[role] or "（缺）"))


if __name__ == "__main__":
    main()
