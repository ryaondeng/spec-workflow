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
        src = (b"class M300Control {\n"
               b" public:\n"
               b"  void FlyForward(uint_32 v);\n"
               b"};\n"
               b"void M300Control::FlyForward(uint_32 v) { }\n"
               b"int standalone() { return 0; }\n"
               b"namespace {\n"
               b"int hidden() { return 1; }\n"
               b"}\n")
        syms, _, _, _ = scan(get_adapter(".cpp"), src, "a.cpp")
        qnames = {s["qname"] for s in syms}
        self.assertIn("M300Control", qnames)                       # class
        self.assertIn("M300Control::FlyForward", qnames)           # .cpp 定义
        self.assertIn("standalone", qnames)
        self.assertNotIn("hidden", qnames)                         # 匿名命名空间跳过
        kinds = {s["qname"]: s["kind"] for s in syms}
        self.assertEqual(kinds["M300Control::FlyForward"], "method")
        self.assertEqual(kinds["standalone"], "function")

    def test_header_method_declaration(self):
        src = (b"class Image2RTSPNodelet {\n"
               b"  virtual void onInit();\n"
               b"};\n")
        syms, _, _, _ = scan(get_adapter(".h"), src, "x.h")
        self.assertTrue(any(s["qname"] == "Image2RTSPNodelet::onInit" and s["kind"] == "method"
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
           "from yolov7.msg import recTargetInfo, ncuCmd\n"
           "rospy.init_node('yolo_node', anonymous=True)\n"
           "#rospy.init_node('commented_out')\n"
           "rospy.Subscriber('NcuCmd', ncuCmd, cb)\n"
           "pub = rospy.Publisher('/RecTargetInfo', recTargetInfo, queue_size=10)\n"
           "srv = rospy.ServiceProxy('/set_mode', SetMode)\n")

    def setUp(self):
        _, _, self.ifaces, _ = scan(get_adapter(".py"), self.SRC, "d.py")

    def test_node_topic_service(self):
        got = {(i["kind"], i["name"], i.get("role")) for i in self.ifaces}
        self.assertIn(("node", "yolo_node", None), got)
        self.assertIn(("topic", "NcuCmd", "sub"), got)
        self.assertIn(("topic", "/RecTargetInfo", "pub"), got)
        self.assertIn(("service", "/set_mode", "client"), got)

    def test_commented_code_ignored(self):
        self.assertFalse(any(i["name"] == "commented_out" for i in self.ifaces))

    def test_message_types_captured(self):
        pub = [i for i in self.ifaces if i.get("role") == "pub"][0]
        self.assertEqual(pub["msg"], "recTargetInfo")


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
                "src/ncu/package.xml": "<package><name>ncu</name></package>",
                "src/ncu/src/a.cpp": "int a() { return 1; }\n",
                "src/ros_rtsp/package.xml": "<package><name>ros_rtsp</name></package>",
                "src/ros_rtsp/src/b.cpp": "int b() { return 2; }\n",
                "src/yolov7/package.xml": "<package><name>yolov7</name></package>",
                "src/yolov7/detect.py": "def detect():\n    pass\n",
                "photo/x.jpg": "bin",
            }
            for rel, content in files.items():
                p = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
            data = inv.build_inventory(tmp, project_type="catkin")
            names = [(m["name"], m["kind"]) for m in data["modules"]]
            self.assertEqual(names, [("ncu", "package"), ("ros_rtsp", "package"),
                                     ("yolov7", "package")])
            self.assertEqual(data["project_type"], "catkin")
            # 包内符号归属正确的包
            a_sym = [s for s in data["symbols"] if s["qname"] == "a"][0]
            self.assertEqual(a_sym["module"], "MOD-001")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


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
