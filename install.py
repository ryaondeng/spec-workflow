#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-workflow 安装器（跨平台，Windows 原生 Python 可用；Linux/macOS 亦可）。

与 install.sh 语义一致：把 skills/ 下全部 skill 复制到目标 skills 目录。
    install.py --global                    # 全局安装（~/.codebuddy/skills/）
    install.py --project <path>            # 项目级安装（<path>/.codebuddy/skills/）
    install.py --project <path> --force    # 覆盖安装（删除旧目录后重装）

系统要求：
  - 需要 Python 3.7+（Windows/Linux/macOS 通用）
  - bash 版 install.sh 需要 Git Bash / WSL（仅 Unix 风格 shell 环境）
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")


def skills_src(repo_root):
    d = Path(repo_root) / "skills"
    if not d.is_dir():
        sys.exit("❌ 未找到 skills 源码目录: %s" % d)
    return sorted(p for p in d.iterdir() if p.is_dir())


def dest_base(mode, target):
    if mode == "global":
        return Path.home() / ".codebuddy" / "skills"
    return (Path(target) / ".codebuddy" / "skills").resolve()


def _force_utf8_output():
    """Windows 控制台/管道默认 GBK：输出 emoji（❌）会触发 UnicodeEncodeError。
    统一把 stdout/stderr 切到 UTF-8（Python 3.7+）；异常时静默降级，不影响主流程。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    _force_utf8_output()
    ap = argparse.ArgumentParser(prog="install.py", description="spec-workflow 安装器（跨平台）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--global", dest="mode", action="store_const", const="global",
                   help="全局安装（~/.codebuddy/skills/）")
    g.add_argument("--project", metavar="PATH", help="项目级安装（<path>/.codebuddy/skills/）")
    ap.add_argument("--force", action="store_true", help="覆盖安装（删除旧目录后重装）")
    ap.add_argument("--skip-deps", action="store_true",
                    help="跳过 dev-docs 运行时依赖安装（tree-sitter 系；默认自动 pip install）")
    a = ap.parse_args(argv)
    mode = "project" if a.project else "global"

    srcs = skills_src(Path(__file__).resolve().parent)
    if not srcs:
        sys.exit("❌ skills/ 下没有可安装的 skill")
    base = dest_base(mode, a.project or "")
    base.mkdir(parents=True, exist_ok=True)

    count = 0
    for src in srcs:
        name = src.name
        dest = base / name
        if dest.exists():
            if not a.force:
                print("[SKIP] 已存在，跳过（如需更新请加 --force）: %s" % dest)
                continue
            shutil.rmtree(dest)
            print("[REFRESH] 覆盖安装: %s" % dest)
        else:
            print("[ADD] %s -> %s" % (name, dest))
        shutil.copytree(src, dest, ignore=IGNORED, symlinks=True)
        count += 1

    if count == 0:
        print("（无新增，全部已存在或跳过）")
    else:
        print("已安装 %d 个 skill：%s" % (count, ", ".join(s.name for s in srcs)))

    # dev-docs 运行时依赖（v1.5：tree-sitter 为硬依赖，全语言统一抽取）
    req = Path(__file__).resolve().parent / "skills" / "dev-docs" / "requirements.txt"
    if req.is_file() and not a.skip_deps:
        print("安装 dev-docs 运行时依赖: %s" % req.name)
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req)])
        if r.returncode != 0:
            print("⚠ 依赖安装失败——dev-docs 需 tree-sitter 系运行时依赖，"
                  "请手动执行: %s -m pip install -r %s" % (sys.executable, req))
    elif a.skip_deps:
        print("[SKIP] 依赖安装（--skip-deps）；dev-docs 运行前需自行安装 tree-sitter 系依赖")

    print("打开该项目的 AI 会话说「开始开发 X」或「恢复 X」即可使用；"
          "review 阶段质量门控由 spec-health-check 驱动")


if __name__ == "__main__":
    main()
