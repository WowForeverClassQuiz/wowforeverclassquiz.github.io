# World of Warcraft: Forever Character Oracle

A personality quiz that recommends a **class, specialization and talent build** for
*World of Warcraft: Forever*. By default it runs in **confidence mode**: it asks the most informative questions one at a time and stops once it is 90% sure of one
specialization (there is no minimum, and it never asks more than 30). It draws on a pool of 103 questions, 73 of which only this mode asks. Participants can instead choose a fixed **short (10), medium (20) or long (30)** reading; the questions are of five kinds (pick one, rate 1-10, pick two,
rank four, spend six points) and are scored with a transparent, deterministic algorithm. It comes in two editions that share one scoring engine:

* **Local app** (run with Python, below): the quiz plus an administrative dashboard. Nothing leaves your machine.
  * *Participant interface* (`/`): the quiz, a result reveal, class and specialization pages, a build card, and a shareable blurb.
  * *Administrative interface* (`/#/admin/...`): question editor, scoring inspector, simulation,
    profile editor, build editor, and configuration management (export, import, reset, history).
  * *REST API* (`/api/v1`): everything the interface does, documented at `/docs`.
* **Static website** (`python tools/build_static.py`): only the quiz, as plain files for GitHub Pages or any static host,
  scored in the visitor's browser. See [Publish it as a website](#publish-it-as-a-website).

Every specialization of every class can be the result. Under random answers every class is chosen equally often (to within
about 0.3 percentage points) and each specialization wins at least 23% of its class's results; see [Balance](#balance-algorithm-130).

## Status of the talent builds (read this)

The scoring engine, API and interface are complete and tested. **The talent data is a hand-built draft, and no build is verified.**

* **Every result shows a build**, even though none is verified: the draft catalog and 27 draft builds ship with the application
  ([app/drafts.py](app/drafts.py)) and are part of the seed, so a new database and the published website both have them. Each build is
  labelled "Draft (not verified)", the page says it **may not match the current World of Warcraft: Forever talent trees**, and it gives the
  date the talent tree data was last updated (**November 2, 2026**, the date of Blizzard's Beta Development Notes it reflects; the data was
  compiled on November 3, 2026).
* The build is drawn as the class's **three talent trees**, laid out like the in-game talent window: rows by tier, a rank badge on every
  talent (`2/5`), unspent talents dimmed, maxed talents green, with the tree of your specialization highlighted. The source data gives each
  talent's row and ranks but not its exact column, so a talent's position *within* its row is approximate; the page says so.
* Each result also carries a **role and gear guide** for the specialization ([app/spec_guides.py](app/spec_guides.py)): its role in dungeons and in
  raids, what to look out for on gear, and which specializations compete with it for similar gear. It is general guidance on how those roles and
  gear types work in Classic-style World of Warcraft, written for this project. It was not read from Forever's item list, and the page says so.
* The application ships **no data read from the World of Warcraft: Forever client**. [catalog/forever-talents-draft-2026-11-03.json](catalog/forever-talents-draft-2026-11-03.json)
  is a **draft catalog of all 27 trees (468 talents)**, assembled on 2026-11-03 from GuildOrder's Forever talent pages (reviewed October 2026) plus
  Blizzard's *Beta Development Notes, updated November 2*, which lists changes only. `catalog/build_forever_draft.py` rebuilds it and checks
  109 structural claims from the notes; [catalog/RECONCILIATION.md](catalog/RECONCILIATION.md) records which the source already
  contained (62) and which were applied by hand (47: Rogue, Warrior and Shaman). You can also import a catalog in *Admin > Build Editor > Talent data*.
* Draft data is flagged `data_status: "draft"`. Allocations are validated against it (point total, ranks, row gates, and the
  prerequisites the notes state), but **the server refuses to mark any build `verified` against draft data**.
* Known gaps in the draft: the source shows no talent-to-talent prerequisites (only 6 are recorded, from the notes); `column`
  is list order and gives no real grid position; percentage-only changes are not modelled; the pages were read through a summarising
  fetch tool; and a few notes entries are ambiguous (listed in the ledger). Replace the draft with a client export when you have one.
* [catalog/forever-builds-draft-2026-11-03.json](catalog/forever-builds-draft-2026-11-03.json) holds **27 best-guess leveling and general-PvE
  builds, one per specialization**, each a full 51-point allocation with a legal point-by-point leveling order. They are in the seed already; to
  add them to a database whose configuration you have edited (it writes one revision and backs up the old configuration first):

  ```bash
  python catalog/install_drafts.py
  ```

  How they were made: RankedBoost's WoW Forever build pages (build 1.60.1.70707, "updated November 2") are the model: its leveling build
  where one exists, otherwise its PvE damage, healing or tank build. Rogue Subtlety has only a PvP source, so that build is my own
  extrapolation and the least trustworthy. RankedBoost still uses some pre-patch talents, so every build was remapped onto the new
  trees (removed talents dropped, ranks capped, moved talents taken from their new tree). Reddit and other forums could not be read by the
  tools I had, so no community consensus is reflected beyond RankedBoost and the guide sites. Each build is `draft`, is checked as *legal* on the
  draft catalog, and says so on its record; that shows the allocation is legal in unverified data and says nothing about its quality.
