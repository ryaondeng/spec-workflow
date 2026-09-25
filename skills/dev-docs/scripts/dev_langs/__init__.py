# -*- coding: utf-8 -*-
"""dev_langs — 语言适配器层（tree-sitter 全语言统一抽取）。

对外出口：
- EXT_LANG: {ext: lang}（原 dev_inventory.EXT_LANG 语义，单一事实源迁至此）
- get_adapter(ext): 按扩展名路由适配器（未注册返回 None）
- available_extractors(): 语言 -> {extractor, version}

适配器模式：每语言一个 LanguageAdapter 子类（base.py），tree-sitter 为运行时
硬依赖；ROS .msg/.srv 无官方 grammar，用文本解析适配器（同接口，extractor=text）。
未注册扩展名（.vue/.proto/.launch 等）不参与符号提取，仅进 L0 文件清单
（v1.5.7 起删除 CODE_EXTS 死代码，口径如实：这些扩展名不参与模块划分）。
"""
from .base import (  # noqa: F401
    LanguageAdapter,
    MissingGrammar,
    ambiguous_test_stem,
    docstrings_by_def_line,
    get_parser,
    identifier_counts,
    is_decl_line,
    is_test_file,
    line_kind_ts,
    macro_defs,
)
from .registry import EXT_LANG, adapters, available_extractors, get_adapter  # noqa: F401
