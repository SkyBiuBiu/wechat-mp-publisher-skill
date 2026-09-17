#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 README 用的「主题样例」配图。

同一段内容 × 6 套主题，各自用该主题组件库里的真实组件装配，再用本机
Chrome 无头模式截成 PNG。这样 README 上看到的每张图，就是那套主题实际
会排出来的样子 —— 不是示意图。

用法：
    python tools/make_theme_previews.py                 # 全部重生成到 docs/images/
    python tools/make_theme_previews.py --theme moyu-green
    python tools/make_theme_previews.py --keep-html     # 保留中间 HTML 便于排查

依赖：本机 Chrome（脚本会自动找几个常见安装路径）+ pillow（裁剪底部空白）。
改主题库组件后应重跑本脚本，否则 README 配图会与组件库不一致。
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "docs", "images")

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

# 截图宽度（微信正文区约 677px，留点余量）与倍率
WIN_W = 720
SCALE = 2
VIEW_H = 2400          # 先截高一点，再裁掉底部空白


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.isfile(p):
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None


# ---------------------------------------------------------------- 采样内容
# 六套主题共用同一段内容，才能横向对比。文字刻意写短，一屏内看得完。
P_INTRO = (
    '<span leaf="">公众号编辑器会剥掉 </span>'
    '<span style="{code}"><span leaf="">&lt;style&gt;</span></span>'
    '<span leaf="">、</span>'
    '<span style="{code}"><span leaf="">class</span></span>'
    '<span leaf=""> 和大部分现代 CSS，能留下来的只有</span>'
    '<span style="{ul}"><span leaf="">内联样式</span></span>'
    '<span leaf="">。所以排版不是写一份 CSS，而是把</span>'
    '<span style="{ul}"><span leaf="">每个组件展开成一棵挂满 style 属性的 DOM 树</span></span>'
    '<span leaf="">。</span>'
)
P_BODY = (
    '<span leaf="">这套主题库把这件事做成了可复用的零件：章节标题、正文段落、'
    '引用卡、提示条、标签组，各自带着完整的内联样式，拼起来就是一篇成稿。</span>'
)
P_END = '<span leaf="">同一段内容，换一套主题，气质完全不同。</span>'

CODE_GREEN = ("background:#F3F4F6;color:#1F2937;padding:2px 6px;"
              "border-radius:4px;font-size:13px;font-weight:600;")
CODE_OLIVE = ("background:#eeefe9;color:#23251d;padding:2px 6px;border-radius:4px;"
              "font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;"
              "font-size:13px;border:1px solid #b6b7af;")