* The test suite also uses a small *synthetic* catalog to exercise the validator. Its names are invented and it is never loaded
  by the application.

**Class and spell icons.** Each result page shows the class emblem and an iconic spell of the specialization (for example Cat Form for Feral Combat),
and the class icon beside each class in the score chart. These are Blizzard's artwork. They are **not stored in this repository**: visitors' browsers load
them from Wowhead's public icon server (`wow.zamimg.com`), which means that server sees the visitor's address when an icon loads. If an icon cannot
load, a coloured badge takes its place. To host them yourself or drop them, change `ICON_BASE` in [app/static/icons.js](app/static/icons.js).

## Confidence mode, and the maths

**Confidence mode** (the default) works like a twenty-questions game. After each answer the Oracle works out how likely each of the 27 pairs of class and specialization is,
picks the unanswered question that will tell it the most, and stops as soon as its confidence in the specialization the scoring currently recommends has reached **90%**. There is no
minimum number of questions, and it never asks more than 30. A certainty meter shows how sure it was when each question was put to you (it starts at 0%, rises with every question, and moves when you go on to the next question, not when you
choose an answer), with the odds of the class, the specialization and the role beside it, and you can also *Reveal now* at whatever certainty
it has reached. The result then says which mode it was, how many questions it rests on and the model's confidence ("93% sure"). Simulated respondents need about 6
questions on average (a median of 5, and 9 or fewer for nine in ten); people who answer at random run to the limit about a third of the time and get a lower confidence
and a weaker label.

