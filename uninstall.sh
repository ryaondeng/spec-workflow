#!/usr/bin/env bash
# spec-workflow 卸载脚本
# 用法: bash uninstall.sh --project <path> | --global
# 只移除安装的 skill 目录，项目内 spec/<feature>/ 数据不受影响

set -euo pipefail

MODE=""
TARGET=""
while [ $# -gt 0 ]; do
    case "$1" in
        --project) MODE="project"; TARGET="$2"; shift 2 ;;
        --global)  MODE="global"; shift ;;
        *) echo "用法: bash $0 [--project <path> | --global]" >&2; exit 1 ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "用法: bash $0 [--project <path> | --global]" >&2; exit 1
fi

if [ "$MODE" = "global" ]; then
    DEST="${HOME}/.codebuddy/skills/spec-dev-workflow"
else
    DEST="${TARGET%/}/.codebuddy/skills/spec-dev-workflow"
fi

if [ -e "$DEST" ]; then
    rm -rf "$DEST"
    echo "[REMOVED] $DEST"
    echo "项目内 spec/ 数据已保留"
else
    echo "[SKIP] 未安装: $DEST"
fi
