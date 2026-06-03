#!/bin/bash
# Auto Lint — Run ruff fix + format after Python file edits

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only lint Python files, skip migrations
if echo "$FILE_PATH" | grep -qE '\.py$' && ! echo "$FILE_PATH" | grep -qE '/migrations/'; then
  if [ -f "$FILE_PATH" ]; then
    ruff check "$FILE_PATH" --fix --quiet 2>/dev/null
    ruff format "$FILE_PATH" --quiet 2>/dev/null
  fi
fi

exit 0
