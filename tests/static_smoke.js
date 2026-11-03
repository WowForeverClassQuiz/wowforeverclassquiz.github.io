// Browser smoke test for the static edition (the folder tools/build_static.py writes, served from any path).
//
//   1. python tools/build_static.py && python -m http.server --directory site 8080
//   2. Open http://localhost:8080/ in a browser, open the DevTools console, paste this whole file and press Enter.
//
// It answers all thirty questions through the real controls and checks the result. Results are left in
// window.__staticSmokeResults. The final PASS/FAIL table is printed to the console.

(async function run() {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const results = [];
  const check = (name, ok, info = "") => results.push({ test: name, result: ok ? "PASS" : "FAIL", info: String(info) });
  // The same fixed answer set as tests/conftest.py: Druid / Feral Combat on the seed configuration.
  const ANSWERS = { q01: "a", q02: "c", q03: "c", q04: "a", q05: "c", q06: "d", q07: "b+c", q08: "d", q09: "a+d", q10: "a", q11: "a+c", q12: "b", q13: "d", q14: "c",
    q15: "a+b", q16: "c", q17: "6", q18: "1", q19: "10", q20: "10", q21: "5", q22: "10", q23: "1", q24: "5", q25: "b+c", q26: "a+b", q27: "b+d", q28: "b", q29: "b", q30: "b" };
  const respond = async (type, value) => {
    if (type === "pick_two") {
      const want = value.split("+");
      for (const box of [...document.querySelectorAll("input[type=checkbox]:checked")]) { if (!want.includes(box.value)) { box.click(); await sleep(15); } }
      for (const id of want) { const box = document.querySelector(`input[type=checkbox][value="${id}"]`); if (!box.checked) box.click(); await sleep(15); }
    } else {
      document.querySelector(`input[type=radio][value="${value}"]`).click();
    }
    await sleep(20);
  };

  // ---- the page is the static edition -----------------------------------------------------------------------------
  const base = location.href.split("#")[0];
  check("page is in static mode", document.querySelector('meta[name="oracle-mode"]').content === "static");
  check("no Admin link is shown", !document.querySelector('[data-nav="admin"]'));
  check("the disclaimer footer is present", /Not affiliated with or endorsed by Blizzard/.test(document.querySelector(".sitefoot")?.textContent || ""));
  const data = await (await fetch(new URL("data/oracle.json", document.baseURI))).json();
  const quiz = data.quiz;
  check("the data file holds 30 questions of three kinds", quiz.questions.length === 30 && new Set(quiz.questions.map((q) => q.type)).size === 3);

  // ---- answer every question through the real controls -------------------------------------------------------------
  location.hash = "#/"; await sleep(300);
  document.getElementById("begin").click(); await sleep(100);
  for (let k = 0; k < quiz.questions.length; k++) {
    const q = quiz.questions[k];
    document.querySelectorAll(".dots button")[k].click(); await sleep(20);
    await respond(q.type, ANSWERS[q.id]);
  }
  check("Reveal is enabled once all 30 are answered", !document.getElementById("reveal").disabled);
  document.getElementById("reveal").click(); await sleep(2000);

  // ---- the result --------------------------------------------------------------------------------------------------
  const hero = document.querySelector(".result-hero");
  check("a result is shown", !!hero);
  check("class and specialization are Druid / Feral Combat", hero?.querySelector("h1").textContent === "Druid" && hero?.querySelector("h2").textContent === "Feral Combat",
    `${hero?.querySelector("h1").textContent} / ${hero?.querySelector("h2").textContent}`);
  const text = document.body.innerText;
  check("the 'what the class does' section is shown", text.includes("What the Druid does"));
  check("a build card is shown", text.includes("Your build"));
  check("the class ranking chart has nine rows", document.querySelectorAll(".bar-row").length === 9, document.querySelectorAll(".bar-row").length);
  check("the admin shortcut is hidden", !text.includes("Inspect in admin"));
  const requests = performance.getEntriesByType("resource").map((e) => e.name);
  check("nothing was requested from an /api/ path", !requests.some((u) => u.includes("/api/")), requests.filter((u) => u.includes("/api/")).join(","));
  check("every request stayed on this site", requests.every((u) => u.startsWith(location.origin)));

  // ---- admin routes are not reachable -------------------------------------------------------------------------------
  location.hash = "#/admin/config"; await sleep(500);
  check("an admin URL shows the quiz, not an admin page", !document.getElementById("adminnav") || document.getElementById("adminnav").hidden);

  console.table(results);
  const failed = results.filter((r) => r.result === "FAIL");
  console.log(failed.length ? `${failed.length} FAILED` : `All ${results.length} static-site checks passed`);
  window.__staticSmokeResults = results;
})();
