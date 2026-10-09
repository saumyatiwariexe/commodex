# Changelog

Newest first. Every change to the idea, scope, or docs gets an entry (see AGENTS.md section 4).

## 2026-10-09: v0.5 Project renamed to Commodex
**Changed**
- Renamed project from GoldSpread Intelligence to Commodex.
- Removed all occurrences of "GoldSpread Intelligence" / "goldspread" across `README.md`, `docs/PRD.md`, and `docs/ARCHITECTURE.md`.

**Why:** Project naming standardization as requested.

## 2026-10-09: v0.4 Hashing pinned
**Changed**
- `MODEL.md`: new section 12 (hashing and reproducibility). Defines what `snapshot_hash`, `config_hash` and `code_version` are, the canonical serialization rules (sorted keys, no whitespace, float and null handling, ISO dates, reject NaN and infinity), the `sha256:v1:` format, the snapshot-hash procedure, and what the hashes do not prove.
- `AUTH.md`: new section 2.1 pinning argon2id parameters (64 MiB, 3 iterations, 4 lanes, 16-byte salt, 32-byte hash) with rehash-on-login. JWT secret must be at least 32 random bytes. Added hash-format checks to the auth test list.
- `TESTING.md`: new section 11 with ten hashing and reproducibility tests. Definition of done is now section 12.
- `DATA_PIPELINE.md`: snapshot hash now points to MODEL.md section 12.4 and states that partition files are hashed once and never rewritten.
- `DATABASE.md`: points to the hash format and canonicalization rules.
- `AGENTS.md`: code conventions now require hashing through `model/canonical.py` and argon2id for passwords.

**Why:** the canonical-JSON rule existed only in `WEB3.md`, which was deleted in v0.2. That left `config_hash` and the snapshot hash with no serialization spec, so identical inputs could hash differently and the reproducibility claim would not hold. Argon2id parameters were left to library defaults.

**Decision:** snapshot hash covers file bytes taken at first write, not logical content, because Parquet writes are not guaranteed byte-identical. The trade-off is that re-writing a partition changes the hash, so partitions are immutable by rule.

**Unverified:** the OWASP minimum argon2id numbers are quoted from memory. Check the current OWASP Password Storage Cheat Sheet. The pinned values follow RFC 9106's lower-memory recommendation and should be confirmed against it too.

**Not changed:** PRD, FRONTEND, BACKEND, ARCHITECTURE, DEPLOYMENT, DEMO_PLAN. The `HashBadge` component only displays the stored string.

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