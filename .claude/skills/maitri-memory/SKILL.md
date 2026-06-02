---
name: maitri-memory
description: Persistent memory skill that maintains a markdown file for tracking all activity during a task. Read the file before each step and update it after each action to maintain continuity across context windows. Also maintains ARCHITECTURE_REFERENCE.md as a living document.
---

# /maitri-memory - Persistent Task Memory Skill

## MANDATORY CHECKLIST - EVERY SINGLE ACTION

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BEFORE each step:                                                       │
│    □ Read memory file (docs/memory/<task>-<date>.md)                    │
│                                                                          │
│  AFTER each action:                                                      │
│    □ Update memory file (Progress Log, Current Step, Files Modified)   │
│    □ Check: Did I modify API routes, database, or config files?         │
│        → YES: Update ARCHITECTURE_REFERENCE.md NOW                      │
│        → NO:  Continue to next step                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

**This checklist is NON-NEGOTIABLE. Follow it for EVERY action you take.**

---

## Commands

```
/maitri-memory start <task-name>     # Initialize new memory file
/maitri-memory continue <task-name>  # Resume existing task
/maitri-memory status                # List all memory files
/maitri-memory arch-status           # Check architecture doc health
/maitri-memory arch-refresh          # Full architecture scan/update (or CREATE if missing)
```

---

## Session Start

When starting or continuing a task:
1. **Check if `docs/ARCHITECTURE_REFERENCE.md` exists**
   - If YES: Read it for system context
   - If NO: **CREATE IT IMMEDIATELY** using the template below and scanning the codebase
2. Read/create memory file at `docs/memory/<task-name>-<YYYY-MM-DD>.md`

**CRITICAL:** If ARCHITECTURE_REFERENCE.md does not exist, you MUST create it before proceeding with any other work. Use `/maitri-memory arch-refresh` or manually create it using the template.

---

## Memory File Template

```markdown
# Task: <task-name>

**Status:** IN_PROGRESS | COMPLETED | BLOCKED
**Last Updated:** <timestamp>

## Objective
<What you're trying to accomplish>

## Current Step
<What you're working on right now>

## Progress Log

### <timestamp> - <action-summary>
- **Action:** <what was done>
- **Result:** <outcome>
- **Files:** <files modified>

## Architecture Changes
<!-- REQUIRED: Update this after EVERY action. Write "None" if no changes. -->

| Timestamp | Updated? | Section Changed | Reason |
|-----------|----------|-----------------|--------|
| <time>    | Yes/No   | <section>       | <why>  |

## Pending Tasks
- [ ] Task 1
- [ ] Task 2

## Files Modified

| File | Change | Description |
|------|--------|-------------|
| path/to/file | CREATE/MODIFY/DELETE | Brief description |

## Discoveries & Notes
<Important findings, context, reference information>
```

---

## ARCHITECTURE_REFERENCE.md Template

When creating the architecture doc, scan the codebase and populate ALL sections. This is the single source of truth for how the system is structured.

```markdown
# <Project Name> - Architecture Reference

**Generated:** <YYYY-MM-DD>
**Last Updated:** <ISO timestamp>
**Branch:** `<current branch>`
**Status:** <project status>

---

## SYSTEM ASSETS & CONNECTION STRINGS

### Database
```
Type: <PostgreSQL/SQLite/etc>
Host: <host>
Port: <port>
Database: <name>
ORM: <Prisma/Drizzle/etc>
Connection String: <from .env.example, never actual secrets>
```

### Authentication
```
Provider: <NextAuth/Auth0/etc>
Method: <OAuth/JWT/etc>
```

### External Services
```
<List any APIs, webhooks, etc>
```

---

## DIRECTORY STRUCTURE

```
<project-name>/
├── docs/
│   ├── ARCHITECTURE_REFERENCE.md  # This document
│   ├── memory/                    # Maitri-memory task tracking
│   └── ...
├── src/ or app/
│   ├── ...
├── prisma/ or db/
│   └── schema.prisma
├── tests/
└── ...
```

---

## DEPENDENCY GRAPH

### Technology Stack

```
Frontend:
├── <framework>
├── <ui library>
└── <styling>

