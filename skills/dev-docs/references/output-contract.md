# references/output-contract.md — 产物契约

> dev-docs 所有产物的结构、ID、元数据约定。机器按此解析，AI 按此填写。

## 1. 落位与目录

- 目标项目默认 `<目标项目>/docs/dev-docs/`（可用 `--out` 改子目录名）。
- 该目录内容随目标项目 git 入库；`.baseline.json`、`inventory.json` 为机器维护，**人工不手改**。
- 若目标项目已有同类文档/规则（docs、`.codebuddy/rules/`、README、ADR）：**摘录 + 链接，不复制、不覆盖**；冲突以项目自有文档为准。
- **文件命名面向人工阅读**：模块/接口/数据文档用**语义 slug**（模块 path 转写：`pico.md`、`pico-evaluation.md`、根模块 `root.md`），
  机器用的 MOD 编号只留在 frontmatter `doc_id`，不作为文件名。

```text
docs/dev-docs/
├── index.md                    # report 渲染的入口/地图/覆盖率
├── architecture.md             # 架构（ARCH-001）
├── reference/<module-slug>.md  # ★ 模块唯一详档（概览四问 + 符号索引表 + 分级契约）
├── data/<module-slug>.md       # 数据层（可选）
├── inventory.json              # 机器盘点唯一源
└── .baseline.json              # 漂移检测基线
```

## 2. 文档集与稳定 ID

| type | 物理文件 | doc_id | 登记内容（check 锚点） |
|:---|:---|:---|:---|
| index | index.md | INDEX | —（report 生成） |
| architecture | architecture.md | ARCH-001 | 无符号锚点（人工 checklist 审） |
| reference | reference/<slug>.md | =MOD-id | 该模块全部 FUN/API 的隐藏锚点 `<!-- @FUN-xxx -->` |
| data | data/<slug>.md | DATA-MOD-xxx | 无硬性锚点（可选） |

- ID 由 inventory 分配，**唯一且稳定**：`FUN-001…`（函数/方法）、`API-001…`（端点）、`MOD-000/001…`（模块）、`ARCH-001`；
  人工/低置信登记（register 命令）分配 `SYM-…`（符号）/ `EPT-…`（端点）/ `ITF-…`（接口契约资产），存于 `.registered.json`。
- **登记锚点格式（v1.2 引入，v1.3 放开 kind 前缀，勿改）**：符号卡片标题只写语义名（`### Pico.run_tool`），ID 以隐藏注释放在签名/handler 行尾：`<!-- @FUN-135 -->` / `<!-- @API-002 -->` / `<!-- @SYM-001 -->`。删除一个符号的卡片 = check 报 orphan。
- **对账口径（v1.3）**：登记集 = inventory 自动枚举 ∪ `.registered.json` 人工登记；文档锚点不在登记集 → phantom（编造仍拦）；register 条目指向的源文件消失 → ERROR（登记腐化）。

## 语义地图（.semantic-map.json，LLM 提取产物）

```json
{"version": 1,
 "modules": [{"name": "ncu", "path": "src/ncu",
   "responsibility": "一句话职责",
   "files": ["src/ncu/main.cpp", "src/ncu/Demo.srv"],
   "ignored_files": [{"path": "third_party/x.lib", "reason": "vendored"}],
   "key_symbols": [{"name": "NCU::spin", "kind": "method", "file": "src/ncu/main.cpp", "line": 12}],
   "interfaces": [{"kind": "srv", "name": "ncu/Demo", "file": "src/ncu/Demo.srv"}],
   "depends_on": ["其他模块名"], "tests": ["test/..."]}]}
```

- 由 AI 分批读码产出、**用户确认后**生效；`check` 用它统计**文件归属覆盖率**并输出未归属文件清单（缺地图仅提示不门禁）
- 纪律：每个条目必须带来源 `file`；签名/字段引用源码原文；看不见的写 "not visible in sources"，禁止凭记忆补
- 详档内部结构（固定）：`## 概览（四问）` → `## 符号索引`（表格：ID｜符号｜类型｜说明，机器全量生成）→ `## 详细契约`（按 `## 模块级函数` / `## 类：<名>` / `## HTTP 端点` 分节）。
- `MOD-000` 为仓库根自身代码模块（如根目录脚本/CI），可空但应保留占位或 retired。

## 页面树（.devdocs-plan.json，v1.4，plan 命令维护）

```json
{"version": 1, "source": "semantic-map",
 "pages": [{"slug": "reference/pico-providers", "type": "reference", "module_id": "MOD-004",
   "title": "模型后端适配层", "parent": "index",
   "purpose": "四类客户端如何统一成 complete()，怎么加新后端",
   "sections": ["概览", "组件与协作", "使用指南", "对外接口面", "符号索引", "详细契约"],
   "source_files": ["pico/providers/clients.py"], "status": "generated"}]}
```

