# DrivePulseAI API

## Garage lifecycle (Phase 4.3)

Apply `cd backend && .venv/bin/alembic upgrade head` before using the updated
Garage. Migration `0003_garage_lifecycle` changes only the onboarding completion
check: completed accounts may have no vehicles. Existing timestamps, records,
and owner-constrained foreign keys are preserved.

- `PUT /api/v1/vehicles/{id}` replaces validated metadata and returns the complete
  onboarding/vehicle snapshot. ID, owner and creation time cannot be edited.
- `DELETE /api/v1/vehicles/{id}` returns the updated snapshot. It clears a removed
  first-vehicle reference and retains completion. An active vehicle is replaced by
  the oldest remaining vehicle, ordered by creation timestamp then ID; removing the
  last vehicle clears active selection. The app explains this before confirmation.
- Existing `POST /api/v1/vehicles` retains its vehicle response and activates a new
  vehicle only when no active vehicle exists. Optional UUID header `X-Vehicle-ID`
  deduplicates matching creation retries; reusing it for different metadata or an
  already-owned foreign ID returns 409. Mobile retains the ID while the form is open.

All writes serialize on the account's onboarding row and commit references and
vehicle changes atomically. All endpoints require verified Firebase credentials
and the matching `X-Account-UID` precondition. No telemetry associations are created.
The first-vehicle onboarding endpoint cannot restart a completed journey after
its original vehicle has been deleted.

Downgrade to `0002_onboarding_vehicles` is possible only when completed accounts
still have valid first/active references. Otherwise it refuses without changing
data; it never clears completion or invents vehicle references to force rollback.

FastAPI validates Firebase ID tokens and stores minimal user profiles in PostgreSQL.
Firebase remains responsible for passwords, email verification, login, and sessions.

## Implemented flow

1. The Android app signs in with Firebase (email/password or Google) and has a verified email.
2. The account screen obtains a fresh Firebase ID token and sends
   `PUT /api/v1/users/me` with `Authorization: Bearer <ID token>` and no body.
3. The Firebase Admin SDK checks the signature, expiry, audience/project, issuer,
   revoked tokens, and disabled/deleted users. The API requires a verified email.
4. PostgreSQL atomically inserts or updates the profile keyed by Firebase UID.
   Repeat or simultaneous requests cannot create duplicate rows for the same UID.
5. The API returns that user's profile. The account screen confirms synchronization
   or offers a retry. Backend downtime does not delete the Firebase account.

`GET /api/v1/users/me` reads the existing profile (404 before first sync).
Neither endpoint accepts another user's UID as an identity parameter. Profile
values come exclusively from verified token claims. Passwords, password hashes,
refresh tokens, and ID tokens are never stored in this database.

| Column in `users` | Purpose |
| --- | --- |
| `firebase_uid` | Primary key linking to Firebase Auth |
| `email` | Email from the verified token |
| `username` | Firebase display name; nullable and not unique |
| `created_at` | First profile synchronization time |
| `updated_at` | Most recent synchronization time |

Account-owned vehicles and onboarding milestones are persisted as described below.
Telemetry and reports are not persisted. No custom backend sessions
are created. Signing out clears the device's Firebase session; it does not delete
this profile or revoke every previously issued token. Revocation/disabled-user
checks run on each protected request. Deleting a Firebase user does not currently
remove its PostgreSQL row automatically; that requires a future deletion flow.

## Local setup

From the repository root:

