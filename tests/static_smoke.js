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
  // The same fixed answer set as tests/conftest.py: a Feral Combat Druid on the seed configuration.
  const ANSWERS = { q01: "a", q02: "c", q03: "0-0-6-0", q04: "a", q05: "c", q06: "d", q07: "b>c>a>d", q08: "d", q09: "3-0-0-3", q10: "a", q11: "a>c>b>d", q12: "b", q13: "d", q14: "c",
    q15: "3-3-0-0", q16: "c", q17: "6", q18: "1", q19: "10", q20: "10", q21: "5", q22: "10", q23: "1", q24: "5", q25: "b+c", q26: "a>b>c>d", q27: "b+d", q28: "b", q29: "b", q30: "b" };
  const respond = async (type, value) => {
    if (type === "pick_two") {
      const want = value.split("+");
      for (const box of [...document.querySelectorAll("input[type=checkbox]:checked")]) { if (!want.includes(box.value)) { box.click(); await sleep(15); } }
      for (const id of want) { const box = document.querySelector(`input[type=checkbox][value="${id}"]`); if (!box.checked) box.click(); await sleep(15); }
    } else if (type === "ranking") {
      for (let box; (box = document.querySelector("input[type=checkbox]:checked")); ) { box.click(); await sleep(15); }          // undo any ranking first
      for (const id of value.split(">")) { document.querySelector(`input[type=checkbox][value="${id}"]`).click(); await sleep(15); }
    } else if (type === "allocation") {
      for (let b; (b = document.querySelector('[data-alloc$=":-"]:not(:disabled)')); ) { b.click(); await sleep(10); }          // take every point back first
      for (const [i, p] of value.split("-").map(Number).entries()) for (let k = 0; k < p; k++) { document.querySelector(`[data-alloc="${i}:+"]`).click(); await sleep(10); }
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
  check("the data file holds 30 questions of five kinds", quiz.questions.length === 30 && new Set(quiz.questions.map((q) => q.type)).size === 5);

  // ---- answer every question through the real controls -------------------------------------------------------------
  location.hash = "#/"; await sleep(300);
  // ---- the first page: credit line with version, build and date; a way to the class pages -----------------------------------------
  const introText = document.getElementById("view").innerText;
  const credit = document.querySelector(".credit");
  const creditLink = credit?.querySelector("a");
  check("the first page credits the developer, with a link to github.com/Anibru", !!credit && /Developed by Anibru/.test(credit.textContent) && creditLink?.href === "https://github.com/Anibru", credit?.textContent);
  check("the credit line gives the version, build number and date", /v\d+\.\d+\.\d+/.test(credit?.textContent || "") && /build \S+/.test(credit?.textContent || "") && /(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}/.test(credit?.textContent || ""), credit?.textContent);
  check("the old 'scored right here in your browser' line is gone", !/scored right here in your browser/.test(introText) && !/Nothing is stored on the server/.test(introText));
  check("the first page offers the classes", !!document.getElementById("browse-classes"));
  document.getElementById("browse-classes").click(); await sleep(700);
  check("the classes page lists nine classes, each linking to its own page", document.querySelectorAll(".spec-class").length === 9 && document.querySelectorAll("a.spec-class-head").length === 9);
  document.querySelector("a.spec-class-head").click(); await sleep(700);
  check("a class page shows what the class does and its three specializations", /What the .* does/.test(document.getElementById("view").innerText) && document.querySelectorAll(".spec-list .spec-tile").length === 3);
  const classHeading = document.querySelector(".spec-page h1")?.textContent;
  document.querySelector('a[rel="next"]').click(); await sleep(700);
  check("Next on a class page moves to the next class", !!document.querySelector(".spec-page h1") && document.querySelector(".spec-page h1").textContent !== classHeading);
  location.hash = "#/"; await sleep(500);

  // ---- 0. the three quiz lengths: pick, answer, read the result, then sharpen it with the extra questions -----------------------
  const byId = Object.fromEntries(quiz.questions.map((q) => [q.id, q]));
  const lengthOf = Object.fromEntries(quiz.lengths.map((l) => [l.id, l]));
  const answerQuestions = async (ids) => {
    for (let k = 0; k < ids.length; k++) {
      document.querySelectorAll(".dots button")[k].click(); await sleep(20);
      await respond(byId[ids[k]].type, ANSWERS[ids[k]]);
    }
  };
  const picked = () => document.querySelector('input[name="quiz-length"]:checked')?.value;
  let page;
  check("the intro offers confidence mode, short, medium and long, with confidence mode chosen first",
    [...document.querySelectorAll('input[name="quiz-length"]')].map((i) => i.value).join() === "adaptive,short,medium,long" && picked() === "adaptive", picked());
  check("each option says how many questions it has", ["10 questions", "20 questions", "30 questions"].every((t) => document.querySelector(".lengths").innerText.includes(t)));
  check("the intro line explains the chosen mode", /At least 10 questions, then the Oracle stops as soon as it is 90% sure/.test(document.getElementById("view").innerText));
  // ---- confidence mode (the default): the Oracle picks each question and stops once it is sure ------------------------------------
  const idByText = Object.fromEntries(quiz.questions.map((q) => [q.text, q.id]));
  const until = async (test, ms = 4000) => { for (let t = 0; t < ms && !test(); t += 50) await sleep(50); return test(); };
  check("confidence mode is offered first and says how it works", /Confidence/.test(document.querySelector(".lengths").innerText) && /10–30 questions/.test(document.querySelector(".lengths").innerText));
  document.getElementById("begin").click(); await sleep(500);
  let asked = 0, sawLabel = "";
  for (let guard = 0; guard < 40; guard++) {
    await until(() => document.querySelector(".question"));
    const q = byId[idByText[document.querySelector(".question").textContent]];
    await respond(q.type, ANSWERS[q.id]);
    asked++;
    await until(() => document.getElementById("reveal") || (document.getElementById("next") && !document.getElementById("next").disabled));
    sawLabel = document.getElementById("certainty-label")?.textContent || sawLabel;
    if (document.getElementById("reveal")) break;
    document.getElementById("next").click(); await sleep(150);
  }
  check("it showed how sure it was while asking", /The Oracle is \d+% sure/.test(sawLabel) && !!document.querySelector(".certainty-bar .tick"), sawLabel);
  check("it asked at least ten questions and stopped before the whole quiz", asked >= 10 && asked < 30, asked);
  document.getElementById("reveal").click(); await sleep(2200);
  page = document.getElementById("view").innerText;
  check("the result is a confidence reading on the questions it asked", /Confidence reading/.test(page) && new RegExp(`${asked} questions`).test(page), asked);
  check("the result states the model's confidence", /\d+% sure/.test(page) && (Number(/(\d+)% sure/.exec(page)[1]) >= 90), /(\d+)% sure/.exec(page)?.[0]);
  check("the confidence reading found Feral Combat Druid, like the full quiz", document.querySelector(".result-hero h1")?.textContent === "Druid" && document.querySelector(".result-hero h2")?.textContent === "Feral Combat");
  check("a confidence reading offers no sharpening step", !document.getElementById("refine"));
  document.getElementById("restart").click(); await sleep(100);

  document.querySelector('input[name="quiz-length"][value="short"]').click(); await sleep(100);
  check("choosing a fixed length changes the intro line", /10 questions\. There are no right answers/.test(document.getElementById("view").innerText));
  document.getElementById("begin").click(); await sleep(100);
  check("the short quiz has ten questions", document.querySelectorAll(".dots button").length === 10 && /Question 1 of 10/.test(document.getElementById("view").innerText));
  await answerQuestions(lengthOf.short.question_ids);
  document.getElementById("reveal").click(); await sleep(2000);
  page = document.getElementById("view").innerText;
  check("the short reading says it is short and rests on ten questions", /Short reading/.test(page) && /10 questions/.test(page));
  check("the short result offers ten more questions", !!document.getElementById("refine") && /10 more questions/.test(document.getElementById("refine").textContent));
  document.getElementById("refine").click(); await sleep(150);
  check("sharpening keeps the ten answers and asks ten more", document.querySelectorAll(".dots button").length === 20 && document.querySelectorAll(".dots button.done").length === 10 &&
    /Question 1 of 20/.test(document.getElementById("view").innerText) === false);
  const rest = lengthOf.medium.question_ids.filter((id) => !lengthOf.short.question_ids.includes(id));
  for (const id of rest) {
    const k = lengthOf.medium.question_ids.indexOf(id);
    document.querySelectorAll(".dots button")[k].click(); await sleep(20);
    await respond(byId[id].type, ANSWERS[id]);
  }
  document.querySelectorAll(".dots button")[lengthOf.medium.question_ids.length - 1].click(); await sleep(50);      // Reveal sits on the last question
  document.getElementById("reveal").click(); await sleep(2000);
  page = document.getElementById("view").innerText;
  check("the sharpened result is a medium reading on twenty questions", /Medium reading/.test(page) && /20 questions/.test(page));
  check("a medium result offers ten more", /10 more questions/.test(document.getElementById("refine")?.textContent || ""));
  document.getElementById("restart").click(); await sleep(100);
  check("restarting offers the lengths again, confidence mode first", picked() === "adaptive");
  document.querySelector('input[name="quiz-length"][value="long"]').click(); await sleep(100);

  document.getElementById("begin").click(); await sleep(100);
  for (let k = 0; k < quiz.questions.length; k++) {
    const q = quiz.questions[k];
    document.querySelectorAll(".dots button")[k].click(); await sleep(20);
    if (/\bnull\b/.test(document.getElementById("view").innerText)) check(`question ${q.id} shows no stray "null"`, false);
    await respond(q.type, ANSWERS[q.id]);
  }
  check("Reveal is enabled once all 30 are answered", !document.getElementById("reveal").disabled);
  document.getElementById("reveal").click(); await sleep(2000);

  // ---- the result --------------------------------------------------------------------------------------------------
  const hero = document.querySelector(".result-hero");
  check("a result is shown", !!hero);
  check("class and specialization are Feral Combat Druid", hero?.querySelector("h1").textContent === "Druid" && hero?.querySelector("h2").textContent === "Feral Combat",
    `${hero?.querySelector("h1").textContent} / ${hero?.querySelector("h2").textContent}`);
  const text = document.body.innerText;
  check("the 'what the class does' section is shown", text.includes("What the Druid does"));
  check("a build card is shown", text.includes("Your build"));
  check("the build is drawn as three talent trees with talents filled in", document.querySelectorAll(".talent-tree").length === 3 && document.querySelectorAll(".talent.some, .talent.max").length > 5, document.querySelectorAll(".talent.some, .talent.max").length);
  check("the build is shown although it is not verified, and says so", /Draft \(not verified\)/.test(text) && !!document.querySelector(".talent-trees"));
  check("the build warns it may be out of date and gives the date of the talent data", /may not match the current World of Warcraft: Forever talent trees/.test(text) && /last updated\s*November 2, 2026/.test(text));
  check("the role in dungeons and raids, gear to look for and competing specs are shown", ["in dungeons", "in raids", "gear to look out for", "who competes with you for gear"].every((s) => text.toLowerCase().includes(s)));
  check("the class icon and a spell icon head the result", document.querySelectorAll(".hero-icons .wow-icon").length === 2, document.querySelectorAll(".hero-icons .wow-icon").length);
  check("the result page shows no stray \"null\"", !/\bnull\b/.test(text));
  check("the class ranking chart has nine rows", document.querySelectorAll(".bar-row").length === 9, document.querySelectorAll(".bar-row").length);
  check("the admin shortcut is hidden", !text.includes("Inspect in admin"));
  const requests = performance.getEntriesByType("resource").map((e) => e.name);
  check("nothing was requested from an /api/ path", !requests.some((u) => u.includes("/api/")), requests.filter((u) => u.includes("/api/")).join(","));
  check("every request stayed on this site, apart from the class and spell icons", requests.every((u) => u.startsWith(location.origin) || u.startsWith("https://wow.zamimg.com/images/wow/icons/")), requests.filter((u) => !u.startsWith(location.origin) && !u.includes("zamimg.com")).join(","));

  // ---- the "also in the stars" cards open specialization pages, which can be paged through; the result can be shared -----------------
  const altLinks = [...document.querySelectorAll(".alt-link")];
  check("both 'also in the stars' cards link to a specialization page", altLinks.length === 2 && altLinks.every((a) => /^#\/specs\/[a-z]+\/[a-z_]+$/.test(a.getAttribute("href"))), altLinks.map((a) => a.getAttribute("href")).join(","));
  const share = document.getElementById("share-text");
  check("the share blurb names the class and specialization, the numbers and a link", !!share && /Feral Combat Druid/.test(share.value) && /Class scores: Druid \+[\d.]+/.test(share.value) && /https?:\/\//.test(share.value), share?.value);
  check("a button copies the blurb", !!document.getElementById("share-copy"));
  const onResult = document.getElementById("view").innerText;
  check("the build shows neither 'how this was put together' nor its source", !/How this was put together/i.test(onResult) && !/Source:/.test(onResult));
  const altText = altLinks[0].innerText;
  location.hash = altLinks[0].getAttribute("href"); await sleep(900);
  const specName = document.querySelector(".spec-page h2")?.textContent || "";
  const onSpec = document.getElementById("view").innerText;
  check("the first card opens that specialization's page", !!document.querySelector(".spec-page") && specName !== "" && altText.includes(specName), specName);
  check("the page shows the defining traits with the participant's own scores", document.querySelectorAll(".trait-list li").length === 3 && document.querySelectorAll(".trait-score").length === 3);
  check("the page has what the class does, the role and gear guide and a drawn build", /What the .* does/.test(onSpec) && /Role and gear for a/.test(onSpec) && document.querySelectorAll(".talent-tree").length === 3);
  check("the page says how it relates to the result and does not call the build 'yours'", /Also in the stars/.test(onSpec) && !/Your build/.test(onSpec), "");
  check("the page has no 'how this was put together' or source line", !/How this was put together/i.test(onSpec) && !/Source:/.test(onSpec));
  document.querySelector('a[rel="next"]').click(); await sleep(700);
  const nextName = document.querySelector(".spec-page h2")?.textContent;
  check("Next moves to a different specialization", !!nextName && nextName !== specName, nextName);
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true })); await sleep(700);
  check("the left arrow key goes back", document.querySelector(".spec-page h2")?.textContent === specName);
  location.hash = "#/specs"; await sleep(700);
  check("the index lists all 27 specializations in nine classes", document.querySelectorAll(".spec-class").length === 9 && document.querySelectorAll(".spec-tile").length === 27);
  [...document.querySelectorAll("a")].find((a) => /Back to my result/.test(a.textContent)).click(); await sleep(700);
  check("back to my result shows the result again", !!document.querySelector(".result-hero"));

  // ---- admin routes are not reachable -------------------------------------------------------------------------------
  location.hash = "#/admin/config"; await sleep(500);
  check("an admin URL shows the quiz and no admin page", !document.getElementById("adminnav") || document.getElementById("adminnav").hidden);

  console.table(results);
  const failed = results.filter((r) => r.result === "FAIL");
  console.log(failed.length ? `${failed.length} FAILED` : `All ${results.length} static-site checks passed`);
  window.__staticSmokeResults = results;
})();
