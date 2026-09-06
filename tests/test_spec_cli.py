#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-workflow 编排引擎 M0 单元测试（标准库 unittest，零依赖）"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "skills/spec-dev-workflow/scripts/spec_cli.py"

FILL_REQ = """# 需求文档
## 背景
系统需要批量导入能力，当前人工操作效率低。
## 功能范围
- 支持 CSV 上传解析与字段校验
- 失败行给出错误与行号
## 验收标准
- AC-01 合法 CSV 导入成功并返回行数（P0）
- AC-02 非法行给出明确错误与行号，不中断整体（P0）
- AC-03 空文件返回友好提示（P1）
"""
FILL_02 = """# 设计文档
## 架构
graph TD A[入口] --> B[服务] --> C[存储]
## 模块
- Importer: 解析与校验
- Reporter: 错误行报告
## 接口
POST /api/import  body{csv} 返回 {imported, errors}
## 错误处理
400 参数错误 / 422 数据校验错误
"""
FILL_03 = """# 实现计划
- [ ] T01 实现 CSV 解析模块
- [ ] T02 实现字段校验与错误收集
- [ ] T03 实现导入接口与结果返回
- [ ] T04 编写单元测试
"""
FILL_04 = """# 单测计划
## 用例（覆盖核心逻辑/边界/错误路径）
| 用例 | 场景 | 期望 |
| U01 | 合法 CSV 两行 | 导入成功返回 2 |
| U02 | 含非法行 | 报告行号不中断 |
| U03 | 空文件 | 友好提示 |
| U04 | 表头缺失 | 422 错误 |
"""
FILL_06 = """# CR 报告
## 审查维度
安全/性能/正确性/可维护性/测试
## 发现
- NIT: Importer 命名可更明确（不阻塞）
- MINOR: 缺少导入大小上限（建议后续加）
"""
FILL_07 = """# 文档更新计划
## 更新清单
- README.md：新增批量导入章节（用法与示例）
- API 文档：POST /api/import 定义
- CHANGELOG.md：记录导入能力上线
## 执行记录
- 三处文档均已更新完成
"""
FILL_08_HALF = """- [x] T01 实现 CSV 解析模块
- [ ] T02 实现字段校验与错误收集
"""
FILL_08_ALL = """- [x] T01 实现 CSV 解析模块
- [x] T02 实现字段校验与错误收集
- [x] T03 实现导入接口与结果返回
- [x] T04 编写单元测试
"""


