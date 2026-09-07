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
            {"name": "Barbell curl", "sets": 3, "reps": "10", "rest": "45 sec"},
            {"name": "Bench triceps dip", "sets": 3, "reps": "12", "rest": "45 sec"},
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

PROGRAM_EXPANSIONS = [
    (f"30-minute-{i}", f"30-minute {name}", 30, focus, f"A focused {focus} session for a compact training day.", title, equipment, exercises)
    for i, name, focus, title, equipment, exercises in [
        (2, "core spark", "core", "Core Spark", ["bodyweight", "yoga mat"], [{"name": "Hollow-body hold", "sets": 3, "reps": "20 sec", "rest": "30 sec"}, {"name": "Reverse crunch", "sets": 3, "reps": "12", "rest": "30 sec"}]),
        (3, "leg express", "leg day", "Leg Express", ["kettlebells", "bodyweight"], [{"name": "Kettlebell goblet squat", "sets": 3, "reps": "10", "rest": "45 sec"}, {"name": "Reverse lunge", "sets": 3, "reps": "10/side", "rest": "45 sec"}]),
        (4, "upper pulse", "upper body", "Upper Pulse", ["dumbbells", "benches"], [{"name": "Incline dumbbell curl", "sets": 3, "reps": "10", "rest": "45 sec"}, {"name": "Dumbbell bench press", "sets": 3, "reps": "10", "rest": "45 sec"}]),
        (5, "bodyweight base", "full-body", "Bodyweight Base", ["bodyweight", "yoga mat"], [{"name": "Bodyweight squat", "sets": 3, "reps": "15", "rest": "30 sec"}, {"name": "Plank shoulder tap", "sets": 3, "reps": "16 total", "rest": "30 sec"}]),
        (6, "ruck primer", "hybrid", "Ruck Primer", ["rucking gear", "step"], [{"name": "Loaded step-up", "sets": 3, "reps": "10/side", "rest": "45 sec"}, {"name": "Ruck walk", "sets": 1, "reps": "12 min", "rest": "—"}]),
        (7, "triceps thirty", "upper body", "Triceps Thirty", ["dumbbells", "bodyweight"], [{"name": "Dumbbell overhead triceps extension", "sets": 3, "reps": "10", "rest": "45 sec"}, {"name": "Diamond push-up", "sets": 3, "reps": "AMRAP", "rest": "45 sec"}]),
    ]
] + [
    (f"45-minute-{i}", f"45-minute {name}", 45, focus, f"A balanced {focus} session with room for deliberate strength work.", title, equipment, exercises)
    for i, name, focus, title, equipment, exercises in [
        (2, "abs and engine", "core", "Abs and Engine", ["ab roller", "bodyweight", "yoga mat"], [{"name": "Ab-wheel rollout", "sets": 4, "reps": "8", "rest": "60 sec"}, {"name": "Mountain climber", "sets": 4, "reps": "30 sec", "rest": "30 sec"}]),
        (3, "kettlebell build", "leg day", "Kettlebell Build", ["kettlebells", "bodyweight"], [{"name": "Kettlebell swing", "sets": 4, "reps": "15", "rest": "45 sec"}, {"name": "Reverse lunge", "sets": 4, "reps": "10/side", "rest": "45 sec"}]),
        (4, "press and arms", "upper body", "Press and Arms", ["barbells", "dumbbells", "benches"], [{"name": "Barbell bench press", "sets": 4, "reps": "6", "rest": "90 sec"}, {"name": "Barbell curl", "sets": 3, "reps": "10", "rest": "45 sec"}]),
        (5, "full-body tempo", "full-body", "Full-body Tempo", ["resistance bands", "bodyweight"], [{"name": "Bodyweight squat", "sets": 4, "reps": "15", "rest": "30 sec"}, {"name": "Resistance band pressdown", "sets": 3, "reps": "15", "rest": "30 sec"}]),
        (6, "station circuit", "hybrid", "Station Circuit", ["workout station", "step", "bodyweight"], [{"name": "Loaded step-up", "sets": 4, "reps": "10/side", "rest": "45 sec"}, {"name": "Bear crawl", "sets": 4, "reps": "30 sec", "rest": "45 sec"}]),
        (7, "back and biceps", "upper body", "Back and Biceps", ["pull-up bar", "dumbbells"], [{"name": "Pull-up", "sets": 4, "reps": "AMRAP", "rest": "75 sec"}, {"name": "Hammer curl", "sets": 3, "reps": "10", "rest": "45 sec"}]),
    ]
] + [
    (f"60-minute-{i}", f"60-minute {name}", 60, focus, f"A complete {focus} training block with strength, preparation, and recovery.", title, equipment, exercises)
    for i, name, focus, title, equipment, exercises in [
        (2, "core strength", "core", "Core Strength", ["ab roller", "bodyweight", "yoga mat"], [{"name": "Ab-wheel rollout", "sets": 5, "reps": "8", "rest": "60 sec"}, {"name": "Side plank", "sets": 4, "reps": "30 sec/side", "rest": "30 sec"}]),
        (3, "barbell legs", "leg day", "Barbell Legs", ["barbells", "benches"], [{"name": "Back squat", "sets": 5, "reps": "5", "rest": "120 sec"}, {"name": "Barbell deadlift", "sets": 4, "reps": "5", "rest": "120 sec"}]),
        (4, "upper strength", "upper body", "Upper Strength", ["barbells", "pull-up bar", "benches"], [{"name": "Barbell overhead press", "sets": 4, "reps": "8", "rest": "90 sec"}, {"name": "Pull-up", "sets": 4, "reps": "AMRAP", "rest": "75 sec"}]),
        (5, "full-body forge plus", "full-body", "Full-body Forge Plus", ["dumbbells", "benches"], [{"name": "Dumbbell bench press", "sets": 4, "reps": "10", "rest": "60 sec"}, {"name": "Dumbbell Romanian deadlift", "sets": 4, "reps": "12", "rest": "60 sec"}]),
        (6, "ruck endurance", "hybrid", "Ruck Endurance", ["rucking gear", "wind bike", "step"], [{"name": "Ruck walk", "sets": 1, "reps": "25 min", "rest": "—"}, {"name": "Wind bike sprint", "sets": 8, "reps": "30 sec", "rest": "60 sec"}]),
        (7, "arms and core", "hybrid", "Arms and Core", ["dumbbells", "bodyweight", "yoga mat"], [{"name": "Alternating dumbbell curl", "sets": 3, "reps": "12 total", "rest": "45 sec"}, {"name": "Hollow-body hold", "sets": 4, "reps": "20 sec", "rest": "30 sec"}]),
    ]
]

