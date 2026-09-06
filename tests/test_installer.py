#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py / uninstall.py 跨平台安装器单测（标准库 unittest，零依赖）。"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL = REPO / "install.py"
UNINSTALL = REPO / "uninstall.py"
EXPECTED = {"dev-docs", "spec-dev-workflow", "spec-health-check"}


def run(script, *args, cwd=None):
    return subprocess.run([sys.executable, str(script)] + list(args),
                          capture_output=True, text=True, cwd=cwd or str(REPO))


class InstallerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec-install-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _skills_dir(self):
        return self.tmp / ".codebuddy" / "skills"

    def test_install_then_uninstall_symmetric(self):
        r = run(INSTALL, "--project", str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        names = {p.name for p in self._skills_dir().iterdir() if p.is_dir()}
        self.assertEqual(names, EXPECTED)
        # 安装目录干净：不带 __pycache__ / *.pyc
        caches = list(self._skills_dir().rglob("__pycache__"))
        self.assertEqual(caches, [])
        # 非 force 重复安装 = skip，不覆盖
        r2 = run(INSTALL, "--project", str(self.tmp))
        self.assertIn("已存在", r2.stdout)
        # 卸载对称：三 skill 全移除
        r3 = run(UNINSTALL, "--project", str(self.tmp))
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertEqual(list(self._skills_dir().iterdir()), [])

    def test_force_refresh(self):
        run(INSTALL, "--project", str(self.tmp))
        dest = self._skills_dir() / "dev-docs" / "_meta.json"
        dest.write_text("tampered", encoding="utf-8")
        r = run(INSTALL, "--project", str(self.tmp), "--force")
        self.assertEqual(r.returncode, 0)
        self.assertIn("覆盖", r.stdout)
        self.assertNotEqual(dest.read_text(encoding="utf-8"), "tampered")

    def test_global_mode_dry(self):
        # 全局安装到真实 HOME 有副作用，这里只验证参数被接受与模式解析（不实际安装）
        r = run(INSTALL, "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--project", r.stdout)
        self.assertIn("--global", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