# 各主题：容器样式 + 章节标题组件 + 段落组件 + 特色组件
THEMES = {
    "moyu-green": {
        "container": ("max-width:677px;margin:0 auto;background:#ffffff;"
                      "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
                      "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
                      "color:#374151;line-height:1.75;letter-spacing:0.5px;"
                      "overflow-x:hidden;"),
        "body": """
  <!-- 组件 4 章节标题 chapter-title -->
  <section style="margin-top:16px;margin-bottom:32px;padding:0 20px;">
    <section style="display:flex;align-items:center;gap:16px;margin-bottom:24px;">
      <section style="text-align:center;flex-shrink:0;">
        <p style="margin:0;font-size:28px;font-weight:900;color:#059669;line-height:1;letter-spacing:-2px;"><span leaf="">01</span></p>
        <p style="margin:0;font-size:8px;font-weight:700;color:#D1D5DB;letter-spacing:2px;"><span leaf="">PART</span></p>
      </section>
      <span style="width:1px;height:36px;background:#E5E7EB;flex-shrink:0;"><span leaf=""><br></span></span>
      <section>
        <p style="margin:0 0 1px;font-size:17px;font-weight:900;color:#111827;letter-spacing:0.3px;"><span leaf="">排版为什么值得单独做一层</span></p>
        <p style="margin:0;font-size:11px;font-weight:600;color:#9CA3AF;letter-spacing:1.5px;"><span leaf="">WHY TYPOGRAPHY</span></p>
      </section>
    </section>
    <!-- 组件 5 正文段落 paragraph -->
    <p style="margin-bottom:16px;font-size:14px;line-height:1.9;text-align:justify;">
      {intro}
    </p>
    <p style="margin-bottom:16px;font-size:14px;line-height:1.9;text-align:justify;">
      {body}
    </p>
    <!-- 组件 9a quote-box -->
    <section style="background:#F9FAFB;border:1px dashed #D1D5DB;border-radius:8px;padding:12px 16px;margin-bottom:24px;text-align:justify;">
      <p style="font-size:13px;color:#374151;margin:0;line-height:1.6;">
        <span leaf="">换主题不用动一个字 —— </span><strong style="color:#059669;"><span leaf="">内容归内容，视觉归视觉</span></strong><span leaf="">。</span>
      </p>
    </section>
    <p style="margin-bottom:16px;font-size:14px;line-height:1.9;text-align:justify;">{end}</p>
  </section>
""",
    },
    "red-white": {
        "container": ("max-width:677px;margin:0 auto;background:#ffffff;"
                      "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
                      "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
                      "color:#374151;line-height:1.75;letter-spacing:0.5px;"
                      "overflow-x:hidden;"),
        "body": """
  <!-- 组件 5 章节标题 -->
  <section style="margin-top:16px;margin-bottom:28px;padding:0 10px;">
    <section style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;padding-bottom:14px;border-bottom:3px solid #DC2626;">
      <section style="display:flex;align-items:center;">
        <span style="display:inline-block;background:#DC2626;color:#FFFFFF;font-size:18px;font-weight:900;padding:4px 14px;border-radius:6px;margin-right:14px;line-height:1.3;"><span leaf="">01</span></span>
        <section>
          <p style="font-size:10px;color:#DC2626;font-weight:700;letter-spacing:3px;margin:0 0 2px;text-transform:uppercase;">
            <span leaf="">WHY TYPOGRAPHY</span>
          </p>
          <h3 style="font-size:18px;font-weight:800;color:#1C1917;margin:0;letter-spacing:0.5px;">
            <span leaf="">排版为什么值得单独做一层</span>
          </h3>
        </section>
      </section>
    </section>
    <!-- 组件 6 正文段落 -->
    <p style="margin-bottom:20px;font-size:15px;line-height:1.8;text-align:justify;">
      {intro}
    </p>
    <p style="margin-bottom:20px;font-size:15px;line-height:1.8;text-align:justify;">
      {body}
    </p>
    <!-- 组件 8a 粉底左竖条金句引用 -->
    <section style="background:#FEF2F2;border-radius:0 10px 10px 0;border-left:4px solid #DC2626;padding:18px 22px;margin-bottom:24px;">
      <p style="font-size:16px;font-weight:800;color:#991B1B;margin:0;line-height:1.8;">
        <span leaf="">「换主题不用动一个字 —— 内容归内容，视觉归视觉。」</span>
      </p>
    </section>
    <p style="margin-bottom:20px;font-size:15px;line-height:1.8;text-align:justify;">{end}</p>
  </section>
""",
    },
    "graphite-minimal": {
        "container": ("max-width:677px;margin:0 auto;background:#FFFFFF;"
                      "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
                      "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
                      "color:#52525B;line-height:1.8;letter-spacing:0.3px;"
                      "overflow-x:hidden;"),
        "body": """
  <!-- 组件 5 章节标题（超大水印编号） -->
  <section style="margin-top:16px;margin-bottom:32px;padding:0 10px;">
    <section style="position:relative;padding-bottom:20px;border-bottom:1px solid #E4E4E7;">
      <p style="font-size:48px;font-weight:900;color:#E4E4E7;margin:0;line-height:1;letter-spacing:-2px;">
        <span leaf="">01</span>
      </p>
      <section style="margin-top:-8px;">
        <p style="font-size:10px;color:#A1A1AA;font-weight:500;letter-spacing:3px;margin:0 0 6px;text-transform:uppercase;">
          <span leaf="">WHY TYPOGRAPHY</span>
        </p>
        <h3 style="font-size:20px;font-weight:800;color:#27272A;margin:0;letter-spacing:0.5px;line-height:1.4;">
          <span leaf="">排版为什么值得单独做一层</span>
        </h3>
      </section>
    </section>
    <!-- 组件 6 正文段落 -->
    <p style="margin-bottom:22px;font-size:15px;line-height:1.8;text-align:justify;color:#52525B;letter-spacing:0.3px;">
      {intro}
    </p>
    <p style="margin-bottom:22px;font-size:15px;line-height:1.8;text-align:justify;color:#52525B;letter-spacing:0.3px;">
      {body}
    </p>
    <!-- 组件 8b 极浅灰底内容引用块 -->
    <section style="background:#FAFAFA;border:1px solid #E4E4E7;padding:20px 22px;margin:0 0 28px;">
      <p style="font-size:11px;color:#A1A1AA;margin:0 0 8px;letter-spacing:2px;font-weight:500;">
        <span leaf="">REFERENCE</span>
      </p>
      <p style="font-size:15px;color:#3F3F46;margin:0;line-height:1.8;text-align:justify;">
        <span leaf="">换主题不用动一个字 —— 内容归内容，视觉归视觉。</span>
      </p>
    </section>
    <p style="margin-bottom:22px;font-size:15px;line-height:1.8;text-align:justify;color:#52525B;letter-spacing:0.3px;">{end}</p>
  </section>
""",
    },
    "zen-whitespace": {
        "container": ("max-width: 677px;margin: 0 auto;background: #FFFFFF;"
                      "font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', "
                      "'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;"
                      "color: #525252;line-height: 1.9;letter-spacing: 0.3px;"
                      "overflow-x: hidden;"),
        "body": """
  <!-- 组件 5 章节标题（衬线大字 + 短细线） -->
  <section style="margin-top: 48px;margin-bottom: 32px;padding: 0 16px;">
    <p style="font-size: 10px;color: #4A5D52;font-weight: 600;letter-spacing: 4px;margin: 0 0 10px;text-transform: uppercase;">
      <span leaf="">01 · WHY TYPOGRAPHY</span>
    </p>
    <h3 style="font-family: 'Noto Serif SC', Georgia, 'Times New Roman', serif;font-size: 22px;font-weight: 700;color: #2B2B2B;margin: 0 0 16px;letter-spacing: 0.5px;line-height: 1.4;">
      <span leaf="">排版为什么值得单独做一层</span>
    </h3>
    <section style="width: 40px;height: 2px;background: #4A5D52;">
      <span leaf=""><br></span>
    </section>
  </section>
  <!-- 组件 6 正文段落 -->
  <p style="margin-bottom: 26px;font-size: 15px;line-height: 1.9;text-align: justify;color: #525252;padding: 0 16px;">
    {intro}
  </p>
  <p style="margin-bottom: 26px;font-size: 15px;line-height: 1.9;text-align: justify;color: #525252;padding: 0 16px;">
    {body}
  </p>
  <!-- 组件 8a 居中衬线大字引用 -->
  <section style="margin: 0 16px 32px;padding: 36px 20px;border-top: 1px solid #E8E8E8;border-bottom: 1px solid #E8E8E8;text-align: center;">
    <p style="font-family: 'Noto Serif SC', Georgia, 'Times New Roman', serif;font-size: 17px;font-weight: 600;color: #2B2B2B;margin: 0;line-height: 1.9;letter-spacing: 0.8px;">
      <span leaf="">「换主题不用动一个字 —— 内容归内容，视觉归视觉。」</span>
    </p>
  </section>
  <p style="margin-bottom: 26px;font-size: 15px;line-height: 1.9;text-align: justify;color: #525252;padding: 0 16px;">{end}</p>
""",
    },
    "moyu-ticket": {
        "container": ("max-width:677px;margin:0 auto;background:#ffffff;"
                      "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
                      "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
                      "color:#374151;line-height:1.75;letter-spacing:0.5px;"),
        "body": """
  <!-- 组件 3 章节标题 chapter-title -->
  <section style="margin-top:16px;margin-bottom:32px;padding:0 20px;">
    <section style="display:flex;align-items:center;gap:12px;margin-bottom:24px;padding-bottom:12px;border-bottom:2px solid #1a1a1a;">
      <section style="background:#059669;color:#fff;font-size:12px;font-weight:800;padding:6px 12px;letter-spacing:2px;"><span leaf="">01</span></section>
      <section style="font-size:18px;font-weight:800;color:#1a1a1a;letter-spacing:1px;"><span leaf="">排版为什么值得单独做一层</span></section>
      <section style="font-size:12px;color:#888;"><span leaf="">/ WHY TYPOGRAPHY</span></section>
    </section>
    <!-- 组件 5 正文段落 paragraph -->
    <p style="font-size:14px;color:#555;line-height:1.9;margin-bottom:16px;text-align:justify;">
      {intro}
    </p>
    <p style="font-size:14px;color:#555;line-height:1.9;margin-bottom:16px;text-align:justify;">
      {body}
    </p>
  </section>
  <!-- 组件 11 核心观点卡片（硬阴影描边） -->
  <section style="margin-bottom:32px;padding:0 20px;">
    <section style="background:#fffef8;border:2px solid #1a1a1a;box-shadow:3px 3px 0 #1a1a1a;padding:20px;margin-bottom:0;">
      <p style="font-size:15px;color:#1a1a1a;font-weight:700;line-height:1.8;margin:0 0 12px;text-align:center;">
        <span leaf="">换主题不用动一个字，</span>
        <span style="color:#059669;font-size:24px;"><span leaf="">0</span></span>
        <span leaf=""> 处内容改动</span>
      </p>
      <p style="font-size:14px;color:#555;line-height:1.8;margin:0;text-align:justify;">
        <span leaf="">内容归内容，视觉归视觉 —— 同一段文字换一套主题，气质完全不同。</span>
      </p>
    </section>
  </section>
""",
    },
    "olive-journal": {
        "container": ("max-width:677px;margin:0 auto;padding:8px;box-sizing:border-box;"
                      "background:#fdfdf8;color:#4d4f46;"
                      "font-family:'IBM Plex Sans',-apple-system,system-ui,'PingFang SC',"
                      "'Hiragino Sans GB','Microsoft YaHei',sans-serif;line-height:1.75;"),
        "body": """
  <!-- 组件 3 章节标题 section-title -->
  <section style="margin-top:24px;">
    <section style="font-family:'IBM Plex Sans',-apple-system,sans-serif;">
      <section style="display:flex;align-items:center;gap:14px;">
        <section style="text-align:center;flex-shrink:0;">
          <p style="margin:0;font-size:24px;font-weight:800;color:#23251d;line-height:1;letter-spacing:-2px;"><span leaf="">01</span></p>
          <p style="margin:0;font-size:8px;font-weight:700;color:#9ea096;letter-spacing:2px;"><span leaf="">PART</span></p>
        </section>
        <span style="width:1px;height:36px;background:#bfc1b7;flex-shrink:0;display:inline-block;overflow:hidden;vertical-align:middle;font-size:0;line-height:0;"><span leaf="">&nbsp;</span></span>
        <section>
          <p style="margin:0 0 1px;font-size:17px;font-weight:800;color:#23251d;letter-spacing:0.2px;"><span leaf="">排版为什么值得单独做一层</span></p>
          <p style="margin:0;font-size:11px;font-weight:600;color:#65675e;letter-spacing:1.2px;"><span leaf="">WHY TYPOGRAPHY</span></p>
        </section>
      </section>
    </section>
  </section>
  <!-- 组件 10 正文段落 richtext-paragraph -->
  <section style="margin-top:24px;">
    <section style="font-family:'IBM Plex Sans',-apple-system,sans-serif;">
      <p style="margin:0 0 14px;font-size:14px;line-height:1.9;text-align:justify;color:#4d4f46;">
        {intro}
      </p>
      <p style="margin:0;font-size:14px;line-height:1.9;text-align:justify;color:#4d4f46;">
        {body}
      </p>
    </section>
  </section>
  <!-- 组件 15 重点观点卡 key-point-card -->
  <section style="margin-top:24px;">
    <section style="font-family:'IBM Plex Sans',-apple-system,sans-serif;">
      <section style="background:#fdfdf8;border-radius:6px;padding:16px 18px;border:1px solid #bfc1b7;">
        <p style="font-size:14px;color:#4d4f46;margin:0;line-height:1.8;text-align:justify;">
          <strong style="color:#23251d;border-bottom:3px solid #ed7b2f;"><span leaf="">换主题不用动一个字</span></strong><span leaf="">&nbsp;内容归内容，视觉归视觉。</span>
        </p>
      </section>
    </section>
  </section>
""",
    },
}


