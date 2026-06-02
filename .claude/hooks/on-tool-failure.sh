#!/usr/bin/env bash
# on-tool-failure.sh — PostToolUseFailure hook for self-healing agents
#
# Reads JSON from stdin, injects category-specific fix instructions via additionalContext.
# Tracks retry counts per unique error to prevent infinite loops.
# After 3 retries of the same error, escalates to "try a fundamentally different approach".
#
# Input (stdin JSON): tool_name, tool_input, error, is_interrupt, session_id, hook_event_name
# Output (stdout JSON): hookSpecificOutput.additionalContext with fix instructions
# Exit: always 0 (non-zero would be treated as hook failure)

set -euo pipefail

# ── Read stdin ──────────────────────────────────────────────────────────────
INPUT=$(cat)

# ── Parse fields ────────────────────────────────────────────────────────────
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
ERROR=$(echo "$INPUT" | jq -r '.error // ""')
IS_INTERRUPT=$(echo "$INPUT" | jq -r '.is_interrupt // false')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')

# ── Silent exit on user interrupt ───────────────────────────────────────────
if [ "$IS_INTERRUPT" = "true" ]; then
  exit 0
fi

# ── Silent exit if no error ─────────────────────────────────────────────────
if [ -z "$ERROR" ]; then
  exit 0
fi

# ── State directory ─────────────────────────────────────────────────────────
STATE_DIR="/tmp/claude-heal-${SESSION_ID}"
RETRY_DIR="${STATE_DIR}/retries"
mkdir -p "$RETRY_DIR"

# ── Clean up stale state dirs (older than 24h) ─────────────────────────────
find /tmp -maxdepth 1 -name 'claude-heal-*' -type d -mmin +1440 -exec rm -rf {} + 2>/dev/null || true

# ── Compute unique error key ────────────────────────────────────────────────
ERROR_SNIPPET=$(echo "$ERROR" | head -c 200)
ERROR_KEY=$(echo "${TOOL_NAME}:${ERROR_SNIPPET}" | md5sum | cut -d' ' -f1)

# ── Track retry count ──────────────────────────────────────────────────────
RETRY_FILE="${RETRY_DIR}/${ERROR_KEY}"
if [ -f "$RETRY_FILE" ]; then
  COUNT=$(cat "$RETRY_FILE")
  COUNT=$((COUNT + 1))
else
  COUNT=1
fi
echo "$COUNT" > "$RETRY_FILE"

MAX_RETRIES=3

# ── Escalation after max retries ───────────────────────────────────────────
if [ "$COUNT" -gt "$MAX_RETRIES" ]; then
  CONTEXT="🔧 SELF-HEALING (attempt ${COUNT}/${MAX_RETRIES} — ESCALATION): You have tried this ${MAX_RETRIES} times with the same approach and it keeps failing. STOP repeating the same fix. Try a FUNDAMENTALLY DIFFERENT approach — different tool, different strategy, different file, or different algorithm. If you have genuinely exhausted all automated approaches, explain clearly what you tried and ask the human for guidance."
  jq -n --arg ctx "$CONTEXT" '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUseFailure",
      "additionalContext": $ctx
    }
  }'
  exit 0
fi

# ── Categorize error and build fix instructions ────────────────────────────
INSTRUCTION=""

# Test failures
if echo "$ERROR" | grep -qiE 'pytest|FAILED|AssertionError|AssertionError|vitest|FAIL|test.*fail|expect.*received'; then
  INSTRUCTION="TEST FAILURE: Read the FULL error output carefully. Identify the exact failing assertion and what value was expected vs received. Fix the ROOT CAUSE in the source code (not the test unless the test itself is wrong). Then re-run the tests to verify your fix."

# Build / compile / import errors
elif echo "$ERROR" | grep -qiE 'tsc|SyntaxError|ModuleNotFound|Cannot find module|ImportError|compile.*error|build.*fail|TypeError.*is not|ReferenceError'; then
  INSTRUCTION="BUILD/COMPILE ERROR: Read ALL error messages (there may be multiple). Fix imports, type annotations, or syntax errors. Check that referenced modules and variables exist. Rebuild/recompile after fixing."

# Git merge conflicts
elif echo "$ERROR" | grep -qiE 'CONFLICT|merge conflict|conflict.*marker'; then
  INSTRUCTION="GIT CONFLICT: Read the conflicting files and look for <<<<<<< / ======= / >>>>>>> markers. Resolve each conflict by choosing the correct version (or combining both). Stage the resolved files with git add, then continue the merge/rebase."

# Missing command or file
elif echo "$ERROR" | grep -qiE 'command not found|No such file|ENOENT|not found.*path|FileNotFoundError'; then
  INSTRUCTION="MISSING COMMAND/FILE: Verify the command exists (use 'which' or 'type') or that the file path is correct (use 'ls' to check). The path may be wrong, the tool may not be installed, or you may be in the wrong directory. Adjust your approach accordingly."

# Permission errors
elif echo "$ERROR" | grep -qiE 'Permission denied|EACCES|permission.*error|Operation not permitted'; then
  INSTRUCTION="PERMISSION ERROR: Check file permissions with 'ls -la'. You may need to use a different path, fix file permissions, or take an alternative approach that doesn't require elevated privileges."

# Network / service errors
elif echo "$ERROR" | grep -qiE 'Connection refused|ECONNREFUSED|timeout|ETIMEDOUT|ECONNRESET|network.*error|fetch.*fail'; then
  INSTRUCTION="NETWORK/SERVICE ERROR: Check if the required service is running (try 'docker ps' or 'lsof -i'). Start the service if needed, or wait briefly and retry. If the service is external, verify the URL/port is correct."

# Edit tool errors (old_string not found / not unique)
elif echo "$ERROR" | grep -qiE 'old_string.*not found|not unique|old_string.*not unique|Could not find'; then
  INSTRUCTION="EDIT TOOL ERROR: The text you tried to match doesn't exist in the file or matches multiple locations. Use the Read tool to verify the file path is correct and see the CURRENT file contents, then retry with the exact old_string that matches the actual content."

# Fallback — generic error
else
  INSTRUCTION="UNEXPECTED ERROR: Read the error message carefully. Diagnose the root cause — don't guess. Check relevant files, verify assumptions, and fix the underlying issue. Do NOT give up or ask the human unless you have exhausted all approaches."
fi

# ── Build and emit response ─────────────────────────────────────────────────
CONTEXT="🔧 SELF-HEALING (attempt ${COUNT}/${MAX_RETRIES}): ${INSTRUCTION}"

jq -n --arg ctx "$CONTEXT" '{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUseFailure",
    "additionalContext": $ctx
  }
}'

exit 0
