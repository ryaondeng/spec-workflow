# spec-workflow

Spec 驱动开发工作流：编排引擎（状态机 / handoff / 门禁 / resume）+ 质量门禁 + skills 分发。

## 目录结构

```
spec-workflow/
├── skills/                  # 分发物（install.py 拷贝到目标环境）
│   ├── spec-dev-workflow/   # 编排引擎 CLI（spec_cli.py）
│   └── dev-docs/            # 逆向文档提取（从存量代码生成开发文档）
├── tests/                   # 根回归（29 例）
├── install.py / install.sh  # 安装脚本
└── docs/                    # 设计文档（本地留存，不入库）
```

## 开发环境（Python 3.12 + uv）

本仓库开发环境统一 **Python 3.12**，依赖由 [uv](https://docs.astral.sh/uv/) 管理并锁定在 `uv.lock`。

```bash
uv sync                 # 创建 .venv 并安装 dev 依赖（pytest / ruff）
uv run pytest -q        # 跑全部测试（根 29 例 + dev-docs 43 例）
uv run ruff check .     # 静态检查
```

可选：tree-sitter 语言解析后端（dev-docs 的 C++/Java/JS/Shell 符号级提取）：

```bash
uv sync --group ts
```

**无 uv 时**：测试本身基于 stdlib `unittest`，裸 Python 直接可跑（不装任何依赖）：

```bash
python3 -m unittest tests.test_spec_cli tests.test_installer tests.test_health_check
cd skills/dev-docs && python3 -m unittest tests.test_dev_docs
```

## 依赖红线

- **运行时零第三方依赖**：`skills/` 下的所有脚本必须能被裸 Python 直接执行（`pyproject.toml` 中 `dependencies = []`）。
- 开发期工具（pytest / ruff）与可选解析后端（tree-sitter）只进 `uv.lock`，不属于分发物。
- dev-docs 的可选依赖说明见 `skills/dev-docs/SKILL.md` 与 `references/known-limits.md`。

## 安装 skills

```bash
python3 install.py            # 或 bash install.sh
python3 uninstall.py          # 卸载
```
