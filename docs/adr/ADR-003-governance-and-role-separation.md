# ADR-003 — AI governance and role separation

Status: Accepted

## Context
The project is expected to evolve across many AI sessions and Coding Agents. Relying on chat memory creates architecture and quality drift.

## Decision
Repository governance SSOT is authoritative. The Main AI / Orchestrator controls roadmap, architecture, task contracts, review, and PASS/BLOCKED decisions. Coding Agents execute scoped tasks only.

## Reason
This allows future AIs to safely take over from repository state rather than hidden conversational memory.

## Consequences
- Governance files must be maintained with project changes.
- Important route/architecture/release decisions require ADR or SSOT updates.
- Coding Agent receipts are evidence inputs, not final PASS authority.

## Forbidden
Treating a Coding Agent's self-declared completion as project PASS without Orchestrator review.
