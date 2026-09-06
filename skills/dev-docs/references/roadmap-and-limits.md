# references/roadmap-and-limits.md — 已知限制与后续方向（v2）

> 用途：记录 dev-docs 当前版本（v1.x）的设计取舍、已知不理想点与 v2 方向。
> AI 使用本 skill 时**只读参考**：按当前版本能力执行，不要在产物理顺前自行“实现”v2 形态；
> 存量项目迁移到 v2 属于一次受控重构，需另行安排，不混入日常增量提取。

## 1. 当前版本（v1.2）怎么工作（一句话）

- 产物 = `docs/dev-docs/`：`architecture.md` + **每模块一份唯一详档**（`reference/<slug>.md`：概览四问 + 符号索引表 + 分级契约）+ `index.md` + `inventory.json`/`.baseline.json`。
- 符号标题**只写语义名**（`### Pico.run_tool`），机器稳定 ID（FUN/API/MOD）以**隐藏锚点** `<!-- @FUN-135 -->` 放在签名/handler 行尾供对账；对账三态 orphan/phantom/stale；`check` 另报告"语义填充度（剩余未填 TODO）"。

## 2. 已知限制 / 不理想点

| # | 现象 | 状态 |
|:---|:---|:---|
| L1 | 符号 ID 直接写在标题里 | ✅ v1.2 已解决（锚点隐藏化） |
| L2 | `modules/` 与 `api/` 双写同一批符号契约 | ✅ v1.2 已解决（合并为 reference 单层） |
| L3 | 符号平铺 H3 难扫、无分组 | ✅ v1.2 已解决（索引表 + 按函数/类/端点分节） |
| L4 | 不表达架构分层（controller/service/dao） | 待定（v2 方向） |
| L5 | 无"对外接口面"专项产物（api-surface） | 待定（v2 方向） |
| L6 | 早期存量 api 标题重复 | ✅ 已随 v1.2 迁移消除（api 层取消） |

## 3. v2 方向（评估中，未开工）

- **架构分层为一等维度**：inventory 符号打 `layer: api|service|data|support`（命名+注解启发，识别不到不强标）；详档按层分节；不分层项目退化为平铺。
- **对外接口面（api-surface.md）**：只含对外面（HTTP 端点 + 对外/public service 方法 + 数据模型），DAO 内部不进契约面，留在详档。
- **索引导航**：index 增加"分层视图（跨模块）"。
- **符号卡片表格化**：参数/返回/错误用 Markdown 表格（借鉴 vortex api 模板的字段化契约）。

## 4. 门禁/工具优化 backlog

| # | 想法 | 状态 |
|:---|:---|:---|
| G1 | `check` 报告“语义填充度（剩余未填 TODO）” | ✅ 已实现（v1.1，仅提示不改退出码） |
| G2 | 语义完成度可选项（`check --require-filled` 拦截未填完） | 待定（需先定“完成”口径） |
| G3 | drift 符号级粒度：给“待补文档清单”直喂 extract | 待定 |
| G4 | 按符号指纹判 stale（而非整文件 hash，区分改注释 vs 改签名） | 待定 |
| G5 | CI / git hook 提交后自动 `check --drift` | 待定（见 spec-workflow 计划池 P1） |
| G6 | 大仓库 inventory 增量扫描缓存 | 待定 |
| G7 | command 门禁白名单 + 相对 skill 定位（双安装形态） | 待定 |

## 5. 使用约定

- 遇到用户提及“编号难读 / 结构重复 / 分层 / 对外接口文档”等问题 → 指向本文件说明是已登记方向，不现场重构。
- 新产项目保持 v1 结构以维持对账；v2 实施前任何迁移都要设计“保留已填语义”的搬移路径。
