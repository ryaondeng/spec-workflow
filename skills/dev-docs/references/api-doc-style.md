# references/api-doc-style.md — 函数级/端点级文档风格

> 对象：`modules/*.md` 与 `api/*.md` 里的符号条目。目标是**调用者视角**（怎么调、返回什么、错了怎么看），不是源码翻译。

## 1. 函数/方法条目模板（FUN-xxx）

```markdown
### FUN-012 — spec_cli.phase_ids
- 签名：`phase_ids(pipeline) -> List[str]`（evidence: 事实）
- 职责：…（evidence: 推断，依据调用点 …）
- 参数：pipeline — 加载后的流水线定义
- 返回：阶段 id 列表；输入非法时行为 unknown
- 错误：ValueError（evidence: 事实，见 raise）
- 示例：
  ```python
  # 取自 tests/test_spec_cli.py::test_xxx
  ids = phase_ids(pipeline)
  ```
```

写每节前先对照源码；**参数/默认值/返回类型以 inventory 的 signature 与源码为准**，语义段用 evidence 标注（规则见 evidence-protocol.md）。

## 2. HTTP 端点条目模板（API-xxx）

```markdown
### API-002 — POST /api/v1/auth/login
- handler：`auth.login`（evidence: 事实）
- 请求参数：body {username: string(必填), password: string(必填)}；query 无
- 响应：200 {token, expires_in}；错误 401（凭证错误）/ 429（限流）——以实际 raise/返回为准
- 鉴权：无 / Bearer / Cookie（evidence: 事实/缺失）
- 示例（取自 tests/test_auth.py::test_login）
```

端点发现是**机器枚举**（FastAPI/Flask 等路由装饰器），枚举不到的框架/路由自动标 low/unknown——不要手工补"想象中的端点"。

## 3. 示例质量要求（核心防幻觉点）

1. 示例**必须取自测试**：先在 `inventory.json.tests` 里找覆盖该符号的用例（tested_by 启发），再打开测试文件摘抄真实调用。
2. 找不到覆盖用例：不编造，写 `<!-- TODO 无现成测试，示例待补（不臆造） -->`。
3. 示例应剪裁（去掉断言噪声）但**保持真实参数与语义**，标注来源文件。

## 4. 风格红线

- 标识符/路径/签名不翻译、不改写；叙述语言中英二选一（调用方声明）。
- 每个符号条目**独立成段**，标题必须是 `### FUN-xxx — …` / `### API-xxx — …`（对账锚点，勿改格式）。
- 不写空话（"该函数非常重要"）；写不出就 unknown/TODO，别堆形容词。
- 变更记录（Added/Changed/Deprecated）放「人工补充」区由人维护。
