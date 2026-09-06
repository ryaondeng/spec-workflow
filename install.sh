#!/usr/bin/env bash
# spec-workflow 安装脚本（M0 简化版）
# 用法:
#   bash install.sh --project <project-path>   # 项目级安装
#   bash install.sh --global                    # 全局安装（~/.codebuddy/skills/）
#   bash install.sh --project <path> --force    # 覆盖安装（删除旧目录后重装）
# 安装单元 = skills/spec-dev-workflow 整体（SKILL.md + scripts + pipelines + templates + references）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$REPO_ROOT/skills/spec-dev-workflow"
SKILL_NAME="spec-dev-workflow"

if [ ! -d "$SKILL_SRC" ]; then
    echo "❌ 未找到 skill 源码: $SKILL_SRC" >&2
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

if [ "$MODE" = "global" ]; then
    DEST="${HOME}/.codebuddy/skills/${SKILL_NAME}"
else
    if [ -z "$TARGET" ]; then
        echo "❌ --project 需要指定项目路径" >&2; exit 1
    fi
    DEST="${TARGET%/}/.codebuddy/skills/${SKILL_NAME}"
fi

if [ -e "$DEST" ]; then
    if [ "$FORCE" = "1" ]; then
        rm -rf "$DEST"
        echo "[REFRESH] 覆盖安装: $DEST"
    else
        echo "[SKIP] 已存在，跳过（如需更新请加 --force）: $DEST"
        exit 0
    fi
fi

mkdir -p "$(dirname "$DEST")"
cp -r "$SKILL_SRC" "$DEST"
echo "[ADD] spec-workflow skill 已安装: $DEST"
echo "      打开该项目的 AI 会话说「开始开发 X」或「恢复 X」即可使用"
echo "      流水线定义: $DEST/pipelines/default.json（项目可用 spec/pipeline.json 覆盖）"
