# AGENTS.md

Rules for any AI agent (Claude, Cursor, Copilot, Windsurf, etc.) working in this repository. Read this file first, every session.

Project: **Commodex**, Hack in Hills '26, Track 03 (Commodity Derivatives Intelligence).
If your IDE expects a different filename, copy this file to `CLAUDE.md`, `.cursorrules`, or `.agent/rules.md`. Keep one source and copy it, never maintain two diverging versions.

---

## 1. Session start checklist
1. Read this file, `README.md`, `PRD.md`, and the doc for the area you are about to touch.
2. Read the latest entries in `CHANGELOG.md`.
3. Check the open blockers in `README.md` ("Open items that block the build"). Do not assume they are resolved.
4. State in one sentence what you are about to do before you do it.

## 2. Source of truth
The docs are the spec. Code follows docs. If code and docs disagree, stop and fix the disagreement (section 4) rather than silently picking one.

| Doc | Owns |
|-----|------|
| PRD.md | Goals, scope tiers (P0/P1/P2), requirements, risks |
| ARCHITECTURE.md | Components, data flow, repo layout, design principles |
| DATA_PIPELINE.md | Ingestion adapters, parsing, validation, storage layout |
| DATABASE.md | DuckDB and SQLite schemas, integrity rules |
| MODEL.md | Normalization, pairing, signals, costs, backtest, attribution |
| BACKEND.md | API endpoints, jobs, config |
| FRONTEND.md | Screens, components, demo mode |
| AUTH.md | Login, roles, threats (P2) |
| TESTING.md | Test strategy, look-ahead tests, CI |
| DEPLOYMENT.md | Docker, demo safety, release checklist |
| DEMO_PLAN.md | Build order, team split, demo script, cut rules |
| CHANGELOG.md | History of changes to the idea and the docs |

## 3. Non-negotiables
Never violate these. If a request, a skill, or a library suggestion would, stop and say so.
1. **No continuous near-month series.** Contracts are identified by (symbol, expiry_date).
2. **No look-ahead.** A decision at date t uses only data dated <= t. Fills happen at t+1 settlement or later.
3. **Validate the returned date** against the requested date for every Bhavcopy response. Mismatch means discard.
4. **Parse dates explicitly.** Request is DD/MM/YYYY, response Date is MM/DD/YYYY, ExpiryDate is like `04SEP2026`. Never use format inference.
5. **Costs always applied.** Report results net of costs, using the prices of the contracts actually held. Settlement price is not an executable fill.
6. **Separate strategy from gold.** Always report beta, alpha and beta-neutral PnL next to headline results.
7. **Raw data is immutable.** Cleaning creates new tables, never edits `bhav_raw`.
8. **Hold-out is touched once.** Never tune on it. Report it a single time.
9. **A null result is acceptable.** Never tune, cherry-pick, or relax costs to manufacture an edge.
10. **Respect the data source.** If MCX blocks scripted access, do not circumvent robots rules, rotate identities, or drive a browser to evade limits. Switch to the LocalFiles adapter (manually downloaded files).

## 4. Iteration protocol: when the idea changes
Triggers: the human changes goals, scope, stack, or a model rule; adds or drops a feature; or you find a contradiction between docs.

1. **Restate** the change in one sentence and classify it using the impact map below.
2. **Update PRD.md first** (goals, scope tier, risks). The PRD leads, the other docs follow.
3. **Walk the impact map** and update every affected doc in the same change.
4. **Search for stale references** to the old idea (grep for its terms) and remove or fix them. Renumber sections if you removed one and other docs cite it by number.
5. **Update the README index** and the `Skills` line under each affected doc title if docs were added, removed, or changed in purpose.
6. **Add a CHANGELOG entry**: what changed, why, which docs were touched, and anything that is now unverified.
7. **Tell the human** in a short summary. Flag decisions you could not make yourself.
8. If the change reverses an earlier decision, add a line `Decision:` in the changelog with the reason. Use the `engineering:architecture` skill for a full ADR only when the tradeoff is non-trivial.

### Impact map
| Change | Update at least |
|--------|-----------------|
| Goal, scope tier, new or dropped feature | PRD, DEMO_PLAN, then the doc for the feature |
| Data source or field change | DATA_PIPELINE, DATABASE, TESTING |
| Model rule (pairing, signal, costs, backtest, attribution) | MODEL, TESTING, FRONTEND (honesty panel, report screens), PRD |
| New endpoint or schema change | BACKEND, DATABASE, TESTING, FRONTEND if displayed |
| New screen or component | FRONTEND, DEMO_PLAN, TESTING (e2e) |
| Auth or roles | AUTH, BACKEND, DATABASE, TESTING |
| Infra, CI, deployment | DEPLOYMENT, ARCHITECTURE, TESTING |
| Any doc added or removed | README index, AGENTS.md table, CHANGELOG |

## 5. Skills: when to use which
Skills tell you **how** to do something well. The docs and non-negotiables decide **what** to do. If a skill conflicts with the docs, the docs win.

Names below are as they appear in the skill list that was available when this file was written. Your IDE may show them with different prefixes. Match by description if a name is missing. If nothing matches, proceed with the docs alone and say so.

