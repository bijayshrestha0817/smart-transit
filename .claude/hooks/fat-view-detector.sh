#!/bin/bash
# Fat View Detector — Warn when a view file is getting too large

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if echo "$FILE_PATH" | grep -qE 'v1/views/.*\.py$'; then
  if [ -f "$FILE_PATH" ]; then
    LINE_COUNT=$(wc -l < "$FILE_PATH")
    if [ "$LINE_COUNT" -gt 200 ]; then
      printf '{"systemMessage":"Warning: %s has %d lines. Views should be thin — move business logic to services and queries to repositories."}\n' "$(basename "$FILE_PATH")" "$LINE_COUNT"
    fi
  fi
fi

exit 0
