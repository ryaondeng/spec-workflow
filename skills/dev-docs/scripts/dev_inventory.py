# -*- coding: utf-8 -*-
"""dev-docs 盘点核心：文件树扫描 / 语言指纹 / 模块划分 / 符号与端点枚举 / 确定性输出。

原则：
- 输出确定性：同一代码两次盘点结果 byte-identical（不写入时间戳；遍历顺序稳定）。
- 盘点不可靠处显式 unknown/低置信标注，不假装覆盖。
- Python 用标准库 ast（可靠）；Java/TypeScript/Shell 用启发式（低置信，见 lang-mapping.md）。
- 该模块只做"读"，不写任何文档文件。
"""

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict

# ---------------- 常量 ----------------

# 语言指纹：ext -> (lang, 枚举器级别 reliable|heuristic)
EXT_LANG = {
    ".py": ("python", "reliable"),
    ".java": ("java", "heuristic"),
    ".kt": ("kotlin", "heuristic"),
    ".ts": ("typescript", "heuristic"),
    ".tsx": ("typescript", "heuristic"),
    ".js": ("javascript", "heuristic"),
    ".mjs": ("javascript", "heuristic"),
    ".cjs": ("javascript", "heuristic"),
    ".go": ("go", "heuristic"),
    ".rs": ("rust", "heuristic"),
    ".sh": ("shell", "heuristic"),
    ".rb": ("ruby", "heuristic"),
    ".php": ("php", "heuristic"),
}
# 参与端点发现的语言（后端常见）
ROUTE_LANGS = ("python", "java", "typescript", "javascript")

# catkin/ROS 工作空间的构建产物目录（project-type=catkin 时并入排除清单）
CATKIN_EXCLUDE = ["build", "devel", "install", "log"]
# 全文件清单的单文件大小上限：超过则跳过并记 note（防二进制/构建产物撑爆清单）
ALL_FILES_MAX_BYTES = 2 * 1024 * 1024

DEFAULT_EXCLUDE = [
    ".git", "node_modules", "__pycache__", "dist", "build", "out", "target",
    ".venv", "venv", "vendor", ".idea", ".vscode", ".codebuddy", ".specworkflow",
    "*.pyc", "*.pyo", "*.egg-info", "*.min.js", "*.map", ".d.ts",
    "migrations", "coverage", ".pytest_cache", ".tox", ".mypy_cache", "generated-images",
]

SCHEMA_VERSION = 1


# ---------------- 工具 ----------------

