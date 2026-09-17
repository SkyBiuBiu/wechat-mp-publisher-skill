#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「同一段代码 × 多套主题」的着色对照页（需先跑 highlight_code.py，零依赖）。

**为什么要有这个工具**
--------------------
`highlight_code.py --show-palette --all-themes` 打印的是色值，色值看不出"扎不扎眼"——
`#A1D9C7` 和 `#D9B8A1` 谁刺眼，只能眼睛看。这个工具把同一段代码在每套主题下都排一遍，
一页翻完即可确认两件事：

  1. **配色确实跟着主题走**（换主题换色相，不是所有主题都一个色）；
  2. **没有哪套主题的 token 扎眼**（改明度/饱和度常量后回归看这个）。

顺带也是"自定义主题是否自动适配"的验收口：新主题登记进 `theme-index.md` 后重跑，
它应该自动出现在页面里、并且用的是它自己的色相。

用法：
    python tools/make_code_preview.py                       # 全部已注册主题 + 内置样例代码
    python tools/make_code_preview.py -o /tmp/x.html
    python tools/make_code_preview.py --code-file demo.py --lang python
    python tools/make_code_preview.py --themes moyu-green,olive-journal
    python tools/make_code_preview.py --style light          # 出通用库 1b 浅色版
"""

import argparse
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFS = os.path.join(ROOT, "references")
INDEX = os.path.join(REFS, "theme-index.md")
HL = os.path.join(HERE, "..", "scripts", "highlight_code.py")

# 内置样例：刻意覆盖注释 / 字符串 / 数字 / 关键字 / 函数 / 运算符，能一眼比出 token 差异
SAMPLE = '''# Agent Loop 骨架：七步里只有第 2 步属于模型
messages = [system_prompt, user_input]

for step in range(max_steps):                      # 预算护栏，不在七步之内
    ctx = trim(messages, token_budget)             # 1 组装上下文
    resp = model.chat(ctx, tools=tool_schemas)     # 2 模型决策

    if not resp.tool_calls:                        # 3 终止判断
        return resp.content

    for call in resp.tool_calls:
        args = validate(call, schemas)             # 4 意图解析
        result = registry.execute(args)            # 5 执行工具 / 检索
        messages.append(observation(args, result)) # 6 结果回填
    compact(messages)                              # 7 记忆更新
'''

# theme-index.md 里没有"这套主题的色相从哪来"这种注解，人工补一句可读性说明。
# 未列出的主题（含自定义主题）自动留空，不影响生成。
NOTES = {
    "moyu-green": "主色即身份，关键词取主色相的绿",
    "moyu-ticket": "主色同为绿 #059669，但组件库气质不同",
    "red-white": "主色红 #DC2626",
    "olive-journal": "主色是墨黑 #1e1f23，彩度 0.020 → 色相不可信，取点睛橙 #ed7b2f",
    "graphite-minimal": "主色是石墨灰 #52525B，彩度 0.035 → 同样落到点睛橙 #F97316",
    "zen-whitespace": "墨绿 #4A5D52 彩度仅 0.075，判为有色 → 取到自己的绿",
}


def registered_themes():
    """从 theme-index.md 取 (标识, 中文名)，保持文件顺序。"""
    if not os.path.isfile(INDEX):
        sys.exit("[X] 读不到主题索引：{}".format(INDEX))
    text = io.open(INDEX, encoding="utf-8").read()
    rows = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= set("-: "):
            continue
        m = re.search(r"theme-([A-Za-z0-9_-]+)\.md", cells[3])
        if m and cells[0] != "主题":
            rows.append((m.group(1), cells[0]))
    return rows


def render_block(tid, code_file, lang, style, scheme):
    cmd = [sys.executable, HL]
    if code_file:
        cmd += ["--code-file", code_file]
    else:
        cmd += ["-"]
    cmd += ["--lang", lang, "--theme", tid, "--style", style, "--scheme", scheme]
    if code_file:
        p = subprocess.run(cmd, capture_output=True, cwd=ROOT)
    else:
        p = subprocess.run(cmd, capture_output=True, cwd=ROOT,
                           input=SAMPLE.encode("utf-8"))
    if p.returncode != 0 or not p.stdout.strip():
        err = (p.stderr or b"").decode("utf-8", "replace").strip()
        print("[!] {} 渲染失败：{}".format(tid, err[-200:]), file=sys.stderr)
        return None
    return p.stdout.decode("utf-8").strip()


PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>代码块着色 · 主题对照</title>
<style>
body{{margin:0;padding:32px 24px 64px;background:#F1F5F9;
font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;
color:#0F172A;-webkit-font-smoothing:antialiased;}}
/* 页面按**手机正文宽度**排版，不是按桌面。用 760px 排版会得出
   "75 列也放得下、不用滑"的错误结论 —— 手机上正文只有 328px。 */
.wrap{{max-width:328px;margin:0 auto;}}
h1{{font-size:18px;margin:0 0 8px;letter-spacing:-0.2px;line-height:1.5;}}
.lead{{font-size:13px;color:#475569;line-height:1.85;margin:0 0 4px;}}
.lead code{{background:#E2E8F0;padding:1px 4px;border-radius:3px;font-size:12px;
font-family:Consolas,Monaco,monospace;}}
.case{{margin:36px 0 0;}}
.case h2{{font-size:15px;margin:0 0 3px;}}
.tid{{font-size:12px;color:#94A3B8;font-family:Consolas,Monaco,monospace;
font-weight:400;margin-left:6px;}}
.note{{font-size:13px;color:#64748B;margin:0 0 10px;line-height:1.7;}}
</style></head><body><div class="wrap">
<h1>代码块按语言着色 · 同一段代码 × {n} 套主题</h1>
<p class="lead">本页宽度就是手机正文宽度 328px，所以每一块代码都是它在手机上的真实样子
—— 超宽的那几块会横滑（顶栏右侧有「👉 左右滑动」），而不是折行。</p>
<p class="lead">配色由主题库的「设计变量速查表」推导：<strong>关键词留在主色相本身</strong>
（保住主题身份），函数 / 数字 / 字符串 / 内置 / 类型依次取 +35° / +70° / +140° /
+195° / +262°；六个色相同处一个明度带（<code>L≈0.68~0.78</code>）与一个饱和度带
（<code>S≈0.45~0.62</code>）—— 丰富来自色相，秩序来自明度与饱和度。
主色是墨黑/灰的主题（色相不可信）会自动改取它登记的点睛强调色。</p>
{body}
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser(
        description="生成「同一段代码 × 多套主题」的着色对照页")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "code-theme-preview.html"),
                    help="输出路径，默认 <skill>/code-theme-preview.html")
    ap.add_argument("--themes", default=None,
                    help="逗号分隔的主题标识；默认取 theme-index.md 里全部已注册主题")
    ap.add_argument("--code-file", default=None, help="用自己的代码文件（默认内置样例）")
    ap.add_argument("--lang", default="python", help="语言标识，默认 python")
    ap.add_argument("--style", choices=["dark", "light"], default="dark",
                    help="dark=通用库 1a（默认）/ light=1b")
    ap.add_argument("--scheme", choices=["rich", "calm"], default="rich",
                    help="rich=色环配色（默认）/ calm=单色克制版")
    args = ap.parse_args()

    if args.themes:
        # 显式给了标识也要尽量配回中文名；不在索引里的（如自定义主题）就显示标识
        known = dict(registered_themes())
        pairs = [(t.strip(), known.get(t.strip(), t.strip()))
                 for t in args.themes.split(",") if t.strip()]
    else:
        pairs = registered_themes()
    if not pairs:
        sys.exit("[X] 没有可用主题")

    chunks = []
    for tid, cn in pairs:
        block = render_block(tid, args.code_file, args.lang, args.style, args.scheme)
        if block is None:
            continue
        # 剥掉溯源注释，预览页不需要
        block = re.sub(r"^\s*<!--.*?-->\s*", "", block, flags=re.S).strip()
        note = NOTES.get(tid, "")
        chunks.append('<section class="case"><h2>{}'
                      '<span class="tid">{}</span></h2>{}'
                      "{}</section>".format(
                          cn, tid,
                          '<p class="note">{}</p>'.format(note) if note else "",
                          block))
        print("[OK] {}（{}）".format(tid, cn))

    if not chunks:
        sys.exit("[X] 一套主题都没渲染出来")

    io.open(args.out, "w", encoding="utf-8", newline="\n").write(
        PAGE.format(n=len(chunks), body="\n".join(chunks)))
    print("[OK] 已写出 {}（{} 套主题，语言 {}，{}）".format(
        args.out, len(chunks), args.lang, args.style))
    print("     → 浏览器打开翻一遍：换主题该换色相；超宽的行该横滑而不是折行；")
    print("       改明度/饱和度常量后回来看有没有扎眼的")


if __name__ == "__main__":
    main()
