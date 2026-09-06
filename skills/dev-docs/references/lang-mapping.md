# references/lang-mapping.md — 语言指纹与发现约定

> dev-docs 的盘点按语言能力分档。**可靠的由 AST 精确枚举；启发式的正则近似并显式标注低置信；未列语言不假装覆盖（unknown）。**

## 1. 能力分档

| 语言 | 枚举器 | 级别 | 说明 |
|:---|:---|:---|:---|
| Python | `ast`（stdlib） | **可靠** | 函数/类方法/签名/装饰器路由（FastAPI/Flask 等）/测试用例 |
| Java | 正则启发 | 低置信 | 方法签名、Spring `@*Mapping` 路由；类边界易误判，需抽审 |
| TypeScript / JavaScript | 正则启发 | 低置信 | `export function`、`const f = (…)=>`、类方法签名；JS 动态类型易漏 |
| Shell | 正则启发 | 低置信 | `name()` / `name () {` 函数；无类/类型 |
| 其他（Go/Rust/Kotlin/Ruby/PHP…） | 未实现 | unknown | 不产出符号；`inventory.confidence` 标注"低置信/未覆盖" |

> 原则：盘点不可靠处显式 unknown/低置信，**不假装覆盖**（宁可少列并标注，不可虚列误导）。

## 2. 入口与模块发现的通用约定（AI 补 architecture/模块四问时用）

| 形态 | 后端服务 | CLI | 库/SDK | 前端 |
|:---|:---|:---|:---|:---|
| 入口 | `main.py`/`app.js`/`server.go`/Spring `Application` | `cmd/`、`__main__.py`、`bin/x.js` | `__init__.py`、`index.ts`、`lib.rs` | `main.tsx`、`App.vue` |
| 契约来源 | 路由注册 + handler 签名 + Pydantic/Bean | argparse/cobra/clap 子命令 | `__all__`/export/pub 导出 | 路由表 + props/类型 |
| 路由形态 | FastAPI `@app.post`/Flask `@bp.route`/Spring `@*Mapping`/Django urls | — | — | 前端路由表 |
| 数据模型 | ORM Model / dataclass / Bean + DDL | 配置文件 | 类型声明 | schema（localStorage/API 返回类型） |
| 测试约定 | `tests/`、`test_*.py` | 同上 | 同上 | `*.test.ts(x)` |

## 3. 跨语言执行要点

1. 起手先跑 `dev_docs.py inventory` 看 `langs` 与 `confidence.notes`：知道哪些语言可靠、哪些低置信。
2. 低置信语言文档在合入前**必须**人工抽审（名字/默认值/错误处理各抽 ≥3 处对照源码）。
3. 一个仓库多语言：按语言分节写 architecture；模块文档标注该模块语言。
4. 依赖分析仅 python 自动（import）；其余语言依赖留给 AI 从构建清单（package.json/pom.xml/go.mod）在 architecture/模块四问里补（evidence: 事实——文件路径）。
5. 框架未识别/私有注解：路由枚举为 0 属正常，先查 confidence，再人工决定是否补端点条目。
