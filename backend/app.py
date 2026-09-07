"""Flask application and JSON API for Forge Fitness."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DEFAULT_DATABASE = BASE_DIR / "backend" / "workouts.db"

ALLOWED_EQUIPMENT = (
    "dumbbells",
    "kettlebells",
    "resistance bands",
    "bodyweight",
    "treadmill",
    "elliptical",
    "roman chair",
    "pull-up bar",
    "barbells",
    "rucking gear",
    "ab roller",
    "step",
    "jump box",
    "benches",
    "metal clubs",
    "macebells",
    "workout station",
    "wind bike",
    "yoga mat",
)
CATEGORIES = ("full-body", "leg day", "upper body", "core", "hybrid")
DURATIONS = (30, 45, 60)
GEMINI_MAX_MESSAGE_LENGTH = 500
GEMINI_MAX_RESPONSE_LENGTH = 2000
GEMINI_MODEL = "gemini-2.0-flash"

SEED_PROGRAMS = [
    (
        "30-minute",
        "30-minute charge",
        30,
        "hybrid",
        "A focused circuit for days when you want a complete session without the long warm-up.",
        "#e3ff61",
    ),
    (
        "45-minute",
        "45-minute build",
        45,
        "full-body",
        "The balanced middle ground: strength, conditioning, and enough time to move well.",
        "#9ee7ff",
    ),
    (
        "60-minute",
        "60-minute forge",
        60,
        "hybrid",
        "A complete training block with room for progressive strength work and a strong finish.",
        "#ffb38a",
    ),
]

SEED_WORKOUTS = [
    {
        "title": "Dumbbell Engine",
        "category": "full-body",
        "duration": 30,
        "equipment": ["dumbbells", "benches"],
        "description": "A dense, low-fuss circuit that trains every major movement pattern.",
        "program": "30-minute",
        "video_url": "https://www.youtube.com/watch?v=U0bhE67HuDY",
        "exercises": [
            {"name": "Goblet squat", "sets": 3, "reps": "10", "rest": "30 sec"},
            {"name": "Dumbbell bench press", "sets": 3, "reps": "10", "rest": "30 sec"},
            {"name": "One-arm row", "sets": 3, "reps": "10/side", "rest": "30 sec"},
            {"name": "Dumbbell Romanian deadlift", "sets": 3, "reps": "12", "rest": "45 sec"},
        ],
    },
    {
        "title": "Kettlebell Legs",
        "category": "leg day",
        "duration": 45,
        "equipment": ["kettlebells", "bodyweight"],
        "description": "Build resilient legs with a squat, hinge, and single-leg emphasis.",
        "program": "45-minute",
        "video_url": "https://www.youtube.com/watch?v=YSxR4Jq8fYQ",
        "exercises": [
            {"name": "Kettlebell goblet squat", "sets": 4, "reps": "8", "rest": "60 sec"},
            {"name": "Kettlebell swing", "sets": 4, "reps": "15", "rest": "45 sec"},
            {"name": "Reverse lunge", "sets": 3, "reps": "10/side", "rest": "45 sec"},
            {"name": "Single-leg calf raise", "sets": 3, "reps": "15/side", "rest": "30 sec"},
        ],
    },
    {
        "title": "Pull + Press",
        "category": "upper body",
        "duration": 45,
        "equipment": ["barbells", "pull-up bar", "benches"],
        "description": "A classic upper-body session pairing confident presses with strong pulls.",
        "program": "45-minute",
        "video_url": "https://www.youtube.com/watch?v=IODxDxX7oi4",
        "exercises": [
            {"name": "Barbell bench press", "sets": 4, "reps": "6", "rest": "90 sec"},
            {"name": "Pull-up", "sets": 4, "reps": "AMRAP", "rest": "75 sec"},
            {"name": "Barbell overhead press", "sets": 3, "reps": "8", "rest": "60 sec"},
            {"name": "Inverted row", "sets": 3, "reps": "10", "rest": "60 sec"},
        ],
    },
    {
        "title": "Core Control",
        "category": "core",
        "duration": 30,
        "equipment": ["ab roller", "bodyweight", "yoga mat"],
        "description": "Anti-extension and anti-rotation work to make every other lift feel better.",
        "program": "30-minute",
        "video_url": "https://www.youtube.com/watch?v=DN4jV5P5pNw",
        "exercises": [
            {"name": "Dead bug", "sets": 3, "reps": "10/side", "rest": "30 sec"},
            {"name": "Ab-wheel rollout", "sets": 4, "reps": "8", "rest": "60 sec"},
            {"name": "Side plank", "sets": 3, "reps": "30 sec/side", "rest": "30 sec"},
            {"name": "Bear crawl", "sets": 3, "reps": "30 sec", "rest": "45 sec"},
        ],
    },
    {
        "title": "Barbell Foundation",
        "category": "full-body",
        "duration": 60,
        "equipment": ["barbells", "workout station", "benches"],
        "description": "A deliberate full-body strength day built around steady, repeatable sets.",
        "program": "60-minute",
        "video_url": "https://www.youtube.com/watch?v=op9kVnSso6Q",
        "exercises": [
            {"name": "Back squat", "sets": 5, "reps": "5", "rest": "120 sec"},
            {"name": "Barbell deadlift", "sets": 4, "reps": "5", "rest": "120 sec"},
            {"name": "Barbell row", "sets": 4, "reps": "8", "rest": "90 sec"},
            {"name": "Bench press", "sets": 4, "reps": "8", "rest": "90 sec"},
        ],
    },
    {
        "title": "Trail Hybrid",
        "category": "hybrid",
        "duration": 60,
        "equipment": ["rucking gear", "wind bike", "step"],
        "description": "Strength endurance and loaded conditioning for a session that travels well outdoors.",
        "program": "60-minute",
        "video_url": "https://www.youtube.com/watch?v=7V2VqN1Q2uA",
        "exercises": [
            {"name": "Loaded step-up", "sets": 4, "reps": "10/side", "rest": "60 sec"},
            {"name": "Wind bike sprint", "sets": 8, "reps": "30 sec", "rest": "60 sec"},
            {"name": "Ruck walk", "sets": 1, "reps": "20 min", "rest": "—"},
            {"name": "Bodyweight squat", "sets": 3, "reps": "20", "rest": "45 sec"},
        ],
    },
]


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
    )
    app.config.from_mapping(
        DATABASE=os.environ.get("FORGE_DATABASE", str(DEFAULT_DATABASE)),
        JSON_SORT_KEYS=False,
        SECRET_KEY=os.environ.get("FORGE_SECRET_KEY", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FORGE_COOKIE_SECURE", "").lower() == "true",
        GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID", ""),
        GOOGLE_CLIENT_SECRET=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        MICROSOFT_CLIENT_ID=os.environ.get("MICROSOFT_CLIENT_ID", ""),
        MICROSOFT_CLIENT_SECRET=os.environ.get("MICROSOFT_CLIENT_SECRET", ""),
        GEMINI_API_KEY=os.environ.get("GEMINI_API_KEY", ""),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"] and not oauth_providers_from_config(app.config):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    validate_oauth_config(app.config)
    oauth = OAuth(app)
    register_oauth_providers(app, oauth)

    @app.context_processor
    def auth_context():
        return {
            "current_user": session.get("user"),
            "oauth_providers": oauth_providers(app),
        }

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    @app.teardown_appcontext
    def close_database(_exception=None):
        database = g.pop("database", None)
        if database is not None:
            database.close()

    @app.cli.command("init-db")
    def init_db_command():
        initialize_database(app)
        print("Initialized Forge Fitness database.")

    with app.app_context():
        initialize_database(app)

    @app.get("/")
    def home():
        return render_template("index.html", page="home")

    @app.get("/catalog")
    def catalog():
        return render_template("catalog.html", page="catalog")

    @app.get("/programs")
    def programs():
        return render_template("programs.html", page="programs")

    @app.get("/admin")
    @admin_required
    def admin():
        return render_template("admin.html", page="admin")

    @app.get("/login")
    def login():
        return render_template("login.html", page="login", providers=oauth_providers(app))

    @app.get("/login/<provider>")
    def login_provider(provider):
        client = oauth.create_client(provider)
        if client is None:
            return api_error("That sign-in provider is not configured.", 404)
        redirect_uri = url_for("auth_callback", provider=provider, _external=True)
        return client.authorize_redirect(redirect_uri)

    @app.get("/auth/callback/<provider>")
    def auth_callback(provider):
        client = oauth.create_client(provider)
        if client is None:
            return api_error("That sign-in provider is not configured.", 404)
        token = client.authorize_access_token()
        userinfo = token.get("userinfo")
        if userinfo is None:
            userinfo = client.userinfo()
        session.clear()
        session["user"] = {
            "sub": userinfo.get("sub") or userinfo.get("id"),
            "name": userinfo.get("name") or userinfo.get("preferred_username") or userinfo.get("email"),
            "email": userinfo.get("email") or userinfo.get("preferred_username"),
            "provider": provider,
        }
        session.permanent = True
        return redirect(url_for("admin"))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/api/equipment")
    def equipment():
        return jsonify(list(ALLOWED_EQUIPMENT))

    @app.get("/api/chat/status")
    def chat_status():
        return jsonify({"configured": bool(app.config.get("GEMINI_API_KEY"))})

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True)
        message = payload.get("message", "").strip() if isinstance(payload, dict) else ""
        if not message:
            return jsonify({"error": "Tell me what you want from today's workout."}), 400
        if len(message) > GEMINI_MAX_MESSAGE_LENGTH:
            return jsonify({"error": f"Message must be {GEMINI_MAX_MESSAGE_LENGTH} characters or fewer."}), 400
        if not app.config.get("GEMINI_API_KEY"):
            return jsonify({
                "error": "The workout coach is not configured yet. Set GEMINI_API_KEY to enable suggestions."
            }), 503
        try:
            answer = generate_gemini_response(
                app.config["GEMINI_API_KEY"],
                message,
                get_workout_catalog(),
            )
        except GeminiError as error:
            return jsonify({"error": str(error)}), 502
        if not answer:
            return jsonify({"error": "The workout coach returned an empty suggestion."}), 502
        return jsonify({"answer": answer[:GEMINI_MAX_RESPONSE_LENGTH]})

    @app.get("/api/workouts")
    def list_workouts():
        database = get_db()
        clauses = []
        values: list[object] = []
        if request.args.get("category") in CATEGORIES:
            clauses.append("category = ?")
            values.append(request.args["category"])
        if request.args.get("duration", "").isdigit():
            duration = int(request.args["duration"])
            if duration in DURATIONS:
                clauses.append("duration = ?")
                values.append(duration)
        if request.args.get("program"):
            clauses.append("program = ?")
            values.append(request.args["program"])
        if request.args.get("q"):
            clauses.append("(title LIKE ? OR description LIKE ?)")
            term = f"%{request.args['q'].strip()}%"
            values.extend([term, term])
        query = "SELECT * FROM workouts"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY duration ASC, title COLLATE NOCASE ASC"
        rows = database.execute(query, values).fetchall()
        return jsonify([serialize_workout(row) for row in rows])

    @app.post("/api/workouts")
    @admin_required
    def create_workout():
        payload = request.get_json(silent=True) or {}
        errors, cleaned = validate_workout(payload)
        if errors:
            return jsonify({"errors": errors}), 400
        database = get_db()
        cursor = database.execute(
            """INSERT INTO workouts
               (title, category, duration, equipment, description, exercises, video_url, program)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cleaned["title"],
                cleaned["category"],
                cleaned["duration"],
                json.dumps(cleaned["equipment"]),
                cleaned["description"],
                json.dumps(cleaned["exercises"]),
                cleaned["video_url"],
                cleaned["program"],
            ),
        )
        database.commit()
        row = database.execute("SELECT * FROM workouts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(serialize_workout(row)), 201

    @app.get("/api/workouts/<int:workout_id>")
    def get_workout(workout_id):
        row = get_db().execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
        if row is None:
            return api_error("Workout not found.", 404)
        return jsonify(serialize_workout(row))

    @app.route("/api/workouts/<int:workout_id>", methods=["PUT", "PATCH"])
    @admin_required
    def update_workout(workout_id):
        database = get_db()
        existing = database.execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
        if existing is None:
            return api_error("Workout not found.", 404)
        payload = request.get_json(silent=True) or {}
        current = serialize_workout(existing)
        if request.method == "PATCH":
            merged = {**current, **payload}
        else:
            merged = payload
        errors, cleaned = validate_workout(merged)
        if errors:
            return jsonify({"errors": errors}), 400
        database.execute(
            """UPDATE workouts SET title = ?, category = ?, duration = ?, equipment = ?,
               description = ?, exercises = ?, video_url = ?, program = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                cleaned["title"],
                cleaned["category"],
                cleaned["duration"],
                json.dumps(cleaned["equipment"]),
                cleaned["description"],
                json.dumps(cleaned["exercises"]),
                cleaned["video_url"],
                cleaned["program"],
                workout_id,
            ),
        )
        database.commit()
        row = database.execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
        return jsonify(serialize_workout(row))

    @app.delete("/api/workouts/<int:workout_id>")
    @admin_required
    def delete_workout(workout_id):
        database = get_db()
        cursor = database.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
        database.commit()
        if cursor.rowcount == 0:
            return api_error("Workout not found.", 404)
        return jsonify({"deleted": workout_id})

    @app.get("/api/programs")
    def list_programs():
        database = get_db()
        program_rows = database.execute("SELECT * FROM programs ORDER BY duration").fetchall()
        workouts = database.execute(
            "SELECT * FROM workouts ORDER BY duration ASC, title COLLATE NOCASE ASC"
        ).fetchall()
        by_program: dict[str, list[dict]] = {}
        for workout in workouts:
            by_program.setdefault(workout["program"], []).append(serialize_workout(workout))
        return jsonify(
            [
                {
                    **dict(program),
                    "workouts": by_program.get(program["slug"], []),
                }
                for program in program_rows
            ]
        )

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return api_error("Resource not found.", 404)
        return error

    return app


def get_db() -> sqlite3.Connection:
    if "database" not in g:
        g.database = sqlite3.connect(current_app_database())
        g.database.row_factory = sqlite3.Row
    return g.database


class GeminiError(RuntimeError):
    """A safe, user-facing failure from the optional Gemini integration."""


def get_workout_catalog() -> dict:
    database = get_db()
    workouts = [
        serialize_workout(row)
        for row in database.execute(
            "SELECT title, category, duration, equipment, description, exercises, program "
            "FROM workouts ORDER BY duration ASC, title COLLATE NOCASE ASC"
        ).fetchall()
    ]
    programs = [
        dict(row)
        for row in database.execute(
            "SELECT slug, name, duration, focus, description FROM programs ORDER BY duration ASC"
        ).fetchall()
    ]
    return {"workouts": workouts, "programs": programs}


def generate_gemini_response(api_key: str, message: str, catalog: dict) -> str:
    prompt = f"""You are Forge Fitness Coach, a concise workout suggestion assistant.
The user asks: {message}

Use ONLY the catalog below. Recommend one or more existing workout titles and/or
existing program names exactly as written. Never invent workouts, programs,
equipment, exercises, durations, or links. Only mention equipment from the
allowed equipment list. Do not diagnose, treat, or make medical claims.
If the user reports pain, tell them to stop and seek qualified medical advice.
Suggest a warm-up, the selected catalog workout/program, and one practical
next step in at most 180 words. Say that they should stop if pain occurs.

Allowed equipment:
{", ".join(ALLOWED_EQUIPMENT)}

Catalog JSON:
{json.dumps(catalog, separators=(",", ":"))}
"""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key, http_options={"timeout": 10000})
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=500,
            ),
        )
        text = (response.text or "").strip()
    except (ImportError, OSError, TimeoutError, ValueError) as error:
        raise GeminiError("The workout coach is temporarily unavailable. Please try again.") from error
    except Exception as error:
        raise GeminiError("The workout coach is temporarily unavailable. Please try again.") from error
    if len(text) > GEMINI_MAX_RESPONSE_LENGTH:
        text = text[:GEMINI_MAX_RESPONSE_LENGTH].rstrip() + "…"
    catalog_names = {
        item["title"] for item in catalog["workouts"]
    } | {
        item["name"] for item in catalog["programs"]
    }
    if not any(name.lower() in text.lower() for name in catalog_names):
        raise GeminiError("The workout coach could not ground that suggestion in the catalog.")
    return text


def oauth_providers(app: Flask) -> list[str]:
    return [
        provider
        for provider in ("google", "microsoft")
        if app.config.get(f"{provider.upper()}_CLIENT_ID")
    ]


def validate_oauth_config(config: dict) -> None:
    for provider in ("GOOGLE", "MICROSOFT"):
        client_id = str(config.get(f"{provider}_CLIENT_ID", "")).strip()
        client_secret = str(config.get(f"{provider}_CLIENT_SECRET", "")).strip()
        if bool(client_id) != bool(client_secret):
            raise ValueError(
                f"{provider}_CLIENT_ID and {provider}_CLIENT_SECRET must be configured together."
            )
    if oauth_providers_from_config(config) and not str(config.get("SECRET_KEY", "")).strip():
        raise ValueError("SECRET_KEY is required when OAuth is configured.")


def oauth_providers_from_config(config: dict) -> list[str]:
    return [
        provider
        for provider in ("GOOGLE", "MICROSOFT")
        if str(config.get(f"{provider}_CLIENT_ID", "")).strip()
    ]


def register_oauth_providers(app: Flask, oauth: OAuth) -> None:
    if app.config.get("GOOGLE_CLIENT_ID"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    if app.config.get("MICROSOFT_CLIENT_ID"):
        oauth.register(
            name="microsoft",
            client_id=app.config["MICROSOFT_CLIENT_ID"],
            client_secret=app.config["MICROSOFT_CLIENT_SECRET"],
            server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile User.Read"},
        )


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not oauth_providers_from_config(current_app_config()):
            return view(*args, **kwargs)
        if session.get("user"):
            return view(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Authentication required.", "login_url": url_for("login")}), 401
        return redirect(url_for("login", next=request.url))

    return wrapped


def current_app_config() -> dict:
    from flask import current_app

    return current_app.config


def current_app_database() -> str:
    # Imported lazily to keep helpers straightforward to exercise.
    from flask import current_app

    return current_app.config["DATABASE"]


def initialize_database(app: Flask) -> None:
    database = sqlite3.connect(app.config["DATABASE"])
    database.row_factory = sqlite3.Row
    with open(BASE_DIR / "backend" / "schema.sql", encoding="utf-8") as schema_file:
        database.executescript(schema_file.read())
    if database.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == 0:
        database.executemany(
            "INSERT INTO programs (slug, name, duration, focus, description, accent) VALUES (?, ?, ?, ?, ?, ?)",
            SEED_PROGRAMS,
        )
    if database.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 0:
        for workout in SEED_WORKOUTS:
            database.execute(
                """INSERT INTO workouts
                   (title, category, duration, equipment, description, exercises, video_url, program)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workout["title"],
                    workout["category"],
                    workout["duration"],
                    json.dumps(workout["equipment"]),
                    workout["description"],
                    json.dumps(workout["exercises"]),
                    workout["video_url"],
                    workout["program"],
                ),
            )
    database.commit()
    database.close()


