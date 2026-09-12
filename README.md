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

**无 uv 时**：根回归基于 stdlib `unittest` 可直接跑；dev-docs（v1.5 起）依赖 tree-sitter，
安装 `skills/dev-docs/requirements.txt` 后运行：

```bash
python3 -m unittest tests.test_spec_cli tests.test_installer tests.test_health_check
pip install -r skills/dev-docs/requirements.txt
python3 -m unittest discover -s skills/dev-docs/tests -t skills/dev-docs
```

## 依赖说明（v1.5 变更）

- **dev-docs 运行时依赖 tree-sitter**（2026-09-12 拍板：全语言统一走 tree-sitter 适配器抽取，
  「零第三方依赖」约定作废）；依赖声明见 `pyproject.toml` 与 `skills/dev-docs/requirements.txt`，
  `install.py` 安装时自动 pip install（`--skip-deps` 可跳过）。
- 编排引擎（spec-dev-workflow）仍为纯 stdlib。
- pytest / ruff 仅开发期工具。

## 安装 skills

```bash
python3 install.py            # 或 bash install.sh
python3 uninstall.py          # 卸载
```