def run(*args, cwd=None, env=None):
    """执行 CLI，返回 (rc, stdout+stderr 合并输出)；成功路径的机器输出无 stderr 干扰"""
    proc = subprocess.run([sys.executable, str(CLI)] + list(args),
                          capture_output=True, text=True, cwd=cwd, env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def ho(**kw):
    d = {"summary": kw.get("summary", "阶段完成"),
         "key_decisions": kw.get("key_decisions", ["关键决策"]),
         "artifacts": kw.get("artifacts", {}),
         "next_inputs": kw.get("next_inputs", {})}
    return json.dumps(d, ensure_ascii=False)


class EngineCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = str(Path(self._td.name) / "spec")
        rc, out = run("init", self.root, "user-auth", "--name", "用户认证")
        self.assertEqual(rc, 0, out)
        # 目录名 = <yyyymmddhhmm>-user-auth（时间戳前缀）；取 spec_root 下唯一的 feature 目录
        dirs = [p for p in Path(self.root).iterdir() if p.is_dir()]
        self.assertEqual(len(dirs), 1, out)
        self.fd = dirs[0]                             # 文档目录（spec 产物）
        self.f = self.fd.name                         # 完整目录名（ts-slug）
        self.sess = Path(self.root).resolve().parent / ".specworkflow" / "sessions" / self.f  # 会话目录

    def tearDown(self):
        self._td.cleanup()

    def read_state(self):
        return json.loads((self.sess / "state.json").read_text())

    def fill(self, name, text):
        (self.fd / name).write_text(text, encoding="utf-8")

    def complete(self, phase, summary="阶段完成"):
        return run("phase-complete", self.root, self.f, phase, "--handoff",
                   ho(summary=summary))

    def test_init_ok(self):
        """AC-02: init 生成模板+state+00-index，含 pipeline 记录"""
        st = self.read_state()
        self.assertEqual(st["pipeline"]["id"], "spec-default")
        self.assertEqual(st["current_phase"], "requirements")
        self.assertTrue((self.fd / "01-requirements.md").is_file())
        self.assertTrue((self.fd / "00-index.md").is_file())
        self.assertIn("SPEC_TEMPLATE_PENDING",
                      (self.fd / "01-requirements.md").read_text())

    def test_init_timestamp_dirname(self):
        """目录名带时间戳前缀（yyyymmddhhmm-slug），便于按时间排序"""
        m = re.match(r"^\d{12}-user-auth$", self.f)
        self.assertIsNotNone(m, "目录名应为 <yyyymmddhhmm>-user-auth，实际: %s" % self.f)

    def test_empty_template_gate(self):
        """AC-05: 空模板（带标记）收口被拦，状态不变"""
        rc, out = self.complete("requirements")
        self.assertEqual(rc, 1)
        self.assertIn("未填写", out)
        self.assertEqual(self.read_state()["phases"]["requirements"]["status"], "pending")

    def test_skip_out_of_order(self):
        """AC-04: 越级收口被拒"""
        rc, out = self.complete("design")
        self.assertEqual(rc, 1)
        self.assertIn("越级", out)

    def test_full_progress_and_atomicity(self):
        """AC-03 + AC-05: 合法收口推进、00-index 刷新；handoff 超限/缺字段被拒且状态不变"""
        self.fill("01-requirements.md", FILL_REQ)
        rc, out = self.complete("requirements", "需求明确 3 条 AC")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.read_state()["current_phase"], "design")
        self.fill("02-design.md", FILL_02)
        self.fill("03-implementation-plan.md", FILL_03)
        rc, out = self.complete("design", "设计完成")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.read_state()["current_phase"], "implementation")
        # implementation 门禁前置：填 08 使门禁可过
        self.fill("08-commit.md", FILL_08_HALF)
        # handoff 超限被拒
        rc, out = run("phase-complete", self.root, self.f, "implementation",
                      "--handoff", json.dumps({"summary": "x" * 6000,
                                               "key_decisions": [], "artifacts": {},
                                               "next_inputs": {}}))
        self.assertEqual(rc, 1)
        self.assertIn("超限", out)
        # handoff 缺字段被拒
        rc, out = run("phase-complete", self.root, self.f, "implementation",
                      "--handoff", '{"summary":"only"}')
        self.assertEqual(rc, 1)
        self.assertIn("缺少必填字段", out)
        # 原子性：仍在 implementation 且未完成
        st = self.read_state()
        self.assertEqual(st["current_phase"], "implementation")
        self.assertEqual(st["phases"]["implementation"]["status"], "pending")
        # 合法收口
        rc, out = self.complete("implementation", "T01 完成")
        self.assertEqual(rc, 0, out)
        idx = (self.fd / "00-index.md").read_text()
        self.assertIn("✅ 已完成", idx)
        # handoff 落在会话目录（.specworkflow/sessions/），不在文档目录
        self.assertFalse((self.fd / "handoff").exists())
        self.assertTrue((self.sess / "handoff/implementation.json").is_file())

    def test_skip_phase(self):
        """AC-07: --skip 带原因后流程继续，看板显示跳过"""
        self.fill("01-requirements.md", FILL_REQ)
        rc, out = self.complete("requirements")
        self.assertEqual(rc, 0, out)
        rc, out = run("phase-complete", self.root, self.f, "design",
                      "--skip", "无设计必要")
        self.assertEqual(rc, 0)
        self.assertIn("已跳过", out)
        st = self.read_state()
        self.assertEqual(st["phases"]["design"]["status"], "skipped")
        self.assertEqual(st["current_phase"], "implementation")

    def test_restore_json(self):
        """AC-06: restore --json 输出完整（状态+最近 handoff+suggest）"""
        self.fill("01-requirements.md", FILL_REQ)
        rc, out = self.complete("requirements", "需求明确")
        self.assertEqual(rc, 0, out)
        rc, out = run("restore", self.root, self.f, "--json")
        self.assertEqual(rc, 0)
        d = json.loads(out)
        self.assertEqual(d["current_phase"], "design")
        self.assertEqual(d["last_handoff"]["phase"], "requirements")
        self.assertIn("确认", d["suggest"])  # design 是确认点

    def test_gate_precheck(self):
        """gate 独立预检对空模板失败，rc=1"""
        rc, out = run("gate", self.root, self.f)
        self.assertEqual(rc, 1)
        self.assertIn("未填写", out)

    def test_handoff_read_missing(self):
        rc, out = run("handoff", "read", self.root, self.f, "requirements")
        self.assertEqual(rc, 1)
        self.assertIn("不存在", out)

    def test_end_to_end_commit(self):
        """AC-09: 全流程到 commit 终态"""
        self.fill("01-requirements.md", FILL_REQ)
        rc, out = self.complete("requirements")
        self.assertEqual(rc, 0, out)
        self.fill("02-design.md", FILL_02)
        self.fill("03-implementation-plan.md", FILL_03)
        rc, out = self.complete("design")
        self.assertEqual(rc, 0, out)
        self.fill("08-commit.md", FILL_08_HALF)
        rc, out = self.complete("implementation")
        self.assertEqual(rc, 0, out)
        self.fill("04-unit-test-plan.md", FILL_04)
        rc, out = self.complete("unit-test")
        self.assertEqual(rc, 0, out)
        rc, out = run("phase-complete", self.root, self.f, "integration-test",
                      "--skip", "无集成环境")
        self.assertEqual(rc, 0, out)
        self.fill("06-code-review-report.md", FILL_06)
        rc, out = run("phase-complete", self.root, self.f, "review",
                      "--handoff", ho(summary="CR 完成"),
                      "--review-result", review_result(90))
        self.assertEqual(rc, 0, out)
        self.fill("07-docs-update-plan.md", FILL_07)
        rc, out = self.complete("docs")
        self.assertEqual(rc, 0, out)
        self.fill("08-commit.md", FILL_08_ALL)
        rc, out = self.complete("commit", "全部任务完成并提交")
        self.assertEqual(rc, 0, out)
        st = self.read_state()
        self.assertIsNone(st["current_phase"])
        self.assertEqual(st["phases"]["commit"]["status"], "completed")
        rc, out = run("status", self.root, self.f)
        self.assertIn("全部阶段已完成", out)


