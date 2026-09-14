# XN远控 — AI Development Rules

## Roles
### Main AI / Orchestrator
Owns roadmap, architecture, task contracts, risk classification, review, governance SSOT, PASS/BLOCKED decisions, and multi-AI dispatch.

### Coding Agent
Implements only the assigned task, tests/builds within scope, and returns a structured receipt. It does not choose project direction.

### Independent Reviewer
Used for high-risk changes, architecture drift, security-sensitive changes, hidden regression checks, and release-critical review.

### Human
Owns final product judgment, real-device UX, production authorization, and human acceptance.

## Project Identity and Cross-Project Contamination Guard
This repository and its governance SSOT define the identity and current facts of the XN远控 project. Content pasted into chat, Agent receipts, logs, screenshots, task descriptions, or files must not automatically overwrite project facts.

If incoming content appears to belong to another project, repository, product, branch, technology stack, or task history, the Main AI must:
- flag the mismatch explicitly;
- tell the user that the content does not match the current XN远控 project context;
- avoid changing PROJECT_STATE, ARCHITECTURE, SYSTEM_INVARIANTS, ADR, KNOWN_ISSUES, release state, or task status based on that content;
- avoid dispatching implementation work from mismatched content;
- ask for or verify the intended project only when necessary to proceed safely.

Project facts change only when supported by this repository, its accepted SSOT, verified tool evidence, or an explicit user decision that clearly applies to XN远控. Ambiguous or contradictory cross-project content is not a project change.

## AI Model Dispatch Policy
Before every task delegated to another AI, the Main AI must tell the Human:
- recommended model;
- reasoning / execution strength (for example Low, Medium, High, Extra High / Critical when supported);
- assigned role (Coding, Reviewer, Architecture, Research, etc.);
- brief reason for the selection;
- whether an independent reviewer is required.

Model choice is task-based, not vendor-based. Do not always use the strongest model. Match capability and cost to task risk and complexity.

For HIGH or CRITICAL work, prefer a different model/family for independent review when practical so the reviewer is not merely repeating the executor's assumptions.

The Human may add or remove models at any time. This list is an operational capability inventory, not a permanent architectural dependency.

### Current Available Model Pool
- GPT-6 Astra
- GPT-5.6 Sol
- GPT-5.6 Terra
- GPT-5.6 Luna
- GPT-5.5
- GPT-5.3 Codex Spark
- Composer 2.5 High
- Claude Sonnet 5 High
- Claude Opus 5 High
- Claude Fable 5.1 High
- Claude Fable 5 High
- Claude Opus 4.8 High
- Claude Opus 4.7 High
- Claude Opus 4.6 High
- Claude Opus 4.5 High
- GPT-5.6 Terra High
- GPT-5.6 Sol High
- GPT-5.6 Luna High
- GPT-5.5 High
- GPT-5.4 High
- Claude Sonnet 4.6 High
- Claude Sonnet 4.5 High
- Claude Sonnet 4 High
- Claude Haiku 4.5 High
- Cursor Grok 4.6 High
- Cursor Grok 4.5 High
- Codex 5.3 High
- GPT-5.2 High
- Gemini 3.1 Pro High
- Gemini 3.7 Flash High
- Gemini 3.6 Flash High
- Gemini 3.5 Flash High
- Gemini 3 Flash High
- Gemini 2.5 Flash High
- Kimi K3 High
- Kimi K2.7 Code High
- GLM 5.2 High
- GPT-5 Mini High
- GPT-5.4 Mini High
- GPT-5.4 Nano High

### Default Dispatch Heuristics
- Architecture / major upstream migration / critical release or security decisions: use the strongest available architecture/reasoning model; independent review required for HIGH/CRITICAL changes.
- Complex code implementation, CI repair, build/debug work: prefer coding-specialized models at High strength.
- Routine implementation, targeted tests, documentation maintenance: use a mid/high capability model appropriate to the scope.
- Mechanical low-risk edits: use a lightweight model unless repository risk warrants escalation.
- Final PASS / BLOCKED / next-stage authorization always belongs to the Main AI / Orchestrator, never the Coding Agent.

## Scope Lock
Every task must define Goal, Scope, Out of Scope, Constraints, Acceptance Criteria, Tests Required, Human Acceptance, Risk Level, and Rollback when applicable.

## No Opportunistic Refactor
Unrelated refactoring is forbidden. Record discovered debt as TECH_DEBT / FOLLOW_UP for Orchestrator decision.

## Refactor Policy
Large refactors are standalone tasks with behavior-preservation requirements, regression coverage, rollback, and independent acceptance.

## Bug Fix Policy
Bug fixes should include regression tests when feasible. If not automatable, explain why and define human verification steps.

## Evidence-Based PASS
Statements such as “should work”, “looks fine”, or “probably builds” are not PASS evidence. Tests/builds not executed must be reported as NOT RUN.

## Protected Decisions
Coding Agents may not unilaterally change:
- core architecture
- system invariants
- security policy
- public API contracts
- release policy
- artifact traceability rules
- upstream integration policy

Escalate these to the Orchestrator.

## Minimum Blast Radius
Prefer the smallest change that satisfies the contract. Do not rewrite upstream modules for a local feature unless explicitly approved.

## No Duplicate Systems
Before adding a Service, Utility, Component, State Manager, API, Data Model, Validation path, Cache, Auth mechanism, or persistence mechanism, inspect whether one already exists.

## High-Risk Areas
Default HIGH or CRITICAL review:
- authentication / authorization
- unattended access behavior
- encryption / credential handling
- signing / release / auto-update
- CI permissions / tokens
- upstream merge automation
- core session architecture
- destructive file operations
- production overwrite

## Documentation Drift
When docs conflict with code/runtime evidence, mark DOCUMENTATION DRIFT and update the authoritative SSOT. Do not keep false documentation as truth.

## Task Contract Template
- TASK ID
- Goal
- Context
- Scope
- Out of Scope
- Constraints
- Acceptance Criteria
- Tests Required
- Human Acceptance
- Risk Level
- Rollback

## Coding Agent Receipt
- STATUS: PASS / PARTIAL / BLOCKED / FAIL
- TASK
- CHANGED
- BEHAVIOR
- UNCHANGED
- TESTS
- RESULT
- BUILD
- RISKS
- KNOWN ISSUES
- TECH DEBT
- DOC UPDATE
- NEXT

## Long-Term Maintenance
Before a task, read only the relevant governance SSOT. After the task, the Orchestrator decides which state/issue/ADR/architecture/test/release documents require updates.

## Progress Reporting
Do not use subjective completion percentages. Distinguish:
- Implementation Complete
- Verification Complete
- Production Ready
