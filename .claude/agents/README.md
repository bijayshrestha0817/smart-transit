# Agents

Specialized agents for complex, multi-step tasks.

---

## What Are Agents?

Agents are autonomous Claude instances that handle specific complex tasks. Unlike skills (which provide inline guidance), agents:

- Run as separate sub-tasks
- Work autonomously with minimal supervision
- Return comprehensive reports when complete

---

## Available Agents (2)

### expert-react-frontend-engineer

**Purpose:** Generate and modify React code following React 19 best practices, modern hooks, and TypeScript patterns.

**When to use:**

- Building new React components or pages
- Modifying existing React code
- Implementing hooks, Server Components, or Actions
- Optimizing component performance
- Any React/TypeScript code generation

**Model:** Sonnet

---

### plan-reviewer

**Purpose:** Review development plans before implementation, tailored to this project's Next.js 16 / React 19 stack.

**When to use:**

- Before starting complex features
- Validating architectural plans against project conventions
- Identifying missing considerations (auth, error handling, API patterns)
- Getting a second opinion on approach

**Model:** Opus

---

## When to Use Agents vs Skills

| Use Agents When...                | Use Skills When...              |
| --------------------------------- | ------------------------------- |
| Task requires multiple steps      | Need inline guidance            |
| Complex analysis needed           | Checking best practices         |
| Autonomous work preferred         | Want to maintain control        |
| Task has clear end goal           | Ongoing development work        |
| Example: "Review my feature plan" | Example: "Creating a new route" |

**Both can work together:**

- Skill provides patterns during development
- Agent reviews the result when complete

---

## How to Use

Ask Claude:

```
Use the expert-react-frontend-engineer agent to build a claims filter component.
```

```
Use the plan-reviewer agent to review my plan for implementing pagination.
```

---

## Creating New Agents

Agents are markdown files with YAML frontmatter in `.claude/agents/`:

```markdown
---
name: agent-name
description: When to use this agent with examples.
model: opus
---

# Agent Name

Your role and instructions here.
```

**Tips:**

- Be specific in instructions
- Include project context (tech stack, conventions)
- Specify exactly what format to return results in
- Set the right model (`opus` for complex analysis, `sonnet` for code generation)