* **How the probability is defined.** A logit choice model: a person of each type is assumed to pick responses with probability proportional to exp(their contribution
  to that type's scores). Bayes' rule over the 27 types then gives the probabilities; the quiz's own class and specialization scores *are* the evidence in it. The
  "probabilities" are exact inside the model, and the model is an assumption about how people answer (its two sharpness constants say how consistently). Read
  "90% sure" as "the answers are as consistent with one specialization as the model requires"; no study of real respondents backs the figure.
* **The first question and the pace.** The first question is drawn at random from the personality questions (the thirty fixed-quiz questions and the class-separating ones), so two readings do not
  begin the same way; after that every question is chosen by information gain. The confidence is scaled by the number of questions asked: after n questions it counts for n / (n + k) of what the
  model says (k = 1 by default: 50% after one question, 91% after ten, 97% after thirty), so a reading needs about ten questions on average and an inconsistent respondent is not told "90% sure"
  after three lucky answers. The figure the Oracle states while it asks is the best certainty reached so far, scaled the same way, so it rises with every question even when a surprising answer
  lowers the current certainty (the stopping rule tests the current one, and a finished reading states it). Near the threshold it is compressed smoothly so it never claims 90% before the Oracle has it.
  Both the scaling (Profiles & Settings, "Question scaling k", 0 turns it off) and the random opening can be changed. In simulation, for respondents 70% as consistent as the model assumes, k = 1 makes the reading exactly right 98.5% of the time
  against 86.0% without the scaling, at the cost of about five more questions (11.7 against 6.2); the stated 91% is then a little below what the readings earn.
* **What "sure" means.** The confidence is not only the probability of one specialization. Every type earns credit toward the recommendation: 1 for the recommended specialization,
  half for another specialization of its class and half for one with a similar role (tank, healer, melee damage or ranged damage), the larger of the two when both apply. A person whose three Mage
  specializations are all gaining, or who sits between Protection Paladin and Protection Warrior, therefore reaches 90% sooner. The probabilities of the specialization, the class and the role are shown
  beside the figure, and the two credits are in Profiles & Settings (set both to 0 for the specialization's probability alone). It is an expected credit, not a probability of the exact specialization;
  in simulation it saves about half a question to two questions, at a cost of a few points of exact-specialization accuracy for inconsistent respondents.
* **The question pool.** 103 questions: the thirty of the fixed quizzes plus q31 to q103, which only confidence mode asks
  (*Confidence mode only* under *Asked in* in the Question Editor). The thirty separate classes well and the specializations of one class poorly: Arcane against Frost Mage
  had almost no evidence behind it, and every one of the weakest pairs was within a class. The twenty added questions are two for each class (a choice with an answer per
  specialization, and a ranking or six-point split) plus a role question and a distance question. They carry slightly less evidence per question than the originals, so the
  shorter quizzes come from covering the weak pairs. No weight was made heavier to get there. The short, medium and long quizzes do not ask them and are unchanged.
  q51 to q74 ([app/seed_classes.py](app/seed_classes.py)) are personality questions in which every answer belongs to a different class (ten choices, seven rankings, seven six-point splits), written for a
  person torn among their three leading classes. They carry about 20% more class evidence per question than the originals, because each answer names a class no other answer does; every trio of
  classes has at least four of them that tell all three apart. Raising the question limit does not make the Oracle more right, only more sure (it was tested), so the limit stays at 30.
  q75 to q103 ([app/seed_tiebreakers.py](app/seed_tiebreakers.py)) are **tiebreakers**: forced choices between the finalists, such as "as a protector, do you trust more in the light to guard, the
  structure and workmanship of steel, or the strength of the wild?" (Protection Paladin, Protection Warrior or Feral Combat Druid) and "as a follower of the light, do you prefer to seek retribution,
  stand in judgement, or spread forgiveness?" (the three Paladin specializations). There is one for each class, eight for groups that share a role (tanks, two groups of healers, two of melee damage,
  three of casters) and twelve two-way questions for the closest pairs. Each lists its finalists, and it is asked only when they together hold at least 80% of the probability (a setting), so it comes
  up when the reading has narrowed to those candidates; two of three finalists are enough, so a three-way question also serves when only the top two remain. In simulation they are asked in about half of
  all readings and save up to half a question with no change in accuracy; a forced choice separates its finalists up to 40% more sharply than the comparable four-way questions.
* **Choosing the next question.** The question with the largest expected information gain over all 27 types. Six rules that aim each question at the current leading
  specialization were simulated against it (a table in the PDF); none needed fewer questions, because once one specialization leads, the most informative question is
  already the one that separates it from its closest rivals.
* **How far to trust the figure.** Simulated respondents who are 70% as consistent as the model assumes are right about 88% of the time when the Oracle says about 94%, and
  respondents 50% as consistent about 70% when it says 91%. Raising the confidence threshold in the settings narrows that gap at the cost of more questions.
* **Settings.** Admin > Profiles & Settings: whether the mode is offered, the minimum (1 means none) and maximum number of questions, the confidence threshold and the two sharpness
  values. The browser edition runs the same code as the server (a test compares every step of whole question paths), and `POST /api/v1/adaptive/next` is the API
  behind it.
* **The maths document.** [docs/oracle-math.pdf](docs/oracle-math.pdf) explains every calculation behind a selection (response tables, baseline subtraction, class,
  trait and specialization scores, ties, confidence labels, quiz lengths, the balance tables, the confidence model, its question choice and stopping rule, a worked
  example, assumptions and limits) with tables of the numbers, and lists every question and answer weight. It is built from the live configuration and fixed-seed
  simulations: rebuild it after changing anything with `python tools/build_math_pdf.py` (about 20 seconds; needs `pip install -r requirements-dev.txt`). The published
  website carries a copy at `/oracle-math.pdf`.

## Class and specialization pages, and sharing

* **Class pages and specialization pages.** The first page has a *Browse the classes and specializations* button (and the navigation bar a *Classes* link). It opens an
  index of the nine classes; each class has its own page (what it does, its three specializations), and each specialization has a page: the **traits that
  define it** (primary, secondary and so on, with how much each counts and, once you have a result, your own score in each), what it does, its role and gear
  guide and its build. Page through with *Previous* and *Next* or the left and right arrow keys. The **Also in the stars** cards on a result open the page of the
  runner-up specialization and of your next-closest specialization in your class. Pages are served by `GET /api/v1/specializations/{class}/{spec}` and are
  carried in the static site's data.
* **Share your result.** At the top of the result page, inside the hero, is a prominent **Share my results!** button. It opens the device's share sheet where there is one (phones, and
  Safari and Edge on desktop) and otherwise copies the blurb to the clipboard; beside it are *Copy the text* and links that post the blurb on X, Reddit or in an email (the blurb goes to those sites
  only when you click, and the quiz itself still sends nothing). Further down, a *Share your result* box shows the blurb: a short text with your class, specialization, your three best class scores and a link
  to the quiz, which *Copy to share* puts on the clipboard (and *Share…* opens the share sheet). An administrator can change the wording
  in **Admin > Profiles > Share format**: write the text you like and put `{placeholders}` where details of the result should go (`{class}`, `{spec}`,
  `{spec_score}`, `{class_scores}`, `{traits}`, `{confidence}`, `{questions}`, `{quiz_length}`, `{also_class}`, `{also_spec}`, `{next_spec}`, `{title}`, `{link}`);
  a live preview uses a sample result. The format is saved with the configuration (`quiz.share_template`), so it is exported, imported and published with the
  website like everything else. A template with an unknown placeholder or a stray brace is refused.
* **Version stamp.** The first page ends with *Developed by Anibru* (linking to https://github.com/Anibru), the version (`APP_VERSION` in
  [app/version.py](app/version.py); see [CHANGELOG.md](CHANGELOG.md)), the build number and the date. On the published site the build number is the GitHub Actions run
  number and the commit is the short hash of the commit that was built; run locally they come from git, or read `dev` and `unknown` without it.