def serialize_workout(row: sqlite3.Row | dict) -> dict:
    data = dict(row)
    for key in ("equipment", "exercises"):
        try:
            data[key] = json.loads(data[key]) if isinstance(data[key], str) else data[key]
        except (TypeError, json.JSONDecodeError):
            data[key] = []
    return data


def validate_workout(payload: dict, partial: bool = False) -> tuple[list[str], dict]:
    errors: list[str] = []
    cleaned: dict = {}
    required = ("title", "category", "duration", "equipment", "description", "exercises", "program")
    if not isinstance(payload, dict):
        return ["A JSON object is required."], {}
    for key in required:
        if key not in payload and not partial:
            errors.append(f"{key} is required.")
    title = str(payload.get("title", "")).strip()
    if not 3 <= len(title) <= 100:
        errors.append("Title must be between 3 and 100 characters.")
    cleaned["title"] = title
    category = payload.get("category")
    if category not in CATEGORIES:
        errors.append("Choose a valid workout category.")
    cleaned["category"] = category
    try:
        duration = int(payload.get("duration"))
    except (TypeError, ValueError):
        duration = 0
    if duration not in DURATIONS:
        errors.append("Duration must be 30, 45, or 60 minutes.")
    cleaned["duration"] = duration
    equipment = payload.get("equipment", [])
    if not isinstance(equipment, list) or not equipment:
        errors.append("Choose at least one equipment type.")
        equipment = []
    unknown_equipment = [
        item for item in equipment
        if not isinstance(item, str) or item not in ALLOWED_EQUIPMENT
    ]
    if unknown_equipment:
        errors.append("Unsupported equipment: " + ", ".join(map(str, unknown_equipment)))
    cleaned["equipment"] = list(dict.fromkeys(
        item for item in equipment if isinstance(item, str) and item in ALLOWED_EQUIPMENT
    ))
    description = str(payload.get("description", "")).strip()
    if not 10 <= len(description) <= 500:
        errors.append("Description must be between 10 and 500 characters.")
    cleaned["description"] = description
    exercises = payload.get("exercises", [])
    if not isinstance(exercises, list) or not 1 <= len(exercises) <= 20:
        errors.append("Add between 1 and 20 exercises.")
        exercises = []
    normalized_exercises = []
    for index, exercise in enumerate(exercises):
        if not isinstance(exercise, dict) or not str(exercise.get("name", "")).strip():
            errors.append(f"Exercise {index + 1} needs a name.")
            continue
        normalized_exercises.append(
            {
                "name": str(exercise["name"]).strip()[:100],
                "sets": str(exercise.get("sets", "")).strip()[:20],
                "reps": str(exercise.get("reps", "")).strip()[:30],
                "rest": str(exercise.get("rest", "")).strip()[:30],
            }
        )
    cleaned["exercises"] = normalized_exercises
    video_url = str(payload.get("video_url", "")).strip()
    parsed_url = urlparse(video_url) if video_url else None
    if video_url and (parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc):
        errors.append("Video link must be a valid http(s) URL.")
    cleaned["video_url"] = video_url[:500]
    program = payload.get("program", "")
    if program not in [seed_program[0] for seed_program in SEED_PROGRAMS]:
        errors.append("Choose a valid workout program.")
    cleaned["program"] = program
    return errors, cleaned


def api_error(message: str, status: int):
    return jsonify({"error": message}), status


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
