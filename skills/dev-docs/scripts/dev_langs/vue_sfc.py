# -*- coding: utf-8 -*-
"""dev_langs.vue_sfc — Vue 单文件组件适配器（v1.7.0，外评 B4-3/P2-1）。

范围（最小可用，经高仿真 SFC 样本检测）：
- 切出 `<script>` / `<script setup>` 块，复用 TS 语法（typescript grammar 兼容 JS）
  抽取函数/类/方法/箭头函数赋值——与 js_ts 同一扫描器（注释/字符串天然不误抓）；
- 每组件一个 `component` 符号（优先 options API `name:` 字段，退回文件名）；
- `defineProps` / `defineEmits` 正则识别 → prop/emit 契约符号；
- template/style 不解析（如实缺失）；外链 `<script src=…>` 跳过并记 note；
- scan_deps：script 块内 import 语句源（保序去重，供依赖映射）。

已知局限（如实口径）：options API 的 `methods: {...}` 对象方法不展开（js_ts 对
对象字面量方法的既有局限，函数体符号以 function 形式入档）；template 内联
表达式不抽符号。行号换算：符号行 = script 块内行号 + 块起始偏移；file 保持
.vue 原路径。
"""
import re

from .base import LanguageAdapter
from .js_ts import TsTreeSitterAdapter

_SCRIPT_RE = re.compile(r"<script([^>]*)>(.*?)</script>", re.S | re.I)
_PROPS_RE = re.compile(r"\bdefineProps\s*(?:<[^>]*>)?\s*\(")
_EMITS_RE = re.compile(r"\bdefineEmits\s*(?:<[^>]*>)?\s*\(")
_IMPORT_RE = re.compile(r"import\s+[^;]*?from\s+['\"]([^'\"]+)['\"]")
_COMP_NAME_RE = re.compile(r"(?m)^\s*name\s*:\s*['\"]([A-Za-z_$][\w$]*)['\"]")

_SCANNER = TsTreeSitterAdapter()   # 复用 TS 扫描器（单例；counters 由调用方传入）


class VueSfcAdapter(LanguageAdapter):
    lang = "vue"
    exts = (".vue",)
    grammar = "typescript"          # script 块用 TS 语法解析（doctor 探测同源）

    def _scan(self, data, rel_path, module_id, counters):
        text = data.decode("utf-8", "replace")
        symbols, deps, notes = [], [], []
        comp = rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        comp_done = False
        for m in _SCRIPT_RE.finditer(text):
            attrs, body = m.group(1), m.group(2)
            if re.search(r"\bsrc\s*=", attrs):
                notes.append({"note": "vue_sfc_external_script %s（外链 script 不解析）"
                                      % rel_path})
                continue
            off = text[:m.start(2)].count("\n")
            # 组件符号（每 SFC 一个）：优先 options API 的 name 字段，退回文件名。
            # 组件是 Vue 项目的核心单元，必须有卡片锚点（v1.7.0 质量检测补充）。
            if not comp_done:
                nm = _COMP_NAME_RE.search(body)
                comp_name = (nm.group(1) if nm else comp)
                symbols.append(self._symbol(
                    self._fun_id(counters), "component", module_id, comp_name,
                    rel_path, text[:m.start(2)].count("\n") + 1,
                    "Vue 组件（%s，evidence: 事实）" % comp_name))
                comp_done = True
            syms, _e, _i, _n = _SCANNER._scan(
                body.encode("utf-8"), rel_path + ".ts", module_id, counters)
            for s in syms:
                s["file"] = rel_path
                s["line"] = s.get("line", 1) + off
            symbols += syms
            for im in _IMPORT_RE.finditer(body):
                if im.group(1) not in deps:
                    deps.append(im.group(1)[:120])
            for rx, kind in ((_PROPS_RE, "prop"), (_EMITS_RE, "emit")):
                pm = rx.search(body)
                if pm:
                    symbols.append(self._symbol(
                        self._fun_id(counters), kind, module_id,
                        "%s.%s" % (comp, kind), rel_path,
                        text[:m.start(2) + pm.start()].count("\n") + 1,
                        "define%s（%s 组件契约，evidence: 事实）"
                        % ("Props" if kind == "prop" else "Emits", comp)))
        return symbols, [], [], notes

    def scan_deps(self, data):
        text = data.decode("utf-8", "replace")
        out = []
        for m in _SCRIPT_RE.finditer(text):
            if re.search(r"\bsrc\s*=", m.group(1)):
                continue
            for d in _SCANNER.scan_deps(m.group(2).encode("utf-8")):
                if d not in out:          # 多 script 块共依赖：保序去重
                    out.append(d)
        return out