## Install and run

Requires Python 3.11 or newer.

```bash
python -m venv .venv
```

Activate it (`source .venv/bin/activate` on macOS/Linux, `.venv\Scripts\activate` on Windows), then:

```bash
pip install -r requirements.txt
```

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

| URL | What |
|---|---|
| http://127.0.0.1:8000/ | Quiz and administrative dashboard |
| http://127.0.0.1:8000/docs | Interactive API documentation |
| http://127.0.0.1:8000/openapi.json | OpenAPI schema |

On first launch the database `data/oracle.db` is created and seeded with the original quiz.
Later launches keep your edits. Set `ORACLE_DB=/path/to/file.db` to use a different database.

### Security

The server listens on the loopback interface by default and has **no login**. Do not expose it
to a network as is. To require a token for every administrative endpoint (and for explanations in
`/evaluate`), start it with:

```bash
ORACLE_ADMIN_TOKEN=choose-a-secret uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The admin pages then ask for the token once per browser session. Participant endpoints
(`/quiz`, `/classes`, `/evaluate` without explanation) stay open and never expose scoring weights.

## Publish it as a website

The **static edition** is the quiz without a server: plain files that GitHub Pages, or any static host, can serve for free.
The visitor's browser does the scoring, with a JavaScript port of the scoring engine ([app/static/engine.js](app/static/engine.js)).
`tests/test_static_parity.py` runs the same answers through both engines and requires identical output down to the last digit
(scores, ranks, ties, interpretation text, builds), on the seed, an edited configuration and an all-tied one.

```bash
python tools/build_static.py                       # writes ./site
python -m http.server --directory site 8080        # then open http://localhost:8080/
```

What you get: the quiz and result page only. The administrative dashboard is not published, and a visitor's answers are
never sent anywhere. The page works from a site root and from a sub-path (everything is relative), and says it is a fan project
not affiliated with Blizzard.

**Trade-offs to know about**

* **The scoring weights are public.** The browser needs them to score, so `data/oracle.json` contains every weight and anyone can
  read it with "view source". The local app's `/quiz` never exposes them; the static site cannot hide them. For a personality
  quiz that is usually fine, but it means a determined visitor can read off which answers lead to which class.
* **Edits need a rebuild.** The site is a snapshot. To publish changes made in the local admin dashboard, export them
  (*Admin > Configuration > Export*) and build from the export: `python tools/build_static.py --config exported.json`.
* **Builds are the draft builds** described above, labelled as such on the result page.
* **After a deploy, only the page itself can be stale.** GitHub Pages lets browsers keep files for ten minutes. Every file the page loads (the styles, each script module and
  the quiz data) is therefore requested with a hash of the build (`?v=...`), so a browser never mixes new data with old code. `index.html` can still be up to ten minutes
  old; the build number in its footer shows which version you are looking at.

### Putting it on GitHub Pages (free)

GitHub Pages is free for **public** repositories. You do this part yourself, because it needs your sign-in. Do not give anyone your
password (and do not paste it into a chat); use `gh auth login` or a personal access token, and turn on two-factor authentication.

1. **Create an empty public repository** on github.com (no README, no .gitignore, no licence: this folder has its own).
   The name decides the address:
   * `WowForeverClassQuiz.github.io` (exactly `<username>.github.io`) is served at `https://wowforeverclassquiz.github.io/`;
   * any other name, say `character-oracle`, is served at `https://wowforeverclassquiz.github.io/character-oracle/`.
2. **Push this folder.** Authenticate first (`gh auth login`, or use a personal access token as the password when git asks):

   ```bash
   git init -b main
   git add .
   git commit -m "Forever Character Oracle"
   git remote add origin https://github.com/WowForeverClassQuiz/<repository-name>.git
   git push -u origin main
   ```

   `.gitignore` keeps your local database (`data/`), the virtual environment and the generated `site/` folder out of the repository.
3. **Turn Pages on.** In the repository: *Settings > Pages > Build and deployment > Source: GitHub Actions*.
4. **Publish.** The workflow [.github/workflows/pages.yml](.github/workflows/pages.yml) runs on every push to `main`: it installs the
   dependencies, **runs the test suite** (nothing is published if the two scoring engines disagree or a specialization becomes
   unreachable), builds `site/`, and deploys it. Watch it in the *Actions* tab; the address appears on the deploy step and in
   *Settings > Pages*. If the very first run fails at the Pages steps because step 3 came after the push, open *Actions >
   Publish to GitHub Pages > Run workflow* once more.

Other free static hosts (Cloudflare Pages, Netlify and similar) can serve the same `site/` folder: either upload it after running
the build, or have the host run `python tools/build_static.py --out site` and publish the `site` directory.

## How the recommendation is calculated

