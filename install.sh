#!/usr/bin/env bash
# spec-workflow 安装脚本（M0/M1）
# 用法:
#   bash install.sh --project <project-path>   # 项目级安装
#   bash install.sh --global                    # 全局安装（~/.codebuddy/skills/）
#   bash install.sh --project <path> --force    # 覆盖安装（删除旧目录后重装）
# 安装单元 = skills/ 下全部 skill（spec-dev-workflow 编排流程 + spec-health-check 质量评审 + dev-docs 文档逆向）
# Windows 兼容: Windows 无原生 bash——项目级/全局安装请用同目录 install.py（python install.py [--project <path>|--global] [--force]），
# 或经 Git Bash / WSL 运行本脚本。三个 bash 脚本（install.sh/uninstall.sh/skills/*/scripts/*.sh）同理需 Git Bash/WSL。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"

if [ ! -d "$SKILLS_SRC" ]; then
    echo "❌ 未找到 skills 源码目录: $SKILLS_SRC" >&2
    exit 1
fi

MODE=""
TARGET=""
FORCE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --project) MODE="project"; TARGET="$2"; shift 2 ;;
        --global)  MODE="global"; shift ;;
        --force)   FORCE=1; shift ;;
        *) echo "用法: bash $0 [--project <path> | --global] [--force]" >&2; exit 1 ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "用法: bash $0 [--project <path> | --global] [--force]" >&2
    exit 1
fi

if [ "$MODE" = "project" ] && [ -z "$TARGET" ]; then
    echo "❌ --project 需要指定项目路径" >&2; exit 1
fi

BASE=""
if [ "$MODE" = "global" ]; then
    BASE="${HOME}/.codebuddy/skills"
else
    BASE="${TARGET%/}/.codebuddy/skills"
fi

# 安装 skills/ 下每个 skill（不递归）
count=0
for src in "$SKILLS_SRC"/*/; do
    [ -d "$src" ] || continue
    name="$(basename "$src")"
    dest="$BASE/$name"
    if [ -e "$dest" ]; then
        if [ "$FORCE" = "1" ]; then
            rm -rf "$dest"
            echo "[REFRESH] 覆盖安装: $dest"
        else
            echo "[SKIP] 已存在，跳过（如需更新请加 --force）: $dest"
            continue
        fi
    fi
    mkdir -p "$(dirname "$dest")"
    cp -r "$src" "$dest"
    # 清理源目录可能带入的 Python 缓存，保持安装目录干净
    find "$dest" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    echo "[ADD] $name 已安装: $dest"
    count=$((count + 1))
done

if [ "$count" -eq 0 ] && [ "$FORCE" != "1" ]; then
    echo "（无新增，全部已存在或跳过）"
fi
echo "打开该项目的 AI 会话说「开始开发 X」或「恢复 X」即可使用；review 阶段质量门控由 spec-health-check 驱动"
