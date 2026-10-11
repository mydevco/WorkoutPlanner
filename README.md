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
run_windows.py           PyInstaller entry point for the Windows executable
forge_fitness.spec       Reproducible Windows packaging configuration
```

## Setup and run

Python 3.12 or 3.13 is recommended on Windows. Python 3.14 can work when
current wheels are available, but the native `python-rtmidi` and PyInstaller
packages may lag a new Python release. If dependency installation fails on
3.14, install Python 3.13 and recreate the virtual environment.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m backend.app
```

For Windows PowerShell, the setup script creates the environment and installs
dependencies:

```powershell
.\setup_windows.ps1
.\.venv\Scripts\Activate.ps1
python -m backend.app
```

### Recovering a failed or locked Windows `.venv`

The `venvlauncher.exe` copy error usually means `.venv` is stale, partially
created, or locked by a running Python process, IDE terminal, test runner, or
editor. Deactivate the environment, stop the app or test process, and close
terminals or IDE windows that use this project before removing it. These
commands remove only the project's `.venv` directory:

```powershell
deactivate
Get-Process -Name python,pythonw -ErrorAction SilentlyContinue
# Close only the listed project processes, terminals, or IDE task.
Remove-Item -LiteralPath .\.venv -Recurse -Force
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `py -3.13` is not installed, replace it with `py -3.12` or `python`.
If `Remove-Item` reports that a file is still in use, close the remaining
Python process or IDE terminal and rerun only that `Remove-Item` command. The
equivalent scripted recovery is:

```powershell
.\setup_windows.ps1 -ResetVenv
```

Open <http://127.0.0.1:5000>. The database is created and seeded on first
start. Set `FORGE_DATABASE` to use a different SQLite file and set
`FLASK_DEBUG=1` only for local development. A production deployment should
use a WSGI server, for example:

```bash
gunicorn "backend.app:create_app()"
```

## Windows native MIDI drum practice

Open <http://127.0.0.1:5000/practice> to use the eight-pad practice page.
The Flask process receives MIDI directly through `mido` and the native
`python-rtmidi` backend; the browser never uses Web MIDI. Refresh the device
list, select an input, and connect or disconnect it from the page. Notes
36–43 map to pads 1–8. Keyboard keys `A S D F J K L ;` and pointer clicks
remain available when no controller is connected. If the native backend or a
device is unavailable, the rest of the app still works and the page reports
the specific status.

Build a Windows `.exe` from a Windows PowerShell terminal:

```powershell
.\setup_windows.ps1
.\build_windows.ps1
.\dist\ForgeFitness.exe
```

The executable starts the local server on `127.0.0.1:5000`; open that URL
after launch. `PORT` can change the port. Windows MIDI drivers and controller
permissions remain host-specific; the executable can still run without a
connected MIDI device.

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
- Programs include duration anchors/focus filtering and a local-first personal
  builder with drag/drop, keyboard reorder controls, localStorage drafts, and
  print-friendly output.
- Exercise catalog derived from seeded workout movements, grouped by body part
  and filterable by allowed equipment, with a print-friendly layout.
- Full-body, leg day, upper body, core, and hybrid focus areas.
- Browser admin at `/admin` plus parameterized JSON CRUD at
  `/api/workouts`.
- Manage Catalog includes a searchable/filterable exercise catalog manager and
  local exercise creation with zero-or-one allowed equipment validation.
- Print-friendly catalog and program views (`Print catalog` / `Print program`
  hide controls and decorative icons).
- Seeded links to practical exercise videos.
- Equipment is restricted to the supported list shown in the admin form.

## Smoke tests

The tests use Python's standard `unittest` runner and Flask's test client:

```bash
python -m unittest discover -s tests -v
```