def review_result(score, **kw):
    base = {
        "score": score,
        "gate": "green" if score >= 85 else ("yellow" if score >= 70 else "red"),
        "dimensions": [{"id": "A需求质量", "score": score - 2},
                       {"id": "B一致性", "score": score - 5},
                       {"id": "C真实性", "score": score - 1},
                       {"id": "D设计计划", "score": score - 3}],
        "issues": [{"severity": "MINOR", "dimension": "B", "desc": "示例问题"}],
        "method": "spec-health-check v0.3 四维评审",
    }
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


class ReviewGateCase(unittest.TestCase):
    """M1：review 质量门控（spec-health-check 接入）"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = str(Path(self._td.name) / "spec")
        rc, out = run("init", self.root, "qa", "--name", "质量演示")
        self.assertEqual(rc, 0, out)
        self.fd = [p for p in Path(self.root).iterdir() if p.is_dir()][0]
        self.f = self.fd.name
        self.sess = Path(self.root).resolve().parent / ".specworkflow" / "sessions" / self.f

    def tearDown(self):
        self._td.cleanup()

    def _fill(self, name, text):
        (self.fd / name).write_text(text, encoding="utf-8")

    def _advance_to_review(self):
        """走完 requirements/design/implementation/unit-test，skip 集成测试 → 停在 review"""
        self._fill("01-requirements.md", FILL_REQ)
        rc, out = run("phase-complete", self.root, self.f, "requirements", "--handoff", ho())
        self.assertEqual(rc, 0, out)
        self._fill("02-design.md", FILL_02)
        self._fill("03-implementation-plan.md", FILL_03)
        rc, out = run("phase-complete", self.root, self.f, "design", "--handoff", ho())
        self.assertEqual(rc, 0, out)
        self._fill("08-commit.md", FILL_08_HALF)
        rc, out = run("phase-complete", self.root, self.f, "implementation", "--handoff", ho())
        self.assertEqual(rc, 0, out)
        self._fill("04-unit-test-plan.md", FILL_04)
        rc, out = run("phase-complete", self.root, self.f, "unit-test", "--handoff", ho())
        self.assertEqual(rc, 0, out)
        rc, out = run("phase-complete", self.root, self.f, "integration-test",
                      "--skip", "无集成环境")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.read_state()["current_phase"], "review")

    def read_state(self):
        return json.loads((self.sess / "state.json").read_text())

    def _complete_review(self, rv=None):
        args = ["phase-complete", self.root, self.f, "review", "--handoff",
                ho(summary="CR 完成")]
        if rv is not None:
            args += ["--review-result", rv]
        return run(*args)

    def test_review_missing_result(self):
        """AC-03: review 阶段缺 --review-result 被拒"""
        self._advance_to_review()
        self._fill("06-code-review-report.md", FILL_06)
        rc, out = self._complete_review()
        self.assertEqual(rc, 1)
        self.assertIn("缺少 --review-result", out)
        self.assertEqual(self.read_state()["phases"]["review"]["status"], "pending")

    def test_review_bad_schema(self):
        """AC-04: review-result schema 非法被拒"""
        self._advance_to_review()
        self._fill("06-code-review-report.md", FILL_06)
        rc, out = self._complete_review(rv='{"score":"high"}')
        self.assertEqual(rc, 1)
        self.assertIn("score 须为 0-100", out)
        rc, out = self._complete_review(rv='not-json')
        self.assertEqual(rc, 1)
        self.assertIn("不是合法 JSON", out)

    def test_review_low_score_rejected(self):
        """AC-05: score < min_score(80) 拒绝收口、状态零变化、输出 issues"""
        self._advance_to_review()
        self._fill("06-code-review-report.md", FILL_06)
        rc, out = self._complete_review(rv=review_result(60))
        self.assertEqual(rc, 1)
        self.assertIn("score=60 < 达标线 80", out)
        self.assertIn("示例问题", out)
        st = self.read_state()
        self.assertEqual(st["phases"]["review"]["status"], "pending")
        self.assertEqual(st["current_phase"], "review")

    def test_review_pass_records_score(self):
        """AC-06: score ≥ min_score 放行，gate_result 记录证据"""
        self._advance_to_review()
        self._fill("06-code-review-report.md", FILL_06)
        rc, out = self._complete_review(rv=review_result(88))
        self.assertEqual(rc, 0, out)
        gr = self.read_state()["phases"]["review"]["gate_result"]
        review_check = [c for c in gr["checks"] if c["type"] == "review"][0]
        self.assertEqual(review_check["score"], 88)
        self.assertTrue(review_check["passed"])

    def test_review_precheck_skips(self):
        """gate 预检对 review 不判失败（显示收口时校验）；builtin 仍需通过"""
        self._advance_to_review()
        self._fill("06-code-review-report.md", FILL_06)
        rc, out = run("gate", self.root, self.f, "--phase", "review")
        self.assertEqual(rc, 0)
        self.assertIn("收口时校验", out)

    def test_nonreview_stage_ignores_review_result(self):
        """AC-07: 无 review 门控的阶段不要求 --review-result"""
        self._fill("01-requirements.md", FILL_REQ)
        rc, out = run("phase-complete", self.root, self.f, "requirements",
                      "--handoff", ho())
        self.assertEqual(rc, 0, out)


class ExtendCase(unittest.TestCase):
    """AC-11: 声明式流水线——项目级覆盖 + command 门控接入（不改引擎）"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = str(Path(self._td.name) / "spec")
        self.f = "myfeat"
        Path(self.root).mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_project_pipeline_command_gate(self):
        cfg = {
            "id": "spec-custom",
            "name": "自定义",
            "version": "1.0",
            "stages": [
                {"id": "requirements", "name": "需求", "artifacts": ["01-requirements.md"],
                 "confirm_point": True,
                 "gate": {"checks": [
                     {"type": "builtin", "rules": ["artifacts_exist", "artifacts_nonempty",
                                                   "no_placeholder", "no_fill_marker"]},
                     {"type": "command", "cmd": "test -f requirements.txt"}]}}
            ]
        }
        (Path(self.root) / "pipeline.json").write_text(json.dumps(cfg, ensure_ascii=False))
        rc, out = run("init", self.root, self.f)
        self.assertEqual(rc, 0, out)
        docs = [p for p in Path(self.root).iterdir() if p.is_dir()][0]
        self.f = docs.name
        (docs / "01-requirements.md").write_text(FILL_REQ, encoding="utf-8")
        # command 不满足 → 拦截
        rc, out = run("gate", self.root, self.f)
        self.assertEqual(rc, 1)
        self.assertIn("command", out)
        # 满足 → 放行收口
        (Path(self.root) / "requirements.txt").write_text("pkg==1.0")
        rc, out = run("phase-complete", self.root, self.f, "requirements",
                      "--handoff", ho())
        self.assertEqual(rc, 0, out)


class TestPlatformCmd(unittest.TestCase):
    """command 门禁命令的跨平台归一（Windows 兼容）。"""

    @staticmethod
    def _mod():
        import importlib.util
        spec = importlib.util.spec_from_file_location("spec_cli_ut", str(CLI))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_posix_passthrough(self):
        mod = self._mod()
        cmd = "python3 check.py --dir ."
        self.assertEqual(mod._platform_cmd(cmd, is_win=False), cmd)

    def test_win_python3_mapped_to_current_interpreter(self):
        mod = self._mod()
        out = mod._platform_cmd("python3 check.py --dir .", is_win=True)
        self.assertTrue(out.startswith('"%s"' % sys.executable), out)
        self.assertTrue(out.endswith(" check.py --dir ."), out)

    def test_win_non_python_kept(self):
        mod = self._mod()
        cmd = "bash health-check.sh ./spec user-auth"
        self.assertEqual(mod._platform_cmd(cmd, is_win=True), cmd)

    def test_win_plain_python3(self):
        mod = self._mod()
        out = mod._platform_cmd("python3", is_win=True)
        self.assertEqual(out, '"%s"' % sys.executable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
