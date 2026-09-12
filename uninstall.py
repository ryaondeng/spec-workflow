#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-workflow 卸载器（跨平台，与 uninstall.sh 语义一致）。

只移除安装的 skills；项目内 spec/ 数据与 .specworkflow/ 会话不受影响。
    uninstall.py --global                 # 全局卸载（~/.codebuddy/skills/）
    uninstall.py --project <path>         # 项目级卸载（<path>/.codebuddy/skills/）
"""
import argparse
import shutil
import sys
from pathlib import Path


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
    ap = argparse.ArgumentParser(prog="uninstall.py", description="spec-workflow 卸载器（跨平台）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--global", dest="mode", action="store_const", const="global",
                   help="全局卸载（~/.codebuddy/skills/）")
    g.add_argument("--project", metavar="PATH", help="项目级卸载（<path>/.codebuddy/skills/）")
    a = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parent
    # 与安装对称：只卸载本仓库 skills/ 中存在的同名目录，不误删其它来源
    names = sorted(p.name for p in (repo_root / "skills").iterdir() if p.is_dir())
    if not names:
        sys.exit("❌ 未找到 skills 源码目录: %s" % (repo_root / "skills"))

    if a.project:
        base = (Path(a.project) / ".codebuddy" / "skills").resolve()
    else:
        base = Path.home() / ".codebuddy" / "skills"

    for name in names:
        dest = base / name
        if dest.exists():
            shutil.rmtree(dest)
            print("[REMOVED] %s" % dest)
        else:
            print("[SKIP] 未安装: %s" % dest)
    print("项目内 spec/ 文档与 .specworkflow/ 会话已保留")


if __name__ == "__main__":
    main()
