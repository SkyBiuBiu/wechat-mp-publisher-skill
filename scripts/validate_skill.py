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
  7. 主题注册表（references/theme-index.md）与主题组件库文件是否一一对应
  8. 组件库源头无反模式（复用 component_lint.py —— 可验证循环的第一关）
  9. 封面规格与配色（几何单一来源、六主题角色无静默回退、点睛色是否上场）
  10. 上游（gzh-design-skill, AGPL-3.0）署名与授权文件是否在位

退出码：0 = 全部通过，1 = 存在 FAIL。

用法：
    python scripts/validate_skill.py
    python scripts/validate_skill.py --quiet     # 只输出问题
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

if HERE not in sys.path:
    sys.path.insert(0, HERE)

# ---- 技能必需文件（相对仓库根） ----------------------------------------------
THEMES = [
    "moyu-green", "red-white", "graphite-minimal",
    "zen-whitespace", "moyu-ticket", "olive-journal",
]

REQUIRED = [
    "SKILL.md",
    "README.md",
    "LICENSE",
    "LICENSE-gzh-design",
    "VERSION",
    "CHANGELOG.md",
    # 脚本层
    "scripts/publish.py",           # 发布链路（微信 API）
    "scripts/preflight.py",         # 接口侧硬约束体检
    "scripts/render_mermaid.py",    # 排版前的 mermaid 预渲染
    "scripts/make_assets.py",       # 封面生成
    "scripts/cover_spec.py",        # 封面几何规格与主题皮肤（make_assets 的依赖）
    "scripts/cover_wall.py",        # 封面墙（全部主题并排验收）
    "scripts/theme_vars.py",        # 主题变量表解析（插图/封面/代码块共用）
    "scripts/watch_ip.py",          # IP 白名单监听
    "scripts/build_zip.py",         # 打包
    "scripts/validate_skill.py",    # 本文件
    # 排版层（上游 gzh-design-skill，原样搬运）
    "scripts/validate_gzh_html.py",  # 产物关
    "scripts/component_lint.py",     # 源头关
    "scripts/wrap_preview.py",       # 一键复制预览页
    "scripts/extract_docx.py",       # docx → markdown
    "references/theme-index.md",
    "references/common-components.md",
    "references/theme-generator.md",
    "references/format-normalize.md",
    "references/eval-cases.md",
    "references/wechat-api-reference.md",
    "assets/preview-template.html",
    "assets/sample-article.md",
    "assets/templates/config.example.json",
] + ["references/theme-{}.md".format(t) for t in THEMES]

# ---- 已删除的旧链路资产：留在这里是防止有人"顺手加回来" ----------------------
RETIRED = [
    "assets/styles",
    "scripts/apply_style.py",
    "scripts/enhance_content.py",
    "references/style-presets.md",
    "assets/templates/article.html",
    "assets/templates/article.template.html",
]

# ---- 扫描时跳过的目录 --------------------------------------------------------
SKIP_DIRS = {
    ".git", "__pycache__", "dist", "build", ".venv", "venv", "env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "tmp", "sandbox",
}

# ---- 密钥扫描 -----------------------------------------------------------------
SECRET_SCAN_SKIP = {"config.example.json"}
SECRET_SCAN_SKIP_RE = re.compile(r"^\.token_cache.*\.json$")
SECRET_SCAN_EXTS = {".py", ".json", ".md", ".yml", ".yaml", ".html", ".txt",
                    ".sh", ".ps1", ".bat", ""}

APPID_RE = re.compile(r"\bwx[0-9a-fA-F]{16}\b")
APPSECRET_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")


def is_placeholder(val):
    """占位/演示值：wx0000...（AppID 骨架）或全 0（AppSecret 骨架）。"""
    core = val[2:] if val.lower().startswith("wx") else val
    return len(set(core.lower())) <= 1


RESOURCE_PREFIXES = ("scripts/", "references/", "assets/")
RESOURCE_RE = re.compile(r"`([A-Za-z0-9_./{}-]+\.(?:py|md|json|html|png|jpg|txt|yml|yaml|docx|pdf))`")
# 文档里的示意路径（assets/xx.png、mermaid-N.png 之类）不是真实引用，跳过
PLACEHOLDER_PATH_RE = re.compile(r"(x{2,}|-N\.|\{|\bmy-|\b示例|\bsample_)", re.I)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

