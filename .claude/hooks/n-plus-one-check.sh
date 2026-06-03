#!/bin/bash
# N+1 Check — Remind to verify select_related/prefetch_related after repository edits

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if echo "$FILE_PATH" | grep -qE '/repository/.*\.py$'; then
  printf '{"systemMessage":"Repository file edited. Verify all querysets use select_related/prefetch_related for related fields accessed downstream. Run /n-plus-one-detector if unsure."}\n'
fi

exit 0
