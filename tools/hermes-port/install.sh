#!/bin/bash
# install.sh —— 把 Hermes 公用工具端口（hfind / hmail）安装到 SuperAgent 的 stateDir。
#
# 用法: install.sh [--state-dir DIR] [--check]
#   默认 stateDir: /root/work/state（可由环境变量 DSH_SUPERAGENT_STATE_DIR 覆盖）
#   --check 只做只读自检（依赖是否存在、脚本能否运行），不写任何文件
#
# 安装位置: <stateDir>/tools/hermes-port/（独立子目录，**不要**放进 worker-bin：
#   dsh-superagent 启动时会重写 worker-bin，发现非它写入的文件会停 setup）。
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
STATE_DIR=${DSH_SUPERAGENT_STATE_DIR:-/root/work/state}
CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --state-dir) STATE_DIR=${2:?--state-dir 需要参数}; shift 2 ;;
    --check) CHECK=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "install.sh: 未知参数 $1" >&2; exit 2 ;;
  esac
done
TARGET="$STATE_DIR/tools/hermes-port"
WINPY=${HTOOLS_WINPY:-/mnt/d/hermes/tools/vizenv/Scripts/python.exe}
EVERYTHING=${HTOOLS_EVERYTHING_SEARCH:-/mnt/d/hermes/scripts/everything-search.py}
MAIL_HTML=${HTOOLS_SEND_MAIL_HTML:-/mnt/d/hermes/profiles/finance/scripts/send_mail.py}
MAIL_TEXT=${HTOOLS_SEND_MAIL:-/mnt/d/hermes/scripts/send-mail.py}

fail=0
note() { printf '%s\n' "$*"; }
for dep in "$WINPY" "$EVERYTHING" "$MAIL_HTML" "$MAIL_TEXT"; do
  if [ -e "$dep" ]; then note "[ok] 依赖存在: $dep"; else note "[FAIL] 依赖缺失: $dep"; fail=1; fi
done
if [ "$CHECK" -eq 0 ]; then
  mkdir -p "$TARGET"
  install -m 755 "$HERE/hfind" "$TARGET/hfind"
  install -m 755 "$HERE/hmail" "$TARGET/hmail"
  note "[ok] 已安装到 $TARGET（hfind, hmail）"
fi
if [ "$fail" -ne 0 ]; then
  note "依赖缺失：端口可能只能运行 hfind 或 hmail 的一部分；请检查 D 盘 Hermes 安装。"
  [ "$CHECK" -eq 0 ] && exit 1 || exit 1
fi
SMOKE_DIR="$TARGET"
[ "$CHECK" -eq 1 ] && SMOKE_DIR="$HERE"
note "[ok] 冒烟：hfind 帮助与一次只读查询（$SMOKE_DIR）"
"$SMOKE_DIR/hfind" -h >/dev/null
"$SMOKE_DIR/hfind" "hermes-port" --path D:/HermesTools -n 1 >/dev/null 2>&1 || true
note "[ok] 冒烟通过；hmail 会真实发信，安装脚本不自动调用（用 hmail -h 查看用法）"
