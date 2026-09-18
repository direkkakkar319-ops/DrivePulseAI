# Authentication API

Run from `backend/` with Python 3.11+:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m app.init_db
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

SQLite is the local default. Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL
before initializing a PostgreSQL database. `app.init_db` creates initial tables;
it does not migrate existing schemas. API documentation is at `/docs`.

| Endpoint | Request | Result |
| --- | --- | --- |
| POST /auth/register | email, password (12–128 characters) | New account and session |
| POST /auth/login | email, password | Session |
| POST /auth/google | id_token | Verified Google account and session |
| GET /auth/me | Authorization: Bearer token | Current user |
| POST /auth/logout | Authorization: Bearer token | Revoke current session (204) |

Session responses contain `access_token`, `token_type`, `expires_at` (Unix seconds),
and `user` (`id`, `email`). Sessions expire after `SESSION_HOURS` (24 by default).
Only SHA-256 token digests are stored in the database; passwords use Argon2.
Logout revokes the current session. Other devices retain their own sessions.

Set `GOOGLE_WEB_CLIENT_ID` to the same Web OAuth client ID used by the mobile app.
Google's library verifies signature, audience, issuer, and expiry; the API also
requires a verified email and stable Google subject. Missing configuration
returns 503. Password and Google identities are not automatically linked by
email; an existing password account must continue using password login.

Password signup does not verify email ownership. Email verification, password
reset, account linking, and session refresh are outside this initial setup.
Before public deployment, configure HTTPS and shared rate limiting on the
registration/login endpoints. There is no deployment rate limiter in this scaffold.
Vehicle and telemetry routes are still placeholders; use `CurrentUser` from
`app.api.deps` when implementing protected data endpoints and enforce ownership.

Validation:

```bash
python -m pytest -q
ruff check app tests
```

`tests/test_auth.py` tests real password hashing, persistence, session revocation,
expiry, and Google handling with a mocked Google verifier. Live Google sign-in
requires the configured Android app and Google Cloud project.

New auth files: `models/user.py` stores identities/sessions; `schemas/auth.py`
defines contracts; `services/auth_service.py` hashes/verifies/issues credentials;
`api/routes/auth.py` implements routes; `init_db.py` bootstraps tables.