results = []  # (level, title, detail)


def ok(title, detail=""):
    results.append(("OK", title, detail))


def fail(title, detail=""):
    results.append(("FAIL", title, detail))


def warn(title, detail=""):
    results.append(("WARN", title, detail))


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def walk_files():
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

    leftover = [p for p in RETIRED if os.path.exists(os.path.join(ROOT, p))]
    if leftover:
        fail("旧链路资产已清退",
             "这些文件属于已被推翻的旧排版/校验链路，不该再出现：" + "、".join(leftover))
    else:
        ok("旧链路资产已清退", "{} 项".format(len(RETIRED)))


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

    fields = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
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
        ok("SKILL.md frontmatter",
           "name={} / description {} 字".format(fields["name"], len(desc)))


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
    if os.path.isfile(cpath) and "[{}]".format(version) not in read(cpath):
        fail("版本一致性", "CHANGELOG.md 中没有 [{}] 条目".format(version))
        return
    ok("版本一致性", "v{} 与 CHANGELOG 一致".format(version))


# ---- 4. Python 语法 ----------------------------------------------------------
def check_python_syntax():
    bad, count = [], 0
    for path in walk_files():
        if not path.endswith(".py"):
            continue
        count += 1
        try:
            compile(read(path), path, "exec")
        except SyntaxError as e:
            bad.append("{}:{} {}".format(os.path.relpath(path, ROOT), e.lineno, e.msg))
        except Exception as e:                       # noqa: BLE001
            bad.append("{}: {}".format(os.path.relpath(path, ROOT), e))

    if bad:
        fail("Python 语法", "；".join(bad))
    else:
        ok("Python 语法", "{} 个脚本编译通过".format(count))


# ---- 5. 密钥扫描 -------------------------------------------------------------
def check_secrets():
    hits, checked = [], 0
    for path in walk_files():
        name = os.path.basename(path)
        if name in SECRET_SCAN_SKIP or SECRET_SCAN_SKIP_RE.match(name):
            continue
        if os.path.splitext(name)[1].lower() not in SECRET_SCAN_EXTS:
            continue
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
                    if "示例" in line or "形如" in line or "例如" in line:
                        continue
                    hits.append("{}:{} {} {}".format(rel, i, label, val[:8] + "…"))

    if hits:
        fail("密钥扫描", "发现 {} 处可疑明文：{}".format(len(hits), "；".join(hits)))
    else:
        ok("密钥扫描", "{} 个文件无泄露".format(checked))


# ---- 6. 文档引用路径 ---------------------------------------------------------
def check_references():
    missing_all = []
    total = 0
    for name in ("SKILL.md", "README.md", "docs/manual.md"):
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            continue
        refs = set()
        for m in RESOURCE_RE.finditer(read(path)):
            ref = m.group(1)
            if not ref.startswith(RESOURCE_PREFIXES):
                continue
            if "{" in ref or PLACEHOLDER_PATH_RE.search(ref):
                continue          # 示意路径，不是真实引用
            refs.add(ref)
        total += len(refs)
        missing_all += ["{} → {}".format(name, r) for r in sorted(refs)
                        if not os.path.exists(os.path.join(ROOT, r))]

    if missing_all:
        fail("文档引用路径", "指向不存在的文件：" + "、".join(missing_all))
    else:
        ok("文档引用路径", "{} 处引用全部有效".format(total))


# ---- 7. 主题注册表一致性 -----------------------------------------------------
def check_themes():
    index = os.path.join(ROOT, "references", "theme-index.md")
    if not os.path.isfile(index):
        return
    text = read(index)
    # theme-index.md 自己会引用 theme-generator.md，那不算一套主题
    registered = set(re.findall(r"theme-([A-Za-z0-9_-]+)\.md", text)) - {"generator"}

    missing = sorted(t for t in registered
                     if not os.path.isfile(os.path.join(
                         ROOT, "references", "theme-{}.md".format(t))))
    unregistered = sorted(t for t in THEMES if t not in registered)
    if missing:
        fail("主题注册表", "注册了但组件库不存在：" + "、".join(missing))
        return
    if unregistered:
        fail("主题注册表", "组件库存在但未登记到 theme-index.md：" + "、".join(unregistered))
        return
    ok("主题注册表", "{} 套主题与组件库一一对应".format(len(registered)))


