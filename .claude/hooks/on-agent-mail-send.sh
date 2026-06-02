#!/usr/bin/env bash
# on-agent-mail-send.sh — PostToolUse hook for Agent Mail auto-notification
#
# When an agent sends a message via MCP Agent Mail (send_message or reply_message),
# this hook automatically notifies recipient agents in other NTM panes via `ntm send`.
#
# This eliminates the need for agents to poll their inbox every 2-3 minutes.
# Instead, they receive a push notification immediately when a message arrives.
#
# Input (stdin JSON): tool_name, tool_input, tool_response, tool_use_id, session_id,
#   hook_event_name, cwd, permission_mode, transcript_path
# Note: For reply_message without explicit `to`, recipients are resolved from tool_response
#       (the server defaults `to` to the original sender, which only appears in the response).
# Output: none (notifications are fire-and-forget)
# Exit: always 0 (hook must never fail the sender)

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/data/projects/omnidial-platform}"
PANE_MAP="${PROJECT_DIR}/.ntm/agent-pane-map.json"
NTM_SESSION="omnidial-platform"
LOG_FILE="${PROJECT_DIR}/.ntm/logs/mail-notify.log"

# ── Ensure log directory exists ───────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE" 2>/dev/null || true
}

# ── Read stdin ────────────────────────────────────────────────────────────────
INPUT=$(cat)

# ── Parse tool name ───────────────────────────────────────────────────────────
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# ── Only handle Agent Mail send/reply tools ───────────────────────────────────
case "$TOOL_NAME" in
  mcp__mcp-agent-mail__send_message|mcp__mcp-agent-mail__reply_message)
    ;;
  *)
    exit 0
    ;;
esac

# ── Check pane map exists ─────────────────────────────────────────────────────
if [ ! -f "$PANE_MAP" ]; then
  log "SKIP: No pane map found at $PANE_MAP"
  exit 0
fi

# ── Check ntm is available ────────────────────────────────────────────────────
if ! command -v ntm &>/dev/null; then
  log "SKIP: ntm command not found"
  exit 0
fi

# ── Extract sender name ──────────────────────────────────────────────────────
SENDER=$(echo "$INPUT" | jq -r '.tool_input.sender_name // ""')

# ── Extract all recipient names (to + cc + bcc) ──────────────────────────────
# Phase 1: Try tool_input (explicit recipients from the agent's call)
# Phase 2: Fall back to tool_response (server-resolved recipients, e.g. reply_message defaults)
RECIPIENTS=$(echo "$INPUT" | jq -r '
  (
    [
      (.tool_input.to // [])[],
      (.tool_input.cc // [])[],
      (.tool_input.bcc // [])[]
    ]
  ) as $from_input |
  if ($from_input | length) > 0 then
    $from_input
  else
    # Fall back to tool_response (server-resolved recipients, e.g. reply_message defaults)
    # tool_response may be a string (needs fromjson) or object, and recipients may be
    # at top level (.to) or nested (.deliveries[].payload.to)
    (if (.tool_response | type) == "string" then
      (.tool_response | fromjson? // {})
    else
      (.tool_response // {})
    end) as $result |
    [
      ($result.to // [])[],
      ($result.cc // [])[],
      ($result.bcc // [])[],
      (($result.deliveries // [])[] | .payload | (((.to // [])[]), ((.cc // [])[]), ((.bcc // [])[])))
    ]
  end | unique | .[]
')

# ── Handle broadcast messages ─────────────────────────────────────────────────
IS_BROADCAST=$(echo "$INPUT" | jq -r '.tool_input.broadcast // false')
if [ "$IS_BROADCAST" = "true" ] && [ -z "$RECIPIENTS" ]; then
  # For broadcast, notify all agents in pane map except sender
  RECIPIENTS=$(jq -r 'keys[]' "$PANE_MAP")
fi

# ── Extract subject for notification context ──────────────────────────────────
SUBJECT=$(echo "$INPUT" | jq -r '.tool_input.subject // "new message"')

# ── Notify each recipient ────────────────────────────────────────────────────
NOTIFIED=0
SKIPPED=0

for AGENT in $RECIPIENTS; do
  # Skip sender (don't notify yourself)
  if [ "$AGENT" = "$SENDER" ]; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Look up pane number from map
  PANE=$(jq -r --arg name "$AGENT" '.[$name].pane // empty' "$PANE_MAP" 2>/dev/null)

  if [ -z "$PANE" ]; then
    log "SKIP: Agent '$AGENT' not in pane map"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Fire notification in background (non-blocking)
  # Primary: ntm send --no-cass-check (bypasses broken FTS5 in cass 0.2.1)
  # Fallback: direct tmux send-keys
  NOTIFY_MSG="You have a new Agent Mail message from ${SENDER}: \"${SUBJECT}\". Please check your inbox now using fetch_inbox."
  (
    if ntm send "$NTM_SESSION" --pane="$PANE" --no-cass-check "$NOTIFY_MSG" 2>/dev/null; then
      log "OK: Notified $AGENT (pane $PANE) — from $SENDER re: $SUBJECT"
    else
      # Fallback: inject prompt directly via tmux send-keys
      TMUX_WINDOW=$(/usr/bin/tmux list-windows -t "$NTM_SESSION" -F '#{window_index}' 2>/dev/null | head -1)
      TMUX_WINDOW="${TMUX_WINDOW:-1}"
      TMUX_TARGET="${NTM_SESSION}:${TMUX_WINDOW}.${PANE}"
      if /usr/bin/tmux send-keys -t "$TMUX_TARGET" -l "$NOTIFY_MSG" 2>/dev/null && \
         sleep 0.1 && \
         /usr/bin/tmux send-keys -t "$TMUX_TARGET" Enter 2>/dev/null; then
        log "OK: Notified $AGENT (pane $PANE) via tmux fallback — from $SENDER re: $SUBJECT"
      else
        log "FAIL: both ntm send and tmux fallback failed for $AGENT (pane $PANE)"
      fi
    fi
  ) &

  NOTIFIED=$((NOTIFIED + 1))
done

# Wait for background notifications (with timeout)
wait 2>/dev/null || true

log "DONE: tool=$TOOL_NAME sender=$SENDER notified=$NOTIFIED skipped=$SKIPPED"

exit 0
