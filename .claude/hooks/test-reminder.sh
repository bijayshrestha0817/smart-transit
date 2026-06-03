#!/bin/bash
# Test Reminder — Suggest running related tests after editing service/view files

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if echo "$FILE_PATH" | grep -qE '(v1/views/|v1/service/).*\.py$'; then
  # Extract app name from path
  APP_NAME=$(echo "$FILE_PATH" | sed "s|$CLAUDE_PROJECT_DIR/||" | cut -d'/' -f1)
  if [ -n "$APP_NAME" ] && [ -d "$CLAUDE_PROJECT_DIR/$APP_NAME/tests" ]; then
    printf '{"systemMessage":"Service/view file edited. Consider running related tests: make test ARGS=\"%s/tests/\""}\n' "$APP_NAME"
  fi
fi

exit 0