# ---- 8. 组件库源头关（复用 component_lint.py） --------------------------------
def check_component_lint():
    try:
        import component_lint
    except ImportError as e:
        fail("组件库源头关", "无法加载 component_lint.py：{}".format(e))
        return

    import glob
    refs = sorted(glob.glob(os.path.join(ROOT, "references", "*.md")))
    if not refs:
        fail("组件库源头关", "references/ 下没有 .md")
        return

    total_err, total_warn, clean, details = 0, 0, 0, []
    for path in refs:
        name, found = component_lint.lint_file(path)
        if not found:
            clean += 1
            continue
        errs = [m for lv, m in found if lv == "ERROR"]
        warns = [m for lv, m in found if lv == "WARN"]
        total_err += len(errs)
        total_warn += len(warns)
        for m in errs:
            details.append("{}: {}".format(name, m))

    if total_err:
        fail("组件库源头关", "ERROR×{} —— {}".format(total_err, "；".join(details[:4])))
    elif total_warn:
        warn("组件库源头关", "{} 个库干净；WARN×{} 为上游主题特征用的虚线框"
             "（摸鱼绿 quote-box / 橄榄手记），属 SKILL.md 已声明的例外"
             .format(clean, total_warn))
    else:
        ok("组件库源头关", "{} 个库全部无反模式".format(len(refs)))


# ---- 9. 封面规格与配色（几何单一来源 + 点睛色不许静默失效） -------------------
def check_cover_spec():
    """封面的两道护栏。

    为什么需要它：封面长期有两个**不报错**的毛病 ——
      · 几何散在 make_cover 的绘制逻辑里，改多了就漂开，没人能断言"规格是什么"；
      · 主题登记的强调色一直没被用上（橄榄手记 `#ed7b2f`、石墨极简 `#F97316`），
        主色是墨黑/石墨灰的主题封面因此整张没有颜色，且**不报错**。
    下面把这两件事变成可自动判定的项。判定依据写在每条的注释里。
    """
    try:
        import cover_spec
        import theme_vars
    except ImportError as e:
        fail("封面规格", "无法加载 cover_spec.py / theme_vars.py：{}".format(e))
        return

    # ① 规格自身的一致性：比例、元素是否出画布、基线顺序、环形意象位置
    probs = cover_spec.spec_problems()
    if probs:
        fail("封面规格", "；".join(probs[:4]))
    else:
        c = cover_spec.SPEC["canvas"]
        ok("封面规格", "几何自洽（画布 {}x{} @{}x，比例 {:.2f}:1）".format(
            c["w"], c["h"], c["scale"], float(c["w"]) / c["h"]))

    # ② 画布比例必须与 preflight 的判定同源 —— 那是微信列表页裁切的硬约束，
    #    两处各写一个数就会漂；这里直接从 preflight.py 读出来比对
    pf = os.path.join(HERE, "preflight.py")
    m = re.search(r"COVER_RATIO\s*=\s*([0-9.]+)", read(pf)) if os.path.isfile(pf) else None
    if not m:
        warn("封面对齐 preflight", "读不到 preflight.COVER_RATIO，跳过比对")
    else:
        want = float(m.group(1))
        have = float(cover_spec.SPEC["canvas"]["w"]) / cover_spec.SPEC["canvas"]["h"]
        if abs(have - want) > 0.02:
            fail("封面对齐 preflight", "画布比例 {:.2f} 与 COVER_RATIO {:.2f} 不一致".format(have, want))
        else:
            ok("封面对齐 preflight", "画布比例与 WX108 判定同源（{:.2f}:1）".format(want))

    # ③ 六套主题的封面角色必须**全部**取到值：任一为 None 都会静默回退兜底色
    roles = ("primary", "title", "body", "aux", "light", "accent")
    bad, fallen = [], []
    for tid in THEMES:
        t = theme_vars.asset_theme(tid)
        if not t:
            bad.append("{}(整体取不到配色)".format(tid))
            continue
        miss = [r for r in roles if t.get(r) is None]
        if miss:
            bad.append("{}（缺 {}）".format(tid, "/".join(miss)))
        elif not t["accent_own"]:
            fallen.append(tid)
    if bad:
        fail("封面配色角色", "；".join(bad))
    else:
        ok("封面配色角色", "{} 套主题的 {} 个角色全部命中".format(len(THEMES), len(roles)))

    # ④ 主题**登记了点睛色**时，点睛色不许等于主色 —— 等于就等于没用上。
    #    没登记点睛色的主题（摸鱼绿/红白/摸鱼票据风）豁免，不需要人工维护白名单：
    #    判定条件是"速查表里能不能解析出 accent"，自动成立。
    unused = []
    for tid in THEMES:
        t = theme_vars.tokens(tid, "cover")
        if t["pairs"] and t["accent"]:
            got = theme_vars.asset_theme(tid)
            if got and got["accent"] == got["primary"]:
                unused.append("{}({})".format(tid, t["accent"]))
    if unused:
        fail("点睛色是否上场", "登记了点睛色却与主色相同：" + "、".join(unused))
    else:
        ok("点睛色是否上场", "登记了点睛色的主题都已用上{}".format(
            "；未登记、按设计回退主色的：" + "、".join(sorted(fallen)) if fallen else ""))

    # ⑤ 皮肤表只能登记"已注册主题"，否则是漏登记 theme-index.md
    index = os.path.join(ROOT, "references", "theme-index.md")
    if os.path.isfile(index):
        registered = set(re.findall(r"theme-([A-Za-z0-9_-]+)\.md", read(index))) - {"generator"}
        extra = sorted(set(cover_spec.THEME_SKINS) - registered)
        if extra:
            fail("封面皮肤表", "皮肤表里有未注册主题：" + "、".join(extra))
        else:
            ok("封面皮肤表", "{} 套皮肤与主题注册表一致".format(len(cover_spec.THEME_SKINS)))

    # ⑥ 几何不许回潮：make_cover 里不该再出现字面坐标（一律读 SPEC）。
    #    只查这个函数 —— 底纹/插图的内部比例不属于封面规格。
    src = read(os.path.join(HERE, "make_assets.py"))
    m = re.search(r"\ndef make_cover\(.*?(?=\ndef |\Z)", src, re.S)
    if m:
        lits = re.findall(r"(?<![\w.])\d+(?:\.\d+)?\s*\*\s*S", m.group(0))
        if lits:
            warn("封面几何收口", "make_cover 里仍有字面坐标 {} 处（{}）——"
                 "应先收进 cover_spec.SPEC".format(len(lits), "、".join(sorted(set(lits))[:5])))
        else:
            ok("封面几何收口", "make_cover 全部坐标读自 SPEC")


