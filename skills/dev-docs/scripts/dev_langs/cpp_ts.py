# -*- coding: utf-8 -*-
"""dev_langs.cpp_ts — C/C++ 适配器（tree-sitter 实现）。

收集范围：
- function_definition：.cpp/.cc/.cxx 定义 + 纯头文件内联定义；qualified 名（M300Control::foo）
  拆出 cls，kind=method
- class_specifier / struct_specifier（带名）：kind=class
- field_declaration：仅头文件（.h/.hpp/.hh）中的方法声明 → kind=method（类接口面）
- 匿名命名空间整棵跳过；宏调用只进 scan_calls，不产生符号（防宏爆炸）
- public 一律 True（C++ 无下划线约定）；visibility 暂不判定（二期）
"""
from .base import LanguageAdapter, get_parser, node_text, walk

_HEADER_EXTS = (".h", ".hpp", ".hh")


def _decl_name(data, fn_node):
    """沿 declarator 链下钻取名字。返回 (name, cls)；qualified 名拆 `::` 前缀。"""
    cur = fn_node.child_by_field_name("declarator")
    seen = None
    while cur is not None:
        if cur.type in ("identifier", "field_identifier", "qualified_identifier",
                        "destructor_name", "operator_name"):
            seen = cur
        nxt = cur.child_by_field_name("declarator")
        if nxt is None:
            break
        cur = nxt
    if seen is None:
        return None, None
    t = node_text(data, seen)
    if "::" in t:
        cls, name = t.rsplit("::", 1)
        return name, cls or None
    return t, None


def _sig_text(data, node):
    t = node_text(data, node).split("{", 1)[0]
    t = " ".join(t.split())
    return t.strip()[:200]


class CppTreeSitterAdapter(LanguageAdapter):
    lang = "cpp"
    exts = (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".h")
    grammar = "cpp"

    def _scan(self, data, rel_path, module_id, counters):
        root = get_parser(self.grammar).parse(data).root_node
        is_header = rel_path.lower().endswith(_HEADER_EXTS)
        symbols, notes = [], []
        cls_stack = []

        def on_class(node):
            name_node = node.child_by_field_name("name")
            if name_node is None:
                return None
            name = node_text(data, name_node)
            symbols.append(self._symbol(
                self._fun_id(counters), "class", module_id, name, rel_path,
                node.start_point[0] + 1, _sig_text(data, node)))
            return name

        def on_function(node):
            name, cls = _decl_name(data, node)
            if not name:
                return
            kind = "method" if (cls or cls_stack) else "function"
            symbols.append(self._symbol(
                self._fun_id(counters), kind, module_id,
                "%s::%s" % (cls, name) if cls else name, rel_path,
                node.start_point[0] + 1, _sig_text(data, node),
                cls=cls or (cls_stack[-1] if cls_stack else None)))

        def on_field_decl(node):
            # 类内声明（仅头文件计数，避免与 .cpp 定义重复入表）
            if not is_header:
                return
            decl = node.child_by_field_name("declarator")
            if decl is None:
                return
            fn = decl if decl.type == "function_declarator" else None
            if fn is None:
                for ch in decl.children:
                    if ch.type == "function_declarator":
                        fn = ch
                        break
            if fn is None:
                return
            name, cls = _decl_name(data, fn)
            if not name:
                return
            cls = cls or (cls_stack[-1] if cls_stack else None)
            symbols.append(self._symbol(
                self._fun_id(counters), "method", module_id,
                "%s::%s" % (cls, name) if cls else name, rel_path,
                node.start_point[0] + 1, _sig_text(data, node),
                cls=cls, visibility="public"))

        def visit(node):
            if node.type == "namespace_definition" and node.child_by_field_name("name") is None:
                return                     # 匿名命名空间：内部链接，整棵跳过
            if node.type == "class_specifier" or node.type == "struct_specifier":
                name = on_class(node)
                body = node.child_by_field_name("body")
                if body is not None:
                    if name:
                        cls_stack.append(name)
                    for ch in node.children:
                        visit(ch)
                    if name:
                        cls_stack.pop()
                    return
            elif node.type == "function_definition":
                on_function(node)
            elif node.type == "field_declaration":
                on_field_decl(node)
            elif node.type == "call_expression":
                pass                       # 调用关系走 scan_calls（独立遍历）
            for ch in node.children:
                visit(ch)

        visit(root)
        return symbols, [], [], notes

    def scan_calls(self, data):
        root = get_parser(self.grammar).parse(data).root_node
        out = []
        for n in walk(root):
            if n.type == "call_expression":
                fn = n.child_by_field_name("function")
                if fn is not None:
                    out.append({"line": n.start_point[0] + 1,
                                "callee": node_text(data, fn)[:80]})
        return out

    def scan_deps(self, data):
        root = get_parser(self.grammar).parse(data).root_node
        out = []
        for n in walk(root):
            if n.type == "preproc_include":
                t = node_text(data, n).replace("#include", "").strip()
                out.append(t.strip("\"'")[:120])
        return out
