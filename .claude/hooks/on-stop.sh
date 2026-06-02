#!/usr/bin/env bash
# on-stop.sh — Stop hook for self-healing agents
#
# Detects "giving up" patterns in the last assistant message and blocks premature stopping.
# Allows legitimate completion (tests pass, merged, PR created, etc.) through.
#
# Safety valve: after 5 consecutive blocks, releases the agent to prevent infinite loops.
#
# Input (stdin JSON): stop_hook_active, last_assistant_message, session_id, hook_event_name
# Output (stdout JSON): { "decision": "block", "reason": "..." } to block, or empty/exit 0 to allow
# Exit: always 0

set -euo pipefail

# ── Read stdin ──────────────────────────────────────────────────────────────
INPUT=$(cat)

# ── Parse fields ────────────────────────────────────────────────────────────
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
LAST_MSG=$(echo "$INPUT" | jq -r '.last_assistant_message // ""' | head -c 2000)

# ── State directory ─────────────────────────────────────────────────────────
STATE_DIR="/tmp/claude-heal-${SESSION_ID}"
BLOCK_FILE="${STATE_DIR}/stop-blocks"
mkdir -p "$STATE_DIR"

# ── Phase 1: Safety valve ──────────────────────────────────────────────────
# If stop_hook_active is true (meaning we're already inside a stop-block cycle),
# check the consecutive block counter. After 5 blocks, release.
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  CONSECUTIVE=0
  if [ -f "$BLOCK_FILE" ]; then
    CONSECUTIVE=$(cat "$BLOCK_FILE")
  fi

  if [ "$CONSECUTIVE" -ge 5 ]; then
    # Safety valve: release the agent, reset counter
    echo "0" > "$BLOCK_FILE"
    exit 0
  fi
fi

# ── Phase 2: Give-up detection ──────────────────────────────────────────────
# Skip detection if message is empty
if [ -z "$LAST_MSG" ]; then
  # No message to analyze — allow stop, reset counter
  echo "0" > "$BLOCK_FILE" 2>/dev/null || true
  exit 0
fi

# Check for legitimate completion signals FIRST
COMPLETION_FOUND=false
if echo "$LAST_MSG" | grep -qiE 'completed successfully|all tests pass|successfully merged|pushed to|PR created|pull request created|task.*completed|task.*done|build succeeded|ready for review|no.*pending|verified.*pass|approved|merge.*complete|all.*checks.*pass|changes.*committed.*pushed'; then
  COMPLETION_FOUND=true
fi

# Check for giving-up signals
GIVING_UP_FOUND=false
if echo "$LAST_MSG" | grep -qiE "I'm unable to|I cannot proceed|I can't proceed|unable to resolve|unable to fix|waiting for.*input|need.*help.*from you|could you.*help|could you.*fix|stuck on|cannot proceed|not sure how to|beyond my ability|I'll stop here|let me know if|let me know how|please.*help|I'm not able|I cannot figure|I can't figure|I'm having trouble.*unable|unfortunately.*cannot|unfortunately.*unable|I need your.*help|require.*manual|requires.*manual|human.*intervention|outside.*my.*ability"; then
  GIVING_UP_FOUND=true
fi

# ── Phase 3: Decision ──────────────────────────────────────────────────────
if [ "$GIVING_UP_FOUND" = "true" ] && [ "$COMPLETION_FOUND" = "false" ]; then
  # BLOCK: agent is giving up without completing
  CONSECUTIVE=0
  if [ -f "$BLOCK_FILE" ]; then
    CONSECUTIVE=$(cat "$BLOCK_FILE")
  fi
  CONSECUTIVE=$((CONSECUTIVE + 1))
  echo "$CONSECUTIVE" > "$BLOCK_FILE"

  REASON="🔧 SELF-HEALING: You are giving up on an error instead of fixing it. This is block ${CONSECUTIVE}/5. STOP and re-read the error message. Diagnose the root cause. Try a different approach if your previous attempts failed. You have the tools and context to solve this — use them. Do NOT stop until the issue is resolved or you have exhausted all approaches (at which point explain exactly what you tried)."

  jq -n --arg reason "$REASON" '{
    "decision": "block",
    "reason": $reason
  }'
  exit 0
fi

# Allow stop — either legitimate completion or no giving-up signals detected
# Reset the consecutive block counter
echo "0" > "$BLOCK_FILE" 2>/dev/null || true
exit 0