Scores are **relative compatibility indicators** on a scale with no fixed maximum. The label ("Strong lean", "Clear lean" or
"Close call") is a heuristic based on the gap between the top two classes. The "90% sure" figure comes from the separate confidence model described above.

1. **Class score.** Each answer awards 2 points to its primary class and 1 to its secondary class.
   Because classes appear in different numbers of answers, each question is normalized against the average over
   *every possible response* to it:

   `delta(q, c) = w[q, response, c] - mean over the question's possible responses of w[q, ., c]`,
   `S_c = sum of delta(q, c)` over the questions.

   Example: Q01 answer A gives Druid `2 - 0.5 = +1.5`, Hunter `1 - 0.25 = +0.75`, Mage `0 - 0.5 = -0.5`.
   For every question the contributions of all its possible responses average to zero.

   **Question types.** *Choice* (most of the original sixteen, plus three "this or that" questions with two answers),
   *pick two* (choose two of four items; a pair's weights are the sum of its items', the baseline is the mean over the six possible pairs),
   *ranking* (put four items in order: the item ranked first counts 1.5 times its weights, second 1, third 0.5, last 0; 24 possible orderings),
   *allocation* (spend six points across four items; an item given `p` points counts `p / 3` times its weights; 84 possible splits) and
   *scale* (rate a statement 1-10). A scale question defines two poles, **agree** and **disagree**.
   A rating `r` gives `s = (r - 5.5) / 4.5`, from -1 to +1, and the response carries `max(s, 0) x agree + max(-s, 0) x disagree`.
   So a strong "disagree" counts toward the disagree pole, and a neutral respondent
   contributes about zero, because the baseline is again the mean over all ten ratings. In every type the baseline is the mean over **all
   possible responses**, so no question can favour a class on average. Only two questions are pick-two; the rest of the "choose some of these"
   questions are rankings and point splits, which carry more information per question.
2. **Trait score.** The same normalization over the twelve personality traits gives `T_t`.
   Raw counts (how often a trait appeared) are reported separately.
3. **Specialization score.** `P_s = sum of multiplier x T_trait + m x sum of delta_spec(q, s)`: the trait profile
   (originally 1.5, 1.0 and 0.45 for its primary, secondary and tertiary trait; any number of traits is allowed) plus
   the **direct specialization weights** some answers carry (keys like `warrior/fury`, normalized exactly like class
   weights). `m` is `scoring.spec_weight_multiplier`, 5.0 in the seed. Questions without direct weights contribute
   nothing to the second term. Only the winning class's specializations decide the primary result.
4. **Alternatives.** Second-best class and its best specialization, plus the second-best specialization
   in the winning class.
5. **Quiz lengths.** Each question has a `min_length` (short, medium or long): the shortest quiz that asks it. The quizzes are nested, so
   the medium quiz asks the short quiz's 10 questions plus 10 more, and the long quiz asks all 30. Scoring a length uses only that length's
   questions and is otherwise identical; `POST /evaluate` takes `length` (default `long`), refuses answers to questions the length does not ask
   and reports the ones it is missing. The confidence margins scale with the square root of the share of questions asked
   (`sqrt(10/30)` for short), because the gap between the top two classes of random answers grows about that fast; without this a short quiz would
   be called a "close call" far more often just for being short (a test checks the labels stay comparable across lengths). The "Sharpen it" button on
   a short or medium result adds the next length's questions and keeps every answer already given.
6. **Ties** are deterministic: class order Druid, Hunter, Mage, Paladin, Priest, Rogue, Shaman, Warlock,
   Warrior (editable); then specialization order within the class; then trait order. Scores are compared
   after rounding to 9 decimals so floating-point noise never decides a result. Ties used are listed in the explanation.

The calculation lives in one pure module, [app/scoring.py](app/scoring.py). It reads a configuration
and a set of answers and touches nothing else (no database, no network, no randomness except in the
explicitly seeded batch diagnostic).

## Changing the classification algorithm

Pick the lightest level that does the job.

1. **In the interface (no code).**
   * *Question Editor*: change answer text and class and trait weights. Edits are drafts until you press **Save**;
     **Preview impact** shows what a draft would do to your hypothetical answers and across 3,000 random answer sets;
     **Restore original weights** reloads the seed values as a draft. A live table shows each question's
     baseline and the contribution of every answer.
   * *Profiles*: rename traits, change each specialization's weighted-trait profile (add, remove, reorder),
     edit class and specialization descriptions, set the confidence margins and the class tie-break order.
   * *Simulation*: test temporary changes without saving anything; the batch diagnostic reveals classes that
     win more or less often than an even split.
   * *Scoring Inspector*: pick any response set and see every answer's raw weight, baseline and adjusted
     contribution, per class and per trait, plus what single-answer changes would flip the result.
2. **By configuration file.** *Admin > Configuration > Export*, edit the JSON, then *Import*. The server
   validates the whole file first (unknown ids, non-finite or negative weights, wrong question or answer counts,
   unverifiable builds ...) and writes a backup before replacing anything. Every change, import or reset is a
   numbered revision you can inspect or restore. *Reset to original* restores the seed data after a typed confirmation.
