---
name: bug-report
description: Investigate bugs and create structured bug beads with Jira sync. Triggers on "bug report", "create bug", "file bug", "report bug", or when a user describes a bug symptom to investigate and track.
---

# Bug Report Skill

## Overview

Investigate a reported bug, identify root cause through codebase analysis, create a structured bug bead in beads_rust, sync to Jira, and notify the team. Produces consistent, thorough bug reports with standardized descriptions.

## When to Use

- User reports a bug or unexpected behavior
- User asks to "create a bug", "file a bug", or "report a bug"
- User describes a symptom that needs investigation and tracking

## Invocation

```
/bug-report <symptom description>
/bug-report --priority 2 --assignee "Backend Dev" <symptom description>
/bug-report --skip-investigation <symptom description with known root cause>
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--priority` | `1` | Priority level (1=highest, 4=lowest) |
| `--assignee` | Auto-detect from affected files | Who should fix it |
| `--labels` | Auto-detect from affected files | Comma-separated labels |
| `--sprint` | None | Sprint label (e.g., `sprint:2`) |
| `--skip-investigation` | `false` | Skip codebase investigation (use when root cause is already known) |

---

## Process

### Step 1: Parse the Bug Report

Extract from the user's input:
- **Symptom**: What is the user observing?
- **Expected behavior**: What should happen instead?
- **Context**: Any files, components, or flows mentioned?

If the description is too vague, ask ONE clarifying question before proceeding.

### Step 2: Investigate the Codebase (unless `--skip-investigation`)

Delegate to an `explore-medium` agent to trace the bug:

```
Agent(subagent_type="oh-my-claudecode:explore-medium",
      prompt="Investigate: <symptom>. Trace the data/control flow
              from <source> to <destination>. Find root cause.
              Report: affected files, code snippets, analysis.")
```

The investigation should:
- Trace the full data flow (DB → API → Service → WebSocket → Frontend, or whichever layers are relevant)
- Identify the **root cause** (not just the symptom)
- List all **affected files** with specific line references
- Propose a **suggested fix**

### Step 3: Auto-Detect Metadata

From the investigation results, derive:

| Metadata | Rule |
|----------|------|
| **Assignee** | Files in `frontend/` → "Frontend Dev", files in `backend/` → "Backend Dev", mixed → "Frontend Dev" (UI symptom) or "Backend Dev" (data symptom) |
| **Labels** | Always include `bug`. Add `frontend`/`backend`/`websocket`/`api`/`database` based on affected files. Add sprint label if known. |

User-provided `--assignee` and `--labels` override auto-detection.

### Step 4: Write the Bug Description

Use the **Bug Description Template** below. Write the description to a temp file first to avoid shell escaping issues:

```bash
# Write description to temp file
cat > /tmp/bug-description.txt << 'TEMPLATE'
<filled template content>
TEMPLATE
```

### Step 5: Create the Bead

```bash
DESCRIPTION=$(cat /tmp/bug-description.txt) && \
br create "<title>" \
  -t bug \
  -p <priority> \
  -a "<assignee>" \
  -e <estimate_minutes> \
  -l "<labels>" \
  -d "$DESCRIPTION" \
  --json
```

**Title format**: `Bug: <concise symptom description>`
**Estimate**: Based on suggested fix complexity (simple wiring fix: 60-120m, logic bug: 120-240m, architectural issue: 240-480m)

### Step 6: Add Audit Comment

```bash
br comments add <bead-id> "Bug reported by <reporter>. Root cause: <one-line summary>. Fix: <one-line suggested fix>."
```

### Step 7: Sync to Jira

```bash
python3 jira-sync/sync_bead.py <bead-id>
```

### Step 7b: Set External Ref on Bead

The Jira sync script often fails to write the `external_ref` back to the bead due to database locking. **Always set it manually** after Jira sync using the Jira ID from the sync output:

```bash
br update <bead-id> --external-ref <BMO-XXX> --json
```

Then verify it was set:

```bash
br show <bead-id> --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('external_ref:', d[0].get('external_ref', 'NOT SET'))"
```

**IMPORTANT**: Do NOT skip this step. The `external_ref` links the bead to Jira and is required for the branching convention (`feature/BMO-XXX-short-title`).

### Step 8: Notify Team (Optional)

If Agent Mail is active, send notification to the assignee and Team Lead:

```
send_message(
  project_key="/data/projects/omnidial-platform",
  sender_name=<your-name>,
  to=[<assignee-agent>, <team-lead-agent>],
  subject="New bug: <bead-id> - <title>",
  body_md="**Bug filed:** `<bead-id>` / Jira `<jira-id>`\n\n**Symptom:** <symptom>\n**Root cause:** <one-line>\n**Priority:** P<n>\n\nPlease prioritize — bugs take precedence over new features per AGENTS.md.",
  topic="bugs"
)
```