def build_html(theme_id, spec):
    code = CODE_OLIVE if theme_id == "olive-journal" else CODE_GREEN
    if theme_id == "olive-journal":
        ul = "border-bottom:2px solid #ed7b2f;font-weight:600;color:#23251d;"
    elif theme_id == "graphite-minimal":
        ul = "border-bottom:2px solid #52525B;font-weight:600;color:#27272A;"
    elif theme_id in ("red-white",):
        ul = "border-bottom:2px solid #FECACA;font-weight:600;"
    elif theme_id == "zen-whitespace":
        ul = "border-bottom:1.5px solid #B5C8BC;font-weight:500;"
    else:
        ul = "border-bottom:2px solid #A7F3D0;font-weight:600;"

    body = spec["body"].replace("{intro}", P_INTRO.format(code=code, ul=ul)) \
                       .replace("{body}", P_BODY) \
                       .replace("{end}", P_END)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>html,body{margin:0;padding:0;background:#fff}"
        "body{width:%dpx}</style></head><body>"
        '<section style="%s">%s</section></body></html>'
    ) % (WIN_W, spec["container"], body)


def shoot(chrome, html_path, png_path):
    url = "file:///" + html_path.replace("\\", "/").lstrip("/")
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=%d" % SCALE,
           "--window-size=%d,%d" % (WIN_W, VIEW_H),
           "--screenshot=" + png_path, url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.isfile(png_path):
        raise RuntimeError("截图失败：{}\n{}".format(r.stdout[-500:], r.stderr[-500:]))


