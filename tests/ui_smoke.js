// Browser smoke test for the interface requirements in section 15 of the specification.
//
// Run it against a freshly loaded app (http://127.0.0.1:8000/) with the server running:
//   1. Open the app and reload the page so no quiz state exists.
//   2. Open the browser DevTools console and paste this whole file, then press Enter.
// It prints a PASS/FAIL table. It edits one weight (Q01 answer A, Druid) and restores it,
// so the configuration revision advances by 2 and the scoring ends up unchanged.
//
// The results are also left in window.__uiSmokeResults.

(async function run() {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const results = [];
  const check = (name, ok, info = "") => results.push({ test: name, result: ok ? "PASS" : "FAIL", info: String(info) });
  const api = async (path, opts) => (await fetch("/api/v1" + path, opts)).json();
  const btn = (text, i = 0) => [...document.querySelectorAll("button")].filter((b) => b.textContent.trim() === text)[i];
  const go = async (hash, ms = 1100) => { location.hash = hash; await sleep(ms); };
  // A fixed answer set for all thirty questions -> Druid / Feral Combat on the seed configuration (the same set as tests/conftest.py;
  // seven questions are pick-two, whose answers are pairs).
  const ANSWERS = { q01: "a", q02: "c", q03: "c", q04: "a", q05: "c", q06: "d", q07: "b+c", q08: "d", q09: "a+d", q10: "a", q11: "a+c", q12: "b", q13: "d", q14: "c",
    q15: "a+b", q16: "c", q17: "6", q18: "1", q19: "10", q20: "10", q21: "5", q22: "10", q23: "1", q24: "5", q25: "b+c", q26: "a+b", q27: "b+d", q28: "b", q29: "b", q30: "b" };
  const N = 30;
  /** Give the question currently on screen its response through the real controls. */
  const respond = async (q, value) => {
    if (q.type === "pick_two") {
      const want = value.split("+");
      for (const box of [...document.querySelectorAll("input[type=checkbox]:checked")]) { if (!want.includes(box.value)) { box.click(); await sleep(20); } }   // release first: a third box is locked
      for (const id of want) { const box = document.querySelector(`input[type=checkbox][value="${id}"]`); if (!box.checked) box.click(); await sleep(20); }
    } else {
      document.querySelector(`input[type=radio][value="${value}"]`).click();
    }
    await sleep(25);
  };

  // ---- 1. all thirty questions are accessible, in all three types -------------------------------------------------
  await go("#/", 500);
  const quiz = await api("/quiz");
  document.getElementById("begin").click(); await sleep(100);
  const dots = [...document.querySelectorAll(".dots button")];
  check("30 progress dots are rendered", dots.length === N, dots.length);
  let reachable = 0;
  const seen = new Set();
  for (let k = 0; k < N; k++) {
    document.querySelectorAll(".dots button")[k].click(); await sleep(30);
    const q = quiz.questions[k];
    const controls = q.type === "scale" ? document.querySelectorAll(".scale-opt input").length : document.querySelectorAll(".answer input").length;
    if (document.querySelector(".question").textContent === q.text && controls === (q.type === "scale" ? 10 : q.answers.length)) { reachable++; seen.add(q.type); }
  }
  check("every question opens with the right controls (4/2 answers, 10 ratings, or 4 pick-two items)", reachable === N, reachable);
  check("all three question types are present", seen.size === 3, [...seen].join(","));

  // ---- 2. navigation preserves answers ---------------------------------------------------------
  document.querySelectorAll(".dots button")[0].click(); await sleep(50);
  document.querySelectorAll(".answer input")[1].click(); await sleep(50);
  document.getElementById("next").click(); await sleep(50);
  document.getElementById("prev").click(); await sleep(50);
  check("Previous/Next keep the chosen answer", document.querySelectorAll(".answer input")[1].checked);

  // ---- 2b. pick-two locks after two choices; a scale rating is a single choice
  const pick = quiz.questions.find((q) => q.type === "pick_two");
  document.querySelectorAll(".dots button")[quiz.questions.indexOf(pick)].click(); await sleep(50);
  for (const id of ["a", "b", "c"]) { const box = document.querySelector(`input[type=checkbox][value="${id}"]`); if (!box.disabled) box.click(); await sleep(20); }
  check("Pick-two allows exactly two choices", document.querySelectorAll("input[type=checkbox]:checked").length === 2 && document.querySelector('input[type=checkbox][value="c"]').disabled);
  const scale = quiz.questions.find((q) => q.type === "scale");
  document.querySelectorAll(".dots button")[quiz.questions.indexOf(scale)].click(); await sleep(50);
  document.querySelector('.scale-opt input[value="7"]').click(); await sleep(50);
  check("A scale question holds one rating", document.querySelectorAll(".scale-opt input:checked").length === 1 && document.querySelector('.scale-opt input[value="7"]').checked);

  // ---- 3. the result cannot be revealed before completion --------------------------------------
  document.querySelectorAll(".dots button")[N - 1].click(); await sleep(50);
  await respond(quiz.questions[N - 1], ANSWERS[quiz.questions[N - 1].id]);
  check("Reveal is disabled while questions are unanswered", document.getElementById("reveal").disabled);
  check("No result is shown before completion", !document.querySelector(".result-hero"));

  // ---- 4. complete the quiz; the result agrees with the API ------------------------------------
  const answers = {};
  for (let k = 0; k < N; k++) {
    const q = quiz.questions[k];
    document.querySelectorAll(".dots button")[k].click(); await sleep(25);
    await respond(q, ANSWERS[q.id]);
    answers[q.id] = ANSWERS[q.id];
  }
  check("Reveal becomes enabled when all 30 are answered", !document.getElementById("reveal").disabled);
  document.getElementById("reveal").click(); await sleep(2200);
  const apiResult = await api("/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers, include_explanation: true }) });
  check("Result shows the class and specialization paragraphs", document.body.innerText.includes("What the Druid does") && document.body.innerText.includes(apiResult.result.specialization_overview.slice(0, 30)));
  check("Result class and specialization match the API",
    document.querySelector(".result-hero h1").textContent === apiResult.result.primary_class.name &&
    document.querySelector(".result-hero h2").textContent === apiResult.result.primary_specialization.name,
    `${document.querySelector(".result-hero h1").textContent} / ${document.querySelector(".result-hero h2").textContent}`);
  const shown = [...document.querySelectorAll(".bar-row")].map((r) => [r.querySelector(".bar-label").textContent, r.querySelector(".bar-val").textContent.replace("−", "-")]);
  const expected = apiResult.rankings.classes.map((c) => [c.name, (c.score > 0 ? "+" : "") + c.score.toFixed(2)]);
  check("Class ranking on screen equals the API ranking", JSON.stringify(shown) === JSON.stringify(expected), JSON.stringify(shown.slice(0, 3)));

  // ---- 5. the scoring inspector reproduces the API's intermediate values -----------------------
  await go("#/admin/inspector", 1800);
  const q01 = document.querySelector("tbody tr.clickable");
  const table = q01.closest("table");   // the per-question contribution table (not the trait table)
  const headers = [...table.querySelectorAll("thead th")].map((t) => t.textContent);
  const cells = [...q01.children].map((c) => c.textContent.replace("−", "-").replace("·", "0"));
  const col = (name) => cells[headers.indexOf(name)];
  const q = apiResult.explanation.questions[0];
  check("Inspector q01 Druid contribution equals the API (+1.50)", Number(col("Druid")) === q.class_contributions.druid.adjusted, col("Druid"));
  check("Inspector q01 Hunter contribution equals the API (+0.75)", Number(col("Hunter")) === q.class_contributions.hunter.adjusted, col("Hunter"));
  const foot = [...table.querySelector("tfoot tr").children].map((c) => c.textContent.replace("−", "-"));
  const colNames = headers.slice(2, 11);   // class columns, in ranking order
  const totalsMatch = colNames.length === 9 &&
    apiResult.rankings.classes.every((c, i) => colNames[i] === c.name && Math.abs(Number(foot[1 + i]) - c.score) < 0.006);
  check("Inspector column totals equal the API class scores", totalsMatch);

  // ---- 6. the administrator can modify and save weights ----------------------------------------
  const rev0 = (await api("/health")).config_revision;
  const druidScore = async () => (await api("/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers, include_explanation: true }) })).rankings.classes.find((c) => c.id === "druid").score;
  const before = await druidScore();
  await go("#/admin/questions", 1200);
  let card = document.querySelectorAll(".answer-card")[0];
  const input = card.querySelectorAll(".weights")[0].querySelector("input");
  const original = input.value;
  input.value = String(Number(original) + 1); input.dispatchEvent(new Event("input", { bubbles: true })); await sleep(100);
  check("Editing an input does not save anything", (await api("/health")).config_revision === rev0);
  [...card.querySelectorAll("button")].find((b) => b.textContent === "Save").click(); await sleep(1500);
  const after = await druidScore();
  check("Saved weight changes the score by +1 x (1 - 1/4) = +0.75", Math.abs(after - before - 0.75) < 1e-6, `${before} -> ${after}`);
  card = document.querySelectorAll(".answer-card")[0];
  [...card.querySelectorAll("button")].find((b) => b.textContent === "Restore original weights").click(); await sleep(300);
  card = document.querySelectorAll(".answer-card")[0];
  [...card.querySelectorAll("button")].find((b) => b.textContent === "Save").click(); await sleep(1500);
  check("Restoring the original weight restores the original score", Math.abs((await druidScore()) - before) < 1e-6);
  check("Configuration revision advanced by 2", (await api("/health")).config_revision === rev0 + 2, (await api("/health")).config_revision);

  console.table(results);
  const failed = results.filter((r) => r.result === "FAIL");
  console.log(failed.length ? `${failed.length} FAILED` : `All ${results.length} interface checks passed`);
  window.__uiSmokeResults = results;
})();