### 5.1 Skill map
| Task | Primary skill | Also consider |
|------|---------------|---------------|
| Write or update any doc in this repo | `engineering:documentation` | |
| Architecture tradeoff, ADR | `engineering:architecture` | `engineering:system-design` |
| Profile a new Bhavcopy file, check nulls, duplicates, gaps | `data:explore-data` | `data:validate-data` |
| Check a number or analysis before showing it | `data:validate-data` | |
| z-scores, regression, beta/alpha, outliers, significance, multiple testing | `data:statistical-analysis` | `data:analyze` |
| Answer a question about backtest results | `data:analyze` | |
| SQL for DuckDB or SQLite | `data:sql-queries` | `data:write-query` |
| Slow queries or index design | `anthropic-skills:database-optimizer` | Targets PostgreSQL/MySQL; apply to DuckDB/SQLite only where the idea transfers |
| FastAPI endpoints, pydantic models, async patterns | `anthropic-skills:fastapi-expert` | |
| API contracts, pagination, error shapes, versioning | `anthropic-skills:api-designer` | |
| Login, password hashing, JWT, input validation, CORS | `anthropic-skills:secure-code-guardian` | |
| Security audit of code, dependencies, secrets | `anthropic-skills:security-reviewer` | |
| Any chart (spread, curve, equity, waterfall) | `dataviz` | `data:create-viz`, `data:data-visualization` |
| Dashboard layout and interaction | `anthropic-skills:ui-ux-pro-max` | `frontend-design` |
| Accessibility check | `design:accessibility-review` | |
| Microcopy: empty states, errors, labels | `design:ux-copy` | |
| Critique a screen before the demo | `design:design-critique` | |
| Explore visual variants or slides on a canvas | `superdesign:superdesign` | Optional, never required for P0 |
| Quick self-contained HTML dashboard prototype | `data:build-dashboard` | |
| Test plan and test architecture | `engineering:testing-strategy` | |
| Review a change before merging | `engineering:code-review` | `anthropic-skills:security-reviewer` for sensitive code |
| Bug or unexpected behavior | `engineering:debug` | |
| Dockerfile, compose, CI pipeline | `anthropic-skills:devops-engineer` | |
| Pre-demo release check | `engineering:deploy-checklist` | |
| Daily status for the team | `engineering:standup` | |
| .pptx deck for the pitch | `anthropic-skills:pptx` | `superdesign:superdesign` for visual exploration |
| Create or revise a skill, or revise this file's skill map | `anthropic-skills:skill-creator` | |

### 5.2 Rules for using skills
1. Use a skill only when the task matches. Load at most three at once. More just burns context and adds contradictory advice.
2. Read the skill fully before acting on it.
3. **UI precedence** when design skills overlap: `dataviz` decides chart encoding and color. `ui-ux-pro-max` decides layout and interaction. `frontend-design` decides aesthetic direction. `superdesign` is exploratory only. The FRONTEND.md principles (quiet by default, show the work, honesty panel, no continuous series) override all of them.
4. **Stats precedence:** `data:statistical-analysis` guides method choice. MODEL.md fixes the protocol (walk-forward, hold-out, costs). A skill may suggest a test, but it may not change the protocol.
5. **Security precedence:** if `secure-code-guardian` or `security-reviewer` raises a finding, fix it or record why not in the changelog. Do not ignore it.
6. Do not use browser or desktop-control skills to fetch MCX data when scripted access is blocked (non-negotiable 10).
7. When you add a doc or change its purpose, update its `Skills` line.

## 6. Verification and honesty
- Never say something works unless you ran it. Say "not run" when you did not.
- Tag uncertain claims: **[Certain]** (verified by running or by a cited source), **[Likely]**, **[Guessing]**. Mark guesses as guesses in docs too.
- Never invent the MCX endpoint, request format, cost rates, tax rates or contract specs. Leave config placeholders and flag them to the human.
- Report negative results plainly. "No edge survives costs" is a valid finding.
- If you cannot run something (network blocked, missing tool), say what you could not verify and what the human should run.
- Before calling a task done: tests for the change pass, look-ahead tests still pass if the model or data layer changed, docs updated, changelog entry written.

## 7. Code conventions
- Python 3.11+, type hints everywhere, `ruff` and `mypy` clean, `pytest` for tests.
- `model/` holds pure functions with no network or filesystem access. Inject data, return data.
- Config in YAML (`contracts_meta.yaml`, `costs.yaml`), never hard-coded in functions.
- Deterministic runs: fixed seeds, record snapshot hash, config hash, code version with every backtest.
- Hash run inputs only through `model/canonical.py` (MODEL.md section 12). Never call `json.dumps` and `hashlib` directly for this. Passwords use argon2id with the parameters pinned in AUTH.md section 2.1, never a fast hash.
- No network calls in tests. Use fixtures and sample data under `data/samples/`.
- Structured logging. No `print` in library code.
- Small commits, one concern each. Commit messages say what and why.

## 8. Security rules
- No secrets in the repo. Provide `.env.example` with placeholders only.
- Parameterized queries only. No string-built SQL.
- Never log passwords, tokens, or password hashes.
- Dependencies pinned. Run `pip-audit` and `npm audit` in CI.
- Write endpoints require a role (AUTH.md). Public endpoints are read-only.

## 9. Scope control
- P0 first. Do not start P1 or P2 work while a P0 item is broken or untested.
- Cut order when behind schedule: term structure decomposition, then auth, then UI polish. Never cut: date validation, expiry pairing, costs, look-ahead tests, hold-out, attribution, honesty panel.
- Do not add features, dependencies, or services that are not in PRD.md. Propose them first through the iteration protocol.

## 10. Ask the human before you
- Fill in cost or tax rates, or contract specs.
- Choose or change the MCX request details.
- Change a non-negotiable, a scope tier, or the stack.
- Delete files or rewrite more than one doc without a changelog entry.
- Spend effort on anything outside P0 when team size and hours are still unknown.

## 11. Collaboration style
- Lead with the most important risk, disagreement, or missing information. No warm-up, no filler praise.
- Disagree with structure: what you disagree with and why, what you would do instead, and the specific risk of the human's approach.
- Do not change your position under pushback unless the human provides new information.
- Be brief in status messages. Put detail in the docs and the changelog.