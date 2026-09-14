#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仓库自检。本地开发与 CI 共用，零第三方依赖。

检查项：
  1. 技能必需文件是否齐全
  2. SKILL.md frontmatter 是否合法（name / description，name 是否与目录名一致）
  3. VERSION 是否为语义化版本，且 CHANGELOG 中是否有对应条目
  4. 所有 Python 脚本能否通过语法编译
  5. 是否存在泄露的密钥（AppID / AppSecret 形态）
  6. SKILL.md 中引用的仓库内相对路径是否真实存在
  7. 风格预设是否与文件名、token 字典、模板占位符三方一致

退出码：0 = 全部通过，1 = 存在 FAIL。

用法：
    python scripts/validate_skill.py
    python scripts/validate_skill.py --quiet     # 只输出问题
"""

import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 技能必需文件（相对仓库根） ----------------------------------------------
REQUIRED = [
    "SKILL.md",
    "README.md",
    "LICENSE",
    "VERSION",
    "CHANGELOG.md",
    "scripts/publish.py",
    "scripts/preflight.py",
    "scripts/enhance_content.py",
    "scripts/apply_style.py",
    "scripts/watch_ip.py",
    "scripts/make_assets.py",
    "references/wechat-api-reference.md",
    "references/style-presets.md",
    "assets/templates/article.html",
    "assets/templates/article.template.html",
    "assets/templates/config.example.json",
]

# ---- 风格预设：至少要有一条，且字段齐全 --------------------------------------
STYLE_TOKEN_KEYS = {
    "primary", "primary_soft", "text", "text_strong", "muted", "border",
    "card_bg", "code_bg", "code_text", "table_head_bg", "table_head_text",
    "font_size", "line_height", "letter_spacing", "radius", "para_margin",
}

# ---- 扫描时跳过的目录 --------------------------------------------------------
SKIP_DIRS = {
    ".git", "__pycache__", "dist", "build", ".venv", "venv", "env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "tmp", "sandbox",
}

# ---- 密钥扫描：这些文件允许出现占位值 ----------------------------------------
SECRET_SCAN_SKIP = {"config.example.json"}
SECRET_SCAN_EXTS = {".py", ".json", ".md", ".yml", ".yaml", ".html", ".txt", ".sh", ".ps1", ".bat", ""}

APPID_RE = re.compile(r"\bwx[0-9a-fA-F]{16}\b")
APPSECRET_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")

def is_placeholder(val):
    """判断是否为占位/演示值：wx0000...（AppID 骨架）或全 0（AppSecret 骨架）。"""
    core = val[2:] if val.lower().startswith("wx") else val
    return len(set(core.lower())) <= 1

# SKILL.md 中被视为「仓库内资源」的引用前缀
RESOURCE_PREFIXES = ("scripts/", "references/", "assets/templates/")
RESOURCE_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|json|html|png|jpg|txt|yml|yaml))`")

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

results = []  # (level, title, detail)


def ok(title, detail=""):
    results.append(("OK", title, detail))


def fail(title, detail=""):
    results.append(("FAIL", title, detail))


def warn(title, detail=""):
    results.append(("WARN", title, detail))


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def walk_files():
    """遍历仓库内文件，跳过忽略目录。"""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield os.path.join(dirpath, name)


# ---- 1. 必需文件 -------------------------------------------------------------
def check_required():
    missing = [p for p in REQUIRED if not os.path.isfile(os.path.join(ROOT, p))]
    if missing:
        fail("必需文件齐全", "缺失：" + "、".join(missing))
    else:
        ok("必需文件齐全", "{} 个".format(len(REQUIRED)))


# ---- 2. SKILL.md frontmatter -------------------------------------------------
def check_frontmatter():
    path = os.path.join(ROOT, "SKILL.md")
    if not os.path.isfile(path):
        return
    text = read(path)

    if not text.startswith("---"):
        fail("SKILL.md frontmatter", "文件未以 `---` 开头，缺少 YAML frontmatter")
        return

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        fail("SKILL.md frontmatter", "frontmatter 未正确闭合")
        return

    block = m.group(1)
    fields = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()

    problems = []
    if not fields.get("name"):
        problems.append("缺 name")
    if not fields.get("description"):
        problems.append("缺 description")

    dirname = os.path.basename(ROOT)
    if fields.get("name") and fields["name"] != dirname:
        problems.append("name({}) 与目录名({}) 不一致".format(fields["name"], dirname))

    desc = fields.get("description", "")
    if desc and len(desc) < 20:
        problems.append("description 过短（{} 字），可能触发不了技能".format(len(desc)))

    if problems:
        fail("SKILL.md frontmatter", "；".join(problems))
    else:
        ok("SKILL.md frontmatter", "name={} / description {} 字".format(fields["name"], len(desc)))


# ---- 3. 版本一致性 -----------------------------------------------------------
def check_version():
    vpath = os.path.join(ROOT, "VERSION")
    if not os.path.isfile(vpath):
        return
    version = read(vpath).strip()
    if not SEMVER_RE.match(version):
        fail("VERSION 格式", "「{}」不是 语义化版本 x.y.z".format(version))
        return

    cpath = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.isfile(cpath):
        ctext = read(cpath)
        if "[{}]".format(version) not in ctext:
            fail("版本一致性", "CHANGELOG.md 中没有 [{}] 条目".format(version))
            return
    ok("版本一致性", "v{} 与 CHANGELOG 一致".format(version))


# ---- 4. Python 语法 ----------------------------------------------------------
def check_python_syntax():
    bad = []
    count = 0
    for path in walk_files():
        if not path.endswith(".py"):
            continue
        count += 1
        try:
            compile(read(path), path, "exec")
        except SyntaxError as e:
            bad.append("{}:{} {}".format(os.path.relpath(path, ROOT), e.lineno, e.msg))
        except Exception as e:  # 编码错误等
            bad.append("{}: {}".format(os.path.relpath(path, ROOT), e))

    if bad:
        fail("Python 语法", "；".join(bad))
    else:
        ok("Python 语法", "{} 个脚本编译通过".format(count))


# ---- 5. 密钥扫描 -------------------------------------------------------------
def check_secrets():
    hits = []
    checked = 0
    for path in walk_files():
        name = os.path.basename(path)
        if name in SECRET_SCAN_SKIP:
            continue
        if os.path.splitext(name)[1].lower() not in SECRET_SCAN_EXTS:
            continue
        # 跳过本文件自身（里面的正则会自匹配）
        if os.path.abspath(path) == os.path.abspath(__file__):
            continue
        checked += 1
        try:
            text = read(path)
        except (UnicodeDecodeError, OSError):
            continue

        rel = os.path.relpath(path, ROOT)
        for i, line in enumerate(text.splitlines(), 1):
            for label, rx in (("AppID", APPID_RE), ("疑似 AppSecret", APPSECRET_RE)):
                for m in rx.finditer(line):
                    val = m.group(0)
                    if is_placeholder(val):
                        continue
                    # 文档中的示例明示（如 wx 开头 18 位 的描述行）
                    if "示例" in line or "形如" in line or "例如" in line:
                        continue
                    hits.append("{}:{} {} {}".format(rel, i, label, val[:8] + "…"))

    if hits:
        fail("密钥扫描", "发现 {} 处可疑明文：{}".format(len(hits), "；".join(hits)))
    else:
        ok("密钥扫描", "{} 个文件无泄露".format(checked))


# ---- 6. SKILL.md 引用路径 ----------------------------------------------------
def check_references():
    path = os.path.join(ROOT, "SKILL.md")
    if not os.path.isfile(path):
        return
    text = read(path)
    refs = set()
    for m in RESOURCE_RE.finditer(text):
        ref = m.group(1)
        if ref.startswith(RESOURCE_PREFIXES):
            refs.add(ref)

    missing = sorted(r for r in refs if not os.path.exists(os.path.join(ROOT, r)))
    if missing:
        fail("SKILL.md 引用路径", "指向不存在的文件：" + "、".join(missing))
    else:
        ok("SKILL.md 引用路径", "{} 处引用全部有效".format(len(refs)))


# ---- 7. 风格预设 -------------------------------------------------------------
def check_styles():
    """预设要与文件名、token 字典、模板占位符三方对齐，否则渲染会报错或静默漏色。"""
    sdir = os.path.join(ROOT, "assets", "styles")
    if not os.path.isdir(sdir):
        fail("风格预设", "assets/styles/ 目录不存在")
        return
    files = sorted(glob.glob(os.path.join(sdir, "*.json")))
    if not files:
        fail("风格预设", "assets/styles/ 下没有任何预设")
        return

    problems = []
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            data = json.loads(read(path))
        except ValueError as e:
            problems.append("{} 不是合法 JSON：{}".format(name, e))
            continue
        if data.get("id") != name:
            problems.append("{} 的 id 字段是「{}」，与文件名不一致".format(
                name, data.get("id")))
        missing = sorted(STYLE_TOKEN_KEYS - set((data.get("tokens") or {}).keys()))
        if missing:
            problems.append("{} 缺 token：{}".format(name, "、".join(missing)))
        if not (data.get("writing") or {}).get("tone"):
            problems.append("{} 的 writing.tone 为空".format(name))

    tpl = os.path.join(ROOT, "assets", "templates", "article.template.html")
    if os.path.isfile(tpl):
        body = re.sub(r"<!--.*?-->", "", read(tpl), flags=re.S)
        ph = set(re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", body))
        unknown = sorted(ph - STYLE_TOKEN_KEYS)
        unused = sorted(STYLE_TOKEN_KEYS - ph)
        if unknown:
            problems.append("模板用了未定义的占位符：" + "、".join(unknown))
        if unused:
            problems.append("token 没被模板用到：" + "、".join(unused))
    else:
        problems.append("缺少 assets/templates/article.template.html")

    if problems:
        fail("风格预设", "；".join(problems))
    else:
        ok("风格预设", "{} 条，与 token 字典、模板占位符三方一致".format(len(files)))


# ---- main -------------------------------------------------------------------
def main():
    quiet = "--quiet" in sys.argv or "-q" in sys.argv

    print("=" * 64)
    print("  wechat-mp-publisher · 仓库自检")
    print("  根目录：{}".format(ROOT))
    print("=" * 64)

    for fn in (check_required, check_frontmatter, check_version,
               check_python_syntax, check_secrets, check_references, check_styles):
        try:
            fn()
        except Exception as e:  # 自检器自身不应崩
            fail(fn.__name__, "自检器异常：{}".format(e))

    tag = {"OK": "  OK  ", "WARN": " WARN ", "FAIL": " FAIL "}
    for level, title, detail in results:
        if quiet and level == "OK":
            continue
        line = "[{}] {}".format(tag[level], title)
        if detail:
            line += "  —  {}".format(detail)
        print(line)

    fails = sum(1 for r in results if r[0] == "FAIL")
    warns = sum(1 for r in results if r[0] == "WARN")
    print("-" * 64)
    if fails:
        print("结果：失败 {} 项，警告 {} 项".format(fails, warns))
        return 1
    print("结果：全部通过（{} 项检查，{} 项警告）".format(len(results), warns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
