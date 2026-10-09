# Auth

> **Skills:** `anthropic-skills:secure-code-guardian` (hashing, JWT, input validation), `anthropic-skills:security-reviewer` (audit before any public hosting), `anthropic-skills:fastapi-expert` (auth dependencies).

**Priority: P2.** The product is a read-only analytics dashboard. Auth exists only to protect job-starting and ingest endpoints. Do not let it delay P0. If time is short, ship with those endpoints disabled in the public deployment and run them locally.

## 1. Model
| Role | Capabilities |
|------|--------------|
| anonymous | Read public data, runs, signals, alerts |
| viewer | Everything anonymous can do, plus saved alert subscriptions |
| analyst | Start backtests, change configs |
| admin | Trigger ingest, manage users |

Roles are stored in SQLite (`users` table, DATABASE.md). The first admin is created from the command line, not through the API:
```
python -m api.create_user --username admin --role admin
```
The password is prompted interactively and never passed as an argument or stored in an env file.

## 2. Login flow
1. `POST /auth/login` with `{username, password}`.
2. Server looks up the user, verifies the password against an **argon2id** hash (argon2-cffi defaults are acceptable for a hackathon). Use a constant-time compare and return the same generic error for unknown user and wrong password.
3. On success, issue a JWT: HS256, 1 hour expiry, claims `sub` (user id), `role`, `iat`, `exp`. Prefer an httpOnly, SameSite=Strict cookie. If a bearer header is used instead, keep the token in memory, not localStorage.
4. `GET /auth/me` returns the current user and role.
5. Log every attempt (username, time, success) in `login_attempts`.

## 3. Authorization
- FastAPI dependency `require_role("analyst")` on write endpoints.
- Role checks live server-side only. The UI hides buttons for convenience, never for security.
- Role changes only through an admin endpoint that writes an audit log row.

## 4. Threats and controls
| Threat | Control |
|--------|---------|
| Credential stuffing / brute force | Rate limit per IP and per username, short lockout after repeated failures, using `login_attempts` |
| Weak passwords | Minimum length 12, reject the most common passwords, no composition rules |
| Password database leak | argon2id hashes only, no plaintext, no reversible encryption |
| Stolen JWT | Short expiry, httpOnly cookie, secret loaded from environment, rotate on suspected leak |
| CSRF (cookie auth) | SameSite=Strict plus a CSRF token on state-changing requests |
| Role escalation | Server-side checks only, audited role changes |
| Username enumeration | Identical error message and similar response time for unknown user and wrong password |

## 5. What this does not do
- No email, password reset, or social login. A lost password means an admin resets it from the command line.
- No multi-factor authentication. State this plainly if asked.
- No identity verification. Accounts are whatever the admin creates.
- If the audience never logs in, anonymous read access already covers the entire demo.

## 6. Test checklist
Wrong password rejected, unknown user rejected with the same message, lockout after repeated failures, expired JWT rejected, tampered JWT rejected, role gating on every protected route (anonymous, viewer, analyst, admin), password hashes never appear in any API response or log, role change writes an audit row.
