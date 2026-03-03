#!/bin/bash

# Smart Git Commit Script
# 按照 git-commit-standards 规范提交变更

echo "=== 检查 Git 状态 ==="
git status

echo ""
echo "=== 未提交的变更 ==="
git diff --stat

echo ""
echo "=== 请选择 commit 类型 ==="
echo "1) feat     - 新功能"
echo "2) fix      - Bug 修复"
echo "3) refactor - 代码重构"
echo "4) perf     - 性能优化"
echo "5) test     - 测试相关"
echo "6) docs     - 文档变更"
echo "7) chore    - 维护任务"
echo ""
read -p "选择类型 (1-7): " type_choice

case $type_choice in
  1) commit_type="feat" ;;
  2) commit_type="fix" ;;
  3) commit_type="refactor" ;;
  4) commit_type="perf" ;;
  5) commit_type="test" ;;
  6) commit_type="docs" ;;
  7) commit_type="chore" ;;
  *) echo "无效选择"; exit 1 ;;
esac

read -p "输入 scope (如: hooks, agent, deploy): " scope
read -p "输入 subject (简短描述): " subject

if [ -z "$subject" ]; then
  echo "错误: subject 不能为空"
  exit 1
fi

echo ""
read -p "是否需要添加详细说明? (y/n): " add_body

if [ "$add_body" = "y" ]; then
  echo "输入详细说明 (输入空行结束):"
  body=""
  while IFS= read -r line; do
    [ -z "$line" ] && break
    body="${body}${line}\n"
  done
fi

# 构建 commit message
if [ -n "$scope" ]; then
  commit_msg="${commit_type}(${scope}): ${subject}"
else
  commit_msg="${commit_type}: ${subject}"
fi

if [ -n "$body" ]; then
  commit_msg="${commit_msg}\n\n${body}"
fi

echo ""
echo "=== 将要执行的命令 ==="
echo "git add -A"
echo "git commit -m \"${commit_msg}\""
echo ""
read -p "确认提交? (y/n): " confirm

if [ "$confirm" = "y" ]; then
  git add -A
  echo -e "$commit_msg" | git commit -F -
  echo ""
  echo "✓ 提交成功!"
  git log -1 --oneline
else
  echo "已取消"
fi
