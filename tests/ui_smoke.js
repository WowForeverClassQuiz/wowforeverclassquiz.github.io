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
  // A fixed answer set for all thirty questions -> Feral Combat Druid on the seed configuration (the same set as tests/conftest.py;
  // two questions are pick-two (pairs), three are rankings (orderings) and three spend six points (splits)).
  const ANSWERS = { q01: "a", q02: "c", q03: "0-0-6-0", q04: "a", q05: "c", q06: "d", q07: "b>c>a>d", q08: "d", q09: "3-0-0-3", q10: "a", q11: "a>c>b>d", q12: "b", q13: "d", q14: "c",
    q15: "3-3-0-0", q16: "c", q17: "6", q18: "1", q19: "10", q20: "10", q21: "5", q22: "10", q23: "1", q24: "5", q25: "b+c", q26: "a>b>c>d", q27: "b+d", q28: "b", q29: "b", q30: "b" };
  const N = 30;
  // Confidence mode may ask any of the 103 questions, so this respondent answers each the way the model finds most likely for a Feral Combat Druid.
  const MODAL = {"q01": "a", "q02": "c", "q17": "1", "q03": "0-0-6-0", "q04": "a", "q25": "a+b", "q05": "c", "q18": "1", "q06": "d", "q07": "b>c>a>d", "q19": "10", "q08": "c", "q28": "b", "q09": "6-0-0-0", "q20": "10", "q10": "a", "q26": "a>b>c>d", "q11": "b>c>a>d", "q21": "10", "q12": "b", "q29": "a", "q13": "a", "q22": "10", "q14": "a", "q27": "a+d", "q15": "6-0-0-0", "q23": "1", "q16": "c", "q24": "1", "q30": "a", "q31": "b", "q32": "b>a>c>d", "q33": "b", "q34": "b>a>c>d", "q35": "a", "q36": "6-0-0-0", "q37": "a", "q38": "d>a>b>c", "q39": "b", "q40": "0-6-0-0", "q41": "b", "q42": "d>b>a>c", "q43": "c", "q44": "d>b>a>c", "q45": "a", "q46": "0-0-0-6", "q47": "b", "q48": "b>a>c>d", "q49": "a", "q50": "1", "q51": "b", "q52": "a", "q53": "a", "q54": "b", "q55": "d", "q56": "b", "q57": "c", "q58": "c", "q59": "d", "q60": "a", "q61": "d>c>a>b", "q62": "a>d>b>c", "q63": "d>a>b>c", "q64": "a>c>d>b", "q65": "d>c>a>b", "q66": "d>a>b>c", "q67": "d>a>b>c", "q68": "6-0-0-0", "q69": "0-0-0-6", "q70": "0-6-0-0", "q71": "0-0-0-6", "q72": "0-0-6-0", "q73": "0-0-0-6", "q74": "0-0-6-0", "q75": "b", "q76": "a", "q77": "b", "q78": "b", "q79": "b", "q80": "b", "q81": "c", "q82": "a", "q83": "b", "q84": "c", "q85": "b", "q86": "a", "q87": "c", "q88": "a", "q89": "c", "q90": "a", "q91": "b", "q92": "a", "q93": "a", "q94": "a", "q95": "a", "q96": "a", "q97": "a", "q98": "a", "q99": "a", "q100": "a", "q101": "a", "q102": "a", "q103": "a"};
  /** Give the question currently on screen its response through the real controls. */
  const respond = async (q, value) => {
    if (q.type === "pick_two") {
      const want = value.split("+");
      for (const box of [...document.querySelectorAll("input[type=checkbox]:checked")]) { if (!want.includes(box.value)) { box.click(); await sleep(20); } }   // release first: a third box is locked
      for (const id of want) { const box = document.querySelector(`input[type=checkbox][value="${id}"]`); if (!box.checked) box.click(); await sleep(20); }
    } else if (q.type === "ranking") {
      for (let box; (box = document.querySelector("input[type=checkbox]:checked")); ) { box.click(); await sleep(15); }          // undo any ranking first
      for (const id of value.split(">")) { document.querySelector(`input[type=checkbox][value="${id}"]`).click(); await sleep(15); }
    } else if (q.type === "allocation") {
      for (let b; (b = document.querySelector('[data-alloc$=":-"]:not(:disabled)')); ) { b.click(); await sleep(10); }          // take every point back first
      for (const [i, p] of value.split("-").map(Number).entries()) for (let k = 0; k < p; k++) { document.querySelector(`[data-alloc="${i}:+"]`).click(); await sleep(10); }
    } else {
      document.querySelector(`input[type=radio][value="${value}"]`).click();
    }
    await sleep(25);
  };

  // ---- 1. all thirty questions are accessible, in all five types -------------------------------------------------
  await go("#/", 500);
  const quiz = await api("/quiz");
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
      await respond(byId[ids[k]], ANSWERS[ids[k]]);
    }
  };
  const picked = () => document.querySelector('input[name="quiz-length"]:checked')?.value;
  let page;
  check("the intro offers confidence mode, short, medium and long, with confidence mode chosen first",
    [...document.querySelectorAll('input[name="quiz-length"]')].map((i) => i.value).join() === "adaptive,short,medium,long" && picked() === "adaptive", picked());
  check("each option says how many questions it has", ["10 questions", "20 questions", "30 questions"].every((t) => document.querySelector(".lengths").innerText.includes(t)));
  check("the front page says the stopping rule and the limit once each", ((document.getElementById("view").innerText.match(/90%/g) || []).length === 1) && ((document.getElementById("view").innerText.match(/\bstops?\b/g) || []).length === 1) && ((document.getElementById("view").innerText.match(/\bUp to\b/g) || []).length === 1), document.getElementById("view").innerText.match(/90%|stops?|Up to/g));
  // ---- confidence mode (the default): the Oracle picks each question and stops once it is sure ------------------------------------
  const idByText = Object.fromEntries(quiz.questions.map((q) => [q.text, q.id]));
  const until = async (test, ms = 4000) => { for (let t = 0; t < ms && !test(); t += 50) await sleep(50); return test(); };
  check("confidence mode is offered first and says how it works", /Confidence/.test(document.querySelector(".lengths").innerText) && /Up to 30 questions/.test(document.querySelector(".lengths").innerText));
  document.getElementById("begin").click(); await sleep(500);
  let asked = 0, sawLabel = "", sawDetail = "", moved = 0, movedOnChoice = 0, openedWith = "";
  const meters = [];
  const meter = () => document.querySelector(".certainty-bar")?.getAttribute("aria-valuenow");
  for (let guard = 0; guard < 40; guard++) {
    await until(() => document.querySelector(".question"));
    const q = byId[idByText[document.querySelector(".question").textContent]];
    const before = meter();
    meters.push(before);
    await respond(q, MODAL[q.id]);
    if (asked === 0) openedWith = q.id;
    asked++;
    await until(() => document.getElementById("reveal") || (document.getElementById("next") && !document.getElementById("next").disabled));
    sawLabel = document.getElementById("certainty-label")?.textContent || sawLabel;
    sawDetail = document.getElementById("certainty-detail")?.textContent || sawDetail;
    if (meter() !== before) movedOnChoice++;
    if (document.getElementById("reveal")) break;
    document.getElementById("next").click(); await sleep(150);
    if (meter() !== before) moved++;
  }
  check("the meter never moves when an answer is chosen, only when the next question comes", movedOnChoice === 0 && moved > 0, `moved on choice ${movedOnChoice}, moved on next ${moved}`);
  check("the meter also shows the class, specialization and role odds", /\d+% · .+ \d+% · .+ \d+%/.test(sawDetail), sawDetail);
  const openerIds = (await (await fetch("/api/v1/adaptive/next", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers: {} }) })).json()).openers;
  check("confidence mode opened with one of the personality questions", openerIds.length > 40 && openerIds.includes(openedWith), openedWith);
  check("the Oracle reads 0% before the first answer and its meter never falls", meters[0] === "0" && meters.every((v, i) => i === 0 || Number(v) >= Number(meters[i - 1])) && Number(meters[meters.length - 1]) > 0, meters.join(" "));
  check("it showed how sure it was while asking", /The Oracle is \d+% sure/.test(sawLabel) && !!document.querySelector(".certainty-bar .tick"), sawLabel);
  check("it stopped as soon as it was sure, well before the limit of thirty", asked >= 1 && asked < 15, asked);
  document.getElementById("reveal").click(); await sleep(2200);
  page = document.getElementById("view").innerText;
  check("the result is a confidence reading on the questions it asked", /Confidence reading/.test(page) && new RegExp(`${asked} questions`).test(page), asked);
  check("the result shows the class, specialization and role odds", /gives .+ \d+%, .+ \d+% and .+ \d+%/.test(document.getElementById("confidence-detail")?.textContent || ""), document.getElementById("confidence-detail")?.textContent);
  const shareMain = document.getElementById("share-main"), shareHero = document.querySelector(".result-hero");
  check("a prominent Share my results! button sits at the top of the result, inside the hero", !!shareMain && /Share my results!/.test(shareMain.textContent) && !!shareHero && shareHero.contains(shareMain) && shareMain.classList.contains("primary"));
  check("the share bar also offers the clipboard, X, Reddit and email", !!document.getElementById("share-top-copy") && ["share-x", "share-reddit", "share-email"].every((id) => (document.getElementById(id)?.getAttribute("href") || "").length > 20));
  document.getElementById("share-top-copy").click(); await sleep(500);
  check("copying from the top of the result says so", /Copied|Copy failed/.test(document.getElementById("toasts")?.innerText || ""), document.getElementById("toasts")?.innerText);
  check("the result states the model's confidence", /\d+% sure/.test(page) && (Number(/(\d+)% sure/.exec(page)[1]) >= 90), /(\d+)% sure/.exec(page)?.[0]);
  check("the confidence reading found Feral Combat Druid, like the full quiz", document.querySelector(".result-hero h1")?.textContent === "Druid" && document.querySelector(".result-hero h2")?.textContent === "Feral Combat");
  check("a confidence reading offers no sharpening step", !document.getElementById("refine"));
  document.getElementById("restart").click(); await sleep(100);

  document.querySelector('input[name="quiz-length"][value="short"]').click(); await sleep(100);
  check("choosing a fixed length selects it without repeating its size under the cards", document.querySelector('input[name="quiz-length"]:checked')?.value === "short" && (document.getElementById("view").innerText.match(/10 questions/g) || []).length === 1);
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
    await respond(byId[id], ANSWERS[id]);
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
  const dots = [...document.querySelectorAll(".dots button")];
  check("30 progress dots are rendered", dots.length === N, dots.length);
  let reachable = 0;
  const seen = new Set();
  for (let k = 0; k < N; k++) {
    document.querySelectorAll(".dots button")[k].click(); await sleep(30);
    const q = quiz.questions[k];
    const controls = q.type === "scale" ? document.querySelectorAll(".scale-opt input").length : q.type === "allocation" ? document.querySelectorAll(".alloc-row").length : document.querySelectorAll(".answer input").length;
    const view = document.getElementById("view").innerText;
    if (/\bnull\b/.test(view)) check(`question ${q.id} shows no stray "null"`, false, view.slice(0, 80));
    if (document.querySelector(".question").textContent === q.text && controls === (q.type === "scale" ? 10 : q.answers.length) && document.querySelector(".eyebrow-q")?.textContent) { reachable++; seen.add(q.type); }
  }
  check("every question opens with the right controls and a type label, and no stray \"null\"", reachable === N && !results.some((r) => r.result === "FAIL"), reachable);
  check("all five question types are present", seen.size === 5, [...seen].join(","));

  // ---- 2. navigation preserves answers ---------------------------------------------------------
  document.querySelectorAll(".dots button")[0].click(); await sleep(50);
  document.querySelectorAll(".answer input")[1].click(); await sleep(50);
  document.getElementById("next").click(); await sleep(50);
  document.getElementById("prev").click(); await sleep(50);
  check("Previous and Next keep the chosen answer", document.querySelectorAll(".answer input")[1].checked);

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
  const text = document.body.innerText;
  check("the build is drawn as three talent trees with talents filled in", document.querySelectorAll(".talent-tree").length === 3 && document.querySelectorAll(".talent.some, .talent.max").length > 5, document.querySelectorAll(".talent.some, .talent.max").length);
  check("the build is shown although it is not verified, and says so", /Draft \(not verified\)/.test(text) && !!document.querySelector(".talent-trees"));
  check("the build warns it may be out of date and gives the date of the talent data", /may not match the current World of Warcraft: Forever talent trees/.test(text) && /last updated\s*November 2, 2026/.test(text));
  check("the role in dungeons and raids, gear to look for and competing specs are shown", ["in dungeons", "in raids", "gear to look out for", "who competes with you for gear"].every((s) => text.toLowerCase().includes(s)));
  check("the class icon and a spell icon head the result", document.querySelectorAll(".hero-icons .wow-icon").length === 2, document.querySelectorAll(".hero-icons .wow-icon").length);
  check("the result page shows no stray \"null\"", !/\bnull\b/.test(text));
  check("Result class and specialization match the API",
    document.querySelector(".result-hero h1").textContent === apiResult.result.primary_class.name &&
    document.querySelector(".result-hero h2").textContent === apiResult.result.primary_specialization.name,
    `${document.querySelector(".result-hero h1").textContent} / ${document.querySelector(".result-hero h2").textContent}`);
  const shown = [...document.querySelectorAll(".bar-row")].map((r) => [r.querySelector(".bar-label").textContent, r.querySelector(".bar-val").textContent.replace("−", "-")]);
  const expected = apiResult.rankings.classes.map((c) => [c.name, (c.score > 0 ? "+" : "") + c.score.toFixed(2)]);
  check("Class ranking on screen equals the API ranking", JSON.stringify(shown) === JSON.stringify(expected), JSON.stringify(shown.slice(0, 3)));

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


  // ---- 7. the administrator can change what "share" copies ---------------------------------------------------------------------------
  const originalShare = (await api("/quiz")).share_template;
  await go("#/admin/profiles", 1500);
  const shareArea = document.querySelector('textarea[aria-label="Share format"]');
  check("Profiles has a share format editor with the current template and a preview", !!shareArea && shareArea.value === originalShare && /Druid/.test(document.querySelector(".share-preview")?.textContent || ""));
  check("every placeholder has an insert button", document.querySelectorAll(".share-fields button").length === 13);
  shareArea.value = "I am a {class} ({spec}) - {class_scores} - {link}"; shareArea.dispatchEvent(new Event("input", { bubbles: true })); await sleep(100);
  check("the preview follows the template", /I am a Druid \(Feral Combat\) - Druid \+13\.39/.test(document.querySelector(".share-preview").textContent), document.querySelector(".share-preview").textContent);
  const shareCard = shareArea.closest("section");
  [...shareCard.querySelectorAll("button")].find((b) => b.textContent === "Save").click(); await sleep(1500);
  check("the saved template reaches participants", (await api("/quiz")).share_template === "I am a {class} ({spec}) - {class_scores} - {link}");
  const bad = await fetch("/api/v1/quiz", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: (await api("/health")).config_revision, share_template: "Hi {nobody}" }) });
  check("a template with an unknown placeholder is refused", bad.status === 400, bad.status);
  const area2 = document.querySelector('textarea[aria-label="Share format"]');
  [...area2.closest("section").querySelectorAll("button")].find((b) => b.textContent === "Restore the original").click(); await sleep(100);
  [...area2.closest("section").querySelectorAll("button")].find((b) => b.textContent === "Save").click(); await sleep(1500);
  check("restoring the original brings the original template back", (await api("/quiz")).share_template === originalShare);


  // ---- 8. the administrator can change how confidence mode behaves ---------------------------------------------------------------------
  const thresholdNow = async () => (await (await fetch("/api/v1/adaptive/next", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers: {} }) })).json()).threshold;
  await go("#/admin/profiles", 1500);
  let conf = document.querySelector('input[aria-label="Stop at confidence (%)"]');
  check("Profiles has the confidence-mode settings with the current values", !!conf && conf.value === "90" && document.querySelector('input[aria-label="Minimum questions (1 means none)"]')?.value === "1" && document.querySelector('input[aria-label="Maximum questions"]')?.value === "30", conf?.value);
  conf.value = "95"; conf.dispatchEvent(new Event("input", { bubbles: true })); await sleep(100);
  [...conf.closest("section").querySelectorAll("button")].find((b) => b.textContent === "Save").click(); await sleep(1500);
  check("saving the threshold changes what the Oracle waits for", (await thresholdNow()) === 0.95);
  conf = document.querySelector('input[aria-label="Stop at confidence (%)"]');
  conf.value = "90"; conf.dispatchEvent(new Event("input", { bubbles: true })); await sleep(100);
  [...conf.closest("section").querySelectorAll("button")].find((b) => b.textContent === "Save").click(); await sleep(1500);
  check("restoring the threshold works", (await thresholdNow()) === 0.9);

  console.table(results);
  const failed = results.filter((r) => r.result === "FAIL");
  console.log(failed.length ? `${failed.length} FAILED` : `All ${results.length} interface checks passed`);
  window.__uiSmokeResults = results;
})();