- 层级：`index`（根）→ `architecture` / `usage` / `reference/<slug>`；`data` 默认不生成
- 字段语义：`purpose` = 该页工单要回答什么（brief 输出）；`sections` = 结构门禁要求的必需章节；
  `status`：`planned`（未生成）→ `generated`（已生成 draft/正式文件，语义未填尽）→ `filled`（AI-FILL 清空）
- 人工可编辑：重跑 `plan` 只新增缺失页，已有页的 title/purpose/parent/sections/status **不被覆盖**（`--force` 除外）
- check 依据：plan 应有页是否缺失（draft 在 = 中间态不报）、正式页是否缺节

## 每页统一格式（v1.4）

```markdown
# <title>
> <purpose>
**相关源文件**：<机器按 plan.source_files 渲染>
（AI 叙事节：概览/组件与协作/使用指南/…，由 <!-- AI-FILL:… --> 工单引导，位于 AI-GEN 区外）
<!-- AI-GEN:BEGIN --> 机器区（符号索引/详细契约/文档树/覆盖率） <!-- AI-GEN:END -->
## 人工补充（机器不覆盖）
## Sources
<!-- SOURCES:AUTO -->（extract/promote 时替换为本页 file:line 引用清单）
```

- **AI 叙事节必须在 AI-GEN 区外**：重生成只刷新机器区，已填语义永不被冲掉
- `<!-- AI-FILL:ID 要求 -->` 为章节级工单：`check` 统计残留（默认 warn，`--strict` 为 ERROR）
- Sources 由机器生成，勿手写；页内 `file:line` 引用会被 check 校验（引用的文件必须在项目文件全集内）

## 引用与行号（v1.4.1）

- 页内 `路径:行号` 引用属于**可校验声明**，`check` 会逐条核：
  - `ref_file_missing`：文件不在项目文件全集内 → **ERROR**（编造拦截）
  - `ref_line_suspect`：行号指向**空行 / 注释行 / 越界** → WARN（`--strict` 为 ERROR）；
    指向 `import` 行且上下文未在讲"依赖/导入" → 同样报疑似
- `fixrefs [--write]`：空行/越界类按"最近的 def/class/赋值行"自动修正；
  注释/import 类只提示（需人工或 AI 复核），避免把正当引用改坏
- 纪律：**行号来自机器输出**（`brief` 的必覆盖锚点、盘点卡片、`Sources`），不凭记忆手写；
  写完一批内容跑一次 `fixrefs` 即可机制化清零

## 3. frontmatter（每文件头部，机器维护）

```yaml
---
doc_id: MOD-001
type: module
module_id: MOD-001      # module/api/data 用；architecture/index 可省
source_commit: a1b2c3d  # 生成时目标项目 HEAD（git）；非 git 为空
generated_at: 2026-09-06T12:00:00+08:00
inventory_hash: <sha256> # 生成时 inventory 规范哈希
status: current          # draft 文档为 draft；promote 后 current；废弃标 retired
---
```
人工只需关心正文，不手改 frontmatter（重跑会自动刷新 commit/hash）。

## 4. AI-GEN 区域与人工区

```markdown
<!-- AI-GEN:BEGIN -->
…机器/AI 生成区：符号清单、接口骨架，再次 extract 时整体刷新…
<!-- AI-GEN:END -->

## 人工补充（机器不覆盖）
<!-- AI-GEN 之外的内容（标题、四问、人工补充、ADR 链接）在增量重生成时全部保留 -->
```
- 生成/再生成一律先写 `xxx.md.draft`；人工 diff 确认后 `promote` 才覆盖正式文件。
- **禁止**直接编辑 AI-GEN 区内的机器字段（ID/签名/路径）；AI 补的语义填在对应 TODO 之后，保留 evidence 标注。

## 5. 确定性

- `inventory.json` 不含时间戳：同一代码两次 `inventory` 输出 byte-identical → 才能做 CI 漂移（hash 对比）。
- 排除默认项：`.git/node_modules/__pycache__/dist/build/out/target/vendor/.venv/*.pyc/…`，可用 `--exclude` 追加（生成代码、密钥、CI 产物按项目情况加）。

## 6. 生命周期

- 文档与触发代码变更**同一次 git 提交**入库。
- 模块被删除：文档 `status: retired` 并保留历史，不悄悄抹掉。
- 重复提取 = 增量：`extract --module MOD-xxx` 只重写该模块 draft，再 promote。
