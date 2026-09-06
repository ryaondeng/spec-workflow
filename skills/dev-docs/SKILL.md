---
name: dev-docs
version: 1.2.0
description: >
  从已有代码库反建技术文档（dev-docs）：面向没有接口/设计/架构文档的存量项目，
  用机器盘点 + AI 语义 + 覆盖对账三层机制提取出「架构 / 各模块详档（概览四问 + 符号索引表 + 分级契约）/ 数据层（可选）」文档集，
  产物直接落入目标项目 docs/dev-docs/ 并随 git 管理；支持草稿合入、长期漂移检测（check --drift）、按模块增量重生成、
  人工补充区保护（AI-GEN marker）、证据标注防编造（evidence 协议 + unknown）。
  适用于任意语言代码库（首发 Java/Python/TypeScript 语言指纹，其他语言降级并标注低置信）。
  触发词：给项目生成文档、从代码提取文档、反建文档、补接口文档、补架构文档、生成API文档、dev-docs、逆向文档化
---

# dev-docs：从代码库逆向提取项目文档

## 核心原则

1. **机器枚举先行** — 符号/端点/签名等一切事实来自 `scripts/dev_docs.py inventory` 产出的 `inventory.json`；AI 不凭记忆假设、不得缩小覆盖范围，盘点不可靠处显式 `unknown`
2. **AI 只写语义层** — 在 inventory 清单之上逐符号写职责/参数/返回/错误/示例；示例取自测试，禁止编造调用方式
3. **证据协议** — 每条结论标注 事实/推断/假设/缺失；拿不准写 `unknown`，禁止伪造（详见 `references/evidence-protocol.md`）
4. **草稿合入** — AI 产出先落 `*.draft.md`，经人工 diff 确认后 `promote` 转正（只更新 AI-GEN 区）；未抽审 draft 不得进正式文档
5. **对账门禁** — 覆盖对账 `check` ERROR=0（无 orphan/phantom/stale）才可宣告完成
6. **权威来源去重** — 目标项目已有的 docs/rules/README 等同类内容：摘录 + 链接，不复制、不覆盖、不双轨
7. **分层顺序硬约束** — 架构（定位）→ 模块/接口 → 数据，逐层确认，禁止跳过定位层直接写接口
8. **只检查/生成文档，不改代码**；文档与代码同一次提交入库

## 产物契约

目标项目默认输出到 `<目标项目>/docs/dev-docs/`（可在调用时用 `--out` 指定其它子目录名）：

```text
<目标项目>/docs/dev-docs/
├── index.md                    # 文档地图 + 覆盖率摘要（report 自动渲染）
├── architecture.md             # 架构视图（ARCH-001）
├── reference/<module-slug>.md  # ★ 每模块唯一详档：概览四问 + 符号索引表 + 分级契约（标题语义化）
├── data/                       # 可选：数据层/对象模型
├── inventory.json              # 机器盘点（唯一事实源，自动生成）
└── .baseline.json              # 生成基线（自动维护，防漂移）
```

文档集类型与稳定 ID：

| 类型 | 目录 | doc_id | 对应 inventory |
|:---|:---|:---|:---|
| 入口 | index.md | INDEX | —（report 渲染） |
| 架构 | architecture.md | ARCH-001 | modules/deps 综合 |
| 详档 | reference/<module-slug>.md | MOD-xxx | modules[] + symbols[]（FUN）+ endpoints[]（API） |
| 数据 | data/<module-slug>.md | DATA-MOD-xxx | 对象/字段 |

- 每个公开符号/端点卡片带**隐藏锚点** `<!-- @FUN-135 -->`（标题只写语义名；check 解析注释锚点统计登记，删除即 orphan）
- 每份详档结构：`概览（四问）→ 符号索引表（ID｜符号｜类型｜说明，机器全量生成）→ 详细契约（按 模块级函数/类/HTTP 端点 分节）`
- 每文件头部 frontmatter（工具维护）：`doc_id / type / source_commit / generated_at / inventory_hash / status`
- AI-GEN 区 `<!-- AI-GEN:BEGIN --> … <!-- AI-GEN:END -->` 内可被重生成覆盖；区外是人工补充区，**永远保留**

