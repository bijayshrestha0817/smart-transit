---
name: beads-creator
description: Use when creating issue tracking beads from a project plan, PRD, or feature specification. Triggers on "create beads", "initialize beads", "set up issues", "refine beads", or when converting a project plan into trackable work items.
---

# Beads Creator

Manage bead creation and refinement from project plans using the `br` CLI tool.

**Announce at start:** "I'm using the beads-creator skill."

## Usage

- `/beads-creator create <file.md>` — Create beads from a project plan/PRD
- `/beads-creator refine` — Critically review and optimize all beads
- `/beads-creator help` — Show this help

If no subcommand is given, show help.

---

## Subcommand: `create`

Read the provided markdown file(s) carefully. Then create a comprehensive set of beads for all work described.

### Bead Structure

**Epics (type: feature):**
- **Title**: `Epic N: <Name>`
- **Priority**: 1 (all epics are P1)
- **Labels**: `epic`, plus relevant domain/category labels
- **Description**: 1-2 sentence summary of the epic's scope

**Stories (type: task):**
- **Title**: `Story N.M: <Name>`
- **Priority**: 1 for critical/early work, 2 for later/lower priority
- **Assignee**: Use the role/name from the project plan as-is
- **Estimated minutes**: From story points (1pt=60m, 2pt=120m, 3pt=180m, 5pt=300m, 8pt=480m)
- **Labels**: `Npts`, track labels, domain labels, optional `sprint:N`
- **Description**: Full acceptance criteria in markdown:
  ```
  # Story N.M: <Title>
  **Points:** N | **Assignee:** <Dev> | **Dependencies:** <list>

  ## Context & Rationale
  <Why this story exists>

  ## Acceptance Criteria
  - <criterion 1>
  - <criterion 2>
  ```

**Dependencies:**
- **Parent-child**: Every story belongs to an epic
- **Blocks**: Story-to-story dependencies from the plan

### Track Labels (Mandatory on Stories)

Every story MUST have at least one. Multi-track stories get multiple labels.

| Label | When |
|-------|------|
| `backend` | API, database, service logic |
| `frontend` | UI, components, client-side |
| `qa` | Testing, test infrastructure |
| `devops` | Infrastructure, CI/CD, deployment |

### All Labels

| Label | Required |
|-------|----------|
| `epic` | On epics |
| `Npts` (e.g., `3pts`) | On stories |
| `backend` / `frontend` / `qa` / `devops` | At least one per story |
| `sprint:N` | Only if plan specifies sprints |
| Domain labels (e.g., `auth`, `payments`) | Optional — derive from project terminology |

### Execution Order

Use the `br` tool repeatedly to create the actual beads:

1. **First**: All epics (with `br label` after each)
2. **Then**: All stories grouped by epic (with `br label` after each)
3. **Finally**: All dependencies (`br dep add`)

Use `--json` flag to capture bead IDs returned by each `br create` command.

### Rules

- Use markdown in descriptions with acceptance criteria as bullet points
- If plan includes QA tasks, label with `qa` and `testing`
- Only add `sprint:N` if the plan explicitly assigns sprints
- Use assignee names/roles exactly as they appear in the plan
- Beads ARE the issue tracker — no TODO lists
- Each bead's description should be **self-contained** — a future agent should understand it in isolation

### After Creation: Automatic Validation & Refinement

After creating all beads, **automatically proceed** (do not wait for user input):

1. Inform the user: "Beads created. Running validation..."
2. Execute the **Validation Check** (see below)
3. Then execute the full **Refinement** process
4. Then run validation again to confirm
5. Display the **Post-Creation Summary**

---

## Subcommand: `refine`

Perform a critical review of every bead. For each bead, evaluate:

1. **Does it make sense?** Is the scope clear and achievable?
2. **Is it optimal?** Could the task breakdown be improved?
3. **Are dependencies correct?** Are there missing or unnecessary dependencies?
4. **Are track labels present?** Every story must have at least one of `backend`, `frontend`, `qa`, `devops`
5. **Are the descriptions sufficient?** Would a future agent have everything it needs?
6. **Are estimates reasonable?** Do the story points match the scope?

If improvements are found, revise the beads using `br update`, `br label`, `br dep add`, or `br comments add`.

**After refinement:** Run the Validation Check, then display the Post-Creation Summary.

---

## Validation Check

Run after both `create` and `refine` to verify bead integrity. Execute these commands and check for issues:

### Step 1: List all beads and verify structure

```bash
br list --json
```

Check:
- Every `task` type bead has at least one track label (`backend`, `frontend`, `qa`, `devops`)
- Every `task` type bead has a points label (`Npts`)
- Every `feature` type bead has the `epic` label
- No beads have empty descriptions

### Step 2: Verify dependency graph

```bash
br graph --all
```

Check:
- Every story has a parent-child relationship to an epic
- No orphan stories (tasks without a parent epic)
- No circular dependencies
- Blocking dependencies match what the project plan specifies
- `br ready` returns sensible results (stories whose blockers are met)

### Step 3: Spot-check counts

```bash
br list --type feature --json  # Count epics
br list --type task --json     # Count stories
br ready --json                # Ready to work on
```

Verify:
- Epic count matches the number of epics in the project plan
- Story count matches the number of stories in the project plan
- At least some stories are in `ready` state (no circular blocking)

### Step 4: Report issues

If any issues are found, **fix them immediately** using `br update`, `br label`, `br dep add`, etc. Then re-run the checks.

If all checks pass, report:
```
✓ Validation passed
  - N epics, M stories created
  - All stories have track labels
  - All stories have parent epics
  - Dependency graph is clean
  - K stories ready to work on
```

---

## Post-Creation Summary

After validation passes, display:

```
═══════════════════════════════════════════════════════════════
                        BEAD SUMMARY
═══════════════════════════════════════════════════════════════

  TOTALS
  ──────
  Epics:    X
  Stories:  Y  (Z ready, W blocked)

  BY TRACK
  ────────
  Backend:  X stories
  Frontend: Y stories
  QA:       Z stories
  DevOps:   W stories

  VALIDATION
  ──────────
  ✓ All stories have track labels
  ✓ All stories have parent epics
  ✓ Dependency graph is clean

═══════════════════════════════════════════════════════════════
```

---

## Key Principles

- **Create includes automatic refinement + validation** — no need to run them separately
- **Plan space is cheap, implementation is expensive** — get beads right before coding
- **Self-documenting beads** — every bead should be fully understandable in isolation
- **Validate twice** — after creation and after refinement
