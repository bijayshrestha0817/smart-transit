---
name: weekly-summary
description: Use when generating a weekly project summary for semi-technical clients, at end of a work week, or when asked to create a status update. Triggers on "weekly summary", "weekly update", "status report", "client update".
---

# Weekly Summary Generator

## Overview

Generate a concise weekly summary of project progress for semi-technical clients. Covers completed work, upcoming targets, and includes commit references so the next agent can pick up exactly where this week ended.

## When to Use

- End of each work week
- When asked for a "weekly summary", "weekly update", or "status report"
- When preparing a client-facing progress update

## Process

### Step 1: Read Previous Summary

Read `docs/weekly-summary.md` and extract the **End commit** from the most recent summary. This becomes your **Start commit** for the new week.

```bash
head -10 docs/weekly-summary.md
# Look for "End commit: <sha>" — that's your start commit
```

### Step 2: Determine Commit Range

```bash
START_COMMIT="<end-commit-from-last-week>"
END_COMMIT=$(git rev-parse HEAD)
echo "Range: ${START_COMMIT}..${END_COMMIT}"
```

### Step 3: Gather Data

Run all of these to understand what happened this week:

```bash
# All commits in range
git log ${START_COMMIT}..${END_COMMIT} --oneline

# PRs merged to develop in this range
git log ${START_COMMIT}..${END_COMMIT} --merges --oneline

# Beads closed recently
br list --status closed --json

# Beads ready (for "Targeting Next Week")
br ready -t task --json
```

### Step 4: Determine Date Range

Use the dates of the first and last commits in the range. Format as ordinal + abbreviated month:

- `23rd Feb - 27th Feb`
- `3rd Mar - 6th Mar`
- `10th Mar - 14th Mar`

### Step 5: Write the Summary

Use this **exact template**:

```markdown
## Weekly Summary (<date-range>)

Start commit: <full-40-char-sha>
End commit: <full-40-char-sha>

### Completed This Week

- **<Accomplishment headline>** — <one-sentence plain-language explanation>
- **<Accomplishment headline>** — <one-sentence plain-language explanation>
- ...

### Targeting Next Week

- **<Planned work item>** — <brief description of what it means for the product>
- ...

---

**Bottom line:** <2-3 sentence executive summary. Connect completed work to the bigger picture. Preview what's coming next.>
```

### Step 6: Update the File

**Prepend** the new summary to `docs/weekly-summary.md`. The most recent week MUST appear at the top, directly below the `# OmniDial Updates` heading.

Final file structure:

```
# OmniDial Updates

## Weekly Summary (latest week)
...

---

## Weekly Summary (previous week)
...
```

**Important:** Keep the `# OmniDial Updates` heading at the very top. Insert the new summary between the heading and the previous week's summary.

## Writing Guidelines

### Tone: Semi-Technical Client

The audience understands what a database, API, and frontend are — but doesn't care about implementation details.

| ✅ DO | ❌ DON'T |
|-------|---------|
| "Authentication system operational" | "Implemented JWT HS256 with refresh token rotation" |
| "Database foundation fully built" | "Added Alembic dual-target migration with central + tenant schemas" |
| "Real-time communication connected" | "Configured Socket.io with Redis pub/sub adapter and JWT middleware" |
| "QA coverage for completed work" | "Added 727 pytest integration tests with parametrized fixtures" |
| "Agent status bar showing live state" | "Built React 19 component with Zustand store and WebSocket subscription" |

**Rule of thumb:** Describe WHAT was achieved and WHY it matters, not HOW it was built.

### Bullet Formatting

- **Bold the headline** — then one sentence of context after an em dash
- Group related commits/PRs into a single accomplishment (don't list every commit)
- Typically **4–7 bullets** for "Completed" and **3–5 bullets** for "Targeting Next Week"

### "Targeting Next Week"

- Pull from `br ready -t task --json` to see what's unblocked
- Translate technical task titles into product capabilities
- Be realistic — only include what's likely to actually start

### "Bottom line"

- 2–3 sentences max
- Connect the week's work to the overall project milestone
- Mention what's now unblocked or what milestone is approaching
- End on a forward-looking note

## Quick Reference

| Element | Rule |
|---------|------|
| Start commit | End commit from previous week's summary |
| End commit | Current HEAD on `develop` |
| Date format | `Xth Mon - Yth Mon` (e.g., "3rd Mar - 6th Mar") |
| Completed bullets | 4–7 items |
| Targeting bullets | 3–5 items |
| Bottom line | 2–3 sentences |
| Tone | Semi-technical, business-value focused |
| File location | `docs/weekly-summary.md` |
| Insertion point | Prepend (newest first) below `# OmniDial Updates` |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Too technical ("implemented WebSocket JWT auth middleware") | Translate to value ("Real-time communication system connected") |
| Too many bullets (listing every commit) | Group related work into 4–7 accomplishments |
| Missing start/end commits | Always include — agents need these for week-to-week continuity |
| Appending instead of prepending | Newest summary goes at the TOP, below the main heading |
| Vague "Targeting" items ("continue development") | Be specific: "Conference-based outbound calling" |
| Bottom line too long | Keep to 2–3 punchy sentences |
| Using commit SHAs in bullet text | Commits go in the header only; bullets are prose |
