/* Forge Fitness browser UI: intentionally dependency-free for easy deployment. */
(function () {
  "use strict";

  const page = document.body.dataset.page;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const listOrEmpty = (value) => Array.isArray(value) ? value : [];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
  const labelCase = (value) => String(value || "").replace(/\b\w/g, (letter) => letter.toUpperCase());

  async function api(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.errors ? data.errors.join(" ") : (data.error || "Something went wrong."));
    return data;
  }

  function workoutCard(workout, compact = false) {
    const tags = listOrEmpty(workout.equipment).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    const exerciseRows = listOrEmpty(workout.exercises).map((exercise) => `<tr>
      <td>${escapeHtml(exercise.name)}</td>
      <td>${escapeHtml(exercise.sets || "—")}</td>
      <td>${escapeHtml(exercise.reps || "—")}</td>
      <td>${escapeHtml(exercise.rest || "—")}</td>
      <td>${escapeHtml(exercise.instruction || "Move with control through a comfortable range.")}</td>
    </tr>`).join("");
    return `<article class="${compact ? "program-workout" : "workout-card"}">
      <div class="card-top"><span class="badge">${escapeHtml(labelCase(workout.category))}</span><span class="duration">${escapeHtml(workout.duration)} min</span></div>
      <h3>${escapeHtml(workout.title)}</h3>
      <p>${escapeHtml(workout.description)}</p>
      <table class="workout-details"><thead><tr><th>Exercise</th><th>Sets</th><th>Reps/time</th><th>Rest</th><th>How to perform</th></tr></thead><tbody>${exerciseRows}</tbody></table>
      <ul class="tag-list" aria-label="Equipment">${tags}</ul>
      ${compact ? "" : `<div class="card-actions">${workout.video_url ? `<a class="video-link" href="${escapeHtml(workout.video_url)}" target="_blank" rel="noopener noreferrer">Watch movement ↗</a>` : "<span></span>"}<span class="details-link">${listOrEmpty(workout.exercises).length} exercises</span></div>`}
    </article>`;
  }

  function wireMenu() {
    const toggle = $(".menu-toggle");
    const nav = $("#site-nav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  function wirePrint() {
    $$(".print-trigger").forEach((button) => button.addEventListener("click", () => window.print()));
  }

  async function loadHome() {
    const target = $("#featured-workouts");
    if (!target) return;
    try {
      const workouts = await api("/api/workouts");
      $("#workout-count").textContent = String(workouts.length).padStart(2, "0");
      target.innerHTML = workouts.slice(0, 3).map((workout) => workoutCard(workout)).join("");
    } catch (error) {
      target.innerHTML = `<p class="loading">${escapeHtml(error.message)}</p>`;
    }
    wireCoach();
  }

  async function wireCoach() {
    const form = $("#coach-form");
    if (!form) return;
    const status = $("#coach-status");
    const answer = $("#coach-answer");
    try {
      const state = await api("/api/chat/status");
      if (!state.configured) {
        status.textContent = "Coach is optional. Set GEMINI_API_KEY on the server to enable suggestions.";
        form.querySelector("button").disabled = true;
        return;
      }
      status.textContent = "Grounded in the Forge workout catalog.";
    } catch (error) {
      status.textContent = escapeHtml(error.message);
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = $("#coach-message").value.trim();
      if (!message) { status.textContent = "Tell me what you want from today's workout."; return; }
      status.textContent = "Thinking…";
      answer.textContent = "";
      try {
        const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
        answer.textContent = result.answer;
        status.textContent = "Suggestion ready. Stop if pain occurs.";
      } catch (error) {
        status.textContent = error.message;
      }
    });
  }

  async function loadCatalog() {
    const grid = $("#catalog-grid");
    if (!grid) return;
    const search = $("#search-input"), duration = $("#duration-filter"), category = $("#category-filter");
    let timer;
    async function refresh() {
      const params = new URLSearchParams();
      if (search.value.trim()) params.set("q", search.value.trim());
      if (duration.value) params.set("duration", duration.value);
      if (category.value) params.set("category", category.value);
      grid.innerHTML = '<p class="loading">Loading workouts…</p>';
      try {
        const workouts = await api(`/api/workouts?${params.toString()}`);
        $("#results-count").textContent = `${workouts.length} workout${workouts.length === 1 ? "" : "s"} found`;
        $("#empty-state").hidden = workouts.length !== 0;
        grid.innerHTML = workouts.map((workout) => workoutCard(workout)).join("");
        grid.hidden = workouts.length === 0;
      } catch (error) {
        grid.innerHTML = `<p class="loading">${escapeHtml(error.message)}</p>`;
      }
    }
    [duration, category].forEach((field) => field.addEventListener("change", refresh));
    search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(refresh, 180); });
    $("#clear-filters").addEventListener("click", () => { search.value = ""; duration.value = ""; category.value = ""; refresh(); });
    refresh();
  }

  async function loadExercises() {
    const groups = $("#exercise-groups");
    if (!groups) return;
    const bodyPart = $("#body-part-filter");
    const equipment = $("#exercise-equipment-filter");
    let allExercises = [];
    const optionMarkup = (values, label) =>
      `<option value="">${label}</option>${values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("")}`;
    function render(exercises) {
      $("#exercise-count").textContent = `${exercises.length} exercise${exercises.length === 1 ? "" : "s"} found`;
      const grouped = exercises.reduce((result, exercise) => {
        (result[exercise.body_part] ||= []).push(exercise);
        return result;
      }, {});
      groups.innerHTML = Object.entries(grouped).map(([part, items]) => `<section class="exercise-group">
        <div class="exercise-group-heading"><p class="eyebrow">${escapeHtml(part)}</p><span>${items.length} movement${items.length === 1 ? "" : "s"}</span></div>
        <div class="exercise-grid">${items.map((exercise) => `<article class="exercise-card">
          <h2>${escapeHtml(exercise.name)}</h2>
          <p>${escapeHtml(exercise.description)}</p>
          <table class="exercise-usage"><thead><tr><th>Used in</th><th>Sets</th><th>Reps/time</th><th>Rest</th></tr></thead><tbody>
            ${listOrEmpty(exercise.usage).map((use) => `<tr><td>${escapeHtml(use.workout)}</td><td>${escapeHtml(use.sets || "—")}</td><td>${escapeHtml(use.reps || "—")}</td><td>${escapeHtml(use.rest || "—")}</td></tr>`).join("")}
          </tbody></table>
          <ul class="tag-list" aria-label="Equipment">${listOrEmpty(exercise.equipment).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </article>`).join("")}</div>
      </section>`).join("") || "<p class='empty-state'>No exercises match those filters.</p>";
    }
    try {
      allExercises = await api("/api/exercises");
      bodyPart.innerHTML = optionMarkup([...new Set(allExercises.map((item) => item.body_part))].sort(), "All body parts");
      equipment.innerHTML = optionMarkup([...new Set(allExercises.flatMap((item) => item.equipment))].sort(), "All equipment");
      const refresh = () => render(allExercises.filter((item) =>
        (!bodyPart.value || item.body_part === bodyPart.value) &&
        (!equipment.value || item.equipment.includes(equipment.value))
      ));
      bodyPart.addEventListener("change", refresh);
      equipment.addEventListener("change", refresh);
      $("#clear-exercise-filters").addEventListener("click", () => { bodyPart.value = ""; equipment.value = ""; refresh(); });
      refresh();
    } catch (error) {
      groups.innerHTML = `<p class="loading">${escapeHtml(error.message)}</p>`;
    }
  }

  async function loadPrograms() {
    const target = $("#program-list");
    if (!target) return;
    try {
      const programs = await api("/api/programs");
      $("#program-count").textContent = `${programs.length} time-boxed programs`;
      target.innerHTML = programs.map((program, index) => `<section class="program-block">
        <div class="program-block-head">
          <div><div class="program-name"><span class="program-index">0${index + 1}</span><h2>${escapeHtml(program.name)}</h2></div><p>${escapeHtml(program.description)}</p></div>
          <button class="button button-small button-light no-print print-program" type="button">Print program</button>
        </div>
        <div class="program-workouts">${listOrEmpty(program.workouts).length ? listOrEmpty(program.workouts).map((workout) => workoutCard(workout, true)).join("") : "<p>No sessions yet.</p>"}</div>
      </section>`).join("");
      $$(".print-program").forEach((button) => button.addEventListener("click", () => window.print()));
    } catch (error) {
      target.innerHTML = `<p class="loading">${escapeHtml(error.message)}</p>`;
    }
  }

  function equipmentMarkup(equipment) {
    return equipment.map((item) => `<label class="check-item"><input type="checkbox" name="equipment" value="${escapeHtml(item)}"> ${escapeHtml(labelCase(item))}</label>`).join("");
  }

  async function loadAdmin() {
    const form = $("#workout-form");
    if (!form) return;
    const list = $("#admin-list");
    const message = $("#form-message");
    const equipment = await api("/api/equipment").catch(() => []);
    $("#equipment-options").innerHTML = equipmentMarkup(equipment);
    let workouts = [];
    const showMessage = (text, success = false) => { message.textContent = text; message.className = `form-message${success ? " success" : ""}`; };
    function resetForm() {
      form.reset(); $("#workout-id").value = ""; $("#form-heading").textContent = "Add a workout"; $("#submit-label").textContent = "Save workout"; $("#cancel-edit").hidden = true; showMessage("");
    }
    function populate(workout) {
      $("#workout-id").value = workout.id; $("#title").value = workout.title; $("#category").value = workout.category;
      $("#duration").value = workout.duration; $("#program").value = workout.program; $("#description").value = workout.description; $("#video-url").value = workout.video_url || "";
      $("#exercises").value = JSON.stringify(workout.exercises || [], null, 2);
      $$('input[name="equipment"]').forEach((input) => { input.checked = workout.equipment.includes(input.value); });
      $("#form-heading").textContent = "Edit workout"; $("#submit-label").textContent = "Update workout"; $("#cancel-edit").hidden = false;
      window.scrollTo({ top: form.closest(".form-panel").offsetTop - 20, behavior: "smooth" });
    }
    function renderList() {
      $("#admin-count").textContent = `(${workouts.length})`;
      list.innerHTML = workouts.length ? workouts.map((workout) => `<div class="admin-item">
        <div><h3>${escapeHtml(workout.title)}</h3><p>${escapeHtml(workout.duration)} MIN · ${escapeHtml(labelCase(workout.category))}</p></div>
        <div class="admin-item-actions"><button type="button" data-edit="${workout.id}">Edit</button><button type="button" data-delete="${workout.id}">Delete</button></div>
      </div>`).join("") : "<p class='loading'>No workouts yet.</p>";
      $$("[data-edit]", list).forEach((button) => button.addEventListener("click", () => populate(workouts.find((item) => item.id === Number(button.dataset.edit)))));
      $$("[data-delete]", list).forEach((button) => button.addEventListener("click", async () => {
        if (!window.confirm("Delete this workout? This cannot be undone.")) return;
        try { await api(`/api/workouts/${button.dataset.delete}`, { method: "DELETE" }); await refresh(); showMessage("Workout deleted.", true); } catch (error) { showMessage(error.message); }
      }));
    }
    async function refresh() {
      try { workouts = await api("/api/workouts"); renderList(); } catch (error) { list.innerHTML = `<p class="loading">${escapeHtml(error.message)}</p>`; }
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault(); showMessage("");
      let exercises;
      try { exercises = JSON.parse($("#exercises").value); } catch (_error) { showMessage("Exercises must be valid JSON."); return; }
      const selectedEquipment = $$('input[name="equipment"]:checked').map((input) => input.value);
      const payload = { title: $("#title").value, category: $("#category").value, duration: Number($("#duration").value), program: $("#program").value, equipment: selectedEquipment, description: $("#description").value, video_url: $("#video-url").value, exercises };
      const id = $("#workout-id").value;
      try {
        await api(id ? `/api/workouts/${id}` : "/api/workouts", { method: id ? "PUT" : "POST", body: JSON.stringify(payload) });
        await refresh(); resetForm(); showMessage(id ? "Workout updated." : "Workout added.", true);
      } catch (error) { showMessage(error.message); }
    });
    $("#cancel-edit").addEventListener("click", resetForm);
    $("#refresh-workouts").addEventListener("click", refresh);
    refresh();
  }

  wireMenu(); wirePrint();
  if (page === "home") loadHome();
  if (page === "catalog") loadCatalog();
  if (page === "exercises") loadExercises();
  if (page === "programs") loadPrograms();
  if (page === "admin") loadAdmin();
}());
