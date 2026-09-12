# -*- coding: utf-8 -*-
"""dev-docs 核心逻辑单测（unittest，零第三方依赖）。"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import dev_docs      # noqa: E402
import dev_inventory as inv  # noqa: E402


def write_tree(base, files):
    for rel, content in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="devdocs_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestInventory(TmpCase):
    APP = {
        "src/__init__.py": "",
        "src/app.py": (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.post('/api/v1/login')\n"
            "def login(username: str, password: str):\n"
            "    return {'token': 'x'}\n"
            "\n"
            "class UserService:\n"
            "    def create(self, name):\n"
            "        return name\n"
            "\n"
            "def helper(x):\n"
            "    return x * 2\n"
        ),
        "src/other.py": "def _private():\n    pass\n",
        "tests/test_app.py": "def test_login():\n    pass\n",
    }

    def _build(self):
        write_tree(self.tmp, self.APP)
        return inv.build_inventory(self.tmp)

    def test_modules_partition(self):
        data = self._build()
        names = {m["name"] for m in data["modules"]}
        self.assertIn("src", names)
        self.assertIn("tests", names)

    def test_python_symbols_and_endpoint(self):
        data = self._build()
        qnames = {s["qname"] for s in data["symbols"]}
        self.assertIn("login", qnames)
        self.assertIn("UserService.create", qnames)
        self.assertIn("helper", qnames)
        # 私有函数不枚举
        self.assertNotIn("_private", qnames)
        # 端点
        eps = [e for e in data["endpoints"] if e["path"] == "/api/v1/login"]
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["method"], ["POST"])
        self.assertEqual(eps[0]["confidence"], "reliable")
        # 测试索引
        self.assertTrue(any("test_app.py" in t["file"] for t in data["tests"]))
        # 私有被排除于 tests 文档符号之外
        self.assertNotIn("src/other.py",
                         [s["file"] for s in data["symbols"]])

    def test_deterministic(self):
        write_tree(self.tmp, self.APP)
        a = inv.canon_hash(inv.build_inventory(self.tmp))
        b = inv.canon_hash(inv.build_inventory(self.tmp))
        self.assertEqual(a, b)

    def test_unique_ids(self):
        data = self._build()
        ids = [s["id"] for s in data["symbols"]] + \
              [e["id"] for e in data["endpoints"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestDocsMechanics(TmpCase):
    def test_frontmatter_roundtrip(self):
        text = ("---\ndoc_id: MOD-001\ntype: module\nsource_commit: ab12\n"
                "---\nbody\n")
        meta, rest = dev_docs.parse_frontmatter(text)
        self.assertEqual(meta["doc_id"], "MOD-001")
        self.assertEqual(rest, "body\n")
        fm = dev_docs.render_frontmatter(meta)
        self.assertIn("doc_id: MOD-001", fm)

    def test_regen_preserves_manual_area(self):
        """再生成时 marker 外内容保留（人工补充不被覆盖）。"""
        out = os.path.join(self.tmp, "docs", "dev-docs")
        os.makedirs(out)
        final = os.path.join(out, "modules", "MOD-001.md")
        os.makedirs(os.path.dirname(final))
        # 已有正式文件：含 AI 填的语义 + 人工补充
        existing = (
            "---\ndoc_id: MOD-001\ntype: module\nsource_commit: old\n"
            "generated_at: 2020-01-01\ninventory_hash: h\nstatus: current\n---\n"
            "# 模块 MOD-001\n\n"
            "## 职责（AI 已填）\n做什么：登录\n"
            + dev_docs.BEG + "\n"
            + "### FUN-001 — login\n旧符号\n"
            + "\n" + dev_docs.END + "\n"
            + "## 人工补充\n为什么用 JWT：见 ADR-007（人工写，勿覆盖）\n"
        )
        write_tree(self.tmp, {"docs/dev-docs/modules/MOD-001.md": existing})
        # 新渲染文本：换 commit 与新符号
        new_text = (
            "---\ndoc_id: MOD-001\ntype: module\nsource_commit: new\n"
            "generated_at: 2099-01-01\ninventory_hash: h2\nstatus: draft\n---\n"
            "# 模块 MOD-001\n\n"
            + dev_docs.BEG + "\n"
            + "### FUN-002 — logout\n新符号\n"
            + "\n" + dev_docs.END + "\n"
        )
        rel = dev_docs._regen_or_new(out, "modules/MOD-001.md", new_text)
        draft = os.path.join(out, rel)
        txt = dev_docs.read(draft)
        # 新生成区已刷新
        self.assertIn("### FUN-002 — logout", txt)
        self.assertIn("新符号", txt)
        # 旧生成区内容不再残留
        self.assertNotIn("旧符号", txt)
        # 人工区与 AI 填的四问保留
        self.assertIn("做什么：登录", txt)
        self.assertIn("见 ADR-007（人工写，勿覆盖）", txt)
        # frontmatter 保留 doc_id，刷新 commit
        meta, _ = dev_docs.parse_frontmatter(txt)
        self.assertEqual(meta["doc_id"], "MOD-001")
        self.assertNotEqual(meta["source_commit"], "old")


class TestAnalyze(TmpCase):
    def _inv(self, **kw):
        base = {
            "is_git": False, "source_commit": "", "modules": [],
            "symbols": [{"id": "FUN-001", "public": True},
                        {"id": "FUN-002", "public": True}],
            "endpoints": [{"id": "API-001"}],
        }
        base.update(kw)
        return base

    def _doc(self, out, rel, body, commit="deadbeef"):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("---\ndoc_id: x\ntype: api\nsource_commit: %s\n---\n" % commit + body)

    def test_orphan_phantom(self):
        out = os.path.join(self.tmp, "out")
        os.makedirs(out)
        self._doc(out, "reference/MOD-001.md",
                  "### a\n- 签名 <!-- @FUN-001 -->\n\n### GET /x\n- handler <!-- @API-001 -->\n")
        self._doc(out, "reference/MOD-002.md",
                  "### ghost\n- handler <!-- @API-999 -->\n")
        rep = dev_docs.analyze(self._inv(), out)
        self.assertEqual(rep["orphan_syms"], ["FUN-002"])
        self.assertEqual(rep["orphan_eps"], [])
        self.assertEqual(rep["phantom"], ["API-999"])

    def test_clean(self):
        out = os.path.join(self.tmp, "out")
        os.makedirs(out)
        self._doc(out, "reference/MOD-001.md",
                  "### a\n- 签名 <!-- @FUN-001 -->\n### b\n- 签名 <!-- @FUN-002 -->\n### GET /x\n- handler <!-- @API-001 -->\n")
        rep = dev_docs.analyze(self._inv(), out)
        self.assertEqual(rep["orphan_syms"] + rep["orphan_eps"] + rep["phantom"], [])

    def test_unfilled_todo_count(self):
        out = os.path.join(self.tmp, "out")
        os.makedirs(out)
        self._doc(out, "modules/MOD-001.md",
                  "### FUN-001 — a\n- 用途 / 参数 / 返回 / 错误：<!-- TODO AI 依源码填写 -->\n")
        self._doc(out, "modules/MOD-002.md", "### FUN-002 — b\n已填（无占位）\n")
        total, per = dev_docs.unfilled_todo_count(out)
        self.assertEqual(total, 1)
        self.assertTrue(any("MOD-001" in k for k in per))

    def test_stale_by_commit(self):
        out = os.path.join(self.tmp, "out")
        os.makedirs(out)
        self._doc(out, "reference/MOD-001.md",
                  "### a\n- 签名 <!-- @FUN-001 -->\n### b\n- 签名 <!-- @FUN-002 -->\n### GET /x\n- handler <!-- @API-001 -->\n")
        # 文档 source_commit=deadbeef < 当前 HEAD=aaaaaa => 过期（代码已提交未更新文档）
        inv_data = self._inv(is_git=True, source_commit="aaaaaa")
        rep = dev_docs.analyze(inv_data, out)
        self.assertTrue(any("MOD-001.md" in s for s in rep["stale"]))


class TestDocsFilesPresence(unittest.TestCase):
    def test_skill_layout(self):
        skill = os.path.dirname(HERE)
        for name in ("SKILL.md", "_meta.json"):
            self.assertTrue(os.path.exists(os.path.join(skill, name)))
        for ref in ("output-contract", "evidence-protocol", "api-doc-style",
                    "lang-mapping", "anti-patterns"):
            self.assertTrue(os.path.exists(
                os.path.join(skill, "references", ref + ".md")))
        for t in ("index", "architecture", "reference", "data"):
            self.assertTrue(os.path.exists(
                os.path.join(skill, "templates", t + ".md")))
        for s in ("dev_docs.py", "dev_inventory.py"):
            self.assertTrue(os.path.exists(
                os.path.join(skill, "scripts", s)))


class P3Case(TmpCase):
    """v1.3 通用化：文件全集 / register / 对账新口径 / 语义地图 / 非 git 漂移。"""

    def _proj(self, files, name="proj"):
        root = os.path.join(self.tmp, name)
        write_tree(root, files)
        return root

    def test_iter_all_files_includes_unknown_ext(self):
        root = self._proj({"a.py": "x = 1\n", "src/b.msg": "float32 x\n",
                           "data/blob.bin": "raw"})
        entries, hashes, notes = inv.iter_all_files(root, [])
        paths = {e["path"] for e in entries}
        self.assertIn("a.py", paths)
        self.assertIn("src/b.msg", paths)
        self.assertIn("data/blob.bin", paths)
        langs = {e["path"]: e["lang"] for e in entries}
        self.assertEqual(langs["a.py"], "python")
        self.assertIsNone(langs["src/b.msg"])
        self.assertEqual(hashes["a.py"], inv.sha256_file(os.path.join(root, "a.py")))

    def test_iter_all_files_deterministic(self):
        root = self._proj({"a.py": "1", "b/c.msg": "2", "b/d.cpp": "3"})
        e1, h1, _ = inv.iter_all_files(root, [])
        e2, h2, _ = inv.iter_all_files(root, [])
        self.assertEqual([x["path"] for x in e1], [x["path"] for x in e2])
        self.assertEqual(h1, h2)

    def test_detect_project_type(self):
        root = self._proj({"src/ncu/package.xml": "<package/>",
                           "src/ncu/x.cpp": "int main(){}"})
        self.assertEqual(inv.detect_project_type(root, []), "catkin")
        root2 = self._proj({"src/x.py": "x=1"}, name="proj2")
        self.assertEqual(inv.detect_project_type(root2, []), "generic")

    def test_inventory_files_and_project_type(self):
        root = self._proj({"src/x.py": "def f():\n    pass\n",
                           "src/Demo.srv": "float32 x\n---\nbool ok\n"})
        data = inv.build_inventory(root, project_type="auto")
        self.assertEqual(data["project_type"], "generic")
        paths = {f["path"] for f in data["files"]}
        self.assertIn("src/Demo.srv", paths)
        self.assertIn("src/x.py", paths)
        self.assertEqual(data["files_hashes"]["src/x.py"],
                         inv.sha256_file(os.path.join(root, "src/x.py")))
        # 强制 catkin：build/（默认排除）与 devel/（catkin 专属排除）都被排除
        write_tree(root, {"build/junk.o": "junk", "devel/x.txt": "x"})
        data2 = inv.build_inventory(root, project_type="catkin")
        self.assertEqual(data2["project_type"], "catkin")
        self.assertFalse(any(f["path"].startswith("build/") for f in data2["files"]))
        self.assertFalse(any(f["path"].startswith("devel/") for f in data2["files"]))
        self.assertIn("build", data2["excluded"])
        self.assertIn("devel", data2["excluded"])
        # generic 下 devel/ 不被自动排除（build/ 属默认排除，两种类型都排）
        data3 = inv.build_inventory(root, project_type="generic")
        self.assertTrue(any(f["path"].startswith("devel/") for f in data3["files"]))
        self.assertFalse(any(f["path"].startswith("build/") for f in data3["files"]))

    def test_anchor_generalized(self):
        out = os.path.join(self.tmp, "docs", "dev-docs")
        write_tree(out, {"reference/x.md": "<!-- @SYM-001 -->\n<!-- @API-001 -->\n"})
        reg, _ = dev_docs.collect_registered(out)
        self.assertIn("SYM-001", reg)
        self.assertIn("API-001", reg)

    def test_register_verified_and_increment(self):
        root = self._proj({"src/f.cpp": "class NCU {\n  void spin();\n};\n"})
        out = dev_docs.outdir(root, "dev-docs")
        rc = dev_docs.cmd_register(root, out, "symbol", "NCU::spin",
                                   "src/f.cpp", line=2)
        self.assertEqual(rc, 0)
        items = dev_docs.load_registered(out)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "SYM-001")
        self.assertEqual(items[0]["confidence"], "verified")
        # 未命中行号 -> manual；序号自增
        dev_docs.cmd_register(root, out, "interface", "/cmd_vel",
                              "src/f.cpp", line=1)
        items = dev_docs.load_registered(out)
        self.assertEqual(items[1]["id"], "ITF-001")
        self.assertEqual(items[1]["confidence"], "manual")
        dev_docs.cmd_register(root, out, "symbol", "NCU::stop", "src/f.cpp", line=3)
        items = dev_docs.load_registered(out)
        self.assertEqual(items[-1]["id"], "SYM-002")

    def test_register_missing_file_rejected(self):
        root = self._proj({"a.py": "x=1"})
        out = dev_docs.outdir(root, "dev-docs")
        with self.assertRaises(SystemExit):
            dev_docs.cmd_register(root, out, "symbol", "X", "src/ghost.cpp")
        self.assertEqual(dev_docs.load_registered(out), [])

    def test_register_bad_kind_rejected(self):
        root = self._proj({"a.py": "x=1"})
        out = dev_docs.outdir(root, "dev-docs")
        with self.assertRaises(SystemExit):
            dev_docs.cmd_register(root, out, "module", "X", "a.py")

    def test_phantom_new_semantics(self):
        root = self._proj({"src/f.cpp": "void spin(){}\n"})
        out = dev_docs.outdir(root, "dev-docs")
        dev_docs.cmd_register(root, out, "symbol", "spin", "src/f.cpp", line=1)
        write_tree(out, {"reference/x.md": "<!-- @SYM-001 -->\n<!-- @SYM-999 -->\n"})
        data = inv.build_inventory(root)
        rep = dev_docs.analyze(data, out)
        self.assertNotIn("SYM-001", rep["phantom"])   # 已登记 -> 不判 phantom
        self.assertIn("SYM-999", rep["phantom"])      # 无登记无证据 -> 仍拦

    def test_registered_file_error(self):
        root = self._proj({"src/f.cpp": "void spin(){}\n"})
        out = dev_docs.outdir(root, "dev-docs")
        dev_docs.cmd_register(root, out, "symbol", "spin", "src/f.cpp", line=1)
        os.remove(os.path.join(root, "src/f.cpp"))     # 登记后源文件消失 -> 腐化
        data = inv.build_inventory(root)
        rep = dev_docs.analyze(data, out)
        self.assertTrue(any("SYM-001" in e for e in rep["reg_file_errors"]))

    def test_semantic_map_coverage(self):
        root = self._proj({"src/a.py": "x=1", "src/b.msg": "float32 x\n",
                           "third_party/v.lib": "bin"})
        out = dev_docs.outdir(root, "dev-docs")
        data = inv.build_inventory(root)
        # 无地图：uncovered = 全集
        rep = dev_docs.analyze(data, out)
        self.assertFalse(rep["has_semantic_map"])
        self.assertEqual(rep["file_covered"], 0)
        # 地图覆盖部分 + 忽略 vendor
        write_tree(out, {"reference/x.md": ""})
        dev_docs.json_save(os.path.join(out, ".semantic-map.json"), {
            "version": 1,
            "modules": [{"name": "src", "path": "src",
                         "files": ["src/a.py"],
                         "ignored_files": [{"path": "third_party/v.lib",
                                            "reason": "vendored"}]}]})
        rep = dev_docs.analyze(data, out)
        self.assertTrue(rep["has_semantic_map"])
        self.assertEqual(rep["file_total"], 3)
        self.assertEqual(rep["file_covered"], 2)
        self.assertEqual(rep["file_uncovered"], ["src/b.msg"])

    def test_check_passes_without_semantic_map(self):
        root = self._proj({"src/a.py": "def f():\n    pass\n"})
        out = dev_docs.outdir(root, "dev-docs")
        dev_docs.cmd_inventory(root, out, [], quiet=True)
        # 无语义地图：check 仍可跑（提示缺失不门禁）；文档登记锚点后无 orphan/phantom -> PASS
        write_tree(out, {"reference/x.md": "<!-- @FUN-001 -->\n"})
        rc = dev_docs.cmd_check(dev_docs.load_inventory(out), out, drift=False, root=root)
        self.assertEqual(rc, 0)

    def test_drift_nongit_manifest(self):
        root = self._proj({"src/a.py": "def f():\n    pass\n",
                           "src/Demo.srv": "float32 x\n"})
        out = dev_docs.outdir(root, "dev-docs")
        data = dev_docs.cmd_inventory(root, out, [], quiet=True)
        dev_docs.cmd_report(data, root, out)            # 建 baseline（非 git 也写 manifest）
        # 改一个"非代码文件"（.srv）+ 一个代码文件
        write_tree(root, {"src/Demo.srv": "float32 x\nfloat32 y\n",
                          "src/a.py": "def f():\n    return 1\n"})
        data2 = dev_docs.cmd_inventory(root, out, [], quiet=True)
        rep = dev_docs.analyze(data2, out, drift=True)
        d = rep["drift"]
        self.assertIsNotNone(d)
        self.assertIn("src/Demo.srv", d["changed_files"])   # 非 git 也能检出
        self.assertIn("src/a.py", d["changed_files"])


if __name__ == "__main__":
    unittest.main()
