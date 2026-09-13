#!/usr/bin/env bash
# spec-workflow 安装脚本（M0/M1）
# 用法:
#   bash install.sh --project <project-path>   # 项目级安装
#   bash install.sh --global                    # 全局安装（~/.codebuddy/skills/）
#   bash install.sh --project <path> --force    # 覆盖安装（删除旧目录后重装，即"更新"）
#   bash install.sh --project <path> --check    # 只对比源码与已安装版本，不安装
# 升级路径：git pull 后 bash install.sh --check 看版本差 → --force 覆盖更新（全局一次生效；
# 项目级安装需各项目分别更新）。Windows 无 bash 时用同目录 install.py（语义一致）。
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
CHECK=0
while [ $# -gt 0 ]; do
    case "$1" in
        --project) MODE="project"; TARGET="$2"; shift 2 ;;
        --global)  MODE="global"; shift ;;
        --force)   FORCE=1; shift ;;
        --check)   CHECK=1; shift ;;
        *) echo "用法: bash $0 [--project <path> | --global] [--force] [--check]" >&2; exit 1 ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "用法: bash $0 [--project <path> | --global] [--force] [--check]" >&2
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

# _meta.json 的 version 字段（缺失/损坏返回空）
_meta_ver() {
    [ -f "$1/_meta.json" ] || { echo ""; return; }
    grep -o '"version"[^,}]*' "$1/_meta.json" 2>/dev/null | head -1 \
        | sed 's/.*"\([^"]*\)"$/\1/' || true
}

# --check：版本对比表，不安装
if [ "$CHECK" = "1" ]; then
    printf "%-20s %-8s %-8s %s\n" "skill" "源码" "已安装" "状态"
    for src in "$SKILLS_SRC"/*/; do
        [ -d "$src" ] || continue
        name="$(basename "$src")"
        ver="$(_meta_ver "$src")"
        if [ -d "$BASE/$name" ]; then
            cur="$(_meta_ver "$BASE/$name")"
        else
            cur=""
        fi
        if [ -z "$cur" ]; then
            status="未安装"
        elif [ "$cur" = "$ver" ]; then
            status="已是最新"
        else
            status="可更新（--force 覆盖）"
        fi
        printf "%-20s %-8s %-8s %s\n" "$name" "${ver:-?}" "${cur:--}" "$status"
    done
    if [ "$MODE" = "global" ]; then
        echo "升级方式：git pull 后 bash install.sh --global --force（全局一次生效）"
    else
        echo "升级方式：git pull 后 bash install.sh --project <path> --force（项目级需各项目分别更新）"
    fi
    exit 0
fi

# 安装 skills/ 下每个 skill（不递归）
count=0
for src in "$SKILLS_SRC"/*/; do
    [ -d "$src" ] || continue
    name="$(basename "$src")"
    dest="$BASE/$name"
    if [ -e "$dest" ]; then
        if [ "$FORCE" = "1" ]; then
            cur_ver="$(_meta_ver "$dest")"
            src_ver="$(_meta_ver "$src")"
            rm -rf "$dest"
            trans=""
            if [ -n "$cur_ver" ] && [ "$cur_ver" != "$src_ver" ]; then
                trans="（版本 $cur_ver → ${src_ver:-?}）"
            fi
            echo "[REFRESH] 覆盖安装$trans: $dest"
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
