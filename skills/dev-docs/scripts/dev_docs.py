# -*- coding: utf-8 -*-
"""dev-docs CLI：inventory / extract / promote / check / report。

依赖：同目录 dev_inventory.py（Python 3.7+，零第三方依赖）。
产物落位：<目标项目>/docs/<out>/（out 默认 dev-docs）。

本工具只读写 <out>/ 下的文档与 JSON（inventory.json/.baseline.json），
不修改目标项目任何代码文件。语义由 AI 按 SKILL.md 填写，机器只做骨架与门禁。
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dev_inventory as inv   # noqa: E402

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(SKILL_DIR, "templates")
BEG = "<!-- AI-GEN:BEGIN -->"
END = "<!-- AI-GEN:END -->"
ANCHOR = re.compile(r"<!--\s*@(FUN-\d+|API-\d+)\s*-->")   # v1.2：ID 下沉为隐藏锚点
MARK = "<!-- TODO AI 依源码填写"   # 语义未填占位（填充度报告用）
SYM_TODO = "<!-- TODO AI 依源码填写（evidence: 推断/假设需注明） -->"
EP_TODO = "<!-- TODO AI 依源码填写；示例取 tested_by 对应测试 -->"


# ---------------- 通用 ----------------

def eprint(*a):
    print(*a, file=sys.stderr)


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # newline="\n"：跨平台固定 LF，避免 Windows 文本模式把 \n 写成 \r\n，
    # 保证生成的 md/json 在任何平台字节一致（确定性 / git diff / CI 漂移检测依赖）
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def json_load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def json_save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 同 write：固定 LF，跨平台字节一致
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(inv.stable_dumps(obj))


def resolve_root(root):
    """git 仓库内则取仓库根；否则用给定目录。"""
    root = os.path.abspath(root)
    toplevel = inv.run_git(root, ["rev-parse", "--show-toplevel"])
    if toplevel:
        return os.path.abspath(toplevel)
    return root


def outdir(root, sub):
    return os.path.join(root, "docs", sub or "dev-docs")


_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


def module_slug(m):
    """文档文件名用语义化 slug（而非 MOD-编号），编号保留在 frontmatter/doc_id。"""
    path = (m.get("path") or "").strip().strip("/")
    if path in ("", "."):
        return "root"
    slug = _SLUG_RE.sub("-", path).strip("-")
    return slug or (m.get("id") or "mod").lower()


def list_md(out):
    files = []
    if os.path.isdir(out):
        for dp, _, fns in os.walk(out):
            for fn in sorted(fns):
                if fn.endswith(".md") and not fn.endswith(".draft.md"):
                    files.append(os.path.join(dp, fn))
    return sorted(files)


def list_drafts(out):
    files = []
    if os.path.isdir(out):
        for dp, _, fns in os.walk(out):
            for fn in sorted(fns):
                if fn.endswith(".draft.md"):
                    files.append(os.path.join(dp, fn))
    return sorted(files)


# ---------------- frontmatter ----------------

def parse_frontmatter(text):
    """返回 (meta, rest)。无 frontmatter 时 meta=None。"""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            block = text[4:end]
            meta = {}
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            rest = text[end + 4:]
            if rest.startswith("\n"):
                rest = rest[1:]
            return meta, rest
    return None, text


def render_frontmatter(meta):
    lines = ["---"]
    for k in ("doc_id", "type", "module_id", "source_commit", "generated_at",
              "inventory_hash", "status"):
        if k in meta and meta[k]:
            lines.append("%s: %s" % (k, meta[k]))
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------- 渲染 ----------------

class _Safe(dict):
    def __missing__(self, key):
        return ""


def render(tpl_name, values):
    path = os.path.join(TEMPLATES, tpl_name)
    if not os.path.exists(path):
        raise SystemExit("模板缺失: %s" % path)
    return read(path).format_map(_Safe(values))


def meta_for(inv_data, doc_id, typ, module_id=None, status="draft"):
    return {
        "doc_id": doc_id, "type": typ,
        "module_id": module_id or "",
        "source_commit": inv_data.get("source_commit") or "",
        "generated_at": now_iso(),
        "inventory_hash": inv_data.get("_inventory_hash") or "",
        "status": status,
    }


def _sym_card(s):
    """v1.2 符号卡片：语义名标题 + 隐藏 ID 锚点。"""
    return ("### %s\n\n"
            "- 签名：`%s`（file %s:%s, evidence: 事实）<!-- @%s -->\n"
            "- 用途 / 参数 / 返回 / 错误：%s\n"
            % (s["qname"], s.get("signature") or "?", s["file"],
               s.get("line", 0), s["id"], SYM_TODO))


def _ep_card(e):
    methods = ",".join(e["method"]) if isinstance(e["method"], list) else (e["method"] or "*")
    title = ("%s %s" % (methods, e.get("path") or "")).strip()
    return ("### %s\n\n"
            "- handler：`%s`（file %s:%s, evidence: 事实）<!-- @%s -->\n"
            "- 参数 / 响应 / 错误 / 示例：%s\n"
            % (title, e.get("handler") or "", e["file"], e.get("line", 0), e["id"], EP_TODO))


def _ep_title(e):
    methods = ",".join(e["method"]) if isinstance(e["method"], list) else (e["method"] or "*")
    return ("%s %s" % (methods, e.get("path") or "")).strip()


def ref_index_rows(inv_data, module_id):
    """符号索引表行：机器全量生成（ID + 人读名 + 类型）。"""
    rows = []
    for s in inv_data["symbols"]:
        if s["module"] != module_id:
            continue
        rows.append("| @%s | %s | %s | — |" % (s["id"], s["qname"], s.get("kind") or "函数"))
    for e in inv_data["endpoints"]:
        if e["module"] != module_id:
            continue
        rows.append("| @%s | %s | 端点 | — |" % (e["id"], _ep_title(e)))
    return rows


def ref_detail_sections(inv_data, module_id):
    """详细契约：按 模块级函数 / 类 / HTTP 端点 分节（分级组织）。"""
    syms = [s for s in inv_data["symbols"] if s["module"] == module_id]
    eps = [e for e in inv_data["endpoints"] if e["module"] == module_id]
    sections = []
    funcs = [s for s in syms if s.get("kind") == "function"]
    if funcs:
        sections.append("## 模块级函数\n\n" +
                        "\n".join(_sym_card(s) for s in funcs))
    by_cls = {}
    order = []
    for s in syms:
        if s.get("kind") != "method":
            continue
        cls = s.get("cls") or "(未归类方法)"
        if cls not in by_cls:
            by_cls[cls] = []
            order.append(cls)
        by_cls[cls].append(s)
    for cls in order:
        sections.append("## 类：%s\n\n" % cls +
                        "\n".join(_sym_card(s) for s in by_cls[cls]))
    others = [s for s in syms if s.get("kind") not in ("function", "method")]
    if others:
        sections.append("## 其他符号\n\n" +
                        "\n".join(_sym_card(s) for s in others))
    if eps:
        sections.append("## HTTP 端点\n\n" +
                        "\n".join(_ep_card(e) for e in eps))
    return "\n\n".join(sections) if sections else "<!-- 本模块无公开符号 -->"


def reference_tpl_values(inv_data, m):
    return {
        "MOD-id": m["id"], "module_name": m["name"], "path": m["path"],
        "lang": ",".join(m.get("langs") or []),
        "n_symbols": len([s for s in inv_data["symbols"] if s["module"] == m["id"]]) +
                     len([e for e in inv_data["endpoints"] if e["module"] == m["id"]]),
        "generated_at": now_iso(),
        "inventory_hash": inv_data.get("_inventory_hash") or "",
        "status": "draft",
        "deps": ",".join(m.get("deps") or []) or "（无内部依赖或待确认）",
        "index_rows": "\n".join(ref_index_rows(inv_data, m["id"])) or "| — | — | — | — |",
        "detail_rows": ref_detail_sections(inv_data, m["id"]),
    }


def arch_values(inv_data):
    rows = []
    for m in inv_data.get("modules", []):
        rows.append("| %s | %s | %s | %s | %s |"
                    % (m["id"], m["name"], m["path"], "（AI 补：职责）",
                       ",".join(m.get("deps") or []) or "—"))
    entries = []
    for lang in inv_data.get("langs", {}):
        entries.append("- %s：<!-- TODO AI：入口文件/启动命令/路由注册 -->" % lang)
    return {
        "project": os.path.basename(inv_data.get("root") or ""),
        "commit": inv_data.get("source_commit") or "",
        "generated_at": now_iso(),
        "inventory_hash": inv_data.get("_inventory_hash") or "",
        "status": "draft",
        "langs": ",".join(inv_data.get("langs", {})) or "?",
        "module_rows": "\n".join(rows),
        "entry_rows": "\n".join(entries),
        "summary": "<!-- TODO AI：一句话定位 -->",
    }


# ---------------- 骨架拆分（人工区保护） ----------------

def split_doc(text):
    """拆 frontmatter + pre + (BEGIN..END) + post。无 marker 视为整段人工。"""
    meta, rest = parse_frontmatter(text)
    bi = rest.find(BEG)
    ei = rest.find(END)
    if bi == -1 or ei == -1 or ei < bi:
        return meta, rest, None, ""
    pre = rest[:bi]
    inside = rest[bi + len(BEG):ei]
    post = rest[ei + len(END):]
    return meta, pre, inside, post


def compose(meta, pre, inside, post):
    parts = []
    if meta:
        parts.append(render_frontmatter(meta))
    parts.append(pre or "")
    if inside is not None:
        parts.append(BEG + "\n")
        parts.append(inside)
        parts.append("\n" + END)
    parts.append(post or "")
    return "".join(parts)


# ---------------- inventory 命令 ----------------

def cmd_inventory(root, out, extra_exclude, quiet=False):
    data = inv.build_inventory(root, extra_exclude)
    data["_inventory_hash"] = inv.canon_hash(
        {k: v for k, v in data.items() if k != "_inventory_hash"})
    inv_dir = os.path.join(out, "inventory.json")
    json_save(inv_dir, data)
    if not quiet:
        print("inventory -> %s" % os.path.relpath(inv_dir, root))
        print("  modules: %d, symbols: %d, endpoints: %d, tests: %d, langs: %s"
              % (len(data["modules"]), len(data["symbols"]),
                 len(data["endpoints"]), len(data["tests"]),
                 ",".join(data.get("langs", {})) or "?"))
        if data["confidence"]["notes"]:
            print("  low-confidence notes: %d (详见 inventory.json.confidence)"
                  % len(data["confidence"]["notes"]))
    return data


def load_inventory(out):
    return json_load(os.path.join(out, "inventory.json"))


# ---------------- 文档生成（extract） ----------------

def ensure_inventory(out, root, extra_exclude):
    data = load_inventory(out)
    if data is None:
        data = cmd_inventory(root, out, extra_exclude)
    return data


def _regen_or_new(out, rel_path, new_text):
    """目标存在则保留 marker 外（pre/post=标题+人工四问/补充）只刷新生成区，输出 draft。"""
    final = os.path.join(out, rel_path)
    draft = final + ".draft"
    meta_new, rest_new = parse_frontmatter(new_text)
    _, new_pre, new_inside, new_post = split_doc(rest_new)
    if os.path.exists(final):
        meta_old, pre_old, inside_old, post_old = split_doc(read(final))
        fm = dict(meta_new or {})
        if meta_old:
            for k in ("doc_id", "type", "module_id"):
                if meta_old.get(k):
                    fm[k] = meta_old[k]
        pre = pre_old if pre_old is not None else (new_pre or "")
        post = post_old if post_old is not None else (new_post or "")
        inside = new_inside if new_inside is not None else (inside_old or "")
        write(draft, compose(fm, pre, inside, post))
    else:
        write(draft, new_text)
    return os.path.relpath(draft, out)


def extract_layer(inv_data, root, out, layer, module_id):
    modules = inv_data["modules"]
    if module_id:
        modules = [m for m in modules if m["id"] == module_id]
    written = []
    if layer == "architecture":
        written.append(_regen_or_new(out, "architecture.md",
                                     render("architecture.md", arch_values(inv_data))))
    elif layer == "reference":
        for m in modules:
            written.append(_regen_or_new(out, "reference/%s.md" % module_slug(m),
                                         render("reference.md", reference_tpl_values(inv_data, m))))
    elif layer == "data":
        for m in modules:
            vals = {
                "MOD-id": m["id"], "module_name": m["name"],
                "commit": inv_data.get("source_commit") or "",
                "generated_at": now_iso(),
                "inventory_hash": inv_data.get("_inventory_hash") or "",
                "status": "draft",
                "entity_rows": "<!-- TODO AI：依源码中的模型/ORM 类补齐实体与字段（缺失写 unknown） -->",
            }
            written.append(_regen_or_new(out, "data/%s.md" % module_slug(m),
                                         render("data.md", vals)))
    else:
        raise SystemExit("未知 layer: %s（可选 architecture|reference|data）" % layer)
    print("生成 %d 个 draft（<target>.md.draft）：" % len(written))
    for w in written:
        print("  - %s" % w)
    print("AI 填充每处 <!-- TODO ... --> 后，经人工确认执行: promote <file.draft>")


def cmd_promote(out, draft_path):
    if not os.path.isabs(draft_path):
        cand = os.path.join(out, draft_path)
        if os.path.exists(cand):
            draft_path = cand
    draft_path = os.path.abspath(draft_path)
    if not draft_path.endswith(".draft"):
        raise SystemExit("promote 目标需为 *.draft（如 modules/MOD-001.md.draft）")
    if not os.path.exists(draft_path):
        raise SystemExit("draft 不存在: %s" % draft_path)
    final = draft_path[:-len(".draft")]
    text = read(draft_path)
    has_marker = BEG in text and END in text
    print("promote %s -> %s" % (os.path.basename(draft_path),
                                os.path.relpath(final, out)))
    if not has_marker:
        print("  ! 警告：文件无 AI-GEN marker（纯人工文档，promote 将直接转正）")
    meta, rest = parse_frontmatter(text)
    if meta is None or not meta.get("doc_id"):
        print("  ! 警告：文件缺 frontmatter（doc_id），建议补上以便对账")
    else:
        # draft 转正：status current
        meta["status"] = "current"
        text = render_frontmatter(meta) + rest
    write(final, text)
    os.remove(draft_path)
    print("完成。建议运行: check --dir <目标项目>")


# ---------------- 对账（check / report） ----------------

def collect_registered(out):
    reg = set()
    doc_files = []
    for fp in list_md(out):
        base = os.path.basename(fp)
        if base == "index.md":
            continue
        doc_files.append(fp)
        reg |= set(ANCHOR.findall(read(fp)))
    return reg, doc_files


def unfilled_todo_count(out):
    """统计正式文档中未填语义的 TODO 占位数（按行近似）。index 不计。"""
    total = 0
    per = {}
    for fp in list_md(out):
        base = os.path.basename(fp)
        if base == "index.md":
            continue
        c = read(fp).count(MARK)
        per[os.path.relpath(fp, out)] = c
        total += c
    return total, per


def inventory_ids(inv_data):
    ids = set()
    for s in inv_data.get("symbols", []):
        if s.get("public", True):
            ids.add(s["id"])
    for e in inv_data.get("endpoints", []):
        ids.add(e["id"])
    return ids


def stale_docs(inv_data, out):
    """文档 frontmatter.source_commit 落后于当前提交 -> stale。非 git 时不判。"""
    if not inv_data.get("is_git") or not inv_data.get("source_commit"):
        return []
    stale = []
    for fp in list_md(out):
        base = os.path.basename(fp)
        if base == "index.md":
            continue
        meta, _ = parse_frontmatter(read(fp))
        if not meta:
            continue
        sc = meta.get("source_commit", "")
        if sc and sc != inv_data["source_commit"]:
            stale.append(os.path.relpath(fp, out))
    return stale


def drift_diff(inv_now, out):
    """对比 baseline 与当前快照，返回代码变更/符号新增删除/受影响模块。"""
    base = json_load(os.path.join(out, ".baseline.json")) or {}
    if not base:
        return None
    changed = []
    old_hashes = base.get("code_file_hashes") or {}
    for rel, h in (inv_now.get("code_file_hashes") or {}).items():
        if old_hashes.get(rel) != h:
            changed.append(rel)
    old_syms = set(base.get("symbol_ids") or [])
    now_syms = {s["id"] for s in inv_now.get("symbols", [])} | \
               {e["id"] for e in inv_now.get("endpoints", [])}
    old_eps = old_syms
    added = sorted(now_syms - old_eps)
    removed = sorted(old_syms - now_syms)
    tops = sorted({c.split("/")[0] for c in changed})
    # 精确受影响模块（最长路径前缀匹配 MOD-id）
    mods = inv_now.get("modules") or []
    affected_mods = set()
    for rel in changed:
        best = None
        for m in mods:
            p = m.get("path") or ""
            if p == ".":
                continue
            if rel == p or rel.startswith(p + "/"):
                if best is None or len(p) > len(best[0]):
                    best = (p, m["id"])
        if best:
            affected_mods.add(best[1])
        elif "/" not in rel:
            affected_mods.add("MOD-000")
    return {"changed_files": changed, "added_ids": added,
            "removed_ids": removed, "affected_tops": tops,
            "affected_mods": sorted(affected_mods)}


def analyze(inv_data, out, drift=False):
    reg, doc_files = collect_registered(out)
    want = inventory_ids(inv_data)
    orphan_syms = [s["id"] for s in inv_data.get("symbols", [])
                   if s.get("public", True) and s["id"] not in reg]
    orphan_eps = [e["id"] for e in inv_data.get("endpoints", [])
                  if e["id"] not in reg]
    phantom = sorted(reg - want)
    stale = stale_docs(inv_data, out)
    drift_info = None
    if drift:
        drift_info = drift_diff(inv_data, out)
    return {
        "orphan_syms": sorted(orphan_syms), "orphan_eps": sorted(orphan_eps),
        "phantom": phantom, "stale": stale,
        "registered_count": len(reg), "doc_count": len(doc_files),
        "want_count": len(want), "drift": drift_info,
    }


def cmd_check(inv_data, out, drift, root=None):
    if inv_data is None:
        raise SystemExit("缺少 inventory.json，先运行 inventory 或带 --drift 重扫")
    rep = analyze(inv_data, out, drift=drift)
    problems = rep["orphan_syms"] + rep["orphan_eps"] + rep["phantom"] + rep["stale"]
    print("=== dev-docs check ===")
    print("登记符号/端点：%d / %d　文档文件：%d" %
          (rep["registered_count"], rep["want_count"], rep["doc_count"]))
    unf, per = unfilled_todo_count(out)
    if unf:
        worst = max(sorted(per.items()), key=lambda kv: kv[1])
        print("语义填充：剩余未填 TODO %d 处（最多: %s %d）——建议逐符号补齐后再交付（仅提示，不作为门禁）"
              % (unf, worst[0], worst[1]))
    else:
        print("语义填充：全部符号已填 ✓")
    if root and inv_data.get("is_git") and inv_data.get("source_commit"):
        head = inv.head_commit(root)
        if head and head != inv_data["source_commit"]:
            print("提示: 仓库 HEAD(%s) 已领先 inventory(%s)——代码可能已变更，"
                  "建议执行 check --drift 重扫" % (head, inv_data["source_commit"]))
    if drift:
        d = rep["drift"]
        if d is None:
            print("drift: 无基线（请先完成一次 extract + report 建立 baseline）")
        else:
            print("drift: 代码变更文件 %d、受影响模块 %s、新增符号/端点 %d、移除 %d" %
                  (len(d["changed_files"]), (d.get("affected_mods") or d["affected_tops"] or "无"),
                   len(d["added_ids"]), len(d["removed_ids"])))
            if not d["changed_files"] and not d["added_ids"] and not d["removed_ids"]:
                print("drift: 无漂移 ✓")
    for label, items in (("orphan(有码无文)", rep["orphan_syms"] + rep["orphan_eps"]),
                         ("phantom(有文无码)", rep["phantom"]),
                         ("stale(文档过期)", rep["stale"])):
        if items:
            print("[%s] %d 项:" % (label, len(items)))
            for it in items[:20]:
                print("    - %s" % it)
            if len(items) > 20:
                print("    ... 共 %d" % len(items))
    if problems:
        print("RESULT: FAIL（%d 项待处理；修复后重新 check）" % len(problems))
        return 1
    print("RESULT: PASS（ERROR=0）")
    return 0


def index_rows(inv_data, out, rep):
    ref_rows = []
    data_rows = []
    for m in inv_data["modules"]:
        slug = module_slug(m)
        rp = os.path.join("reference", "%s.md" % slug)
        if os.path.exists(os.path.join(out, rp)):
            ref_rows.append("| [%s](%s) | 详档：%s（%s） |" % (m["name"], rp, m["name"], m["id"]))
        dp = os.path.join("data", "%s.md" % slug)
        if os.path.exists(os.path.join(out, dp)):
            data_rows.append("| [%s](%s) | 数据：%s（%s） |" % (m["name"], dp, m["name"], m["id"]))
    status = "PASS" if not (rep["orphan_syms"] or rep["orphan_eps"] or rep["phantom"] or rep["stale"]) else "有未处理项"
    return {
        "project": os.path.basename(inv_data.get("root") or ""),
        "generated_at": now_iso(),
        "source_commit": inv_data.get("source_commit") or "",
        "langs": ",".join(inv_data.get("langs", {})) or "?",
        "n_modules": len(inv_data["modules"]),
        "n_symbols": len(inv_data.get("symbols", [])),
        "n_endpoints": len(inv_data.get("endpoints", [])),
        "n_tests": len(inv_data.get("tests", [])),
        "reference_rows": "\n".join(ref_rows) or "| — | 暂无 reference 详档 |",
        "data_rows": "\n".join(data_rows) or "| — | 数据层（可选，未启用） |",
        "registered": rep["registered_count"],
        "orphan": len(rep["orphan_syms"]) + len(rep["orphan_eps"]),
        "stale": len(rep["stale"]),
        "status": status,
    }


def cmd_report(inv_data, root, out):
    if inv_data is None:
        inv_data = cmd_inventory(root, out, [])
    rep = analyze(inv_data, out)
    vals = index_rows(inv_data, out, rep)
    write(os.path.join(out, "index.md"), render("index.md", vals))
    # baseline
    doc_hashes = {}
    for fp in list_md(out):
        doc_hashes[os.path.relpath(fp, out)] = inv.sha256_file(fp)
    baseline = {
        "generated_at": now_iso(),
        "source_commit": inv_data.get("source_commit") or "",
        "inventory_hash": inv_data.get("_inventory_hash") or "",
        "code_file_hashes": inv_data.get("code_file_hashes") or {},
        "symbol_ids": sorted(({s["id"] for s in inv_data.get("symbols", [])}
                              | {e["id"] for e in inv_data.get("endpoints", [])})),
        "docs": doc_hashes,
    }
    json_save(os.path.join(out, ".baseline.json"), baseline)
    print("index.md 已更新；.baseline.json 已刷新（docs %d）" % len(doc_hashes))
    print("覆盖率：registered %d / %d；orphan %d；phantom %d；stale %d" %
          (rep["registered_count"], rep["want_count"],
           len(rep["orphan_syms"]) + len(rep["orphan_eps"]),
           len(rep["phantom"]), len(rep["stale"])))


# ---------------- CLI ----------------

def _force_utf8_output():
    """Windows 控制台/管道默认 GBK：输出非 GBK 字符（✓ 等）会触发 UnicodeEncodeError。
    统一把 stdout/stderr 切到 UTF-8（Python 3.7+）；异常时静默降级，不影响主流程。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    _force_utf8_output()
    import argparse
    ap = argparse.ArgumentParser(prog="dev_docs.py", description="dev-docs 从代码库逆向生成文档")
    ap.add_argument("command", choices=["inventory", "extract", "promote", "check", "report"],
                    help="inventory 盘点 | extract 生成 draft | promote draft 转正 | check 对账/漂移 | report 索引+基线")
    ap.add_argument("--dir", default=".", help="目标项目目录（默认当前目录；git 仓库内自动取仓库根）")
    ap.add_argument("--out", default="dev-docs", help="输出子目录名（docs/<out>，默认 dev-docs）")
    ap.add_argument("--layer", choices=["architecture", "reference", "data"], help="extract 的层")
    ap.add_argument("--module", help="extract 限定单个 MOD-id")
    ap.add_argument("--exclude", action="append", default=[], help="额外排除模式（可多次）")
    ap.add_argument("--drift", action="store_true", help="check 时重扫与基线对比漂移")
    ap.add_argument("--file", help="promote 的 draft 文件路径（相对 docs/<out>/ 或绝对路径）")
    a = ap.parse_args(argv)

    root = resolve_root(a.dir)
    out = outdir(root, a.out)

    if a.command == "inventory":
        cmd_inventory(root, out, a.exclude)
    elif a.command == "extract":
        if not a.layer:
            raise SystemExit("extract 需要 --layer architecture|reference|data")
        # 复用已有 inventory.json（含当时 exclude），避免再次扫描产出漂移快照
        data = ensure_inventory(out, root, a.exclude)
        extract_layer(data, root, out, a.layer, a.module)
    elif a.command == "promote":
        if not a.file:
            raise SystemExit("promote 需要 --file <draft 路径>（相对 docs/<out>/ 或绝对路径）")
        cmd_promote(out, a.file)
    elif a.command == "check":
        if a.drift:
            data = cmd_inventory(root, out, a.exclude, quiet=True)
        else:
            data = load_inventory(out)
        return cmd_check(data, out, a.drift, root)
    elif a.command == "report":
        data = load_inventory(out)
        cmd_report(data, root, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
