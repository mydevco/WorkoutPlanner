# Forge Fitness

Forge Fitness is a deploy-ready, responsive workout library built with a small
Flask API and a SQLite database. The frontend is intentionally server-rendered
HTML with vanilla CSS and JavaScript, so it can be deployed without a build
step.

## Project layout

```text
backend/                 Flask application, schema, and seed data
frontend/templates/      Accessible HTML pages
frontend/static/         CSS and browser JavaScript
tests/                   Smoke tests for the API and page routes
```

## Setup and run

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m backend.app
```

Open <http://127.0.0.1:5000>. The database is created and seeded on first
start. Set `FORGE_DATABASE` to use a different SQLite file and set
`FLASK_DEBUG=1` only for local development. A production deployment should
use a WSGI server, for example:

```bash
gunicorn "backend.app:create_app()"
```

## Optional Google and Microsoft OAuth

OAuth is opt-in. With no provider credentials configured, the app stays in
local unauthenticated mode exactly as it does by default. When either provider
is configured, `/admin` and workout write endpoints (`POST`, `PATCH`, `PUT`,
and `DELETE` under `/api/workouts`) require a signed-in user. Public pages,
read-only workout/program APIs, and `/healthz` remain accessible.

Set a strong random `FORGE_SECRET_KEY` and configure either or both providers:

```text
FORGE_SECRET_KEY=replace-with-a-long-random-value
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
FORGE_COOKIE_SECURE=true
```

Each provider's client ID and secret must be supplied together. Register these
callback URLs with the provider:

```text
https://your-domain.example/auth/callback/google
https://your-domain.example/auth/callback/microsoft
```

Use `FORGE_COOKIE_SECURE=true` behind HTTPS. The OAuth integration uses
OpenID Connect discovery through Authlib, stores only basic identity claims in
the server-side signed Flask session cookie, and clears the session on logout.
The admin page is not an account-management system; add an allowlist or
authorization layer before exposing it to multiple users.

## Optional Gemini workout coach

The homepage includes an optional, catalog-grounded workout suggestion
assistant powered only by Google Gemini. It is disabled when `GEMINI_API_KEY`
is absent, and the rest of the site continues to work normally. Configure the
key in the server environment; it is never sent to the browser or hard-coded:

```text
GEMINI_API_KEY=...
```

The backend sends the user's bounded prompt plus the current seeded workout and
program catalog to Gemini. Responses are size-limited, grounded to existing
catalog names, and include a stop-if-pain safety reminder. Network/model
failures return a user-safe error without breaking the catalog or admin CRUD.

## Features

- Homepage, searchable workout catalog, and 30/45/60-minute programs.
- Full-body, leg day, upper body, core, and hybrid focus areas.
- Browser admin at `/admin` plus parameterized JSON CRUD at
  `/api/workouts`.
- Print-friendly catalog and program views (`Print catalog` / `Print program`
  hide controls and decorative icons).
- Seeded links to practical exercise videos.
- Equipment is restricted to the supported list shown in the admin form.

## Smoke tests

The tests use Python's standard `unittest` runner and Flask's test client:

```bash
python -m unittest discover -s tests -v
```
