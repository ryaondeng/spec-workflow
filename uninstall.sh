#!/usr/bin/env bash
# spec-workflow 卸载脚本
# 用法: bash uninstall.sh --project <path> | --global
# 只移除安装的 skills，项目内 spec/ 数据与 .specworkflow/ 会话不受影响

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
    BASE="${HOME}/.codebuddy/skills"
else
    [ -n "$TARGET" ] || { echo "❌ --project 需要指定项目路径" >&2; exit 1; }
    BASE="${TARGET%/}/.codebuddy/skills"
fi

for name in spec-dev-workflow spec-health-check; do
    dest="$BASE/$name"
    if [ -e "$dest" ]; then
        rm -rf "$dest"
        echo "[REMOVED] $dest"
    else
        echo "[SKIP] 未安装: $dest"
    fi
done
echo "项目内 spec/ 文档与 .specworkflow/ 会话已保留"
