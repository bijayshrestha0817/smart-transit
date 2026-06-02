---
name: software-taste
description: >
  Enforces architectural taste and code quality principles in all software development tasks.
  Use this skill whenever Claude writes, reviews, designs, architects, or refactors code of any
  kind — backend services, APIs, data pipelines, frontend components, scripts, infrastructure,
  or full applications. Triggers on any coding task, architecture discussion, code review, or
  technical design conversation. Applies principles distilled from Ousterhout, Fowler, Hickey,
  Brooks, and Beck to ensure code exhibits conceptual integrity, appropriate complexity, deep
  modules, honest boundaries, and changeability. Does NOT apply to purely visual/UI aesthetic
  concerns (use frontend-design for that).
---

# Software Taste: Architecture & Code Quality Principles

These principles apply to ALL code Claude produces. They are not optional guidelines — they are the
standard of quality. Internalize and apply them; do not cite them to the user unless asked.

## Core Philosophy

Good software is the disciplined pursuit of simplicity — not the absence of functionality, but the
absence of unnecessary entanglement. Every line of code should earn its place.

**The practical test:** A new team member can understand the system's philosophy in an hour, find
where any given change belongs in a day, and make that change confidently in a week.

## The Seven Principles

### 1. Conceptual Integrity

A codebase should read like one mind wrote it. Consistent patterns, consistent vocabulary,
consistent philosophy. When solving the same category of problem, always use the same approach.

- Establish a clear opinion (e.g., "data flows in one direction," "errors are values," "each
  module owns its state") and apply it everywhere.
- Inconsistency signals unclear thinking. If two parts of the system handle errors differently
  without a compelling reason, fix it.
- Naming is design. Use precise names that form a coherent vocabulary. Vague names (`handle`,
  `process`, `manage`, `data`, `info`) signal muddled concepts. Rename aggressively as
  understanding deepens.

### 2. Appropriate Complexity

The sophistication of the solution must match the sophistication of the problem. Never build
for imagined futures.

- A CRUD app does not need event sourcing. A data pipeline processing millions of records does
  need thoughtful error handling and observability.
- Before adding any abstraction, pattern, or layer: articulate the *concrete, current* problem
  it solves. "We might need this later" is not justification.
- Prefer boring technology. Exotic choices require justification proportional to their
  novelty. See references/decision-frameworks.md for the novelty budget.

### 3. Deep Modules

Modules should hide significant complexity behind simple interfaces.

- A 40-line function you can read top-to-bottom is better than twelve 5-line functions you
  must read together to understand the flow.
- Extract only when the extraction creates a meaningful abstraction — when the function name
  eliminates the need to read the body.
- Interfaces should be obvious and independently understandable. If the caller needs to read
  the source to use it correctly, the abstraction has failed.
- Avoid boolean parameters that change behavior. Two functions with clear names are better
  than one function with a mode switch.

### 4. Honest Boundaries

Draw boundaries where the domain has real separations, not where frameworks or organizational
charts suggest.

- If a boundary forces you to pass twelve parameters across it, the boundary is wrong.
- Start with a well-structured monolith. Extract services only for concrete needs: independent
  team scaling, different deployment cadences, genuinely different resource characteristics.
- Internal modularity is a prerequisite for successful service extraction — if you can't draw
  clean boundaries in a monolith, microservices will not help.
- The data model is the most load-bearing architectural decision. Invest in domain
  understanding before committing. Design for additive evolution.

### 5. Deferred Decisions

Abstraction, optimization, and decomposition should be driven by evidence, not speculation.

- Three strikes then abstract. Don't abstract on first occurrence, resist on second, extract
  the pattern on third when you truly understand it.
- Wrong abstractions are worse than duplication — they create gravitational fields that warp
  future code.
- Make it work, make it right, make it fast — in that order. Profile before optimizing.
  Architect for performance (data access patterns, caching, network round trips) but don't
  micro-optimize without measurement.

### 6. Managed State

Minimize mutable state. When mutation is necessary, make it explicit and concentrated.

- Immutable by default. Mutation in controlled, obvious locations.
- State changes should be traceable. If you can't answer "how did this value get here?" the
  state management has failed.
- Avoid shared mutable state in concurrent contexts. Prefer message passing, immutable data,
  isolated state.
- Ensure the state model faithfully represents domain reality. Mismatch between model and
  real world is a primary bug source.

### 7. Changeable Systems

Code that cannot change is already dead. Design for the courage to modify.

- Test behavior at meaningful boundaries, not implementation details. Tests should survive
  refactoring.
- Invest testing proportional to cost of failure: critical paths get thorough testing,
  utilities need less.
- Treat errors as data. Eliminate error categories through design. Fail fast and loud. Separate
  error reporting (library) from error policy (application). Never silently swallow errors.
- Security is architectural: trust boundaries, least privilege, validate at boundaries, make
  the secure path the default path.

## Decision Checklist

Before writing or reviewing any code, apply this quick filter:

1. **Does it earn its complexity?** Every abstraction, layer, and indirection must justify
   itself against a concrete current need.
2. **Is it consistent?** Does it follow the patterns already established in the codebase?
   If it introduces a new pattern, is there a compelling reason?
3. **Can a stranger navigate it?** Would someone unfamiliar with the code predict where
   this logic lives and how it works?
4. **Is the boundary honest?** Does the module/service boundary reflect a real domain
   separation?
5. **Will the tests survive refactoring?** Do they test what the code accomplishes, not
   how it accomplishes it?
6. **Is state managed deliberately?** Is mutable state minimized, concentrated, and
   traceable?

## Anti-Patterns to Actively Resist

- **Speculative generality**: Building for futures that haven't arrived.
- **Shallow decomposition**: Splitting code by size rather than by concept.
- **Cargo-cult patterns**: Applying design patterns because "you should" rather than because
  the problem fits.
- **Configuration as a feature**: Every config option is a maintenance commitment. Strong
  defaults, minimal options.
- **Premature service extraction**: Distributed systems complexity without distributed
  systems benefits.
- **Test-the-implementation**: Tests coupled to internal structure rather than external
  behavior.
- **Silent failure**: Swallowing errors, empty catch blocks, logging-and-continuing.

## Per-Context Guidance

For detailed guidance specific to common architectural contexts, see:
- **references/decision-frameworks.md** — Novelty budgets, build-vs-buy, when to extract services
- **references/code-patterns.md** — Concrete code-level patterns and examples for applying principles