3. **In code.** Change the formulas in [app/scoring.py](app/scoring.py) and bump `ALGORITHM_VERSION` in
   [app/seed.py](app/seed.py). The seed content (questions, weights, profiles) is in [app/seed.py](app/seed.py) and is
   only used for a fresh database or a reset. Update the matching expectations in `tests/test_scoring.py`.

`expected_question_count` (30) lives in the configuration's `quiz` block and the validator enforces it for the questions the fixed quizzes ask (those marked
*Confidence mode only* are extra), so changing the number of fixed-quiz questions is a deliberate edit of that block plus the questions. Choice questions need 2 to 8 answers, pick-two, ranking
and allocation questions exactly 4, and scale questions exactly the two answers `agree` and `disagree`.

### Balance (algorithm 1.3.0)

The requirement: **every class equally likely to be chosen, every specialization the recommendation at least 20% of the time within its own
class, and all of it at every quiz length, when the answers are random.** "Random" here means every question answered uniformly at random over its
possible responses (each of the ten ratings, each answer, each of the six pairs, each of the 24 orderings or 84 splits of points). It is a diagnostic of the
scoring rules. It does not model real people, who do not answer uniformly, so nothing can promise that their real answers pick every class equally often.
Measured on 100,000 random answer sets (`python tools/balance.py report --n 100000 --seed 4242`). The first table is the **long** quiz; the second compares the three lengths:

| Class | Result share | Its specializations' shares within the class |
|---|---|---|
| Druid | 11.1% | Balance 32.6% · Feral Combat 27.7% · Restoration 39.7% |
| Hunter | 11.1% | Beast Mastery 35.2% · Marksmanship 34.0% · Survival 30.8% |
| Mage | 11.2% | Arcane 34.9% · Fire 26.9% · Frost 38.2% |
| Paladin | 11.1% | Holy 31.0% · Protection 40.1% · Retribution 28.9% |
| Priest | 11.1% | Discipline 33.4% · Holy 40.9% · Shadow 25.7% |
| Rogue | 11.1% | Assassination 34.3% · Combat 31.5% · Subtlety 34.2% |
| Shaman | 11.1% | Elemental Combat 28.6% · Enhancement 31.4% · Restoration 39.9% |
| Warlock | 11.1% | Affliction 37.2% · Demonology 38.9% · Destruction 23.8% |
| Warrior | 11.2% | Arms 38.3% · Fury 35.9% · Protection 25.9% |

| Quiz | Questions | Lowest specialization share | Class shares (an even split is 11.1%) |
|---|---|---|---|
| Short | 10 | 24.1% | 10.8% to 11.4% |
| Medium | 20 | 25.1% | 11.0% to 11.2% |
| Long | 30 | 23.8% | 11.1% to 11.2% |

Equal here means within a fraction of a percentage point of an even 11.1%: with answers that are discrete choices, an exactly equal share cannot be built
in, but the remaining differences (about 0.3 points at most, on the short quiz) are as small as the measurement can resolve (100,000 samples give about
0.1 points of noise). The lowest specialization share is 23.8% (Destruction Warlock) and the highest 40.9% (Holy Priest).
`tests/test_balance.py` enforces at least 20% per specialization and every class within a point of even on a fixed seed (and within half a point on
100,000 samples where numpy is installed), and `tests/test_question_types.py` checks by search that answers exist for all 27 specializations.

**How it was reached, and what changed in the original sixteen questions.** The original trait profiles could not make some
specializations win at all, and some classes were favoured far more than others (worst specialization 7.7% of its class,
classes 8.5-14.5%). The fix is data, listed in [app/seed_tuning.py](app/seed_tuning.py) where anyone can read it, and found with
`tools/balance.py` plus a greedy search that was then reviewed by hand against each answer's meaning:

* five original questions changed type with their answers unchanged: Q07 (weather) and Q11 (objects kept for their beauty) became **rankings**; Q03 (an unfamiliar city), Q09 (a festival) and Q15 (restoring a hard day) became **six-point splits**;
* eight original answers have a different (primary, secondary) class pair, to even out how often each class is favoured;
* **class intensities**: 35 answers shift up to a point of weight between their two classes (for example 2.5 and 0.5, or an even 1.5 and 1.5, where the usual split is 2 and 1), found with
  `tools/equalize_classes.py` so that every class is chosen equally often. The two classes of an answer and the total of 3 never change, so the class scores of a complete
  answer set still sum to zero; Q01, the worked example in this document, is left as written;
