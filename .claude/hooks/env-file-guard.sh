#!/bin/bash
# Env File Guard — Block writes to .env or credential files

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")

if echo "$BASENAME" | grep -qE '^\.env$|^\.env\..+|credentials\.json|secrets\.yaml|secrets\.json'; then
  # Allow .env.sample edits
  if echo "$BASENAME" | grep -qE '\.sample$|\.example$|\.template$'; then
    exit 0
  fi
  printf '{"decision":"block","reason":"Cannot write to secret/credential files (.env, credentials.json, etc.). Edit .env manually or update .env.sample instead."}\n'
fi

exit 0
