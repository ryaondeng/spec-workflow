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

- ID 由 inventory 分配，**唯一且稳定**：`FUN-001…`（函数/方法）、`API-001…`（端点）、`MOD-000/001…`（模块）、`ARCH-001`。
- **登记锚点格式（v1.2，勿改）**：符号卡片标题只写语义名（`### Pico.run_tool`），ID 以隐藏注释放在签名/handler 行尾：`<!-- @FUN-135 -->` / `<!-- @API-002 -->`。删除一个符号的卡片 = check 报 orphan。
- 详档内部结构（固定）：`## 概览（四问）` → `## 符号索引`（表格：ID｜符号｜类型｜说明，机器全量生成）→ `## 详细契约`（按 `## 模块级函数` / `## 类：<名>` / `## HTTP 端点` 分节）。
- `MOD-000` 为仓库根自身代码模块（如根目录脚本/CI），可空但应保留占位或 retired。

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
