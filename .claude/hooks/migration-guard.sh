#!/bin/bash
# Migration Guard — Warn before editing migration files
# Reminds to use `make migrations` instead of manual edits

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if echo "$FILE_PATH" | grep -qE '/migrations/[0-9]'; then
  printf '{"systemMessage":"Warning: Editing a migration file. Prefer `make migrations` to auto-generate. Only add custom code to migrations when explicitly required."}\n'
fi

exit 0