EXPANDED_PROGRAMS = [
    (slug, name, duration, focus, description, "#e3ff61")
    for slug, name, duration, focus, description, _title, _equipment, _exercises in PROGRAM_EXPANSIONS
]
EXPANDED_WORKOUTS = [
    {
        "title": title,
        "category": focus,
        "duration": duration,
        "equipment": equipment,
        "description": description,
        "program": slug,
        "video_url": "",
        "exercises": exercises,
    }
    for slug, _name, duration, focus, description, title, equipment, exercises in PROGRAM_EXPANSIONS
]

EXERCISE_METADATA = {
    "March in place": ("Full body", "Dynamic warm-up", "Stand tall and alternate knee lifts at an easy, steady pace."),
    "Arm circles": ("Shoulders", "Dynamic warm-up", "Sweep straight arms through small then larger circles without shrugging."),
    "World's greatest stretch": ("Full body", "Dynamic warm-up", "Step into a long lunge, place the opposite hand down, and rotate the other arm upward."),
    "Hip hinge reach": ("Hamstrings", "Dynamic warm-up", "Soften your knees, hinge your hips back, and reach forward before standing tall."),
    "Cat-cow": ("Spine", "Dynamic warm-up", "On hands and knees, alternate gently rounding and extending your spine with your breath."),
    "Child's pose": ("Hips", "Static cooldown", "Sit your hips toward your heels, reach long through your arms, and breathe calmly."),
    "Standing quad stretch": ("Quadriceps", "Static cooldown", "Hold one ankle behind you, keep knees close, and gently tuck your hips."),
    "Half-kneeling hip flexor stretch": ("Hip flexors", "Static cooldown", "Kneel with one foot forward, tuck your pelvis, and shift forward gently."),
    "Doorway chest stretch": ("Chest", "Static cooldown", "Place your forearms on a doorway and step through until your chest gently lengthens."),
    "Seated hamstring stretch": ("Hamstrings", "Static cooldown", "Extend one leg, hinge forward from the hips, and hold without bouncing."),
    "Goblet squat": ("Legs", "Hold the weight at your chest, sit your hips down, then drive through the floor to stand."),
    "Dumbbell bench press": ("Chest", "Press the dumbbells from chest level until your arms are straight, then lower with control."),
    "One-arm row": ("Back", "Brace on a bench, pull one weight toward your ribs, and lower it without twisting."),
    "Dumbbell Romanian deadlift": ("Hamstrings", "Hinge at the hips with a soft knee bend, keeping the weights close to your legs."),
    "Kettlebell goblet squat": ("Legs", "Keep the bell close to your chest, squat between your knees, and stand tall."),
    "Kettlebell swing": ("Glutes", "Hike the bell back, snap your hips forward, and let the bell float to chest height."),
    "Reverse lunge": ("Legs", "Step one foot back, lower both knees, then push through the front foot to return."),
    "Single-leg calf raise": ("Calves", "Balance on one foot, lift your heel high, and lower slowly through the full range."),
    "Barbell bench press": ("Chest", "Lower the bar to mid-chest with steady elbows, then press it back to lockout."),
    "Pull-up": ("Back", "Hang from the bar, pull your chest toward it, and lower until your arms are straight."),
    "Barbell overhead press": ("Shoulders", "Start at shoulder height and press the bar overhead while keeping your ribs stacked."),
    "Inverted row": ("Back", "Pull your chest to a bar set at waist height while keeping your body in one straight line."),
    "Barbell curl": ("Biceps", "Keep your elbows close to your ribs, curl the bar toward your shoulders, then lower it slowly."),
    "Bench triceps dip": ("Triceps", "Place your hands on the bench edge, lower your hips with control, then press through your palms to rise."),
    "Dead bug": ("Abs", "Lie on your back and slowly extend the opposite arm and leg while keeping your low back down."),
    "Ab-wheel rollout": ("Abs", "Roll forward from your knees while bracing your midsection, then pull back with control."),
    "Side plank": ("Abs", "Support your body on one forearm and the side of your foot, keeping hips lifted and stacked."),
    "Bear crawl": ("Full body", "Move on hands and feet with knees hovering low, taking slow opposite-hand and foot steps."),
    "Back squat": ("Legs", "Rest the bar securely, squat with a braced torso, and stand by driving through your feet."),
    "Barbell deadlift": ("Posterior chain", "Set your feet under the bar, hinge to grip it, then stand by pushing the floor away."),
    "Barbell row": ("Back", "Hinge with a flat back, pull the bar toward your lower ribs, and lower it smoothly."),
    "Bench press": ("Chest", "Lower the bar to mid-chest with control, then press evenly until your elbows extend."),
    "Loaded step-up": ("Legs", "Place one foot on the step, drive through it to stand, then step down with control."),
    "Wind bike sprint": ("Conditioning", "Pedal hard for the timed interval, keeping a steady posture and controlled breathing."),
    "Ruck walk": ("Conditioning", "Walk tall under your ruck load with short, steady steps and relaxed shoulders."),
    "Bodyweight squat": ("Legs", "Sit your hips back and down, keep your chest proud, then stand through both feet."),
}