* **direct specialization weights** were added to 59 answers (25 of them answers of original questions) and the multiplier raised from 3.0 to 5.0;
* the trait weights of the original sixteen questions and the class pairs of the other answers are untouched; every original question
  except Q14 carries at least one of these changes (the answers' wording is never altered, only the questions that changed type were reworded).
* the short and medium quizzes needed their own tuning: a random choice of 10 or 20 questions leaves some specializations winning under 10% of their
  class's results, so the questions of each length were chosen (class evenness, a mix of question types, enough answers that suit each
  specialization) and the direct weights then tuned for all three lengths at once with `tools/tune_weights.py`, never removing a weight and never
  adding one to an answer that does not suit the specialization (a person reviewed and struck out the proposals that did not fit).

All of it is ordinary configuration: edit or remove any entry in the Question Editor, and use *Simulation > batch* to see the effect.
To re-measure after your own edits (the tool needs numpy, which the application itself does not):

```bash
pip install -r requirements-dev.txt
python tools/balance.py report                       # shares for the seed, at each quiz length (--length short|medium|long)
python tools/balance.py report --config exported.json    # shares for a configuration you exported
python tools/balance.py parity                       # confirm the fast simulator agrees with the real engine
```

The class and trait associations behind the questions are playstyle lore with no science behind them: studies of WoW players found little or
no link between personality and class choice. Balanced here means "no specialization is starved". It makes no claim to predict anything.

**Upgrading an existing database.** A database that still holds the *unedited* seed of an earlier release is upgraded to the
current seed (algorithm 1.3.0) automatically at start-up. A database you have edited is never rewritten silently: new columns are added,
it keeps its questions and keeps working (every question is read as asked in the long quiz only, so such a database offers the one long quiz until you assign lengths in the Question Editor), and *Admin > Configuration > Reset to original* (a backup is written first)
adopts the new seed.

**Result paragraphs.** The result shows "What the class does": a class paragraph and a specialization paragraph, written in this
project's own words from Blizzard's official class pages and the Forever class deep dives (none of it copied), with a link to
Blizzard's page. They are stored in the configuration and editable under *Profiles*.

## API overview

All paths are under `/api/v1`. Mutating configuration calls **require** `expected_revision`;
a stale value returns **409** and nothing changes. Errors use `{"detail": {"code", "message", ...}}`.

| Endpoint | Purpose |
|---|---|
| `GET /quiz` | Questions and answers only, no scoring data; also the quiz lengths on offer and which questions each asks |
| `GET /classes?include_scores&include_builds` | Classes (with their overview text), specializations, roles, build summaries |
| `GET /specializations/{class}/{spec}` | The page of one specialization: overview, defining traits, role and gear guide, default build with its talent trees |
| `GET /version` | Version, build number, commit and date of this build |
| `POST /adaptive/next` | Confidence mode: given the answers so far, how sure the Oracle is, the five most probable types, whether to stop, and which question to ask next |
| `POST /evaluate` | Score an answer set for one quiz `length` (`short`, `medium`, `long`, or `adaptive` for exactly the questions answered; default `long`; `allow_partial`, `include_explanation`, `include_counterfactuals` for admins). Every result carries the model's `confidence.probability` |
| `GET /config`, `/config/default`, `/config/export`, `/config/history[/{rev}]` | Read configuration, original seed, download, revisions |
| `POST /config/import`, `/config/reset`, `/config/history/{rev}/restore` | Replace configuration (with backup) |
| `POST /questions/expand` | Expand a (possibly unsaved) question into every possible response with raw and baseline-subtracted weights |
| `PATCH /questions/{q}/answers/{a}`, `/questions/{q}`, `/classes/{c}/specs/{s}`, `/classes/{c}`, `/traits/{t}`, `/scoring`, `/quiz` (title, subtitle, share format) | Edits. Weight maps you send **replace** the whole map; omitted keys become 0 |
| `POST /simulate`, `/simulate/batch` | What-if evaluation and random-answer diagnostics, for any quiz `length` (never persisted) |
| `GET/POST/PATCH/DELETE /builds...`, `POST /builds/validate`, `POST /builds/{id}/default` | Build records |
| `GET/PUT /talents/catalog` | Imported talent data |
| `GET /health` | Version and revision |

Status codes: 200/201 success, 400 invalid request semantics (unknown ids inside a body, incomplete
assessment, invalid configuration), 404 unknown resource, 409 revision conflict, 422 schema errors
(negative or non-finite weights), 500 unexpected.

## Importing talent data

*Build Editor > Talent data* accepts JSON in this shape (use real data for the current client):

```json
{
  "game": "World of Warcraft: Forever",
  "client_version": "<client build>",
  "source": "<where the data came from>",
  "retrieved_at": "YYYY-MM-DD",
  "points_per_tier": 5,
  "classes": [
    { "id": "druid", "trees": [
      { "id": "balance", "name": "Balance", "talents": [
        { "id": "<talent-id>", "name": "<Talent name>", "tier": 0, "column": 0, "max_rank": 5,
          "requires": [ { "talent_id": "<other-talent-id>", "rank": 5 } ] }
      ] }
    ] }
  ]
}
```

