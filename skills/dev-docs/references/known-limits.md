# references/known-limits.md — 当前机制、已知限制与应答口径

> 用途：AI 使用本 skill 时的**只读参考**——按当前版本能力执行；用户对限制提出疑问时，
> 用本文件口径回答"是已登记的方向"，**不要现场重构**。
> 开发规划（v2 结构方向、门禁 backlog）不在本 skill 内，见 spec-workflow `docs/pool/记录-dev-docs演进方向.md`。

## 1. 当前版本（v1.3）怎么工作（一句话）

- 双轨提取：**规则轨** = `inventory` 文件全集（含未登记语言）+ 符号/端点机器盘点 + 哈希漂移基线；**LLM 轨** = AI 通读建 `.semantic-map.json` 语义地图（每条带来源文件），用户确认后按模板填文档。
- 产物 = `docs/dev-docs/`：`architecture.md` + **每模块一份唯一详档**（`reference/<slug>.md`：概览四问 + 符号索引表 + 分级契约 + 接口契约资产）+ `index.md` + `inventory.json` / `.semantic-map.json` / `.registered.json` / `.baseline.json`。
- 符号标题只写语义名，机器 ID 以隐藏锚点 `<!-- @FUN-135 -->`（kind 前缀已放开：FUN/API/SYM/EPT/ITF）供对账；对账登记集 = 自动枚举 ∪ register 登记；`check` 另报文件归属覆盖率与语义填充度。

## 2. 已知限制 / 不理想点

| # | 现象 | 状态 |
|:---|:---|:---|
| L1 | 符号 ID 直接写在标题里 | ✅ v1.2 已解决（锚点隐藏化） |
| L2 | `modules/` 与 `api/` 双写同一批符号契约 | ✅ v1.2 已解决（合并为 reference 单层） |
| L3 | 符号平铺 H3 难扫、无分组 | ✅ v1.2 已解决（索引表 + 按函数/类/端点分节） |
| L4 | 不表达架构分层（controller/service/dao） | 待定（v2 方向，规划在 docs/pool） |
| L5 | 无"对外接口面"专项产物（api-surface） | 待定（v2 方向，规划在 docs/pool） |
| L6 | 早期存量 api 标题重复 | ✅ 已随 v1.2 迁移消除（api 层取消） |
| L7 | 语言/生态覆盖 | ✅ v1.5 已解决：**全语言统一走 tree-sitter 适配器**（python/cpp/c/java/js/ts/bash 全 reliable，架构见 `docs/next/方案-tree-sitter适配器架构.md`）；ROS .msg/.srv 由文本适配器解析（MSG-/SRV- 入对账）；未注册扩展名仍走"文件全集 + LLM 语义地图 + register 登记"兜底 |
| L8 | 非 git 仓库无 source_commit → stale/drift 失效、"同一次提交"红线无法满足 | 🟡 v1.3 部分解决：全文件哈希 manifest 进 baseline，`check --drift` 非 git 可检出变更；stale 判定仍以 git commit 为主，非 git 靠 drift + 红线降级（同批变更+用户快照） |

## 3. 使用约定

- 遇到用户提及"编号难读 / 结构重复 / 分层 / 对外接口文档 / 语言不支持"等问题 → 指向本文件对应条目说明"已登记的方向/限制"，不现场重构。
- 新产项目保持当前产物结构以维持对账；结构性重构（v2）实施前必须设计"保留已填语义"的搬移路径。