def trim_bottom(png_path, pad=24):
    """裁掉底部成片的纯白，保留 pad 像素余量，并把高度取偶数。"""
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    w, h = im.size
    px = im.load()
    bottom = h
    while bottom > 1:
        row = [px[x, bottom - 1] for x in range(0, w, 7)]
        if any(max(c) - min(c) > 6 or min(c) < 244 for c in row):
            break
        bottom -= 1
    bottom = min(h, bottom + pad * SCALE)
    if bottom % 2:
        bottom += 1
    im.crop((0, 0, w, bottom)).save(png_path, optimize=True)
    return w, bottom


def main():
    ap = argparse.ArgumentParser(description="生成 README 的主题样例配图")
    ap.add_argument("--theme", action="append", default=None,
                    help="只生成指定主题（可重复）；默认全部")
    ap.add_argument("--keep-html", action="store_true", help="保留中间 HTML")
    args = ap.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("[X] 需要 pillow：pip install pillow", file=sys.stderr)
        sys.exit(1)

    chrome = find_chrome()
    if not chrome:
        print("[X] 找不到 Chrome / Edge，无法截图", file=sys.stderr)
        sys.exit(1)
    print("[i] 浏览器: {}".format(chrome))

    ids = args.theme or list(THEMES.keys())
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp_dir = os.path.join(ROOT, "dist", "_preview_src")
    os.makedirs(tmp_dir, exist_ok=True)

    for tid in ids:
        if tid not in THEMES:
            print("[!] 跳过未知主题：{}".format(tid), file=sys.stderr)
            continue
        html = build_html(tid, THEMES[tid])
        src = os.path.join(tmp_dir, "theme-{}.html".format(tid))
        with io.open(src, "w", encoding="utf-8") as f:
            f.write(html)
        png = os.path.join(OUT_DIR, "theme-{}.png".format(tid))
        shoot(chrome, src, png)
        w, h = trim_bottom(png)
        kb = os.path.getsize(png) / 1024.0
        print("  [OK] theme-{}.png  {}x{}  {:.0f} KB".format(tid, w, h, kb))

    if not args.keep_html:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n完成。README 里引用 docs/images/theme-<标识>.png 即可。")


if __name__ == "__main__":
    main()