def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def run_git(root, args):
    try:
        # 显式 UTF-8 + replace：Windows 中文环境 locale 为 GBK，git 输出含非 ASCII
        # 路径时 text=True 会按 locale 解码失败（异常被吞导致静默降级为非 git）。
        out = subprocess.run(
            ["git", "-C", root] + args,
            capture_output=True, encoding="utf-8", errors="replace", timeout=10
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def head_commit(root):
    return run_git(root, ["rev-parse", "--short", "HEAD"]) or ""


def is_git_root(root):
    return bool(run_git(root, ["rev-parse", "--is-inside-work-tree"]))


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_dumps(obj):
    """确定性的 JSON 序列化：dict 按插入序但由构建器固定；此处排序顶层键不适用，
    改为：递归排序 dict 键，保证 byte-identical（覆盖任何插入顺序）。"""
    def _s(o):
        if isinstance(o, dict):
            return {k: _s(o[k]) for k in sorted(o)}
        if isinstance(o, (list, tuple)):
            return [_s(x) for x in o]
        return o
    return json.dumps(_s(obj), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def canon_hash(obj):
    return sha256_text(stable_dumps(obj))


def is_excluded(rel_path, extra):
    parts = rel_path.replace("\\", "/").split("/")
    name = parts[-1]
    for pat in list(DEFAULT_EXCLUDE) + (extra or []):
        if pat.startswith("*."):
            if name.endswith(pat[1:]):
                return True
        elif pat in parts or name == pat:
            return True
    return False


def iter_code_files(root, extra_exclude):
    """遍历代码文件，返回绝对路径列表（排序稳定）。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 就地剪枝排除目录（os.walk 依赖 dirnames 修改）
        keep = []
        for d in sorted(dirnames):
            rel = os.path.relpath(os.path.join(dirpath, d), root)
            if not is_excluded(rel, extra_exclude):
                keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            if is_excluded(rel, extra_exclude):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXT_LANG:
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def detect_langs(root, extra_exclude):
    langs = OrderedDict()
    for fp in iter_code_files(root, extra_exclude):
        ext = os.path.splitext(fp)[1].lower()
        lang, level = EXT_LANG[ext]
        langs.setdefault(lang, level)  # 首次出现的可靠性级别
    return dict(langs)


def detect_project_type(root, extra_exclude):
    """auto 检测项目类型：目录树中发现 package.xml -> catkin，否则 generic。"""
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in sorted(dirnames):
            rel = os.path.relpath(os.path.join(dirpath, d), root)
            if not is_excluded(rel, extra_exclude):
                keep.append(d)
        dirnames[:] = keep
        if "package.xml" in filenames:
            return "catkin"
    return "generic"


def iter_all_files(root, extra_exclude):
    """全文件清单（不经 EXT_LANG 过滤；L0 防漏与漂移基线的事实源）。
    返回 (entries, hashes, notes)：
      entries=[{path, bytes, lang}]（lang=None 表示未登记语言，如 .msg/.cpp）；
      hashes={rel: sha256}（非 git 漂移基线）；
      notes=[{file, note}]（跳过的超大文件）。
    排序稳定；目录剪枝与 iter_code_files 一致。"""
    entries, hashes, notes = [], {}, []
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in sorted(dirnames):
            rel = os.path.relpath(os.path.join(dirpath, d), root)
            if not is_excluded(rel, extra_exclude):
                keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            rel = _rel(root, fp)
            if is_excluded(rel, extra_exclude):
                continue
            try:
                st = os.stat(fp)
            except OSError:
                continue
            if st.st_size > ALL_FILES_MAX_BYTES:
                notes.append({"file": rel,
                              "note": "skipped_large %d bytes" % st.st_size})
                continue
            ext = os.path.splitext(fn)[1].lower()
            lang = EXT_LANG.get(ext, (None, None))[0]
            entries.append({"path": rel, "bytes": st.st_size, "lang": lang})
            hashes[rel] = sha256_file(fp)
    return entries, hashes, notes


def _rel(root, path):
    return os.path.relpath(path, root).replace("\\", "/")


# ---------------- 模块划分 ----------------

def build_modules(root, extra_exclude):
    """代码文件归属划分模块（自底向上聚合单链目录）：
    直接含代码文件的目录为候选；若某目录内只有一个候选子模块且自身无直接代码，
    则上聚到该目录（如 repo/a/pkg/scripts -> repo/a/pkg），多个并列子模块则各自独立。
    根目录自身代码归 MOD-000-root。"""
    code_files = iter_code_files(root, extra_exclude)
    buckets = OrderedDict()  # rel_dir -> [files]
    root_files = []
    for fp in code_files:
        rel = _rel(root, fp)
        d = os.path.dirname(rel)
        if d == "":
            root_files.append(fp)
        else:
            buckets.setdefault(d, []).append(fp)

    # 直接含代码的目录 = 初始候选模块
    members = set(buckets.keys())

    def _count_inside(parent):
        return sum(1 for m in members if m.startswith(parent + "/"))

    changed = True
    while changed:
        changed = False
        for d in sorted(members, key=lambda x: x.count("/"), reverse=True):
            p = os.path.dirname(d)
            if not p or p == "." or p in members or p in buckets:
                # 已上聚到根、自身是候选/有直接代码 => 不再上聚
                continue
            # p 内成员若仅此一个且 p 无直接代码文件 => 上聚
            if _count_inside(p) == 1 and p not in buckets:
                members.discard(d)
                members.add(p)
                changed = True
                break

    modules = []
    if root_files:
        modules.append({
            "id": "MOD-000", "name": "root", "path": ".",
            "langs": _dir_langs(root_files), "kind": "root",
        })
    for i, mdir in enumerate(sorted(members), start=1):
        files = []
        for d, flist in buckets.items():
            if mdir == "." or d == mdir or d.startswith(mdir + "/"):
                files.extend(flist)
        if not files:
            files = [f for f in code_files if _rel(root, f).startswith(mdir + "/")]
        modules.append({
            "id": "MOD-%03d" % i,
            "name": os.path.basename(mdir),
            "path": mdir,
            "langs": _dir_langs(files),
            "kind": "directory",
        })
    return modules


def _dir_langs(files):
    out = OrderedDict()
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        if ext in EXT_LANG:
            out.setdefault(EXT_LANG[ext][0], None)
    return sorted(out)


def module_of(modules, root, filepath):
    rel = _rel(root, filepath)
    d = os.path.dirname(rel)
    if d == "":
        return "MOD-000"
    # 匹配最深路径前缀
    best = "MOD-000"
    best_len = -1
    for m in modules:
        if m["id"] == "MOD-000":
            continue
        p = m["path"]
        if d == p or d.startswith(p + "/"):
            if len(p) > best_len:
                best = m["id"]
                best_len = len(p)
    return best


# ---------------- Python 符号枚举（可靠） ----------------

_HTTP_VERB = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}


def _is_public(name):
    return not name.startswith("_")


def _decorator_name(node):
    """还原装饰器调用/名字的第一段，如 @app.route -> 'app.route'，@app.post -> 'app.post'。"""
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return (base + "." + node.attr) if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _decorator_str(node):
    if isinstance(node, ast.Call):
        fn = _decorator_name(node.func)
        arg0 = None
        if node.args:
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                arg0 = node.args[0].value
        kw = {}
        for k in node.keywords:
            if k.arg and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
                kw[k.arg] = k.value.value
        return {"decorator": fn, "path": arg0, "kw": kw}
    return {"decorator": _decorator_name(node), "path": None, "kw": {}}


def _collect_endpoints(decorators, handler, module_id, filepath, line):
    eps = []
    for d in decorators:
        info = _decorator_str(d)
        fn = info["decorator"] or ""
        tail = fn.rsplit(".", 1)[-1]
        path = info["path"]
        methods = None
        if tail in _HTTP_VERB:
            methods = [tail.upper()]
        elif tail == "route" and "methods" in info["kw"]:
            methods = info["kw"]["methods"].upper().split(",")
        if (methods or tail == "route") and path and path.startswith("/"):
            eps.append({
                "id": "API-XXX", "method": methods or ["*"],
                "path": path, "handler": handler,
            })
        elif fn and (("api" in fn.lower()) or tail in _HTTP_VERB or tail == "route") and path:
            eps.append({
                "id": "API-XXX", "method": (methods or ["*"]),
                "path": path, "handler": handler,
            })
    return eps


def _sig_from_source(source, node):
    """从源码行构造签名文本（含 async/def 起始行至冒号行）。"""
    lines = source.splitlines()
    start = node.lineno - 1
    if start < 0 or start >= len(lines):
        return ""
    # 找参数/返回结束行：统计括号深度
    depth = 0
    buf = []
    i = start
    while i < len(lines):
        line = lines[i]
        buf.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0 and (")" in line or i > start):
            break
        if i - start > 60:  # 防御
            break
        i += 1
    sig = " ".join(x.strip() for x in buf)
    if "->" in sig:
        sig = sig.split("->")[0].rstrip()
    if sig.endswith(":"):
        sig = sig[:-1]
    sig = re.sub(r"\s+", " ", sig)
    return sig.strip()


def scan_python(source, filepath, module_id, counters):
    """返回 (symbols, endpoints, notes)。counters 跨文件共享，保证 ID 全局唯一且输出确定。"""
    symbols, endpoints = [], []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return symbols, endpoints, {"note": "syntax_error %s" % (e,)}

    def _mkid():
        counters["fun"] += 1
        return "FUN-%03d" % counters["fun"]

    def _mkep():
        counters["api"] += 1
        return "API-%03d" % counters["api"]

    def _add_func(name, qname, node, kind):
        sig = _sig_from_source(source, node)
        dec = [_decorator_name(x) for x in getattr(node, "decorator_list", [])]
        return {
            "id": _mkid(), "kind": kind, "module": module_id,
            "qname": qname, "file": filepath, "line": node.lineno,
            "signature": sig, "public": _is_public(name),
            "decorators": dec, "tested_by": [],
        }

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(node.name):
            s = _add_func(node.name, node.name, node, "function")
            symbols.append(s)
            for ep in _collect_endpoints(node.decorator_list, node.name, module_id, filepath, node.lineno):
                ep["id"] = _mkep()
                ep["module"] = module_id
                ep["file"] = filepath
                ep["line"] = node.lineno
                ep["kind"] = "endpoint"
                ep["handler"] = node.name
                ep["confidence"] = "reliable"
                endpoints.append(ep)
                s.setdefault("endpoints", []).append(ep["id"])
        elif isinstance(node, ast.ClassDef) and _is_public(node.name):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(item.name):
                    s = _add_func(item.name, "%s.%s" % (node.name, item.name), item, "method")
                    s["cls"] = node.name
                    symbols.append(s)
                    for ep in _collect_endpoints(item.decorator_list, "%s.%s" % (node.name, item.name),
                                                 module_id, filepath, item.lineno):
                        ep["id"] = _mkep()
                        ep["module"] = module_id
                        ep["file"] = filepath
                        ep["line"] = item.lineno
                        ep["kind"] = "endpoint"
                        ep["confidence"] = "reliable"
                        endpoints.append(ep)
    return symbols, endpoints, {}


def _map_tested(tests):
    """启发式：测试名 test_xxx -> 相关符号名 xxx（供 AI 提取示例时索引，非精确）。"""
    return tests


# ---------------- 启发式扫描（Java/TS/Shell 等，低置信） ----------------

_JAVA_SIG = re.compile(
    r"(?m)^\s*(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
    r"(?:[\w.<>\[\], ?]+)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w, ]+)?\s*\{?"
)
_JAVA_ANN = re.compile(r"(?m)^\s*@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping|Mapping)"
                       r"\s*(\(\s*\"([^\"]+)\"\s*(?:,\s*method\s*=\s*(RequestMethod\.)?(\w+))?\))?")
_TS_EXPORT = re.compile(r"(?m)^\s*export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)")
_TS_CONSTFN = re.compile(r"(?m)^\s*(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?:=>|:)\s*[^=]")
_TS_CLASS_M = re.compile(r"(?m)^\s*(?:(?:public|private|protected|async|static|get|set)\s+)*(\w+)\s*\(([^)]*)\)\s*\{")
_TS_METHOD = re.compile(r"(?m)^\s*(?:(?:public|private|protected)\s+)?(\w+)\s*\(([^)]*)\)\s*:\s*[\w<>\[\]|, ?]+")
_SH_FUNC = re.compile(r"(?m)^\s*([a-zA-Z_][\w]*)\s*\(\s*\)\s*\{|^([a-zA-Z_][\w]*)\s*\(\)")


def scan_heuristic(source, lang, counters):
    out = []
    if lang == "java":
        for m in _JAVA_SIG.finditer(source):
            counters["fun"] += 1
            out.append({"id": "FUN-%03d" % counters["fun"], "kind": "method", "qname": m.group(1),
                        "signature": m.group(0).strip()})
    elif lang in ("typescript", "javascript"):
        for m in _TS_EXPORT.finditer(source):
            counters["fun"] += 1
            out.append({"id": "FUN-%03d" % counters["fun"], "kind": "function", "qname": m.group(1),
                        "signature": "function %s(%s)" % (m.group(1), m.group(2))})
        for m in _TS_CONSTFN.finditer(source):
            counters["fun"] += 1
            out.append({"id": "FUN-%03d" % counters["fun"], "kind": "function", "qname": m.group(1),
                        "signature": "%s(%s)" % (m.group(1), m.group(2))})
    elif lang == "shell":
        for m in _SH_FUNC.finditer(source):
            name = m.group(1) or m.group(2)
            if name:
                counters["fun"] += 1
                out.append({"id": "FUN-%03d" % counters["fun"], "kind": "function", "qname": name,
                            "signature": "%s()" % name})
    return out


# ---------------- 测试索引 ----------------

def collect_tests(root, extra_exclude):
    """测试文件与用例。返回 [{file, cases:[name,...]}]。仅对 python 精确；其它启发式。"""
    tests = []
    for fp in iter_code_files(root, extra_exclude):
        ext = os.path.splitext(fp)[1].lower()
        rel = _rel(root, fp)
        is_test = False
        if ext == ".py":
            base = os.path.basename(fp)
            is_test = base.startswith("test_") or base.endswith("_test.py") or "/test_" in rel or rel.startswith("tests/")
            if is_test:
                cases = []
                try:
                    with open(fp, encoding="utf-8", errors="replace") as fh:
                        tree = ast.parse(fh.read())
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                            cases.append(node.name)
                except (SyntaxError, OSError):
                    pass
                tests.append({"file": rel, "lang": "python", "cases": cases})
    return tests


# ---------------- 主构建 ----------------

def build_inventory(root, extra_exclude=None, project_type="auto"):
    """构建 inventory 结构（不落盘）。project_type: auto|catkin|generic。"""
    extra = extra_exclude or []
    root = os.path.abspath(root)
    ptype = project_type
    if ptype == "auto":
        ptype = detect_project_type(root, extra)
    if ptype == "catkin":
        # catkin 构建产物目录并入排除（对所有扫描生效：代码/全文件/模块/依赖）
        extra = list(extra) + [p for p in CATKIN_EXCLUDE if p not in extra]
    modules = build_modules(root, extra)
    mod_by_id = {m["id"]: m for m in modules}
    langs = detect_langs(root, extra)

    symbols = []
    endpoints = []
    code_file_hashes = {}
    confidence_notes = []
    counters = {"fun": 0, "cls": 0, "api": 0}

    for fp in iter_code_files(root, extra):
        ext = os.path.splitext(fp)[1].lower()
        lang, level = EXT_LANG[ext]
        rel = _rel(root, fp)
        # 测试文件不生成文档符号，只入测试索引
        base = os.path.basename(fp)
        if lang == "python" and (base.startswith("test_") or rel.startswith("tests/")
                                 or base.endswith("_test.py")):
            code_file_hashes[rel] = sha256_file(fp)
            continue
        try:
            with open(fp, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError:
            continue
        code_file_hashes[rel] = sha256_file(fp)
        mid = module_of(modules, root, fp)
        if lang == "python" and level == "reliable":
            try:
                ss, eps, note = scan_python(source, rel, mid, counters)
            except Exception as e:
                ss, eps, note = [], [], {"note": str(e)}
            if note:
                confidence_notes.append({"file": rel, "note": note})
            for s in ss:
                s["file"] = rel
                symbols.append(s)
            for e in eps:
                e["file"] = rel
                endpoints.append(e)
        else:
            # 启发式低置信；跳过明显的重复/大型生成文件由 exclude 兜底
            sigs = scan_heuristic(source, lang, counters)
            # 端点识别 java 注解（低置信）
            if lang == "java":
                for m in _JAVA_ANN.finditer(source):
                    verb = (m.group(4) or "").upper()
                    if not verb and "Mapping" in (m.group(1) or ""):
                        verb = "*"
                    if verb:
                        counters["api"] += 1
                        endpoints.append({
                            "id": "API-%03d" % counters["api"],
                            "kind": "endpoint", "module": mid, "method": verb,
                            "path": m.group(3) or "", "handler": "",
                            "file": rel, "line": 0, "confidence": "heuristic",
                        })
            for s in sigs:
                s["module"] = mid
                s["file"] = rel
                s["public"] = True
                s["confidence"] = "heuristic"
                symbols.append(s)
    # 模块依赖（python import 启发）
    _mod_deps(modules, root, extra)

    tests = collect_tests(root, extra)

    # L0 全文件清单（含未登记语言，如 .cpp/.msg/.srv）+ 非 git 漂移基线
    files, files_hashes, file_notes = iter_all_files(root, extra)
    confidence_notes.extend(file_notes)

    # 为符号稳定 ID：扫描顺序已稳定（排序 + 文件内 AST 顺序），但多文件时 n 跨文件计数需要全局。
    # 处理：python 文件内 ID 是每文件局部；改成全局分配会破坏已生成文档锚点。
    # 结论：ID 采用 "<MOD>:<seq>" 稳定于排序文件顺序；为兼容锚点简单化，此处保留文件内局部 ID，
    # 但为确定性需在排序文件序列中固定（已稳定）。重复风险：同一 qname 跨文件 ID 可能重复——
    # 允许，check 以 (id, file) 判别；文档登记以标题锚点（含 file 名）避免歧义。
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "project_type": ptype,
        "langs": langs,
        "source_commit": head_commit(root),
        "is_git": is_git_root(root),
        "root": root,
        "excluded": list(DEFAULT_EXCLUDE) + list(extra),
        "modules": modules,
        "symbols": symbols,
        "endpoints": endpoints,
        "tests": tests,
        "code_file_hashes": code_file_hashes,
        "files": files,
        "files_hashes": files_hashes,
        "confidence": {"notes": confidence_notes},
    }
    return inventory


def _mod_deps(modules, root, extra):
    """python 模块间 import 启发依赖。"""
    by_path = {m["path"]: m["id"] for m in modules}
    for m in modules:
        if "python" not in m["langs"]:
            continue
        dirpath = os.path.join(root, m["path"]) if m["path"] != "." else root
        deps = set()
        for dirpath2, _, files in os.walk(dirpath):
            if is_excluded(os.path.relpath(dirpath2, root), extra):
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dirpath2, fn)
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        src = fh.read()
                    nodes = ast.parse(src).body
                except (OSError, SyntaxError):
                    continue
                for node in nodes:
                    if isinstance(node, ast.Import):
                        for a in node.names:
                            _map_import_dep(deps, a.name, by_path)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        _map_import_dep(deps, node.module, by_path)
        m["deps"] = sorted(deps - {m["id"]})


def _map_import_dep(deps, imp, by_path):
    for top in by_path:
        if imp == top or imp.startswith(top + "."):
            deps.add(by_path[top])
