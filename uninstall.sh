#!/usr/bin/env bash
# spec-workflow 卸载脚本
# 用法: bash uninstall.sh --project <path> | --global
# 只移除安装的 skills，项目内 spec/ 数据与 .specworkflow/ 会话不受影响
# 注意: Windows 无原生 bash，请用 uninstall.py（python）或经 Git Bash/WSL 运行本脚本

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"

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

# 与安装对称：卸载 skills/ 下同名 skill（含新增的 dev-docs）
count=0
for src in "$SKILLS_SRC"/*/; do
    [ -d "$src" ] || continue
    name="$(basename "$src")"
    dest="$BASE/$name"
    if [ -e "$dest" ]; then
        rm -rf "$dest"
        echo "[REMOVED] $dest"
        count=$((count + 1))
    else
        echo "[SKIP] 未安装: $dest"
    fi
done
if [ "$count" -eq 0 ]; then
    echo "（无已安装项被移除）"
fi
echo "项目内 spec/ 文档与 .specworkflow/ 会话已保留"
