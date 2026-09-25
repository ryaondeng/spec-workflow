# -*- coding: utf-8 -*-
"""dev_langs.js_ts — JavaScript / TypeScript / TSX 适配器（tree-sitter 实现）。

收集范围：
- function_declaration / method_definition / class_declaration
- 箭头函数赋值（const f = (…) => …）→ kind=function
- HTTP 端点（v1.7.0 B4-3）：Express/Koa 风格 `app.get("path", handler)` 与
  NestJS 风装饰器 `@Get("path")` → API- 端点（正则识别；变量路由如实缺失）
- scan_deps：import 语句源（按扩展名选语法解析，与主扫描一致）
- 语法：.js/.mjs/.cjs → javascript；.ts → typescript；.tsx → tsx

v1.5.7（外评 P0-2/P0-3）：拆分为 Js/Ts/Tsx 三个适配器——此前单适配器
lang="javascript" 使 .ts 被报告为 javascript、EXT_LANG/doctor/依赖扫描全部失真；
拆分后每个适配器 lang/grammar 自洽（EXT_LANG: .ts→typescript，.tsx→tsx），
scan_deps 也不再硬编码语法。
"""
import re

from .base import LanguageAdapter, node_text, parse_tree, walk


def _grammar_for(ext):
    if ext == ".ts":
        return "typescript"
    if ext == ".tsx":
        return "tsx"
    return "javascript"


# HTTP 端点（B4-3）：Express/Koa `app.get("path", handler)` + NestJS `@Get("path")`
_EXPRESS_EP = re.compile(
    r"\b(?:app|router|server|api)\.(get|post|put|patch|delete|all)\s*"
    r"\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*([A-Za-z_$][\w$.]*))?", re.I)
_NEST_EP = re.compile(
    r"@\(?(Get|Post|Put|Patch|Delete|All)\)?\s*\(\s*['\"]?([^'\")]*)['\"]?")


def _in_comment(text, pos):
    ls = text.rfind("\n", 0, pos) + 1
    line = text[ls:pos]
    return "//" in line or line.lstrip().startswith("*")


def _scan_http_endpoints(text, counters, api_id, rel_path, module_id):
    """文本级端点识别 -> [{id, method, path, handler, module, file, line}]（注释行跳过）。"""
    out = []
    for m in _EXPRESS_EP.finditer(text):
        if _in_comment(text, m.start()):
            continue
        out.append({"id": api_id(counters), "method": [m.group(1).upper()],
                    "path": m.group(2), "handler": m.group(3) or "unknown",
                    "module": module_id, "file": rel_path,
                    "line": text[:m.start()].count("\n") + 1})
    for m in _NEST_EP.finditer(text):
        if _in_comment(text, m.start()):
            continue
        out.append({"id": api_id(counters), "method": [m.group(1).upper()],
                    "path": m.group(2) or "/", "handler": "unknown",
                    "module": module_id, "file": rel_path,
                    "line": text[:m.start()].count("\n") + 1})
    out.sort(key=lambda e: e["id"])
    return out


class _JsTsBase(LanguageAdapter):
    """共享扫描实现（Js/Ts/Tsx 三适配器复用；语法树结构同族）。"""

    def _scan(self, data, rel_path, module_id, counters):
        grammar = _grammar_for("." + rel_path.lower().rsplit(".", 1)[-1])
        tree, root = parse_tree(grammar, data)
        symbols, deps = [], []
        cls_stack = []

        def on_class(node):
            name_node = node.child_by_field_name("name")
            if name_node is None:
                return None
            name = node_text(data, name_node)
            symbols.append(self._symbol(
                self._fun_id(counters), "class", module_id, name, rel_path,
                node.start_point[0] + 1,
                node_text(data, node).split("{", 1)[0].strip()[:200]))
            return name

        def add_fn(name, node, cls=None, kind="function"):
            if not name:
                return
            symbols.append(self._symbol(
                self._fun_id(counters), "method" if cls else kind, module_id,
                "%s.%s" % (cls, name) if cls else name, rel_path,
                node.start_point[0] + 1,
                node_text(data, node).split("{", 1)[0].strip()[:200],
                cls=cls))

        def visit(node):
            if node.type in ("class_declaration", "class"):
                name = on_class(node)
                if name:
                    cls_stack.append(name)
                for ch in node.children:
                    visit(ch)
                if name:
                    cls_stack.pop()
                return
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                add_fn(node_text(data, name_node) if name_node else None, node)
            elif node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                add_fn(node_text(data, name_node) if name_node else None, node,
                       cls=cls_stack[-1] if cls_stack else None)
            elif node.type in ("lexical_declaration", "variable_declaration"):
                for d in node.children:
                    if d.type == "variable_declarator":
                        name_node = d.child_by_field_name("name")
                        value = d.child_by_field_name("value")
                        if value is not None and value.type in ("arrow_function", "function"):
                            add_fn(node_text(data, name_node) if name_node else None, d)
            elif node.type == "import_statement":
                src = node.child_by_field_name("source")
                if src is not None:
                    deps.append(node_text(data, src).strip("\"'")[:120])
            for ch in node.children:
                visit(ch)

        visit(root)
        endpoints = _scan_http_endpoints(
            data.decode("utf-8", "replace"), counters, self._api_id,
            rel_path, module_id)
        return symbols, endpoints, [], []

    def scan_deps(self, data):
        # 独立解析收集 import 源；语法按子类 grammar（与该适配器扩展名族一致）
        tree, root = parse_tree(self.grammar, data)
        out = []
        for node in walk(root):
            if node.type == "import_statement":
                src = node.child_by_field_name("source")
                if src is not None:
                    out.append(node_text(data, src).strip("\"'")[:120])
        return out


class JsTreeSitterAdapter(_JsTsBase):
    lang = "javascript"
    exts = (".js", ".mjs", ".cjs")
    grammar = "javascript"


class TsTreeSitterAdapter(_JsTsBase):
    lang = "typescript"
    exts = (".ts",)
    grammar = "typescript"


class TsxTreeSitterAdapter(_JsTsBase):
    lang = "tsx"
    exts = (".tsx",)
    grammar = "tsx"
