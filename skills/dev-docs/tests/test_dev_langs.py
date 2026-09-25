# -*- coding: utf-8 -*-
"""dev-docs v1.5 适配器架构单测：dev_langs 包（tree-sitter 全语言统一抽取）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import dev_inventory as inv  # noqa: E402
from dev_langs import EXT_LANG, get_adapter  # noqa: E402


def counters():
    return {"fun": 0, "cls": 0, "api": 0, "msg": 0, "srv": 0, "top": 0, "svc": 0, "nde": 0}


def scan(adapter, src, name="x.py", module="MOD-001"):
    data = src.encode("utf-8") if isinstance(src, str) else src
    return adapter.scan(data, name, module, counters())


class Registry(unittest.TestCase):
    def test_route_and_unsupported(self):
        self.assertEqual(get_adapter(".py").lang, "python")
        self.assertEqual(get_adapter(".CPP").lang, "cpp")       # 大小写不敏感
        self.assertEqual(get_adapter(".msg").lang, "msgsrv")
        self.assertIsNone(get_adapter(".zip"))

    def test_ext_lang_covers_code_exts(self):
        for ext in (".py", ".cpp", ".h", ".c", ".java", ".ts", ".sh", ".msg", ".srv"):
            self.assertIn(ext, EXT_LANG)


class PythonAdapter(unittest.TestCase):
    SRC = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "\n"
        "@app.post('/api/v1/login')\n"
        "def login(user: str, password: str):\n"
        "    return {'token': 'x'}\n"
        "\n"
        "def helper(x):\n"
        "    return x * 2\n"
        "\n"
        "def _private():\n"
        "    pass\n"
        "\n"
        "class UserService:\n"
        "    def create(self, name):\n"
        "        def nested():\n"
        "            return name\n"
        "        return nested()\n"
    )

    def setUp(self):
        self.syms, self.eps, ifaces, self.notes = scan(get_adapter(".py"), self.SRC)

    def test_top_level_and_methods(self):
        qnames = {s["qname"] for s in self.syms}
        self.assertEqual(qnames, {"login", "helper", "UserService.create"})

    def test_private_and_nested_excluded(self):
        # `_private` 与嵌套 `nested` 不产出（与原 ast 版语义一致）
        self.assertTrue(all("_private" not in s["qname"] for s in self.syms))
        self.assertTrue(all("nested" not in s["qname"] for s in self.syms))

    def test_cls_and_kind(self):
        m = [s for s in self.syms if s["qname"] == "UserService.create"][0]
        self.assertEqual(m["kind"], "method")
        self.assertEqual(m["cls"], "UserService")

    def test_decorator_endpoint(self):
        self.assertEqual(len(self.eps), 1)
        self.assertEqual(self.eps[0]["path"], "/api/v1/login")
        self.assertIn("POST", self.eps[0]["method"])   # 旧版语义：method 为列表
        login = [s for s in self.syms if s["qname"] == "login"][0]
        self.assertEqual(login["endpoints"], [self.eps[0]["id"]])

    def test_extractor_and_confidence(self):
        self.assertTrue(all(s["extractor"] == "tree-sitter" for s in self.syms))
        self.assertTrue(all(s["confidence"] == "reliable" for s in self.syms))


class CppAdapter(unittest.TestCase):
    def test_qualified_method_and_class(self):
        src = (b"class DroneController {\n"
               b" public:\n"
               b"  void MoveForward(uint_32 v);\n"
               b"};\n"
               b"void DroneController::MoveForward(uint_32 v) { }\n"
               b"int standalone() { return 0; }\n"
               b"namespace {\n"
               b"int hidden() { return 1; }\n"
               b"}\n")
        syms, _, _, _ = scan(get_adapter(".cpp"), src, "a.cpp")
        qnames = {s["qname"] for s in syms}
        self.assertIn("DroneController", qnames)                       # class
        self.assertIn("DroneController::MoveForward", qnames)           # .cpp 定义
        self.assertIn("standalone", qnames)
        self.assertNotIn("hidden", qnames)                         # 匿名命名空间跳过
        kinds = {s["qname"]: s["kind"] for s in syms}
        self.assertEqual(kinds["DroneController::MoveForward"], "method")
        self.assertEqual(kinds["standalone"], "function")

    def test_header_method_declaration(self):
        src = (b"class VideoNodelet {\n"
               b"  virtual void onInit();\n"
               b"};\n")
        syms, _, _, _ = scan(get_adapter(".h"), src, "x.h")
        self.assertTrue(any(s["qname"] == "VideoNodelet::onInit" and s["kind"] == "method"
                            for s in syms))

    def test_macro_produces_no_symbol_but_call_recorded(self):
        src = b"#define GO(x) move(x)\nint f() { GO(1); return 0; }\n"
        syms, _, _, _ = scan(get_adapter(".cpp"), src, "a.cpp")
        self.assertEqual([s["qname"] for s in syms], ["f"])

    def test_deps_includes(self):
        src = b"#include <ros/ros.h>\n#include \"ncu/database.h\"\nint f(){return 0;}\n"
        # 保留 <> / "" 原样（区分系统头与本地头，供二期依赖归属用）
        self.assertEqual(get_adapter(".cpp").scan_deps(src),
                         ["<ros/ros.h>", "ncu/database.h"])


class MsgSrvAdapter(unittest.TestCase):
    MSG = ("# comment line\n"
           "uint8 voltageNotSafety   # low voltage\n"
           "float64[3] vec\n"
           "uint8 MODE_AUTO=2\n")
    SRV = ("# req\n"
           "uint8 cmd\n"
           "---\n"
           "bool result\n")

    def test_msg_fields(self):
        _, _, ifaces, _ = scan(get_adapter(".msg"), self.MSG, "BatteryState.msg")
        self.assertEqual(len(ifaces), 1)
        i = ifaces[0]
        self.assertEqual(i["kind"], "msg")
        self.assertEqual(i["name"], "BatteryState")
        self.assertEqual(i["id"].split("-")[0], "MSG")
        self.assertEqual(i["fields"][0]["name"], "voltageNotSafety")
        self.assertEqual(i["fields"][1]["array"], "[3]")
        self.assertEqual(i["fields"][2]["constant"], "2")
        self.assertGreater(i["line"], 1)              # 起始行跳过注释

    def test_srv_request_response(self):
        _, _, ifaces, _ = scan(get_adapter(".srv"), self.SRV, "Activation.srv")
        i = ifaces[0]
        self.assertEqual(i["kind"], "srv")
        self.assertEqual(i["request"][0]["name"], "cmd")
        self.assertEqual(i["response"][0]["name"], "result")
        self.assertEqual(i["id"].split("-")[0], "SRV")


class JavaJsBash(unittest.TestCase):
    def test_java_class_method_and_endpoint(self):
        src = ('public class Foo {\n  @PostMapping("/api/x")\n'
               "  public Result handle(Req r) { return null; }\n}\n")
        syms, eps, _, _ = scan(get_adapter(".java"), src, "T.java")
        self.assertEqual([(s["qname"], s["kind"]) for s in syms],
                         [("Foo", "class"), ("Foo.handle", "method")])
        self.assertEqual([(e["method"], e["path"]) for e in eps], [("POST", "/api/x")])

    def test_js_and_ts(self):
        js = ('import x from "y";\nexport function f(a) { return a; }\n'
              "const g = (b) => b * 2;\nclass K { run() {} }\n")
        syms, _, _, _ = scan(get_adapter(".js"), js, "m.js")
        self.assertEqual({s["qname"] for s in syms}, {"f", "g", "K", "K.run"})
        ts = "export const h = async (p) => { return p; };\n"
        syms, _, _, _ = scan(get_adapter(".ts"), ts, "t.ts")
        self.assertEqual([s["qname"] for s in syms], ["h"])

    def test_bash(self):
        syms, _, _, _ = scan(get_adapter(".sh"), "#!/bin/bash\nstart() {\n  echo go\n}\n", "s.sh")
        self.assertEqual([s["qname"] for s in syms], ["start"])


class RospyShapes(unittest.TestCase):
    SRC = ("import rospy\n"
           "from pkg_vision.msg import TargetInfo, CoreCmd\n"
           "rospy.init_node('yolo_node', anonymous=True)\n"
           "#rospy.init_node('commented_out')\n"
           "rospy.Subscriber('CoreCmd', CoreCmd, cb)\n"
           "pub = rospy.Publisher('/TargetInfo', TargetInfo, queue_size=10)\n"
           "srv = rospy.ServiceProxy('/set_mode', SetMode)\n")

    def setUp(self):
        _, _, self.ifaces, _ = scan(get_adapter(".py"), self.SRC, "d.py")

    def test_node_topic_service(self):
        got = {(i["kind"], i["name"], i.get("role")) for i in self.ifaces}
        self.assertIn(("node", "yolo_node", None), got)
        self.assertIn(("topic", "CoreCmd", "sub"), got)
        self.assertIn(("topic", "/TargetInfo", "pub"), got)
        self.assertIn(("service", "/set_mode", "client"), got)

    def test_commented_code_ignored(self):
        self.assertFalse(any(i["name"] == "commented_out" for i in self.ifaces))

    def test_message_types_captured(self):
        pub = [i for i in self.ifaces if i.get("role") == "pub"][0]
        self.assertEqual(pub["msg"], "TargetInfo")


class Doctor(unittest.TestCase):
    def test_doctor_reports_adapters(self):
        import tempfile
        from dev_docs import cmd_doctor
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "dev-docs")
            os.makedirs(out)
            rc = cmd_doctor(tmp, out)
        self.assertEqual(rc, 0)     # 开发环境装齐语法包 → OK


class CatkinModules(unittest.TestCase):
    def test_three_packages(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangscat_")
        try:
            files = {
                "src/pkg_core/package.xml": "<package><name>ncu</name></package>",
                "src/pkg_core/src/a.cpp": "int a() { return 1; }\n",
                "src/pkg_rtsp/package.xml": "<package><name>pkg_rtsp</name></package>",
                "src/pkg_rtsp/src/b.cpp": "int b() { return 2; }\n",
                "src/pkg_vision/package.xml": "<package><name>pkg_vision</name></package>",
                "src/pkg_vision/detect.py": "def detect():\n    pass\n",
                "photo/x.jpg": "bin",
            }
            for rel, content in files.items():
                p = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
            data = inv.build_inventory(tmp, project_type="catkin")
            names = [(m["name"], m["kind"]) for m in data["modules"]]
            self.assertEqual(names, [("ncu", "package"), ("pkg_rtsp", "package"),
                                     ("pkg_vision", "package")])
            self.assertEqual(data["project_type"], "catkin")
            # 包内符号归属正确的包
            a_sym = [s for s in data["symbols"] if s["qname"] == "a"][0]
            self.assertEqual(a_sym["module"], "MOD-001")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class BuildDeclConsistency(unittest.TestCase):
    """v1.5.2：CMake 声明 vs 实际文件一致性（治"文档照抄声明、读者照做会编译失败"）。"""

    def _mk(self, files):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangscmake_")
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        for rel, body in files.items():
            fp = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
        return tmp

    def test_missing_declared_files_reported(self):
        tmp = self._mk({
            "src/p/package.xml": "<package><name>p</name></package>",
            "src/p/CMakeLists.txt": ("add_message_files(\n  FILES\n  a.msg\n  b.msg\n)\n"
                                     "add_executable(node src/main.cpp)\n"),
            "src/p/msg/a.msg": "uint8 x\n",          # 存在（位于 msg/ 下）
            "src/p/src/main.cpp": "int main(){return 0;}\n",
        })
        data = inv.build_inventory(tmp, project_type="catkin")
        issues = data.get("build_issues") or []
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["missing"], ["b.msg"])   # 只报确实缺失的
        self.assertTrue(any("build_decl_missing" in (n.get("note") or "")
                            for n in data["confidence"]["notes"]))  # 同时进 confidence

    def test_all_declared_files_present(self):
        tmp = self._mk({
            "src/p/package.xml": "<package><name>p</name></package>",
            "src/p/CMakeLists.txt": "add_service_files(FILES s.srv)\n",
            "src/p/srv/s.srv": "bool ok\n---\nbool r\n",
        })
        data = inv.build_inventory(tmp, project_type="catkin")
        self.assertEqual(data.get("build_issues"), [])


class TestFileRule(unittest.TestCase):
    """测试文件跨语言统一口径：只入测试索引，不生成符号卡片。"""

    def test_is_test_file(self):
        from dev_langs import is_test_file
        # v1.5.7（外评 P1-3）：C/C++ 裸 `test.cpp` **不**判测试（实测误伤真实 ROS 节点），
        # 只认 test_*/…_test 与测试目录；脚本类维持裸 test.py 判测试
        yes = ["test_foo.py", "foo_test.cpp", "test_bar.cpp", "tests/a.py", "test/b.js",
               "pkg/__tests__/x.ts", "spec/y.rb", "tests.py",
               "tests/test.cpp", "src/test/main.cpp"]
        no = ["test.cpp", "src/pkg_core/src/test.cpp", "DroneController.cpp",
              "core_node.cpp", "detect.py", "src/tests_helper.py",
              "latest.cpp", "attest.py", "image2rtsp.h"]
        for p in yes:
            self.assertTrue(is_test_file(p), p)
        for p in no:
            self.assertFalse(is_test_file(p), p)

    def test_cpp_test_file_indexed_not_documented(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangstest_")
        try:
            files = {
                "src/p/package.xml": "<package><name>p</name></package>",
                "src/p/src/main.cpp": "int app() { return 1; }\n",
                # v1.5.7：裸 test.cpp 按非测试处理（产符号 + ambiguous note）；test_bar.cpp 判测试
                "src/p/src/test.cpp": "int main() { return 0; }\n",
                "src/p/src/test_bar.cpp": "int tst() { return 0; }\n",
            }
            for rel, content in files.items():
                fp = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
            data = inv.build_inventory(tmp, project_type="catkin")
            names = {s["qname"] for s in data["symbols"]}
            self.assertIn("app", names)
            self.assertIn("main", names)                         # 裸 test.cpp 产符号（P1-3）
            self.assertNotIn("tst", names)                       # test_bar.cpp 仍判测试
            self.assertEqual([t["file"] for t in data["tests"]],
                             ["src/p/src/test_bar.cpp"])
            notes = " ".join(n.get("note", "") for n in data["confidence"]["notes"])
            self.assertIn("ambiguous_test_stem", notes)          # 歧义提示可见
            # 锚点稳定不变式：main（裸 test.cpp，延后追加）的 ID 在所有既有符号之后
            def num(s):
                return int(s["id"].split("-")[1])
            self.assertGreater(num(next(s for s in data["symbols"] if s["qname"] == "main")),
                               max(num(s) for s in data["symbols"] if s["qname"] != "main"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ExternalReviewB1(unittest.TestCase):
    """v1.5.7：外评修复清单 B1 批验收（P0-1/2/3/4/5 + P1-2/5）。"""

    def _tmp(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangs_b1_")
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def _write(self, tmp, files):
        import os
        for rel, content in files.items():
            fp = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)

    def test_p0_1_cpp_qualified_name_normalized(self):
        tmp = self._tmp()
        self._write(tmp, {
            "src/p/package.xml": "<package><name>p</name></package>",
            # 换行混入 qualified 名：`Cls::\n    fn(` 曾裂成 `Cls:: gpsToXy`
            "src/p/src/m.cpp": "void M300Control::\n    gpsToXy() {}\n",
        })
        data = inv.build_inventory(tmp, project_type="catkin")
        qnames = {s["qname"] for s in data["symbols"]}
        self.assertIn("M300Control::gpsToXy", qnames)
        self.assertNotIn("M300Control:: gpsToXy", qnames)
        for z in data["zero_refs"]:                       # 零引用表无带空格名
            self.assertNotIn(" ", z["name"])

    def test_p0_2_ts_lang_routing_and_deps(self):
        from dev_langs import EXT_LANG, get_adapter
        self.assertEqual(EXT_LANG[".ts"], "typescript")   # 曾误报 javascript
        self.assertEqual(EXT_LANG[".tsx"], "tsx")
        self.assertEqual(EXT_LANG[".js"], "javascript")
        self.assertEqual(get_adapter(".ts").grammar, "typescript")
        deps = get_adapter(".ts").scan_deps(b'import { x } from "./util";\n')
        self.assertEqual(deps, ["./util"])                # 曾硬编码 javascript 语法

    def test_p0_4_code_exts_removed(self):
        import dev_langs
        import dev_langs.registry as reg
        self.assertFalse(hasattr(dev_langs, "CODE_EXTS"))
        self.assertFalse(hasattr(reg, "CODE_EXTS"))

    def test_p0_5_missing_grammar_degrades_not_exits(self):
        from dev_langs import MissingGrammar, get_parser
        # 未注册语言 → MissingGrammar（可捕获），不再 SystemExit
        with self.assertRaises(MissingGrammar):
            get_parser("zz_fake_lang")
        # 盘点降级：该语言无符号、notes 标注、langs 标 degraded，进程不退出
        tmp = self._tmp()
        self._write(tmp, {"src/p/app.py": "def hi():\n    return 1\n"})
        from dev_langs import base
        orig_gm, orig_ae = base.grammar_module, inv.available_extractors
        orig_cache = base._PARSER_CACHE
        base.grammar_module = lambda lang: ("tree_sitter_nonexistent_pkg_xyz", "language")
        inv.available_extractors = lambda: {"python": {"extractor": "missing",
                                                       "version": ""}}
        base._PARSER_CACHE = {}          # 清缓存，确保真正走到缺包路径
        try:
            data = inv.build_inventory(tmp, project_type="generic")
        finally:
            base.grammar_module, inv.available_extractors = orig_gm, orig_ae
            base._PARSER_CACHE = orig_cache
        self.assertEqual(data["symbols"], [])
        notes = " ".join(n.get("note", "") for n in data["confidence"]["notes"])
        self.assertIn("missing_grammar", notes)
        self.assertEqual(data["langs"].get("python"), "degraded")

    def test_p1_2_deps_array_on_all_modules(self):
        tmp = self._tmp()
        self._write(tmp, {
            "src/p/package.xml": "<package><name>p</name></package>",
            "src/p/src/a.cpp": "int f() { return 1; }\n",
            "scripts/run.py": "import os\n",
        })
        data = inv.build_inventory(tmp, project_type="catkin")
        for m in data["modules"]:
            self.assertIsInstance(m.get("deps"), list, m["id"])   # 无 deps 缺键

    def test_p1_5_constructor_exempt_from_zero_refs(self):
        tmp = self._tmp()
        self._write(tmp, {"src/a/index.js": "class A {\n  constructor() {}\n}\n"})
        data = inv.build_inventory(tmp, project_type="generic")
        names = {z["name"] for z in data["zero_refs"]}
        self.assertNotIn("constructor", names)            # 框架隐式调用，曾进噪音
        self.assertIn("A", names)                         # 类本身零引用仍如实报告


class ExternalReviewB2(unittest.TestCase):
    """v1.5.8：外评修复 B2 批验收（P1-1/7/8/9）。"""

    def _tmp(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangs_b2_")
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def _write(self, tmp, files):
        import os
        for rel, content in files.items():
            fp = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)

    def test_p1_1_python_package_name_mapping(self):
        tmp = self._tmp()
        self._write(tmp, {
            # pkg 有 __init__.py → 末段目录名注册为可导入包名（此前只按路径匹配，恒失配）
            "pkg/__init__.py": "",
            "pkg/core.py": "def f():\n    return 1\n",
            "other/main.py": "from pkg.core import f\n",
        })
        data = inv.build_inventory(tmp, project_type="generic")
        mods = {m["name"]: m for m in data["modules"]}
        self.assertEqual(mods["other"]["deps"], [mods["pkg"]["id"]])

    def test_p1_1_js_relative_and_alias_imports(self):
        tmp = self._tmp()
        self._write(tmp, {
            "web/lib/util.js": "export function u() {}\n",
            "web/main.js": 'import { u } from "./lib/util.js";\n',
            "src/utils/x.js": "export const x = 1;\n",
            "web/app.js": 'import { x } from "@/utils/x.js";\n',
        })
        data = inv.build_inventory(tmp, project_type="generic")
        mods = {m["path"]: m for m in data["modules"]}
        self.assertEqual(mods["web"]["deps"],
                         sorted([mods["web/lib"]["id"], mods["src"]["id"]]))

    def test_p1_7_scan_errors_aggregated(self):
        tmp = self._tmp()
        self._write(tmp, {"src/a/app.py": "def hi():\n    return 1\n"})
        from dev_langs import python_ts
        orig = python_ts.PythonTreeSitterAdapter._scan

        def boom(self, data, rel, mid, counters):
            raise RuntimeError("boom")

        python_ts.PythonTreeSitterAdapter._scan = boom
        try:
            data = inv.build_inventory(tmp, project_type="generic")
        finally:
            python_ts.PythonTreeSitterAdapter._scan = orig
        self.assertEqual(len(data["scan_errors"]), 1)        # 不再只埋 confidence.notes
        self.assertIn("adapter_error", data["scan_errors"][0]["note"])
        self.assertEqual(data["scan_errors"][0]["file"], "src/a/app.py")

    def test_p1_8_include_allowlist_and_default_changes(self):
        tmp = self._tmp()
        self._write(tmp, {
            "migrations/x.py": "def m():\n    return 1\n",   # 默认排除项已移除（P1-8）
            "build/keep.py": "def k():\n    return 1\n",     # build 仍默认排除
        })
        self.addCleanup(inv.set_include_allowlist, [])
        data = inv.build_inventory(tmp, project_type="generic")
        names = {s["qname"] for s in data["symbols"]}
        self.assertIn("m", names)                            # migrations 默认可扫
        self.assertNotIn("k", names)                         # build 仍排除
        # --include 白名单解除 build 排除
        inv.set_include_allowlist(["build"])
        data2 = inv.build_inventory(tmp, project_type="generic")
        self.assertIn("k", {s["qname"] for s in data2["symbols"]})
        # --exclude 追加可禁回 migrations
        data3 = inv.build_inventory(tmp, extra_exclude=["migrations"],
                                    project_type="generic")
        self.assertNotIn("m", {s["qname"] for s in data3["symbols"]})

    def test_p1_9_msg_field_comment_kept(self):
        tmp = self._tmp()
        self._write(tmp, {"ros_msgs/Num.msg": "# 状态\nint32 num  # 目标编号\n"})
        data = inv.build_inventory(tmp, project_type="generic")
        fields = [i for i in data["interfaces"] if i["kind"] == "msg"][0]["fields"]
        self.assertEqual(fields[0].get("comment"), "目标编号")   # 此前注释被丢弃


class ExternalReviewB3(unittest.TestCase):
    """v1.6.0：外评修复 B3 批验收（P1-4 头/源合并）。"""

    def _tmp(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangs_b3_")
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def _write(self, tmp, files):
        import os
        for rel, content in files.items():
            fp = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)

    def test_p1_4_cpp_decl_def_merge(self):
        tmp = self._tmp()
        self._write(tmp, {
            "src/p/package.xml": "<package><name>p</name></package>",
            # 头文件声明 + 源文件定义：同名同类 → 只留定义
            "src/p/inc/fly.h": "class Fly {\npublic:\n    int go(int x);\n};\n",
            "src/p/src/fly.cpp": "int Fly::go(int x) { return x; }\n",
            # 纯接口（头文件声明无定义）→ 保留
            "src/p/inc/api.h": "class Api {\npublic:\n    virtual void onlyDecl();\n};\n",
        })
        data = inv.build_inventory(tmp, project_type="catkin")
        go = [s for s in data["symbols"] if s.get("cls") == "Fly"]
        self.assertEqual(len(go), 1)                          # 不再两张卡
        self.assertTrue(go[0]["file"].endswith("fly.cpp"))    # 保留定义
        self.assertIn("Fly::go", go[0]["qname"])
        decl = [s for s in data["symbols"] if s.get("cls") == "Api"]
        self.assertEqual(len(decl), 1)                        # 纯接口声明保留
        # ID 稳定不变式：合并是"丢弃"不是"重编号"，幸存者 ID 与合并前一致
        self.assertEqual(len({s["id"] for s in data["symbols"]}),
                         len(data["symbols"]))
        notes = " ".join(n.get("note", "") for n in data["confidence"]["notes"])
        self.assertIn("cpp_decl_def_merged", notes)

    def test_p1_4_refs_not_inflated_by_merge(self):
        tmp = self._tmp()
        self._write(tmp, {
            "src/p/package.xml": "<package><name>p</name></package>",
            "src/p/inc/fly.h": "class Fly {\npublic:\n    int go(int x);\n};\n",
            "src/p/src/fly.cpp": "int Fly::go(int x) { return x; }\n",
        })
        data = inv.build_inventory(tmp, project_type="catkin")
        go = [s for s in data["symbols"] if s.get("cls") == "Fly"][0]
        self.assertEqual(go["refs"], 0)    # 声明+定义不算引用；refs 按合并前 decl 位点口径


class LineKindTs(unittest.TestCase):
    """v1.5.2：语法层行性质判定——治"引用落在注释/字符串里"的假事实。"""

    def _mk(self, content, name):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangslk_")
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return p

    def test_python_triple_quoted_block_is_string(self):
        from dev_langs import line_kind_ts
        p = self._mk('x = 1\n"""\ndead = 2\n"""\ny = 3\n', "a.py")
        lines = open(p, encoding="utf-8").read().splitlines()
        self.assertEqual(line_kind_ts(p, 3, lines[2]), "string")   # 三引号内的"注释掉的代码"
        self.assertIsNone(line_kind_ts(p, 1, lines[0]))
        self.assertIsNone(line_kind_ts(p, 5, lines[4]))

    def test_python_indented_comment_is_comment(self):
        from dev_langs import line_kind_ts
        p = self._mk("def f():\n    pass\n    # note\n    return 1\n", "b.py")
        lines = open(p, encoding="utf-8").read().splitlines()
        self.assertEqual(line_kind_ts(p, 3, lines[2]), "comment")  # 缩进注释（列 0 在 block 内）
        self.assertIsNone(line_kind_ts(p, 4, lines[3]))

    def test_cpp_block_comment_is_comment(self):
        from dev_langs import line_kind_ts
        p = self._mk("int a(){return 1;}\n/*\nint dead(){return 0;}\n*/\nint b(){return 2;}\n", "c.cpp")
        lines = open(p, encoding="utf-8").read().splitlines()
        self.assertEqual(line_kind_ts(p, 3, lines[2]), "comment")
        self.assertIsNone(line_kind_ts(p, 1, lines[0]))
        self.assertIsNone(line_kind_ts(p, 5, lines[4]))

    def test_code_line_with_trailing_comment_or_string_is_code(self):
        from dev_langs import line_kind_ts
        p = self._mk('void f();//说明\nconst char *s = "abc";\n', "d.cpp")
        lines = open(p, encoding="utf-8").read().splitlines()
        self.assertIsNone(line_kind_ts(p, 1, lines[0]))   # 行尾注释：仍算代码行
        self.assertIsNone(line_kind_ts(p, 2, lines[1]))   # 行中含字符串：仍算代码行

    def test_docstring_and_literal_lines_are_exempt(self):
        from dev_langs import line_kind_ts
        p = self._mk('"""module doc\nmore\n"""\nDATA = {\n    "k": "v",\n}\n', "f.py")
        lines = open(p, encoding="utf-8").read().splitlines()
        self.assertIsNone(line_kind_ts(p, 1, lines[0]))   # 模块文档字符串起始行：正当锚点
        self.assertIsNone(line_kind_ts(p, 3, lines[2]))   # 文档字符串结束行
        self.assertIsNone(line_kind_ts(p, 5, lines[4]))   # dict 字面量行（含字符串但非整行）

    def test_doxygen_comment_is_exempt(self):
        from dev_langs import line_kind_ts
        p = self._mk("int a;\n/**\n * doc for b\n */\nint b;\n", "g.cpp")
        lines = open(p, encoding="utf-8").read().splitlines()
        for rowno in (2, 3, 4):
            self.assertIsNone(line_kind_ts(p, rowno, lines[rowno - 1]))

    def test_no_grammar_type_returns_none(self):
        from dev_langs import line_kind_ts
        p = self._mk("# comment\nuint8 a\n", "e.msg")
        self.assertIsNone(line_kind_ts(p, 2, "uint8 a"))


class RefCounts(unittest.TestCase):
    """v1.5.3：全库引用计数基建（标识符计数 + C/C++ 宏定义采集）。"""

    def _mk(self, content, name):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangsrefs_")
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return p

    def test_identifier_counts_excludes_comments_and_strings(self):
        from dev_langs import identifier_counts
        p = self._mk('def dead():\n    pass\n'
                     '# dead mentioned in comment\n'
                     's = "dead in string"\n'
                     'x = dead()\n', "a.py")
        c = identifier_counts(p)
        self.assertEqual(c.get("dead"), 2)     # def 行 + 调用行；注释/字符串不计
        self.assertEqual(c.get("x"), 1)

    def test_identifier_counts_no_grammar_empty(self):
        from dev_langs import identifier_counts
        p = self._mk("uint8 voltage\n", "b.msg")
        self.assertEqual(identifier_counts(p), {})

    def test_macro_defs_cpp(self):
        from dev_langs import macro_defs
        p = self._mk("#define LIMIT_PIX_X 25\n"
                     "#define GO(x) move(x)\n"
                     "int f() { return GO(1); }\n", "m.cpp")
        self.assertEqual(macro_defs(p),
                         [("LIMIT_PIX_X", 1), ("GO", 2)])

    def test_macro_defs_python_empty(self):
        from dev_langs import macro_defs
        p = self._mk("X = 1\n", "c.py")
        self.assertEqual(macro_defs(p), [])


class DeterminismAndRecon(unittest.TestCase):
    APP = {
        "src/a.py": "def f():\n    pass\n",
        "src/Demo.msg": "uint8 x\n",
    }

    def _build(self, root):
        return inv.build_inventory(root)

    def test_deterministic(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp(prefix="devlangsdet_")
        try:
            for rel, content in self.APP.items():
                p = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
            a = inv.canon_hash(self._build(tmp))
            b = inv.canon_hash(self._build(tmp))
            self.assertEqual(a, b)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_interfaces_counted_for_recon(self):
        from dev_docs import inventory_ids
        inv_data = {"symbols": [], "endpoints": [],
                    "interfaces": [{"id": "MSG-001", "kind": "msg", "module": "MOD-001",
                                    "name": "Demo", "file": "src/Demo.msg", "line": 1,
                                    "fields": []}]}
        self.assertIn("MSG-001", inventory_ids(inv_data))


if __name__ == "__main__":
    unittest.main()