EXPANSION_EXERCISES = {
    "Core Control": [
        {"name": "Hollow-body hold", "sets": 3, "reps": "20 sec", "rest": "30 sec", "equipment": ["bodyweight", "yoga mat"]},
        {"name": "Reverse crunch", "sets": 3, "reps": "12", "rest": "30 sec", "equipment": ["bodyweight", "yoga mat"]},
        {"name": "Bicycle crunch", "sets": 3, "reps": "16 total", "rest": "30 sec", "equipment": ["bodyweight", "yoga mat"]},
        {"name": "Mountain climber", "sets": 3, "reps": "30 sec", "rest": "30 sec", "equipment": ["bodyweight"]},
        {"name": "Plank shoulder tap", "sets": 3, "reps": "16 total", "rest": "30 sec", "equipment": ["bodyweight"]},
        {"name": "V-sit reach", "sets": 3, "reps": "10", "rest": "30 sec", "equipment": ["bodyweight", "yoga mat"]},
        {"name": "Heel tap", "sets": 3, "reps": "20 total", "rest": "30 sec", "equipment": ["bodyweight", "yoga mat"]},
        {"name": "Bird dog", "sets": 3, "reps": "10/side", "rest": "30 sec", "equipment": ["bodyweight", "yoga mat"]},
        {"name": "Bear plank", "sets": 3, "reps": "20 sec", "rest": "30 sec", "equipment": ["bodyweight"]},
    ],
    "Pull + Press": [
        {"name": "Incline dumbbell curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells", "benches"]},
        {"name": "Hammer curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Concentration curl", "sets": 3, "reps": "10/side", "rest": "45 sec", "equipment": ["dumbbells", "benches"]},
        {"name": "Zottman curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Alternating dumbbell curl", "sets": 3, "reps": "12 total", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Dumbbell spider curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells", "benches"]},
        {"name": "Close-grip bench press", "sets": 3, "reps": "8", "rest": "75 sec", "equipment": ["barbells", "benches"]},
        {"name": "Dumbbell overhead triceps extension", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Dumbbell kickback", "sets": 3, "reps": "12/side", "rest": "45 sec", "equipment": ["dumbbells", "benches"]},
        {"name": "Lying dumbbell triceps extension", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells", "benches"]},
        {"name": "Barbell skull crusher", "sets": 3, "reps": "10", "rest": "60 sec", "equipment": ["barbells", "benches"]},
        {"name": "Resistance band pressdown", "sets": 3, "reps": "15", "rest": "30 sec", "equipment": ["resistance bands"]},
        {"name": "Diamond push-up", "sets": 3, "reps": "AMRAP", "rest": "45 sec", "equipment": ["bodyweight"]},
        {"name": "Dumbbell floor press", "sets": 3, "reps": "10", "rest": "60 sec", "equipment": ["dumbbells"]},
        {"name": "Single-arm overhead extension", "sets": 3, "reps": "12/side", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Bench close-grip push-up", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["bodyweight", "benches"]},
        {"name": "Dumbbell rolling triceps extension", "sets": 3, "reps": "10", "rest": "60 sec", "equipment": ["dumbbells", "benches"]},
        {"name": "Cable-free band curl", "sets": 3, "reps": "15", "rest": "30 sec", "equipment": ["resistance bands"]},
        {"name": "Cross-body hammer curl", "sets": 3, "reps": "12 total", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Reverse curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["barbells"]},
        {"name": "Dumbbell drag curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells"]},
        {"name": "Preacher curl", "sets": 3, "reps": "10", "rest": "45 sec", "equipment": ["dumbbells", "benches"]},
    ],
}

EXERCISE_EXPANSION_METADATA = {
    name: (
        "Abs",
        "Main work",
        f"Perform {name.lower()} with a braced midsection, controlled tempo, and steady breathing.",
    )
    for exercise in EXPANSION_EXERCISES["Core Control"]
    for name in [exercise["name"]]
} | {
    name: (
        "Biceps",
        "Main work",
        f"Perform {name.lower()} with elbows stable, a controlled lift, and a slow return.",
    )
    for name in (
        "Incline dumbbell curl", "Hammer curl", "Concentration curl", "Zottman curl",
        "Alternating dumbbell curl", "Dumbbell spider curl", "Cable-free band curl",
        "Cross-body hammer curl", "Reverse curl", "Dumbbell drag curl", "Preacher curl",
    )
} | {
    name: (
        "Triceps",
        "Main work",
        f"Perform {name.lower()} with elbows controlled and extend fully without locking forcefully.",
    )
    for name in (
        "Close-grip bench press", "Dumbbell overhead triceps extension", "Dumbbell kickback",
        "Lying dumbbell triceps extension", "Barbell skull crusher", "Resistance band pressdown",
        "Diamond push-up", "Dumbbell floor press", "Single-arm overhead extension",
        "Bench close-grip push-up", "Dumbbell rolling triceps extension",
    )
}

WARMUP_BY_CATEGORY = {
    "full-body": [
        {"name": "March in place", "sets": 1, "reps": "2 min", "rest": "15 sec", "type": "Dynamic warm-up"},
        {"name": "World's greatest stretch", "sets": 1, "reps": "5/side", "rest": "15 sec", "type": "Dynamic warm-up"},
    ],
    "leg day": [
        {"name": "March in place", "sets": 1, "reps": "2 min", "rest": "15 sec", "type": "Dynamic warm-up"},
        {"name": "Hip hinge reach", "sets": 1, "reps": "10", "rest": "15 sec", "type": "Dynamic warm-up"},
    ],
    "upper body": [
        {"name": "Arm circles", "sets": 1, "reps": "30 sec", "rest": "15 sec", "type": "Dynamic warm-up"},
        {"name": "Cat-cow", "sets": 1, "reps": "8", "rest": "15 sec", "type": "Dynamic warm-up"},
    ],
    "core": [
        {"name": "Cat-cow", "sets": 1, "reps": "8", "rest": "15 sec", "type": "Dynamic warm-up"},
        {"name": "March in place", "sets": 1, "reps": "2 min", "rest": "15 sec", "type": "Dynamic warm-up"},
    ],
    "hybrid": [
        {"name": "March in place", "sets": 1, "reps": "2 min", "rest": "15 sec", "type": "Dynamic warm-up"},
        {"name": "World's greatest stretch", "sets": 1, "reps": "5/side", "rest": "15 sec", "type": "Dynamic warm-up"},
    ],
}
COOLDOWN_BY_CATEGORY = {
    "leg day": [
        {"name": "Standing quad stretch", "sets": 1, "reps": "30 sec/side", "rest": "—", "type": "Static cooldown"},
        {"name": "Seated hamstring stretch", "sets": 1, "reps": "30 sec/side", "rest": "—", "type": "Static cooldown"},
    ],
    "upper body": [
        {"name": "Doorway chest stretch", "sets": 1, "reps": "30 sec", "rest": "—", "type": "Static cooldown"},
        {"name": "Child's pose", "sets": 1, "reps": "45 sec", "rest": "—", "type": "Static cooldown"},
    ],
}
DEFAULT_COOLDOWN = [
    {"name": "Child's pose", "sets": 1, "reps": "45 sec", "rest": "—", "type": "Static cooldown"},
    {"name": "Half-kneeling hip flexor stretch", "sets": 1, "reps": "30 sec/side", "rest": "—", "type": "Static cooldown"},
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

    @app.get("/exercises")
    def exercises():
        return render_template("exercises.html", page="exercises")

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

    @app.get("/api/exercises")
    def list_exercises():
        query = request.args.get("q", "").strip().lower()
        body_part = request.args.get("body_part", "").strip()
        exercise_type = request.args.get("type", "").strip()
        equipment_filter = request.args.get("equipment", "").strip()
        catalog = get_exercise_catalog()
        if query:
            catalog = [item for item in catalog if query in item["name"].lower() or query in item["description"].lower()]
        if body_part:
            catalog = [item for item in catalog if item["body_part"] == body_part]
        if exercise_type:
            catalog = [item for item in catalog if item["type"] == exercise_type]
        if equipment_filter:
            catalog = [item for item in catalog if equipment_filter in item["equipment"]]
        return jsonify(catalog)

    @app.post("/api/exercises")
    @admin_required
    def create_exercise():
        payload = request.get_json(silent=True) or {}
        errors, cleaned = validate_exercise(payload)
        if errors:
            return jsonify({"errors": errors}), 400
        database = get_db()
        try:
            database.execute(
                """INSERT INTO exercises (name, body_part, exercise_type, equipment, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (cleaned["name"], cleaned["body_part"], cleaned["type"], json.dumps(cleaned["equipment"]), cleaned["description"]),
            )
            database.commit()
        except sqlite3.IntegrityError:
            return jsonify({"errors": ["An exercise with that name already exists."]}), 409
        return jsonify(next(item for item in get_exercise_catalog() if item["name"].casefold() == cleaned["name"].casefold())), 201

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


def get_exercise_catalog() -> list[dict]:
    database = get_db()
    sync_exercise_records(database)
    equipment_by_exercise: dict[str, set[str]] = {}
    usage_by_exercise: dict[str, list[dict]] = {}
    for row in database.execute("SELECT title, equipment, exercises FROM workouts").fetchall():
        try:
            equipment = json.loads(row["equipment"])
            exercises = json.loads(row["exercises"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(equipment, list) or not isinstance(exercises, list):
            continue
        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue
            name = str(exercise.get("name", "")).strip()
            if name:
                exercise_type = exercise_metadata(name)[1]
                tagged_equipment = exercise.get("equipment")
                if not isinstance(tagged_equipment, list):
                    tagged_equipment = (
                        ["bodyweight", "yoga mat"]
                        if exercise_type == "Static cooldown"
                        else ["bodyweight"]
                        if exercise_type == "Dynamic warm-up"
                        else equipment
                    )
                equipment_by_exercise.setdefault(name, set()).update(
                    item for item in tagged_equipment if item in ALLOWED_EQUIPMENT
                )
                usage_by_exercise.setdefault(name, []).append(
                    {
                        "workout": row["title"],
                        "sets": str(exercise.get("sets", "")).strip(),
                        "reps": str(exercise.get("reps", "")).strip(),
                        "rest": str(exercise.get("rest", "")).strip(),
                    }
                )
    catalog = []
    rows = database.execute("SELECT name, body_part, exercise_type, equipment, description FROM exercises").fetchall()
    for row in rows:
        name = row["name"]
        try:
            stored_equipment = json.loads(row["equipment"])
        except (TypeError, json.JSONDecodeError):
            stored_equipment = []
        body_part = row["body_part"]
        exercise_type = row["exercise_type"]
        description = row["description"]
        catalog.append(
            {
                "name": name,
                "body_part": body_part,
                "type": exercise_type,
                "description": description,
                "equipment": sorted(set(stored_equipment) | equipment_by_exercise.get(name, set()), key=str.casefold),
                "usage": usage_by_exercise.get(name, []),
            }
        )
    return sorted(catalog, key=lambda item: item["name"].casefold())


def sync_exercise_records(database: sqlite3.Connection) -> None:
    for row in database.execute("SELECT equipment, exercises FROM workouts").fetchall():
        try:
            workout_equipment = json.loads(row["equipment"])
            workout_exercises = json.loads(row["exercises"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(workout_equipment, list) or not isinstance(workout_exercises, list):
            continue
        for exercise in workout_exercises:
            if not isinstance(exercise, dict):
                continue
            name = str(exercise.get("name", "")).strip()
            if not name:
                continue
            body_part, exercise_type, description = exercise_metadata(name)
            equipment = exercise.get("equipment")
            if not isinstance(equipment, list):
                equipment = workout_equipment if exercise_type == "Main work" else (
                    ["bodyweight", "yoga mat"] if exercise_type == "Static cooldown" else ["bodyweight"]
                )
            database.execute(
                """INSERT OR IGNORE INTO exercises
                   (name, body_part, exercise_type, equipment, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, body_part, exercise_type, json.dumps([item for item in equipment if item in ALLOWED_EQUIPMENT]), description),
            )
    database.commit()


def validate_exercise(payload: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    name = str(payload.get("name", "")).strip()
    if not 3 <= len(name) <= 100:
        errors.append("Name must be between 3 and 100 characters.")
    body_part = str(payload.get("body_part", "")).strip()
    if not 2 <= len(body_part) <= 50:
        errors.append("Body part must be between 2 and 50 characters.")
    exercise_type = payload.get("type")
    if exercise_type not in {"Main work", "Dynamic warm-up", "Static cooldown"}:
        errors.append("Choose Main work, Dynamic warm-up, or Static cooldown.")
    equipment = payload.get("equipment", [])
    if not isinstance(equipment, list):
        errors.append("Equipment must be a list with zero or one item.")
        equipment = []
    if len(equipment) > 1:
        errors.append("Choose no more than one equipment type.")
    if any(item not in ALLOWED_EQUIPMENT for item in equipment):
        errors.append("Equipment must use an allowed equipment type.")
    description = str(payload.get("description", "")).strip()
    if not 10 <= len(description) <= 500:
        errors.append("Description must be between 10 and 500 characters.")
    return errors, {
        "name": name,
        "body_part": body_part,
        "type": exercise_type,
        "equipment": list(dict.fromkeys(equipment)),
        "description": description,
    }


def exercise_metadata(name: str) -> tuple[str, str, str]:
    metadata = EXERCISE_METADATA.get(name) or EXERCISE_EXPANSION_METADATA.get(name)
    if metadata is None:
        return (
            "Full body",
            "Main work",
            "Move with control through a comfortable range and keep your trunk braced.",
        )
    if len(metadata) == 3:
        body_part, exercise_type, description = metadata
        return body_part, exercise_type, description
    body_part, description = metadata
    return body_part, "Main work", description


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
    ensure_seed_arm_exercises(database)
    ensure_expanded_programs(database)
    ensure_seed_mobility_exercises(database)
    database.commit()
    database.close()


def serialize_workout(row: sqlite3.Row | dict) -> dict:
    data = dict(row)
    for key in ("equipment", "exercises"):
        try:
            data[key] = json.loads(data[key]) if isinstance(data[key], str) else data[key]
        except (TypeError, json.JSONDecodeError):
            data[key] = []
    for exercise in data.get("exercises", []):
        if isinstance(exercise, dict):
            name = str(exercise.get("name", "")).strip()
            _, exercise_type, instruction = exercise_metadata(name)
            exercise["type"] = exercise.get("type") or exercise_type
            exercise["instruction"] = instruction
    return data


def ensure_seed_arm_exercises(database: sqlite3.Connection) -> None:
    row = database.execute(
        "SELECT id, exercises FROM workouts WHERE title = ?",
        ("Pull + Press",),
    ).fetchone()
    if row is None:
        return
    try:
        exercises = json.loads(row["exercises"])
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(exercises, list):
        return
    names = {item.get("name") for item in exercises if isinstance(item, dict)}
    additions = [
        exercise for exercise in (
            {"name": "Barbell curl", "sets": 3, "reps": "10", "rest": "45 sec"},
            {"name": "Bench triceps dip", "sets": 3, "reps": "12", "rest": "45 sec"},
        ) if exercise["name"] not in names
    ]
    if additions:
        database.execute(
            "UPDATE workouts SET exercises = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(exercises + additions), row["id"]),
        )


def ensure_seed_mobility_exercises(database: sqlite3.Connection) -> None:
    rows = database.execute("SELECT id, title, category, exercises FROM workouts").fetchall()
    for row in rows:
        try:
            exercises = json.loads(row["exercises"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(exercises, list):
            continue
        names = {item.get("name") for item in exercises if isinstance(item, dict)}
        existing_warmups = [
            item for item in exercises
            if isinstance(item, dict) and item.get("type") == "Dynamic warm-up"
        ]
        existing_cooldowns = [
            item for item in exercises
            if isinstance(item, dict) and item.get("type") == "Static cooldown"
        ]
        warmups = [
            dict(item)
            for item in WARMUP_BY_CATEGORY.get(row["category"], WARMUP_BY_CATEGORY["hybrid"])
            if item["name"] not in names
        ]
        names.update(item["name"] for item in warmups)
        cooldowns = [
            dict(item)
            for item in COOLDOWN_BY_CATEGORY.get(row["category"], DEFAULT_COOLDOWN)
            if item["name"] not in names
        ]
        existing_main = [
            item for item in exercises
            if not isinstance(item, dict) or item.get("type") not in {"Dynamic warm-up", "Static cooldown"}
        ]
        additions = []
        for exercise in EXPANSION_EXERCISES.get(row["title"], []):
            if exercise["name"] not in names:
                additions.append(dict(exercise))
        updated = existing_warmups + warmups + existing_main + additions + existing_cooldowns + cooldowns
        if updated != exercises:
            database.execute(
                "UPDATE workouts SET exercises = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(updated), row["id"]),
            )


def ensure_expanded_programs(database: sqlite3.Connection) -> None:
    for program in EXPANDED_PROGRAMS:
        database.execute(
            "INSERT OR IGNORE INTO programs (slug, name, duration, focus, description, accent) VALUES (?, ?, ?, ?, ?, ?)",
            program,
        )
    for workout in EXPANDED_WORKOUTS:
        row = database.execute(
            "SELECT id, exercises FROM workouts WHERE title = ?",
            (workout["title"],),
        ).fetchone()
        if row is None:
            database.execute(
                """INSERT INTO workouts
                   (title, category, duration, equipment, description, exercises, video_url, program)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workout["title"], workout["category"], workout["duration"],
                    json.dumps(workout["equipment"]), workout["description"],
                    json.dumps(workout["exercises"]), workout["video_url"], workout["program"],
                ),
            )


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
    if program not in {item[0] for item in SEED_PROGRAMS} | {item[0] for item in EXPANDED_PROGRAMS}:
        errors.append("Choose a valid workout program.")
    cleaned["program"] = program
    return errors, cleaned


def api_error(message: str, status: int):
    return jsonify({"error": message}), status


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
