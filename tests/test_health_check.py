#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""health-check.py（health-check.sh 的跨平台等价）单测：纯 Python，Windows/Linux 均可跑。"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HC = REPO / "skills/spec-health-check/scripts/health-check.py"

FILES = ["00-index.md", "01-requirements.md", "02-design.md", "03-implementation-plan.md",
         "04-unit-test-plan.md", "05-integration-test-plan.md", "06-code-review-report.md",
         "07-docs-update-plan.md", "08-commit.md"]


def run(spec_root, name):
    return subprocess.run([sys.executable, str(HC), spec_root, name],
                          capture_output=True, text=True)


class HealthCheckPyCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="hc-spec-"))
        d = self.root / "demo"
        d.mkdir()
        (d / "00-index.md").write_text(
            "| 阶段 | 状态 |\n|:---|:---|\n"
            + "".join("| %02d | ✅ 已完成 |\n" % i for i in range(1, 9)),
            encoding="utf-8")
        (d / "01-requirements.md").write_text(
            "# 需求\n| AC-01 | a |\n| AC-02 | b |\n| AC-03 | c |\n" + "x" * 120,
            encoding="utf-8")
        (d / "02-design.md").write_text("# 设计\n" + "y" * 120, encoding="utf-8")
        (d / "03-implementation-plan.md").write_text(
            "| 任务 | 说明 | 状态 |\n|:---|:---|:---|\n"
            "| T01 | a | [x] |\n| T02 | b | 📝 |\n| T03 | c | ✅ |\n", encoding="utf-8")
        (d / "04-unit-test-plan.md").write_text(
            "| 编号 | 用例 | 状态 |\n|:---|:---|:---|\n"
            "| TC-01 | a | [ ] |\n| TC-02 | b | [x] |\n", encoding="utf-8")
        (d / "05-integration-test-plan.md").write_text("# 集成\n" + "z" * 120, encoding="utf-8")
        (d / "06-code-review-report.md").write_text(
            "| 编号 | 级别 | 问题 |\n|:---|:---|:---|\n| S01 | MINOR | 建议 |\n",
            encoding="utf-8")
        (d / "07-docs-update-plan.md").write_text("# 文档\n" + "d" * 600, encoding="utf-8")
        (d / "08-commit.md").write_text("- [x] T01\n- [x] T02\n- [x] T03\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_summary_counts_and_exit0(self):
        r = run(str(self.root), "demo")
        self.assertEqual(r.returncode, 0, r.stdout)
        for expect in ["index_done=8", "tasks_total_03=3", "tasks_done_03=2",
                       "tasks_total_08=3", "tasks_done_08=3", "acceptance_criteria=3",
                       "unit_test_cases=2", "review_issues=1", "file_missing=0",
                       "structure_errors=0", "=== END SUMMARY ==="]:
            self.assertIn(expect, r.stdout)
        self.assertIn("9 个文件齐全", r.stdout)

    def test_missing_files_exit1(self):
        (self.root / "demo" / "06-code-review-report.md").unlink()
        (self.root / "demo" / "07-docs-update-plan.md").unlink()
        r = run(str(self.root), "demo")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("file_missing=2", r.stdout)
        self.assertIn("structure_errors=2", r.stdout)

    def test_unknown_arg_rejected(self):
        r = subprocess.run([sys.executable, str(HC), str(self.root), "demo", "--bogus"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("未知参数", r.stdout)

    def test_missing_spec_dir(self):
        r = run(str(self.root), "not-exist")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Spec 目录不存在", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
