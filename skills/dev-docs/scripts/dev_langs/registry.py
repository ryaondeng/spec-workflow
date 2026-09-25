# -*- coding: utf-8 -*-
"""dev_langs.registry — 适配器注册表与路由。"""
from .bash_ts import BashTreeSitterAdapter
from .c_ts import CTreeSitterAdapter
from .cpp_ts import CppTreeSitterAdapter
from .java_ts import JavaTreeSitterAdapter
from .js_ts import JsTreeSitterAdapter, TsTreeSitterAdapter, TsxTreeSitterAdapter
from .python_ts import PythonTreeSitterAdapter
from .text_msgsrv import MsgSrvTextAdapter
from .vue_sfc import VueSfcAdapter

_ADAPTERS = (
    PythonTreeSitterAdapter(),
    CppTreeSitterAdapter(),
    CTreeSitterAdapter(),
    JavaTreeSitterAdapter(),
    JsTreeSitterAdapter(),
    TsTreeSitterAdapter(),
    TsxTreeSitterAdapter(),
    VueSfcAdapter(),
    BashTreeSitterAdapter(),
    MsgSrvTextAdapter(),
)

# ext -> lang（保持原 dev_inventory.EXT_LANG 的对外语义；value 为语言名）
EXT_LANG = {ext: a.lang for a in _ADAPTERS for ext in a.exts}

_BY_EXT = {}
for _a in _ADAPTERS:
    for _e in _a.exts:
        _BY_EXT[_e] = _a


def get_adapter(ext):
    """按扩展名路由适配器；未注册语言返回 None（文件仍进 L0 全集）。"""
    return _BY_EXT.get(ext.lower())


def adapters():
    return list(_ADAPTERS)


def available_extractors():
    """语言 -> {extractor, version}（doctor/报告展示用）。

    v1.5.7（外评 P0-3）：探测覆盖适配器**实际会用到的全部语法**（grammar 属性），
    而非仅主语法——此前 JsTs 单适配器 grammar=javascript，tree_sitter_typescript
    缺失时 doctor 仍全绿，.ts 一解析才 SystemExit。"""
    import importlib
    from .base import grammar_module, grammar_version
    out = {}
    for a in _ADAPTERS:
        if getattr(a, "grammar", None):
            module_name, _ = grammar_module(a.grammar)
            try:
                importlib.import_module(module_name)
                out[a.lang] = {"extractor": "tree-sitter",
                               "version": grammar_version(a.grammar) or "?"}
            except ImportError:
                out[a.lang] = {"extractor": "missing", "version": ""}
        else:
            out[a.lang] = {"extractor": "text", "version": ""}
    return out
