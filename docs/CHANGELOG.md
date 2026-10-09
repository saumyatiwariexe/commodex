# Changelog

Newest first. Every change to the idea, scope, or docs gets an entry (see AGENTS.md section 4).

## 2026-10-09: v0.3 Agent rules and skills
**Changed**
- Added `AGENTS.md`: session checklist, non-negotiables, iteration protocol with impact map, skill selection map and precedence rules, verification and honesty rules, code and security conventions, scope control, collaboration style.
- Added this changelog.
- Added a `Skills` line under the title of every doc, naming the skills to use for that area.
- README index now lists `AGENTS.md` and `CHANGELOG.md`.

**Why:** the team is adding the same skills to the IDE, so the agent there needs one place that says what to follow and which skill to reach for.

**Unverified:** skill names were copied from the list available in this session. They may appear differently in your IDE.

## 2026-10-09: v0.2 Web3 removed
**Changed**
- Deleted `WEB3.md` (on-chain signal registry).
- Rewrote `AUTH.md` from wallet sign-in (SIWE) to username and password login with argon2id and JWT. Still P2.
- Removed chain endpoints and env keys from `BACKEND.md`.
- Removed Verify screen, wallet components and wagmi/viem from `FRONTEND.md`.
- `DATABASE.md`: users table now has username and password hash. Added `login_attempts` and `role_audit`. Removed `nonces` and `bt_run.chain_tx_hash`.
- `ARCHITECTURE.md`: removed publisher and registry from the diagram and `contracts/` from the layout.
- `TESTING.md`: removed contract tests and Foundry. Renumbered sections.
- `DEPLOYMENT.md`: removed local chain service, key handling and chain checklist items.
- `DEMO_PLAN.md`: removed the web3 phase, the verification demo step and the "why blockchain" question. The fourth-person role now owns testing and cost-model research.
- `PRD.md`: removed goal G7, the auditor user, and the web3 scope and risk items.

**Why:** Track 03 does not mention blockchain and it competed for time with the core model.

**Decision:** auth stays as a P2 item because job and ingest endpoints need protection if the app is hosted publicly. If it is only run locally, auth can be dropped.

## 2026-10-09: v0.1 Initial doc set
**Added**
- `README.md`, `PRD.md`, `ARCHITECTURE.md`, `DATA_PIPELINE.md`, `DATABASE.md`, `MODEL.md`, `BACKEND.md`, `FRONTEND.md`, `AUTH.md`, `WEB3.md`, `TESTING.md`, `DEPLOYMENT.md`, `DEMO_PLAN.md`.

**Open at this point**
- MCX data access untested. The web fetch was refused by MCX and the sandbox network blocked a direct request, so nothing about the endpoint is verified.
- Team size, skills and available hours unknown.
- Cost rates and contract specs not yet filled from official sources.