`tier` is the zero-based row; a talent in row *r* needs `r x points_per_tier` points in earlier rows of its
tree (set `points_per_tier` from the real game data; do not assume classic values). Tree ids must equal this
app's specialization ids. A class may be imported on its own. Replacing or removing the catalog re-checks
every verified build and downgrades any that no longer validate.

A level-60 build must spend exactly 51 points (talent points begin at level 10, so a level *L* character has
*L - 9*). Talent allocations are allowed to be hybrid, but the build's primary specialization tree must hold the
most points and the build's role must fit the specialization.

## Tests

```bash
pytest
```

357 automated tests cover scoring (normalization, ties, determinism, weight edits), the API (privacy of
`/quiz`, edits, persistence across restart, simulation purity, revision conflicts, import, export and reset),
build validation (51 points, ranks, prerequisites, role consistency, verification rules), the draft talent catalog and the 27 draft builds
with their installer, the guides, drawn talent trees and icons that the result page shows, the **balance** of the seed quiz at each length (`tests/test_balance.py`), the short, medium and long quizzes (`tests/test_lengths.py`), the share format and the specialization pages (`tests/test_share.py`, `tests/test_spec_pages.py`), the version stamp (`tests/test_version.py`), confidence mode and its browser twin (`tests/test_adaptive.py`), the confidence-mode-only questions (`tests/test_extra_questions.py`, `tests/test_class_questions.py`), the class and role credit in the confidence (`tests/test_confidence_credit.py`), the tiebreakers (`tests/test_tiebreakers.py`), the maths PDF (`tests/test_math_pdf.py`), and the **static edition**: the JavaScript engine against
the Python engine and the live API (`tests/test_static_parity.py`, needs `node`, skipped without it) and the site builder, including its cache stamping
(`tests/test_build_static.py`).

The interface tests need a browser; paste a script into the browser console:

* **Local app**: with the server running and a **freshly loaded** page, paste [tests/ui_smoke.js](tests/ui_smoke.js) (about a minute). It checks that
  all 30 fixed-quiz questions open with the right controls for their type, answers survive navigation, the result cannot be revealed early,
  on-screen rankings equal the API's, the inspector reproduces the API's per-question values, and an admin weight edit saves and
  restores (it changes one weight and puts it back, advancing the revision by two, so use a scratch database: `ORACLE_DB=/tmp/smoke.db`).
* **Static site**: serve the `site` folder and paste [tests/static_smoke.js](tests/static_smoke.js). It answers all 30 questions through
  the real controls and checks the result, that no `/api/` request is made, and that the admin pages are not reachable.

## Project layout

```
app/main.py         routes, error mapping, static files
app/models.py       Pydantic models (configuration, requests, responses)
app/scoring.py      pure scoring, simulation and batch diagnostics
app/seed.py         original questions, weights, profiles, placeholder builds
app/seed_tuning.py  the documented balance overlay applied to the seed (type changes, class pairs, direct weights)
app/seed_extra.py   q31 to q50, the twenty specialization questions only confidence mode asks
app/seed_classes.py q51 to q74, the twenty-four class-separating questions only confidence mode asks
app/seed_tiebreakers.py q75 to q103, the tiebreakers: forced choices between finalists, only confidence mode asks them
app/validation.py   cross-reference checks for a whole configuration
app/public.py       the participant view (questions, builds) shared by the API and the static export
app/drafts.py       loads the shipped draft talent catalog and builds into the seed
app/version.py      the application version and the build stamp shown on the first page
app/adaptive.py     confidence mode: the choice model, posterior, information gain and stopping rule
app/spec_guides.py role and gear guidance for each specialization
app/static_export.py  exports a configuration as the data file of the static site
app/builds.py       build validation and presentation
app/database.py     SQLite schema and transactions
app/repository.py   configuration storage, revisions, backups
app/static/         browser interface (plain ES modules, no build step); engine.js is the in-browser scoring engine,
                    icons.js maps classes and specializations to their icons, talenttree.js draws a build,
                    parts.js holds the cards shared by result and specialization pages, share.js fills in the share format,
                    views/specs.js is the class and specialization pages
catalog/            draft Forever talent catalog and 27 draft builds, their build scripts, installer and reconciliation ledger
tools/balance.py    balance report and parity check at each quiz length (developer tool, needs numpy: requirements-dev.txt)
tools/tune_weights.py  suggests direct specialization weights that keep every length balanced
tools/equalize_classes.py  suggests class-weight intensities that make every class equally likely at every length
tools/build_math_pdf.py  builds docs/oracle-math.pdf, the maths behind the selections, from the live configuration
docs/               oracle-math.pdf
tools/build_static.py  builds the static website into ./site
.github/workflows/  GitHub Pages publishing workflow
tests/              pytest suites and the browser smoke tests
data/               created at first run: oracle.db and backups/
```

Quiz answers are held only in the browser tab and are never stored by the server.
