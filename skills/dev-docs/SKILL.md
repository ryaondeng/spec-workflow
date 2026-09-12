---
name: dev-docs
version: 1.3.0
description: >
  从已有代码库反建技术文档（dev-docs）：面向没有接口/设计/架构文档的存量项目，
  用「规则提取（文件全集/机器盘点/对账漂移）+ LLM 提取（AI 通读建语义地图再按模板填文档）」双轨机制，
  产出「架构 / 各模块详档（概览四问 + 符号索引表 + 分级契约 + 接口契约资产）/ 数据层（可选）」文档集，
  产物直接落入目标项目 docs/dev-docs/；支持草稿合入、长期漂移检测（check --drift，非 git 用文件哈希基线）、
  按模块增量重生成、人工补充区保护（AI-GEN marker）、人工登记通道（register，带 file:line 源码证据）、
  证据标注防编造（evidence 协议 + unknown）。
  语言策略：Python 由 AST 可靠提取；其他语言/生态（C++、ROS msg/srv、任意 DSL）由 LLM 语义地图覆盖，
  关键符号用 register 显式登记（不算 phantom）。
  触发词：给项目生成文档、从代码提取文档、反建文档、补接口文档、补架构文档、生成API文档、dev-docs、逆向文档化
---

# dev-docs：从代码库逆向提取项目文档

## 核心原则

1. **双轨提取** — 规则轨：`inventory` 产出**文件全集**（含未登记语言）+ 符号/端点机器盘点 + 哈希漂移基线；LLM 轨：AI 通读代码建**语义地图**（`.semantic-map.json`，每条带来源文件），两轨汇入同一套 `check` 对账
2. **AI 只写语义层** — 在文件全集/语义地图之上写职责/参数/返回/错误/示例；示例取自测试，禁止编造调用方式；盘点/地图不可靠处显式 `unknown`
3. **证据协议** — 每条结论标注 事实/推断/假设/缺失；拿不准写 `unknown`，禁止伪造（详见 `references/evidence-protocol.md`）
4. **草稿合入** — AI 产出先落 `*.draft.md`，经人工 diff 确认后 `promote` 转正（只更新 AI-GEN 区）；未抽审 draft 不得进正式文档
5. **对账门禁** — 覆盖对账 `check` ERROR=0（无 orphan/phantom/stale/登记腐化）才可宣告完成；语言指纹未覆盖的符号走 `register` 显式登记（必须 file:line 真实）即不算 phantom
6. **权威来源去重** — 目标项目已有的 docs/rules/README 等同类内容：摘录 + 链接，不复制、不覆盖、不双轨
7. **分层顺序硬约束** — 架构（定位）→ 模块/接口 → 数据，逐层确认，禁止跳过定位层直接写接口
8. **只检查/生成文档，不改代码**；git 项目文档与代码同一次提交入库；**非 git 项目**降级为"同一批变更 + 用户确认快照"（漂移由文件哈希 manifest 检出）

## 系统要求（跨平台）

- Python 3.7+，零第三方依赖。Windows / Linux / macOS 原生可跑（`scripts/` 全为 Python）。
- Windows 若没有 `python3` 启动名，用 `python` 或 `py -3` 替代下文命令中的 `python3`。
- 生成产物统一 LF 换行（脚本跨平台固定 `newline="\n"`）：任何平台生成结果字节一致，
  确定性（byte-identical）与 git diff / CI 漂移检测不受换行符影响。
- 全仓库安装：`install.py`（跨平台，`python install.py --project <path>` 或 `--global`）；
  Git Bash / WSL 下亦可 `bash install.sh`。bash 脚本（install.sh/uninstall.sh 等）需要 Git Bash/WSL。

## 产物契约

目标项目默认输出到 `<目标项目>/docs/dev-docs/`（可在调用时用 `--out` 指定其它子目录名）：

```text
<目标项目>/docs/dev-docs/
├── index.md                    # 文档地图 + 覆盖率摘要（report 自动渲染）
├── architecture.md             # 架构视图（ARCH-001）
├── reference/<module-slug>.md  # ★ 每模块唯一详档：概览四问 + 符号索引表 + 分级契约（标题语义化）
├── data/                       # 可选：数据层/对象模型
├── inventory.json              # 机器盘点：文件全集 + 符号/端点 + 哈希（唯一事实源，自动生成）
├── .semantic-map.json          # ★ LLM 语义地图（AI 产出 + 用户确认；文件归属/关键符号/接口契约）
├── .registered.json            # 人工/低置信登记（register 命令维护，必须 file:line 源码证据）
└── .baseline.json              # 生成基线（自动维护，防漂移；含全文件哈希）
```

文档集类型与稳定 ID：