Backend:
├── <runtime>
├── <orm>
└── <auth>

Database:
└── <database>
```

---

## DATABASE SCHEMA

### Core Entities

| Table | Description |
|-------|-------------|
| <table> | <purpose> |

### Entity Definitions

<For each table, list columns, types, and relationships>

---

## API ENDPOINTS

### <Category>
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/...` | ... |
| POST | `/api/...` | ... |

---

## DATA FLOW DIAGRAMS

<ASCII diagrams showing how data moves through the system>

---

## ENVIRONMENT VARIABLES

```bash
# From .env.example - never include actual values
DATABASE_URL=
NEXTAUTH_SECRET=
...
```

---

## QUICK COMMANDS

```bash
# Development
npm run dev

# Database
npx prisma migrate dev
npx prisma db seed

# Tests
npm run test:e2e
```

---

## KEY BOUNDARIES

| Component | Responsibility | Never Does |
|-----------|----------------|------------|
| <component> | <what it does> | <what it shouldn't do> |

---

## RELATED DOCUMENTATION

| Document | Path | Purpose |
|----------|------|---------|
| ... | ... | ... |

---

## Document Maintenance

This document should be updated when:
- New services or components are added
- Database schema changes
- API endpoints are added or modified
- Infrastructure changes

**Last Updated:** <date>
**Version:** 1.0
```

---

## Architecture Update Triggers

**Update ARCHITECTURE_REFERENCE.md when you modify:**

| File Pattern | Section to Update |
|--------------|-------------------|
| `**/api/**`, `**/routes/**` | API Endpoints |
| `**/migrations/**`, `schema.prisma` | Database Schema |
| `package.json`, `requirements.txt` | Dependency Graph |
| New directories under `src/` | Directory Structure |
| `.env.example`, config files | Environment Variables |
| `docker-compose*.yml`, `Dockerfile` | System Assets |
| `scripts/*.sh`, `scripts/*.py` | Quick Commands |

**How to update:**
1. Read current ARCHITECTURE_REFERENCE.md
2. Add entry in the appropriate section (match existing format)
3. Update "Last Updated" timestamp at top
4. Log it in your memory file's "Architecture Changes" table

---

## Command Details

### /maitri-memory start <task-name>
1. Check if `docs/ARCHITECTURE_REFERENCE.md` exists
   - If NO: Create it using the template above by scanning the codebase
2. Create `docs/memory/<task-name>-<date>.md` using memory template
3. Ask user for objective
4. Announce: "Memory initialized. Following mandatory checklist for all actions."

### /maitri-memory continue <task-name>
1. Check if `docs/ARCHITECTURE_REFERENCE.md` exists
   - If NO: Create it using the template above by scanning the codebase
2. Find most recent memory file matching task name
3. Read completely, resume from "Current Step"

### /maitri-memory arch-refresh
1. If `docs/ARCHITECTURE_REFERENCE.md` does not exist, CREATE it
2. Scan codebase for current architecture:
   - Read package.json/requirements.txt for dependencies
   - Read schema.prisma or migrations for database schema
   - Scan src/app/api or routes for API endpoints
   - Read .env.example for environment variables
   - Scan directory structure
3. Update ALL sections of ARCHITECTURE_REFERENCE.md
4. Log in memory file if active

### /maitri-memory arch-status
1. Check if `docs/ARCHITECTURE_REFERENCE.md` exists
2. If exists, report last updated date and version
3. If missing, report "ARCHITECTURE_REFERENCE.md does not exist - run /maitri-memory arch-refresh to create it"

---

## Quick Reference

**Memory file location:** `docs/memory/<task-name>-<YYYY-MM-DD>.md`
**Architecture doc:** `docs/ARCHITECTURE_REFERENCE.md`

**Remember:**
- The "Architecture Changes" table in your memory file must be updated after EVERY action - even if just to write "No" in the Updated column
- If ARCHITECTURE_REFERENCE.md doesn't exist, CREATE IT before doing any other work
- This ensures you consciously check whether an architecture update is needed