# ---- 10. 上游署名 -------------------------------------------------------------
def check_upstream():
    lic = os.path.join(ROOT, "LICENSE-gzh-design")
    if not os.path.isfile(lic):
        fail("上游署名", "缺少 LICENSE-gzh-design（上游 AGPL-3.0 授权原文）")
        return
    lic_text = read(lic)
    if "AGPL" not in lic_text.upper():
        warn("上游署名", "LICENSE-gzh-design 里没看到 AGPL 字样，确认一下是不是拿错了文件")

    rtext = read(os.path.join(ROOT, "README.md")) if \
        os.path.isfile(os.path.join(ROOT, "README.md")) else ""
    if "isjiamu/gzh-design-skill" not in rtext:
        warn("上游署名", "README.md 里没写上游仓库地址（isjiamu/gzh-design-skill）")
    else:
        ok("上游署名", "授权原文与来源声明均在位")


# ---- main -------------------------------------------------------------------
def main():
    quiet = "--quiet" in sys.argv or "-q" in sys.argv

    print("=" * 66)
    print("  wechat-mp-publisher-skill · 仓库自检")
    print("  根目录：{}".format(ROOT))
    print("=" * 66)

    for fn in (check_required, check_frontmatter, check_version,
               check_python_syntax, check_secrets, check_references,
               check_themes, check_component_lint, check_cover_spec,
               check_upstream):
        try:
            fn()
        except Exception as e:                       # noqa: BLE001
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
    print("-" * 66)
    if fails:
        print("结果：失败 {} 项，警告 {} 项".format(fails, warns))
        return 1
    print("结果：全部通过（{} 项检查，{} 项警告）".format(len(results), warns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