```bash
docker compose up -d --wait postgres
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

Skip the copy if `backend/.env` is already configured. The Compose password is for
local development only. PostgreSQL listens only on this computer's loopback
interface and keeps its data in the `drivepulse_postgres` Docker volume.

The existing SQLite setting must be replaced with a PostgreSQL URL; SQLite data
is not imported or deleted by this implementation.

### Transition from the custom authentication prototype

Firebase replaces the `/auth/*` password/Google/session API introduced in PR #28.
The mobile app exchanges Google credentials with Firebase; the server accepts
only Firebase bearer tokens. Custom password hashes and `auth_sessions` are no
longer used. Device logout clears the Firebase session but does not revoke already
issued ID tokens; administrative revocation is a separate operation.

Use a fresh PostgreSQL database/schema for `alembic upgrade head`. The prototype's
`users` table (`id`, `password_hash`, `google_subject`) is incompatible with the
Firebase profile table, and this initial migration does not convert it. Preserve
any existing database. If it contains real accounts, plan an explicit identity/data
migration before rollout; existing passwords and custom sessions do not automatically
become Firebase accounts. No existing database is deleted or migrated by this merge.

### Firebase server credentials

For local development, in Firebase project `drivepulse-d2034`, open **Project
settings → Service accounts → Firebase Admin SDK → Generate new private key**.
Keep the downloaded file outside the app, for example in `backend/.secrets/`
(which is gitignored). This is a private server credential; `google-services.json`
is the Android client configuration and cannot replace it.

Set the absolute path in the shell that runs FastAPI:

```bash
export GOOGLE_APPLICATION_CREDENTIALS='/absolute/path/to/private-service-account.json'
cd backend
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The SDK reads `GOOGLE_APPLICATION_CREDENTIALS` from the process environment, not
from Pydantic's `.env` file. A Google-hosted deployment can instead use Application
Default Credentials from its attached service account. That identity needs Firebase
Auth user-read permission for revocation and disabled-user checks. The configured
Firebase project must match the mobile app. Auth emulator mode is deliberately
rejected by this server.

Without usable credentials, protected requests return 503 rather than bypassing
authentication. `/health` is a process liveness check, not proof of Firebase or DB
connectivity. API docs are at `http://localhost:8000/docs`.

### Mobile connection

Set `EXPO_PUBLIC_API_URL` in `mobile/.env` to the backend URL and restart Metro:

- Physical phone: `http://YOUR_COMPUTER_LAN_IP:8000`, on the same Wi-Fi.
- Android emulator: `http://10.0.2.2:8000`.
- Deployed service: its `https://...` URL.

Then run `npm start` inside `mobile/`. Rebuild the Android development APK after
this merge because Google sign-in adds native modules; later API URL changes only
require restarting Metro.
Native requests do not require CORS; web clients must be listed explicitly in
`CORS_ORIGINS`, a JSON array. Production API traffic must use HTTPS.

The app sends fresh claims so recently changed display names are synchronized.
It retries a 401 once with another fresh token, limits network requests to 15
seconds, and allows manual retry after connection/storage failures.

### Cloud PostgreSQL

Set `DATABASE_URL` in the backend environment to your provider's URL, such as
`postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB?sslmode=require`, following the
provider's TLS/certificate instructions. Percent-encode special characters in URL
credentials. Run `alembic upgrade head` against that database before serving users.
The code supports this connection, but no cloud database or API deployment is
provisioned by the local setup. Never put this URL into the mobile environment.

## Validation

```bash
# From repository root; creates a separate database for destructive test fixtures.
docker compose exec -T postgres createdb -U drivepulse drivepulse_test
cd backend
export TEST_DATABASE_URL='postgresql+psycopg2://drivepulse:drivepulse_dev@127.0.0.1:5432/drivepulse_test'
.venv/bin/pytest -q
.venv/bin/ruff check app migrations tests
.venv/bin/ruff format --check app migrations tests
```

The test database name must end in `_test`. Tests migrate it and clear its
`user_onboarding`, `vehicles`, and `users` tables between cases. PostgreSQL tests skip when `TEST_DATABASE_URL` is
absent; CI starts PostgreSQL and runs them. Remote Firebase verification is mocked
in API tests, so they do not establish live project credentials or phone connectivity.
Do not use a real user database as the test database.

## File map

- `app/config.py`: server settings and PostgreSQL-only URL validation.
- `app/core/firebase.py`: Firebase Admin initialization and token verification.
- `app/api/deps.py`: verified identity and request-scoped SQLAlchemy sessions.
- `app/api/routes/users.py`: current-user profile read/upsert endpoints.
- `app/models/user.py`, `app/schemas/user.py`: database and public response models.
- `migrations/`: versioned Alembic schema changes.
- `tests/test_auth.py`: authentication rejection and configuration error tests.
- `tests/test_user_profiles.py`: real PostgreSQL isolation and concurrency tests.

[Firebase token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens)

## Persistent onboarding and Garage (Phase 3.4)

Apply `alembic upgrade head` from `backend/` before serving the updated mobile app.
Migration `0002_onboarding_vehicles` adds `user_onboarding` and `vehicles`; it does
not alter or delete existing `users` rows. Only the dedicated test database was
migrated during implementation. Downgrading this revision removes the two new
tables and their data; use normal deployment backup and migration procedures.

All new endpoints require a verified Firebase bearer token plus `X-Account-UID`
matching the authenticated UID. The header is an account-switch precondition,
never an alternative identity source. A mismatch fails before a database operation.
Existing `/users/me` contracts remain unchanged.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/onboarding` | Load/create account milestones and return owned vehicles |
| `PUT /api/v1/onboarding/profile` | Save `{full_name, driving_licence}` and confirm the profile step |
| `PUT /api/v1/onboarding/first-vehicle` | Atomically save/activate the first vehicle and complete onboarding |
| `GET /api/v1/vehicles` | List only the authenticated account's vehicles |
| `POST /api/v1/vehicles` | Add another owned vehicle after onboarding; keep active selection |
| `GET /api/v1/vehicles/{id}` | Read owned metadata; unknown/foreign IDs return 404 |
| `PUT /api/v1/vehicles/{id}/active` | Persist an owned active vehicle and return refreshed state |

Vehicle bodies contain `powertrain`, `manufacturer`, `model`, integer `year`,
`fuel_type`, and nullable `nickname`. Backend validation mirrors the setup form:
ICE petrol/diesel/CNG; hybrid petrol-electric/diesel-electric; EV null fuel;
nonblank bounded names; year 1886 through next year. Extra fields, including
client-supplied owner IDs and photo data, are rejected.

The onboarding name is separate from Firebase-synchronized `users.username`.
An omitted name falls back to the verified Firebase name, then email prefix.
Skipping optional profile fields confirms the profile step and records
`prefer-not-to-say` for an omitted licence answer. Every licence choice permits access.

First-vehicle requests lock the account's onboarding row. A matching retry returns
the existing first vehicle; a different retry payload returns 409. Creation,
activation, and completion share one transaction. Composite foreign keys prevent
first/active pointers referencing another owner. A lost-response retry never
resets a later active selection. Clients can reload state after ambiguous failures.
Additional-vehicle POST is separate from the singleton idempotent onboarding API.

No avatar binary, local URI, image URL, or cloud storage is persisted. Photos remain
explicitly temporary previews; initials are the fallback. No telemetry is generated
for owned vehicles and no recorded datasets are attached to them.

Existing accounts have no prior durable completion marker and complete this journey
once. Completed accounts enter Home directly on later logins. The mobile app needs
a reachable backend to restore state on entering the signed-in area. Failure offers
Retry/Logout instead of assuming completion. Account rows and vehicles survive
restarts/logout; client state is discarded on logout or UID change.
