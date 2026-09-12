# -*- coding: utf-8 -*-
"""dev_langs.base — 语言适配器基类与公共设施。

适配器模式：每种语言一个 LanguageAdapter 子类，只实现语言相关的扫描钩子；
base.scan() 是 dev_inventory 唯一调用的入口，返回统一 schema 的四元组
(symbols, endpoints, interfaces, notes)。

约定：
- 输入 data 为文件原始字节（tree-sitter 直接解析字节；文本按需 utf-8 replace 解码）。
- 输出确定性：符号顺序 = 节点 start_byte 顺序；ID 由全局 counters 分配。
- tree-sitter 是运行时硬依赖：get_parser 失败直接抛错（由上层给出安装指引）。
- 单文件异常在 base.scan 兜底为 note，不拖垮整个盘点。
"""
import re

# 统一符号 schema 的 TODO 占位（与 dev_docs.SYM_TODO 同文案；此处独立定义防循环导入）
SYM_TODO = "<!-- TODO AI 依源码填写（用途 / 参数 / 返回 / 错误；缺失写 unknown） -->"

# 单符号签名提取的最大行跨度（防超长函数签名拖慢）
_SIG_MAX_SPAN = 60

_PARSER_CACHE = {}

# 多语法包特例：lang -> (模块名, 语言函数名)
_TS_SPECIAL = {
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
}


def grammar_module(lang):
    """语言 -> (语法包模块名, 语言函数名)。"""
    if lang in _TS_SPECIAL:
        return _TS_SPECIAL[lang]
    return "tree_sitter_" + lang, "language"


def grammar_version(lang):
    """语法包版本号（探测/报告用），缺失返回 None。"""
    try:
        import importlib.metadata as md
        return md.version(grammar_module(lang)[0].replace("_", "-"))
    except Exception:
        return None


def get_parser(lang):
    """按语言取 tree-sitter Parser（进程内单例）。语法包缺失时抛出带安装指引的异常。"""
    if lang in _PARSER_CACHE:
        return _PARSER_CACHE[lang]
    try:
        from tree_sitter import Language, Parser
        import importlib
        module_name, func_name = grammar_module(lang)
        mod = importlib.import_module(module_name)
        parser = Parser(Language(getattr(mod, func_name)()))
    except ImportError as e:
        raise SystemExit(
            "缺少运行时依赖 tree-sitter（%s）：请执行 pip install -r skills/dev-docs/requirements.txt" % e
        )
    _PARSER_CACHE[lang] = parser
    return parser


def node_text(data, node):
    """节点原文（utf-8 replace 解码）。"""
    if node is None:
        return ""
    return data[node.start_byte:node.end_byte].decode("utf-8", "replace")


def walk(node):
    """深度优先遍历（含自身），顺序稳定。"""
    stack = [node]
    while stack:
        cur = stack.pop()
        yield cur
        for child in reversed(cur.children):
            stack.append(child)


def sig_from_lines(lines, row0):
    """从源码行构造签名文本（def 起始行至括号闭合；与原 ast 版算法逐行等价）。"""
    start = row0
    if start < 0 or start >= len(lines):
        return ""
    depth = 0
    buf = []
    i = start
    while i < len(lines):
        line = lines[i]
        buf.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0 and (")" in line or i > start):
            break
        if i - start > _SIG_MAX_SPAN:
            break
        i += 1
    sig = " ".join(x.strip() for x in buf)
    if "->" in sig:
        sig = sig.split("->")[0].rstrip()
    if sig.endswith(":"):
        sig = sig[:-1]
    sig = re.sub(r"\s+", " ", sig)
    return sig.strip()


class LanguageAdapter:
    """语言适配器基类。子类实现 _scan，返回 (symbols, endpoints, interfaces, notes)。"""

    lang = ""
    exts = ()
    capability = "reliable"

    def scan(self, data, rel_path, module_id, counters):
        """统一入口（含单文件异常兜底）。"""
        try:
            return self._scan(data, rel_path, module_id, counters)
        except Exception as e:  # noqa: BLE001 单文件异常不拖垮盘点
            return [], [], [], [{"note": "adapter_error %s: %s" % (self.lang, e)}]

    def _scan(self, data, rel_path, module_id, counters):
        raise NotImplementedError

    # ---- ID 分配（全局 counters 共享，保证跨语言唯一） ----

    @staticmethod
    def _fun_id(counters):
        counters["fun"] += 1
        return "FUN-%03d" % counters["fun"]

    @staticmethod
    def _api_id(counters):
        counters["api"] += 1
        return "API-%03d" % counters["api"]

    @staticmethod
    def _iface_id(counters, kind):
        # kind -> (计数器键, ID 前缀)：msg/srv=接口定义；topic/service=ROS 话题/服务绑定；
        # node=ROS 节点入口
        key, prefix = {
            "msg": ("msg", "MSG"), "srv": ("srv", "SRV"),
            "topic": ("top", "TOP"), "service": ("svc", "SVC"),
            "node": ("nde", "NDE"),
        }.get(kind, ("msg", "MSG"))
        counters[key] = counters.get(key, 0) + 1      # 容错：调用方 counters 未预置该键
        return "%s-%%03d" % prefix % counters[key]

    # ---- 公共 schema 构造 ----

    @staticmethod
    def _symbol(sid, kind, module_id, qname, rel_path, line, signature,
                public=True, cls=None, visibility=None, extractor="tree-sitter"):
        s = {
            "id": sid, "kind": kind, "module": module_id, "qname": qname,
            "file": rel_path, "line": line, "signature": signature,
            "public": public, "extractor": extractor, "confidence": "reliable",
            "tested_by": [],
        }
        if cls:
            s["cls"] = cls
        if visibility:
            s["visibility"] = visibility
        return s

    @staticmethod
    def _first_line(data, node, limit=160):
        """节点首行文本（签名展示用）。"""
        t = node_text(data, node).splitlines()
        if not t:
            return ""
        return t[0].strip()[:limit]