### Step 9: Report Summary

Present a summary table to the user:

```
| Field       | Value                        |
|-------------|------------------------------|
| Bead ID     | bd-xxx                       |
| Jira ID     | BMO-xxx                      |
| Title       | Bug: ...                     |
| Priority    | P1                           |
| Assignee    | Frontend Dev                 |
| Labels      | bug, frontend, websocket     |
| Estimate    | 120 minutes                  |
```

---

## Bug Description Template

Every bug description MUST follow this structure. Sections can be brief if the bug is simple, but all sections must be present.

```markdown
# Bug: <Title — one-line symptom description>

**Severity:** <High|Medium|Low> | **Assignee:** <name> | **Sprint:** <TBD or sprint number>
**Reported by:** <reporter name/agent> | **Date:** <YYYY-MM-DD>

## Problem
<2-3 sentences describing what the user observes. Be specific — include the exact incorrect behavior and where it appears.>

## Root Cause Analysis

<Explain WHY the bug occurs. Include:>
- What component/layer is broken
- Why the current code produces the wrong behavior
- Whether this is a logic error, wiring error, missing code, race condition, etc.

### <Sub-heading for each distinct cause if multiple>
- <Detailed explanation with file references>

## Data Flow (showing where it breaks)

<ASCII diagram or step-by-step flow showing the path data takes through the system, with annotations marking where the bug occurs. Example:>

DB (table.column = "expected_value")
  -> ORM Model
  -> API Endpoint (GET /api/v1/...) -- WORKS
  -> WebSocket event                  -- BUG: never received
  -> Frontend Store                   -- STUCK at default
  -> UI Component                     -- renders wrong value

## Affected Files
- <path/to/file1> — <what's wrong in this file>
- <path/to/file2> — <what's wrong in this file>

## Suggested Fix

### Fix 1: <Short title>
<Describe what to change and where. Be specific enough that a dev can implement without re-investigating.>

### Fix 2: <Short title> (if multiple fixes needed)
<Same format>

## Reproduction Steps
1. <Step 1>
2. <Step 2>
3. <Observe: ...>

## Expected Behavior
<What should happen instead.>

[BeadsID:bd-xxx]
```

**IMPORTANT**: The `[BeadsID:bd-xxx]` tag MUST appear at the very end of the description, after all other content. Replace `bd-xxx` with the actual bead ID after creation. Update the description with:

```bash
# After bead creation, update description to include the bead ID tag
UPDATED_DESC=$(cat /tmp/bug-description.txt && echo -e "\n[BeadsID:<bead-id>]")
br update <bead-id> --description "$UPDATED_DESC"
```

---

## Assignee Auto-Detection Rules

| Affected Files Pattern | Assignee |
|------------------------|----------|
| `frontend/**` only | Frontend Dev |
| `backend/**` only | Backend Dev |
| Both frontend + backend (UI symptom) | Frontend Dev |
| Both frontend + backend (data/API symptom) | Backend Dev |
| `qa/**`, test files only | QA Agent |
| Infrastructure, Docker, CI | Backend Dev |

---

## Label Auto-Detection Rules

| Affected Files Pattern | Labels to Add |
|------------------------|---------------|
| Always | `bug` |
| `frontend/src/components/**` | `frontend`, `ui` |
| `frontend/src/hooks/**`, `frontend/src/store/**` | `frontend` |
| `backend/app/api/**` | `backend`, `api` |
| `backend/app/models/**` | `backend`, `database` |
| `backend/app/services/websocket.py` or WS-related | `websocket` |
| `backend/app/services/**` | `backend` |
| Any auth-related files | `security` |

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Description too vague ("it doesn't work") | Always include: what happens, what should happen, where it happens |
| Missing root cause (just describes symptom) | Investigate BEFORE creating the bead — don't skip Step 2 |
| Shell escaping breaks `br create` | Always write description to `/tmp/bug-description.txt` first, then use `$()` substitution |
| Forgot `[BeadsID:bd-xxx]` tag | MUST appear at end of description — update after creation |
| Forgot Jira sync | MUST run `python3 jira-sync/sync_bead.py` — never skip |
| Estimate too low | Minimum 60 minutes even for "simple" bugs — investigation + fix + test + review |

---

## Quick Reference

| Element | Rule |
|---------|------|
| Skill trigger | "bug report", "create bug", "file bug", "report bug" |
| Title format | `Bug: <concise symptom>` |
| Description template | All 7 sections required |
| Bead ID tag | `[BeadsID:bd-xxx]` at end of description |
| Priority default | P1 |
| Estimate minimum | 60 minutes |
| Jira sync | Mandatory — never skip |
| Temp file | Always use `/tmp/bug-description.txt` for shell safety |
