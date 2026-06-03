#!/bin/bash
# Import Sort — Run ruff isort fix after Python file edits

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only sort imports in Python files, skip migrations
if echo "$FILE_PATH" | grep -qE '\.py$' && ! echo "$FILE_PATH" | grep -qE '/migrations/'; then
  if [ -f "$FILE_PATH" ]; then
    ruff check "$FILE_PATH" --select I --fix --quiet 2>/dev/null
  fi
fi

exit 0
