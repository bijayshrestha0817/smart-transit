#!/usr/bin/env bash
# on-agent-register.sh — PostToolUse hook for auto-updating agent-pane-map.json
#
# When an agent registers via macro_start_session, register_agent, or
# create_agent_identity, this hook automatically updates .ntm/agent-pane-map.json
# with the new agent's name, pane number, and role.
#
# This eliminates the need to manually maintain agent-pane-map.json.
# Old entries for the same pane are replaced automatically.
#
# Pane number is derived from NTM_SPAWN_ORDER (set by NTM for each spawned agent):
#   pane = NTM_SPAWN_ORDER + 1  (pane 1 is the coordinator/main pane)
#
# Role is inferred from the task_description in the registration call.
#
# Input (stdin JSON): tool_name, tool_input, tool_response, etc.
# Output: none (fire-and-forget)
# Exit: always 0 (hook must never fail the registering agent)

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/data/projects/omnidial-platform}"
PANE_MAP="${PROJECT_DIR}/.ntm/agent-pane-map.json"
LOG_FILE="${PROJECT_DIR}/.ntm/logs/agent-register.log"

# ── Ensure directories exist ─────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PANE_MAP")"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE" 2>/dev/null || true
}

# ── Read stdin ────────────────────────────────────────────────────────────────
INPUT=$(cat)

# ── Get pane number from NTM environment ──────────────────────────────────────
SPAWN_ORDER="${NTM_SPAWN_ORDER:-}"
if [ -z "$SPAWN_ORDER" ]; then
  log "SKIP: NTM_SPAWN_ORDER not set (not running in NTM)"
  exit 0
fi
PANE=$((SPAWN_ORDER + 1))

# ── Extract agent name from tool response ─────────────────────────────────────
# macro_start_session returns { agent: { name: "..." } }
# register_agent returns { name: "..." }
# create_agent_identity returns { name: "..." }
AGENT_NAME=$(echo "$INPUT" | jq -r '
  (if (.tool_response | type) == "string" then (.tool_response | fromjson? // {})
   else (.tool_response // {}) end) as $r |
  $r.agent.name // $r.name // empty
')

if [ -z "$AGENT_NAME" ]; then
  log "SKIP: Could not extract agent name from tool response"
  exit 0
fi

# ── Determine role from task_description ──────────────────────────────────────
TASK_DESC=$(echo "$INPUT" | jq -r '
  .tool_input.task_description // "" | ascii_downcase
')

case "$TASK_DESC" in
  *"team lead"*|*"code review"*|*"coordination"*)
    ROLE="team-lead" ;;
  *"qa"*|*"testing"*|*"quality"*)
    ROLE="qa" ;;
  *"backend"*|*"fastapi"*|*"api development"*)
    ROLE="backend-dev" ;;
  *"frontend"*|*"react"*|*"next.js"*|*"ui"*)
    ROLE="frontend-dev" ;;
  *)
    ROLE="unknown" ;;
esac

# ── Initialize pane map if missing ────────────────────────────────────────────
if [ ! -f "$PANE_MAP" ]; then
  echo '{}' > "$PANE_MAP"
  log "INIT: Created empty pane map at $PANE_MAP"
fi

# ── Update pane map ───────────────────────────────────────────────────────────
# Remove any existing entry with the same pane number (replaces predecessor),
# then add the new agent entry.
UPDATED=$(jq \
  --arg name "$AGENT_NAME" \
  --argjson pane "$PANE" \
  --arg role "$ROLE" \
  '[to_entries[] | select(.value.pane != $pane)] | from_entries |
   . + { ($name): { pane: $pane, role: $role } }' \
  "$PANE_MAP")

echo "$UPDATED" > "$PANE_MAP"

log "REGISTERED: $AGENT_NAME → pane $PANE, role $ROLE (replaced old pane $PANE entry if any)"

exit 0