## 执行流程

### 0. 前置
- 声明文档语言（zh-CN/en-US，标识符不翻译）；向用户确认目标项目根目录（git 根）与排除范围（生成代码/vendor/密钥文件）
- 若 `docs/dev-docs/` 已存在 `.baseline.json`：本次为**增量/再提取**，先读 baseline 与 index 了解现状

### 1. 机器盘点
```bash
python3 <skill_dir>/scripts/dev_docs.py inventory --dir <目标项目>
```
- 产出 `inventory.json`（唯一事实源，AI 不改）。向用户展示盘点摘要（模块数/符号数/端点数/测试数/低置信区）

### 2. 架构层（ARCH）[确认点①]
- 读 inventory 的模块与依赖 → 生成 `architecture.md` 草稿（技术栈/模块划分表/数据流图）
- **先通过用户确认再进入模块层**（分层顺序硬约束）

### 3. 详档层（reference）[确认点②③]
- 逐模块（建议每批 ≤3-5 个）生成 `reference/<slug>.md` 草稿：概览四问 + 符号索引表（机器全量）+ 分级契约卡片
- AI 填充：四问、索引表“说明”列（每符号一句话）、逐符号契约（用途/参数/返回/错误；示例取自 `tested_by`/测试文件）
- 每批向用户展示，确认后继续

### 4. 数据层（DATA，可选）
- 对象/字段逐项，缺失写 `unknown`，不省略不伪造

### 5. 对账门禁
```bash
python3 <skill_dir>/scripts/dev_docs.py check --dir <目标项目>
```
- ERROR=0（无 orphan/phantom/stale）才可宣告完成；有问题先补齐/修正，禁止降级绕过

### 6. 合入 + 提交
- 每个 draft 经用户 diff 确认后 `promote` 转正（只更新 AI-GEN 区）
- `report` 重建 index + 刷新 `.baseline.json`；文档与触发变更**同一次 git 提交**入库

## CLI 速记

```text
dev_docs.py inventory --dir <目标项目> [--out <子目录名=dev-docs>] [--exclude 额外排除]
dev_docs.py extract  --dir <目标项目> --layer architecture|reference|data [--module MOD-id]
                     # 生成/再生成指定层或模块的 draft 骨架（AI 填语义）
dev_docs.py promote  --dir <目标项目> --file <draft文件>   # draft 转正（人工确认后）
dev_docs.py check    --dir <目标项目> [--drift]        # 对账：orphan/phantom/stale + 语义填充度；exit 0=干净
dev_docs.py report   --dir <目标项目>                  # 重建 index.md + 刷新 baseline
```

## 生成规范

按需加载（阶段匹配，不整读）：
- `references/output-contract.md` — 产物契约/ID 规则/frontmatter/AI-GEN marker
- `references/evidence-protocol.md` — 证据标注 + unknown 规则
- `references/api-doc-style.md` — 函数级/端点级条目模板、示例质量要求
- `references/lang-mapping.md` — Java/Python/TS 指纹与发现约定
- `references/anti-patterns.md` — 红线 + 分层抽审 checklist
- `references/roadmap-and-limits.md` — 已知限制与 v2/后续方向（遇到“编号难读/结构重复/分层/对外接口文档”等反馈时先读，不现场重构）

## 红线（违反不得宣告完成，详见 anti-patterns.md）

1. 不得批量一次生成全部文档不 review——按层/批确认
2. 不得把 AI 内容直接写正式文件——一律 draft → promote
3. 不得用记忆代替扫描——事实以 inventory/源码为准
4. 不得伪造/省略——evidence + unknown
5. 不得覆盖人工区（AI-GEN marker 外）与既有权威文档（摘录+链接）
6. 不得在 check 未 ERROR=0 时宣告完成
7. 不得跳层（先架构后接口）

## 完成条件（同时满足）

- `check` 退出码 0（orphan/phantom/stale 全清或已显式 retired）
- 每个 draft 经人工确认已 promote；人工区/权威链接已补 why
- index.md 覆盖率摘要已更新；产物与触发变更同一次提交
