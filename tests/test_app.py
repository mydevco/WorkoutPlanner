import unittest
import json
import sqlite3
from unittest.mock import patch
from pathlib import Path

from backend.app import EXERCISE_EXPANSION_METADATA, EXERCISE_METADATA, GeminiError, SEED_WORKOUTS, create_app


TEST_DATABASE = Path(__file__).with_name("smoke.sqlite")


class ForgeApiSmokeTest(unittest.TestCase):
    def setUp(self):
        if TEST_DATABASE.exists():
            TEST_DATABASE.unlink()
        self.app = create_app({"TESTING": True, "DATABASE": str(TEST_DATABASE)})
        self.client = self.app.test_client()

    def tearDown(self):
        if TEST_DATABASE.exists():
            TEST_DATABASE.unlink()

    def test_pages_and_healthcheck(self):
        for path in ("/", "/catalog", "/exercises", "/programs", "/admin", "/login"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
        self.assertEqual(self.client.get("/healthz").get_json()["status"], "ok")

    def test_oauth_disabled_keeps_admin_local(self):
        self.assertEqual(self.client.get("/admin").status_code, 200)
        self.assertEqual(self.client.post("/api/workouts", json={}).status_code, 400)

    def test_seed_data_and_filters(self):
        response = self.client.get("/api/workouts?duration=30")
        self.assertEqual(response.status_code, 200)
        workouts = response.get_json()
        self.assertTrue(workouts)
        self.assertTrue(all(item["duration"] == 30 for item in workouts))
        self.assertEqual(len(self.client.get("/api/equipment").get_json()), 19)

    def test_exercise_catalog_covers_seeded_exercises_with_descriptions(self):
        response = self.client.get("/api/exercises")
        self.assertEqual(response.status_code, 200)
        exercises = response.get_json()
        names = {item["name"] for item in exercises}
        seeded_names = {exercise["name"] for workout in SEED_WORKOUTS for exercise in workout["exercises"]}
        self.assertTrue(seeded_names <= names)
        self.assertTrue(all(item["description"] for item in exercises))
        self.assertTrue(all(item["body_part"] for item in exercises))
        self.assertTrue(all(isinstance(item["equipment"], list) for item in exercises))
        self.assertTrue(all(isinstance(item["usage"], list) for item in exercises))
        self.assertTrue(all(set(item["equipment"]) <= set(self.client.get("/api/equipment").get_json()) for item in exercises))
        self.assertTrue(seeded_names <= set(EXERCISE_METADATA))
        js_response = self.client.get("/static/js/app.js")
        js = js_response.get_data(as_text=True)
        js_response.close()
        self.assertIn("const listOrEmpty", js)
        self.assertIn("listOrEmpty(exercise.usage)", js)

    def test_exercise_catalog_includes_new_workout_rows_with_fallback_details(self):
        payload = {
            "title": "New movement row",
            "category": "hybrid",
            "duration": 30,
            "program": "30-minute",
            "equipment": ["bodyweight"],
            "description": "A current workout row used to verify catalog derivation.",
            "exercises": [{"name": "New floor press", "sets": 3, "reps": "8", "rest": "45 sec"}],
        }
        self.assertEqual(self.client.post("/api/workouts", json=payload).status_code, 201)
        exercises = self.client.get("/api/exercises").get_json()
        new_exercise = next(item for item in exercises if item["name"] == "New floor press")
        self.assertTrue(new_exercise["description"])
        self.assertEqual(new_exercise["usage"][0]["workout"], "New movement row")
        workout = self.client.get("/api/workouts").get_json()
        new_workout = next(item for item in workout if item["title"] == "New movement row")
        self.assertIn("instruction", new_workout["exercises"][0])

    def test_exercise_catalog_filters_by_body_part_and_equipment(self):
        response = self.client.get("/api/exercises?body_part=Abs&equipment=ab+roller")
        self.assertEqual(response.status_code, 200)
        exercises = response.get_json()
        self.assertTrue(exercises)
        self.assertTrue(all(item["body_part"] == "Abs" for item in exercises))
        self.assertTrue(all("ab roller" in item["equipment"] for item in exercises))

    def test_arm_exercises_have_metadata_usage_and_printable_availability(self):
        exercises = {item["name"]: item for item in self.client.get("/api/exercises").get_json()}
        self.assertIn("Barbell curl", exercises)
        self.assertIn("Bench triceps dip", exercises)
        self.assertEqual(exercises["Barbell curl"]["body_part"], "Biceps")
        self.assertEqual(exercises["Bench triceps dip"]["body_part"], "Triceps")
        self.assertTrue(exercises["Barbell curl"]["description"])
        self.assertTrue(exercises["Bench triceps dip"]["description"])
        self.assertEqual(exercises["Barbell curl"]["usage"][0]["workout"], "Pull + Press")
        self.assertEqual(exercises["Bench triceps dip"]["usage"][0]["reps"], "12")
        self.assertIn("barbells", exercises["Barbell curl"]["equipment"])
        self.assertIn("benches", exercises["Bench triceps dip"]["equipment"])
        self.assertIn("Barbell curl", self.client.get("/api/workouts").get_data(as_text=True))
        page = self.client.get("/exercises").get_data(as_text=True)
        self.assertIn("Print exercises", page)

    def test_existing_database_receives_arm_seed_backfill(self):
        database = sqlite3.connect(TEST_DATABASE)
        database.execute(
            "UPDATE workouts SET exercises = ? WHERE title = ?",
            (json.dumps([{"name": "Pull-up", "sets": 1, "reps": "1", "rest": "1 sec"}]), "Pull + Press"),
        )
        database.commit()
        database.close()
        create_app({"TESTING": True, "DATABASE": str(TEST_DATABASE)})
        workout = next(item for item in self.client.get("/api/workouts").get_json() if item["title"] == "Pull + Press")
        names = {exercise["name"] for exercise in workout["exercises"]}
        self.assertTrue({"Pull-up", "Barbell curl", "Bench triceps dip"} <= names)
        self.assertTrue({"Arm circles", "Cat-cow", "Child's pose", "Doorway chest stretch"} <= names)

    def test_warmups_and_static_cooldowns_are_ordered_in_every_workout(self):
        workouts = self.client.get("/api/workouts").get_json()
        self.assertTrue(workouts)
        for workout in workouts:
            exercises = workout["exercises"]
            self.assertEqual(exercises[0].get("type"), "Dynamic warm-up")
            self.assertEqual(exercises[-1].get("type"), "Static cooldown")
            self.assertTrue(any(item["type"] == "Dynamic warm-up" for item in exercises))
            self.assertTrue(any(item["type"] == "Static cooldown" for item in exercises))
            self.assertTrue(all(item.get("equipment", []) == [] for item in exercises if item["type"] != "Main work"))
        programs = self.client.get("/api/programs").get_json()
        self.assertEqual({program["duration"] for program in programs}, {30, 45, 60})

    def test_mobility_exercises_have_catalog_metadata_and_allowed_equipment(self):
        exercises = {item["name"]: item for item in self.client.get("/api/exercises").get_json()}
        for name, exercise_type in (
            ("March in place", "Dynamic warm-up"),
            ("Arm circles", "Dynamic warm-up"),
            ("Standing quad stretch", "Static cooldown"),
            ("Child's pose", "Static cooldown"),
        ):
            self.assertIn(name, exercises)
            self.assertEqual(exercises[name]["type"], exercise_type)
            self.assertTrue(exercises[name]["description"])
            self.assertTrue(exercises[name]["usage"])
            self.assertTrue(set(exercises[name]["equipment"]) <= set(self.client.get("/api/equipment").get_json()))

    def test_abs_biceps_triceps_have_twelve_catalog_entries_and_print_details(self):
        exercises = self.client.get("/api/exercises").get_json()
        by_part = {}
        for exercise in exercises:
            by_part.setdefault(exercise["body_part"], []).append(exercise)
        self.assertEqual(len(by_part["Abs"]), 12)
        self.assertEqual(len(by_part["Biceps"]), 12)
        self.assertEqual(len(by_part["Triceps"]), 12)
        allowed = set(self.client.get("/api/equipment").get_json())
        for body_part in ("Abs", "Biceps", "Triceps"):
            self.assertEqual(len({item["name"] for item in by_part[body_part]}), 12)
            for item in by_part[body_part]:
                self.assertTrue(item["description"])
                self.assertTrue(item["usage"])
                self.assertIn(item["type"], {"Main work", "Dynamic warm-up", "Static cooldown"})
                self.assertTrue(set(item["equipment"]) <= allowed)
        page = self.client.get("/exercises").get_data(as_text=True)
        self.assertIn("exercise-groups", page)
        self.assertIn("Print exercises", page)
        self.assertEqual(len(EXERCISE_EXPANSION_METADATA), 31)

    def test_expansion_backfill_is_idempotent_for_existing_database(self):
        first = {item["name"] for item in self.client.get("/api/exercises").get_json()}
        create_app({"TESTING": True, "DATABASE": str(TEST_DATABASE)})
        second = self.client.get("/api/exercises").get_json()
        self.assertEqual(first, {item["name"] for item in second})
        for body_part in ("Abs", "Biceps", "Triceps"):
            self.assertEqual(sum(item["body_part"] == body_part for item in second), 12)

    def test_program_expansion_has_six_programs_per_duration_and_complete_rows(self):
        programs = self.client.get("/api/programs").get_json()
        by_duration = {}
        for program in programs:
            by_duration.setdefault(program["duration"], []).append(program)
        self.assertEqual({duration: len(items) for duration, items in by_duration.items()}, {30: 7, 45: 7, 60: 7})
        allowed = set(self.client.get("/api/equipment").get_json())
        for program in programs:
            self.assertTrue(program["workouts"])
            for workout in program["workouts"]:
                self.assertEqual(workout["duration"], program["duration"])
                self.assertEqual(workout["exercises"][0]["type"], "Dynamic warm-up")
                self.assertEqual(workout["exercises"][-1]["type"], "Static cooldown")
                self.assertTrue(all(set(workout["equipment"]) <= allowed for _ in [0]))
                self.assertTrue(all(exercise.get("instruction") for exercise in workout["exercises"]))

    def test_exercise_page_has_print_controls_and_print_css(self):
        page = self.client.get("/exercises").get_data(as_text=True)
        self.assertIn("Print exercises", page)
        self.assertIn("body-part-filter", page)
        css_response = self.client.get("/static/css/styles.css")
        css = css_response.get_data(as_text=True)
        css_response.close()
        self.assertIn("@media print", css)
        self.assertIn(".site-header", css)
        self.assertIn(".exercise-card", css)
        self.assertIn("display: table-header-group", css)
        catalog = self.client.get("/catalog").get_data(as_text=True)
        programs = self.client.get("/programs").get_data(as_text=True)
        js_response = self.client.get("/static/js/app.js")
        js = js_response.get_data(as_text=True)
        js_response.close()
        self.assertIn("workout-details", js)
        self.assertIn("Print catalog", catalog)
        self.assertIn("Print programs", programs)

    def test_gemini_disabled_and_message_validation(self):
        self.assertEqual(self.client.get("/api/chat/status").get_json(), {"configured": False})
        self.assertEqual(self.client.post("/api/chat", json={}).status_code, 400)
        too_long = "x" * 501
        self.assertEqual(self.client.post("/api/chat", json={"message": too_long}).status_code, 400)
        self.assertEqual(self.client.post("/api/chat", json={"message": "Suggest a workout"}).status_code, 503)

    def test_gemini_mocked_success_and_error(self):
        configured_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(TEST_DATABASE),
                "GEMINI_API_KEY": "test-key",
            }
        )
        client = configured_app.test_client()
        with patch(
            "backend.app.generate_gemini_response",
            return_value="Try Dumbbell Engine from the 30-minute charge. Stop if pain occurs.",
        ) as generate:
            response = client.post("/api/chat", json={"message": "I have 30 minutes and dumbbells."})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Dumbbell Engine", response.get_json()["answer"])
        generate.assert_called_once()

        with patch(
            "backend.app.generate_gemini_response",
            side_effect=GeminiError("The workout coach is temporarily unavailable. Please try again."),
        ):
            response = client.post("/api/chat", json={"message": "Suggest a workout"})
        self.assertEqual(response.status_code, 502)

    def test_workout_crud_and_validation(self):
        payload = {
            "title": "Smoke circuit",
            "category": "hybrid",
            "duration": 30,
            "program": "30-minute",
            "equipment": ["bodyweight"],
            "description": "A short test session for the API smoke suite.",
            "video_url": "https://example.com/video",
            "exercises": [{"name": "Squat", "sets": 3, "reps": "10", "rest": "30 sec"}],
        }
        created = self.client.post("/api/workouts", json=payload)
        self.assertEqual(created.status_code, 201)
        workout_id = created.get_json()["id"]
        changed = self.client.patch(f"/api/workouts/{workout_id}", json={"title": "Updated circuit"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["title"], "Updated circuit")
        invalid = self.client.post("/api/workouts", json={**payload, "equipment": ["unsupported"]})
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("Unsupported equipment", " ".join(invalid.get_json()["errors"]))
        malformed = self.client.post("/api/workouts", json={**payload, "equipment": [["nested"]]})
        self.assertEqual(malformed.status_code, 400)
        deleted = self.client.delete(f"/api/workouts/{workout_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f"/api/workouts/{workout_id}").status_code, 404)

    def test_programs_include_workouts(self):
        response = self.client.get("/api/programs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({program["duration"] for program in response.get_json()}, {30, 45, 60})

    def test_oauth_protects_admin_but_not_public_routes(self):
        protected_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(TEST_DATABASE),
                "SECRET_KEY": "test-secret",
                "GOOGLE_CLIENT_ID": "google-id",
                "GOOGLE_CLIENT_SECRET": "google-secret",
                "MICROSOFT_CLIENT_ID": "",
                "MICROSOFT_CLIENT_SECRET": "",
            }
        )
        client = protected_app.test_client()
        self.assertEqual(client.get("/admin").status_code, 302)
        self.assertEqual(client.get("/api/workouts").status_code, 200)
        self.assertEqual(client.get("/healthz").status_code, 200)
        self.assertEqual(client.post("/api/workouts", json={}).status_code, 401)
        self.assertEqual(client.get("/login").status_code, 200)
        self.assertIn(b"Continue with Google", client.get("/login").data)

    def test_oauth_requires_complete_provider_credentials(self):
        with self.assertRaisesRegex(ValueError, "GOOGLE_CLIENT_ID"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(TEST_DATABASE),
                    "GOOGLE_CLIENT_ID": "google-id",
                    "GOOGLE_CLIENT_SECRET": "",
                }
            )
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(TEST_DATABASE),
                    "SECRET_KEY": "",
                    "GOOGLE_CLIENT_ID": "google-id",
                    "GOOGLE_CLIENT_SECRET": "google-secret",
                }
            )


if __name__ == "__main__":
    unittest.main()
