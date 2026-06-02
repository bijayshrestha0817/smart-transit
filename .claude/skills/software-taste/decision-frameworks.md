# Decision Frameworks

## The Novelty Budget

Every project gets a limited budget for novel technology choices. Spend it deliberately.

- **0-1 novel choices**: Standard CRUD apps, internal tools, MVPs
- **1-2 novel choices**: Products with specific technical requirements (e.g., real-time needs justify a novel messaging system)
- **3+ novel choices**: Only when the domain demands it AND the team has deep expertise in all choices

Novel means: new to the team, new to the organization, or immature in the ecosystem. A mature
technology the team hasn't used is still novel *for that team*.

**Default stack**: Choose the most boring technology that meets requirements. Boring means:
well-documented, widely deployed, easy to hire for, predictable failure modes.

## Build vs. Buy vs. Adopt

| Question | Build | Buy/Adopt |
|---|---|---|
| Is this your core differentiator? | Yes → Build | No → Buy |
| Does an off-the-shelf solution fit 80%+? | No → Build | Yes → Adopt |
| Can you maintain it for 5 years? | Yes → Build | No → Adopt |
| Is the integration cost < build cost? | N/A | Yes → Adopt |

**The 80% trap**: If an off-the-shelf solution fits 80% but the missing 20% is your core value
proposition, that's a build. If the missing 20% is nice-to-have, that's an adopt with workarounds.

## When to Extract a Service

Extract a service from a monolith ONLY when at least two of these are true:

1. **Independent deployment cadence**: This component needs to ship on a different schedule than the rest.
2. **Independent scaling**: This component has fundamentally different resource characteristics (CPU-bound vs. I/O-bound, bursty vs. steady).
3. **Team independence**: A separate team owns this component and the coordination cost of shared deployment exceeds the complexity cost of distribution.
4. **Technology mismatch**: The component genuinely requires a different runtime, language, or storage engine, and the benefit outweighs the operational cost.

If only one is true, improve the monolith's internal boundaries instead.

**Prerequisites before extracting:**
- Clean interface between the component and the rest of the system (if this doesn't exist in the monolith, extraction will fail)
- Operational maturity: monitoring, alerting, deployment automation, runbooks
- Clear data ownership: which service owns which data, how does the other access it

## When to Introduce an Abstraction Layer

Introduce an abstraction layer when:
- You have 3+ concrete implementations of the same pattern (the "three strikes" rule)
- The abstraction maps to a concept the domain expert would recognize
- The abstraction eliminates an error category (not just reduces code)
- Removing the abstraction would require changing 3+ callsites

Do NOT introduce an abstraction when:
- You have only 1-2 implementations ("we might need this")
- The abstraction name is a technical term rather than a domain term (`AbstractFactoryProvider`)
- The abstraction adds a layer without hiding complexity (pass-through methods)
- You're wrapping a stable dependency "just in case" you swap it out

## Database Schema Evolution Rules

1. **Additive changes are always safe**: New tables, new nullable columns, new indexes
2. **Restrictive changes require migration plans**: Removing columns, adding NOT NULL, changing types
3. **Structural changes require careful orchestration**: Splitting/merging tables, changing primary keys, modifying relationships

**Migration strategy**:
- Expand → Migrate → Contract (never do breaking changes in one step)
- New code reads from both old and new locations during transition
- Backfill data before switching reads
- Remove old columns/tables only after all code uses new locations

## Legacy System Modernization

1. **Characterize first**: Write tests that document current behavior before changing anything
2. **Strangler fig**: Build new around old, gradually redirect
3. **Never rewrite from scratch** unless the system is truly unsalvageable AND you have complete requirements documentation AND you have budget for 2x your estimate
4. **Identify the real legacy**: Often the architecture and data model, not the code. If the data model is the problem, new code on old data will inherit old problems.
