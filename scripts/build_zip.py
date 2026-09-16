#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包分发包（Windows / Linux 通用，零第三方依赖）。

产物：dist/wechat-mp-publisher-skill-v<版本>.zip
压缩包内顶层目录为 wechat-mp-publisher-skill/，解压后可直接：
  1. 放到 ~/.workbuddy/skills/ 作为技能使用
  2. 直接 cd 进去当命令行工具用

自动排除：.git、密钥配置、token 缓存、Python 缓存、构建产物。

用法：
    python scripts/build_zip.py
    python scripts/build_zip.py --out /tmp/dist
"""

import argparse
import io
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = os.path.basename(ROOT)

# 不进入压缩包的内容
EXCLUDE_DIRS = {
    ".git", "__pycache__", "dist", "build", ".venv", "venv", "env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "tmp", "sandbox", ".idea", ".vscode",
}
EXCLUDE_FILES = {
    "config.json", "config.local.json", ".token_cache.json",
    ".DS_Store", "Thumbs.db", "desktop.ini",
}
EXCLUDE_EXTS = {".pyc", ".pyo", ".zip", ".swp", ".log"}


def read_version():
    vpath = os.path.join(ROOT, "VERSION")
    if os.path.isfile(vpath):
        with io.open(vpath, encoding="utf-8") as f:
            v = f.read().strip()
        if v:
            return v
    return "0.0.0"


def collect():
    """返回 [(绝对路径, 包内相对路径), ...]，已排序。"""
    items = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if name in EXCLUDE_FILES:
                continue
            if os.path.splitext(name)[1].lower() in EXCLUDE_EXTS:
                continue
            if name.startswith(".token_cache"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            items.append((full, rel))
    items.sort(key=lambda x: x[1])
    return items


def main():
    ap = argparse.ArgumentParser(description="打包 wechat-mp-publisher-skill 分发包")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="输出目录，默认 <仓库>/dist")
    args = ap.parse_args()

    version = read_version()
    os.makedirs(args.out, exist_ok=True)
    zip_name = "wechat-mp-publisher-skill-v{}.zip".format(version)
    zip_path = os.path.join(args.out, zip_name)

    items = collect()
    if not items:
        print("没有可打包的文件")
        return 1

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for full, rel in items:
            zf.write(full, "{}/{}".format(TOP, rel))

    size = os.path.getsize(zip_path)
    print("=" * 64)
    print("  打包完成")
    print("=" * 64)
    print("  版本    : v{}".format(version))
    print("  产物    : {}".format(zip_path))
    print("  文件数  : {}".format(len(items)))
    print("  体积    : {:.1f} KB".format(size / 1024.0))
    print("-" * 64)
    print("  包内清单：")
    for _, rel in items:
        print("    {}".format(rel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