| 类型 | 目录 | doc_id | 对应 inventory |
|:---|:---|:---|:---|
| 入口 | index.md | INDEX | —（report 渲染） |
| 架构 | architecture.md | ARCH-001 | modules/deps 综合 |
| 详档 | reference/<module-slug>.md | MOD-xxx | modules[] + symbols[]（FUN）+ endpoints[]（API）+ .registered.json（SYM/EPT/ITF） |
| 数据 | data/<module-slug>.md | DATA-MOD-xxx | 对象/字段 |

- 每个公开符号/端点卡片带**隐藏锚点** `<!-- @FUN-135 -->`（标题只写语义名；check 解析注释锚点统计登记，删除即 orphan）
- 每份详档结构：`概览（四问）→ 符号索引表（ID｜符号｜类型｜说明，机器全量生成）→ 详细契约（按 模块级函数/类/HTTP 端点 分节）`
- 每文件头部 frontmatter（工具维护）：`doc_id / type / source_commit / generated_at / inventory_hash / status`
- AI-GEN 区 `<!-- AI-GEN:BEGIN --> … <!-- AI-GEN:END -->` 内可被重生成覆盖；区外是人工补充区，**永远保留**

## 执行流程

### 0. 前置
- 声明文档语言（zh-CN/en-US，标识符不翻译）；向用户确认目标项目根目录（git 根）与排除范围（生成代码/vendor/密钥文件）
- ROS/catkin 工作空间自动嗅探（发现 `package.xml` 即按 catkin 处理，排除 build/devel/install/log）；必要时 `--project-type catkin|generic` 显式指定
- 若 `docs/dev-docs/` 已存在 `.baseline.json`：本次为**增量/再提取**，先读 baseline 与 index 了解现状

### 1. 机器盘点（规则轨）
```bash
python3 <skill_dir>/scripts/dev_docs.py inventory --dir <目标项目> [--project-type auto|catkin|generic]
```
- 产出 `inventory.json`：**文件全集**（含未登记语言如 .cpp/.msg/.srv）+ 符号/端点 + 每文件哈希（唯一事实源，AI 不改）
- 向用户展示盘点摘要（project_type/文件全集/模块数/符号数/端点数/测试数/低置信区）
- **语言指纹未覆盖的语言（如 C++）**：文件全集保证"不漏文件"，符号语义由步骤 2 的语义地图覆盖

### 1.5 语义地图（LLM 轨）[确认点⓪]
- AI 按模块分批读码（每批 ≤5-8 文件，优先构建文件/入口/头文件/接口定义），产出 `.semantic-map.json` 草稿：

```json
{"version": 1,
 "modules": [{"name": "ncu", "path": "src/ncu",
   "responsibility": "一句话职责",
   "files": ["src/ncu/main.cpp", "src/ncu/Demo.srv"],
   "ignored_files": [{"path": "third_party/x.lib", "reason": "vendored"}],
   "key_symbols": [{"name": "NCU::spin", "kind": "method", "file": "src/ncu/main.cpp", "line": 12}],
   "interfaces": [{"kind": "srv", "name": "ncu/Demo", "file": "src/ncu/Demo.srv"}],
   "depends_on": [], "tests": []}]}
```

- **反推测纪律**：地图里每个条目必须带来源 `file`；签名/字段引用源码原文；看不见的依赖写 "not visible in sources"，禁止凭记忆补
- **用户确认地图后**才进入架构/详档层；`check` 会用地图统计**文件归属覆盖率**并输出未归属文件清单
- 语言指纹未覆盖、但文档需要登记的关键符号 → `register --kind symbol|endpoint|interface --name … --src <文件> --line <行号>`（必须真实 file:line，登记后不算 phantom）

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
- `report` 重建 index + 刷新 `.baseline.json`（含全文件哈希）；git 项目文档与触发变更**同一次 git 提交**入库；**非 git 项目**降级为"同一批变更 + 用户确认快照"（`check --drift` 用文件哈希基线检出漂移）

## CLI 速记

```text
dev_docs.py inventory --dir <目标项目> [--out <子目录名=dev-docs>] [--exclude 额外排除]
                      [--project-type auto|catkin|generic]
                      # 文件全集 + 符号/端点 + 哈希基线（catkin 自动排除 build/devel/install/log）
dev_docs.py extract  --dir <目标项目> --layer architecture|reference|data [--module MOD-id]
                     # 生成/再生成指定层或模块的 draft 骨架（AI 填语义）
dev_docs.py promote  --dir <目标项目> --file <draft文件>   # draft 转正（人工确认后）
dev_docs.py register --dir <目标项目> --kind symbol|endpoint|interface --name <限定名> \
                     --src <相对项目根文件> [--line N] [--signature S] [--note N]
                     # 人工/低置信登记（语言指纹未覆盖时用）；必须真实 file:line，登记后不算 phantom
dev_docs.py check    --dir <目标项目> [--drift]        # 对账：orphan/phantom/stale/登记腐化 + 文件覆盖 + 语义填充度；exit 0=干净
dev_docs.py report   --dir <目标项目>                  # 重建 index.md + 刷新 baseline（含全文件哈希）
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
