# World of Warcraft: Forever - Character Oracle

A personality quiz that recommends a **class, specialization and talent build** for
*World of Warcraft: Forever*. Thirty indirect questions of three kinds (pick one, rate 1-10, pick two) are
scored with a transparent, deterministic algorithm. It comes in two editions that share one scoring engine:

* **Local app** (run with Python, below): the quiz plus an administrative dashboard. Nothing leaves your machine.
  * *Participant interface* (`/`): the quiz, a result reveal, and a build card.
  * *Administrative interface* (`/#/admin/...`): question editor, scoring inspector, simulation,
    profile editor, build editor, and configuration management (export, import, reset, history).
  * *REST API* (`/api/v1`): everything the interface does, documented at `/docs`.
* **Static website** (`python tools/build_static.py`): only the quiz, as plain files for GitHub Pages or any static host,
  scored in the visitor's browser. See [Publish it as a website](#publish-it-as-a-website).

Every specialization of every class can be the result, and under random answers each one wins at least a quarter of its
class's results; see [Balance](#balance-algorithm-120).

## Status of the talent builds (read this)

The scoring engine, API and interface are complete and tested. **The talent data is a hand-built draft, and no build is verified.**

* The application ships **no data read from the World of Warcraft: Forever client**. All 27 specializations start with a
  placeholder build (`status: pending`, no allocation); the participant sees "Talent allocation pending".
* [catalog/forever-talents-draft-2026-11-03.json](catalog/forever-talents-draft-2026-11-03.json) is a **draft catalog of all 27 trees
  (468 talents)** you can import in *Admin > Build Editor > Talent data*. It was assembled on 2026-11-03 from
  GuildOrder's Forever talent pages (reviewed October 2026) plus Blizzard's *Beta Development Notes, updated November 2*
  (the developer post stamped 2026-11-03 03:20), which lists changes only. `catalog/build_forever_draft.py` rebuilds it and checks
  109 structural claims from the notes; [catalog/RECONCILIATION.md](catalog/RECONCILIATION.md) records which the source already
  contained (62) and which were applied by hand (47: Rogue, Warrior and Shaman).
* Draft data is flagged `data_status: "draft"`. Allocations are validated against it (point total, ranks, row gates, and the
  prerequisites the notes state), but **the server refuses to mark any build `verified` against draft data**.
* Known gaps in the draft: the source shows no talent-to-talent prerequisites (only 6 are recorded, from the notes); `column`
  is list order, not the real grid; percentage-only changes are not modelled; the pages were read through a summarising
  fetch tool; and a few notes entries are ambiguous (listed in the ledger). Replace the draft with a client export when you have one.
* [catalog/forever-builds-draft-2026-11-03.json](catalog/forever-builds-draft-2026-11-03.json) holds **27 best-guess leveling / general-PvE
  builds, one per specialization**, each a full 51-point allocation with a legal point-by-point leveling order. Load the draft
  catalog and builds into your database with one command (it writes one revision and backs up the old configuration first):

  ```bash
  python catalog/install_drafts.py
  ```

  How they were made: RankedBoost's WoW Forever build pages (build 1.60.1.70707, "updated November 2") are the model: its leveling build
  where one exists, otherwise its PvE damage, healing or tank build. Rogue Subtlety has only a PvP source, so that build is my own
  extrapolation and the least trustworthy. RankedBoost still uses some pre-patch talents, so every build was remapped onto the new
  trees (removed talents dropped, ranks capped, moved talents taken from their new tree). Reddit and other forums could not be read
  by the tools I had, so no community consensus is reflected beyond RankedBoost and the guide sites. Each build is `draft`, is
  checked as *legal* on the draft catalog, and says so on its record; that proves legality in unverified data, not quality.
  Guidance text is limited to what follows from the talents taken: no rotations, stat priorities or professions are invented.
* The test suite also uses a small *synthetic* catalog to exercise the validator. Its names are invented and it is never loaded
  by the application.

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

Scores are **relative compatibility indicators, not probabilities**. "Strong lean / Clear lean /
Close call" is a heuristic based on the gap between the top two classes, not a statistical estimate.

1. **Class score.** Each answer awards 2 points to its primary class and 1 to its secondary class.
   Because classes appear in different numbers of answers, each question is normalized against the average over
   *every possible response* to it:

   `delta(q, c) = w[q, response, c] - mean over the question's possible responses of w[q, ., c]`,
   `S_c = sum of delta(q, c)` over the questions.

   Example: Q01 answer A gives Druid `2 - 0.5 = +1.5`, Hunter `1 - 0.25 = +0.75`, Mage `0 - 0.5 = -0.5`.
   For every pick-one or pick-two question the contributions sum to zero.

   **Question types.** *Choice* (the original sixteen, plus three "this or that" questions with two answers),
   *pick two* (choose two of four items; a pair's weights are the sum of its items', the baseline is the mean over the
   six possible pairs) and *scale* (rate a statement 1-10). A scale question defines two poles, **agree** and **disagree**.
   A rating `r` gives `s = (r - 5.5) / 4.5`, from -1 to +1, and the response carries `max(s, 0) x agree + max(-s, 0) x disagree`.
   So a strong "disagree" counts toward the disagree pole instead of counting for nothing, and a neutral respondent
   contributes about zero, because the baseline is again the mean over all ten ratings.
2. **Trait score.** The same normalization over the twelve personality traits gives `T_t`.
   Raw counts (how often a trait appeared) are reported separately.
3. **Specialization score.** `P_s = sum of multiplier x T_trait + m x sum of delta_spec(q, s)`: the trait profile
   (originally 1.5 / 1.0 / 0.45 for its primary, secondary and tertiary trait; any number of traits is allowed) plus
   the **direct specialization weights** some answers carry (keys like `warrior/fury`, normalized exactly like class
   weights). `m` is `scoring.spec_weight_multiplier`, 5.0 in the seed. Questions without direct weights contribute
   nothing to the second term. Only the winning class's specializations decide the primary result.
4. **Alternatives.** Second-best class and its best specialization, plus the second-best specialization
   in the winning class.
5. **Ties** are deterministic: class order Druid, Hunter, Mage, Paladin, Priest, Rogue, Shaman, Warlock,
   Warrior (editable); then specialization order within the class; then trait order. Scores are compared
   after rounding to 9 decimals so floating-point noise never decides a result. Ties used are listed in the explanation.

The calculation lives in one pure module, [app/scoring.py](app/scoring.py). It reads a configuration
and a set of answers and touches nothing else (no database, no network, no randomness except in the
explicitly seeded batch diagnostic).

## Changing the classification algorithm

Pick the lightest level that does the job.

1. **In the interface (no code).**
   * *Question Editor*: change answer text and class/trait weights. Edits are drafts until you press **Save**;
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

`expected_question_count` (30) lives in the configuration's `quiz` block and the validator enforces it, so changing the
number of questions is a deliberate edit of that block plus the questions. Choice questions need 2 to 8 answers, pick-two
exactly 4, and scale questions exactly the two answers `agree` and `disagree`.

### Balance (algorithm 1.2.0)

The requirement: **every class reachable, and every specialization the recommendation at least 20% of the time within its
own class when the answers are random.** "Random" here means every question answered uniformly at random over its possible
responses (each of the ten ratings, each answer, each of the six pairs). It is a diagnostic of the scoring rules, not a model of
real people, who do not answer uniformly. Measured on 100,000 random answer sets (`python tools/balance.py report --n 100000 --seed 4242`):

| Class | Result share | Its specializations' shares within the class |
|---|---|---|
| Druid | 11.0% | Balance 32.8% · Feral Combat 30.0% · Restoration 37.2% |
| Hunter | 10.0% | Beast Mastery 39.4% · Marksmanship 30.1% · Survival 30.5% |
| Mage | 13.0% | Arcane 42.8% · Fire 27.8% · Frost 29.5% |
| Paladin | 10.8% | Holy 30.6% · Protection 36.8% · Retribution 32.6% |
| Priest | 11.8% | Discipline 29.7% · Holy 43.7% · Shadow 26.6% |
| Rogue | 11.8% | Assassination 30.4% · Combat 29.8% · Subtlety 39.8% |
| Shaman | 10.3% | Elemental 33.5% · Enhancement 33.4% · Restoration 33.1% |
| Warlock | 11.3% | Affliction 37.2% · Demonology 31.5% · Destruction 31.3% |
| Warrior | 10.0% | Arms 31.4% · Fury 37.8% · Protection 30.8% |

The lowest share is 26.6% (Priest Shadow) and the highest 43.7%; classes range from 10.0% to 13.0% (an even split is 11.1%).
`tests/test_balance.py` enforces at least 20% per specialization and 8-15% per class on a fixed seed, and `tests/test_question_types.py`
checks by search that answers exist for all 27 specializations.

**How it was reached, and what changed in the original sixteen questions.** The original trait profiles could not make some
specializations win at all, and some classes were favoured far more than others (worst specialization 7.7% of its class,
classes 8.5-14.5%). The fix is data, listed in [app/seed_tuning.py](app/seed_tuning.py) rather than hidden in code, and found with
`tools/balance.py` plus a greedy search that was then reviewed by hand against each answer's meaning:

* four original questions became **pick-two** with their answers unchanged (Q07 weather, Q09 festival, Q11 objects, Q15 restoring a hard day);
* eight original answers have a different (primary, secondary) class pair, to even out how often each class is favoured;
* **direct specialization weights** were added to 42 answers (eight of them answers of original questions) and the multiplier raised from 3.0 to 5.0;
* the trait weights of the original sixteen questions and the class pairs of the other answers are untouched; five original
  questions (Q01, Q06, Q08, Q14, Q16) are entirely unchanged.

All of it is ordinary configuration: edit or remove any entry in the Question Editor, and use *Simulation > batch* to see the effect.
To re-measure after your own edits (the tool needs numpy, which the application itself does not):

```bash
pip install -r requirements-dev.txt
python tools/balance.py report                       # shares for the seed
python tools/balance.py report --config exported.json    # shares for a configuration you exported
python tools/balance.py parity                       # confirm the fast simulator agrees with the real engine
```

The class and trait associations behind the questions are playstyle lore, not science: studies of WoW players found little or
no link between personality and class choice. Balanced here means "no specialization is starved", not "predictive".

**Upgrading an existing database.** A database that still holds the *unedited* seed of an earlier release is upgraded to the
new thirty-question seed (algorithm 1.2.0) automatically at start-up. A database you have edited is never rewritten silently: new columns are added,
it keeps its sixteen questions and keeps working, and *Admin > Configuration > Reset to original* (a backup is written first)
adopts the new seed.

**Result paragraphs.** The result shows "What the class does": a class paragraph and a specialization paragraph, written in this
project's own words from Blizzard's official class pages and the Forever class deep dives (not copied from them), with a link to
Blizzard's page. They are stored in the configuration and editable under *Profiles*.

## API overview

All paths are under `/api/v1`. Mutating configuration calls **require** `expected_revision`;
a stale value returns **409** and nothing changes. Errors use `{"detail": {"code", "message", ...}}`.

| Endpoint | Purpose |
|---|---|
| `GET /quiz` | Questions and answers only, no scoring data |
| `GET /classes?include_scores&include_builds` | Classes, specializations, roles, build summaries |
| `POST /evaluate` | Score a complete answer set (`allow_partial`, `include_explanation`, `include_counterfactuals` for admins) |
| `GET /config`, `/config/default`, `/config/export`, `/config/history[/{rev}]` | Read configuration, original seed, download, revisions |
| `POST /config/import`, `/config/reset`, `/config/history/{rev}/restore` | Replace configuration (with backup) |
| `POST /questions/expand` | Expand a (possibly unsaved) question into every possible response with raw and baseline-subtracted weights |
| `PATCH /questions/{q}/answers/{a}`, `/questions/{q}`, `/classes/{c}/specs/{s}`, `/classes/{c}`, `/traits/{t}`, `/scoring` | Edits. Weight maps you send **replace** the whole map; omitted keys become 0 |
| `POST /simulate`, `/simulate/batch` | What-if evaluation and random-answer diagnostics (never persisted) |
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

180 automated tests cover scoring (normalization, ties, determinism, weight edits), the API (privacy of
`/quiz`, edits, persistence across restart, simulation purity, revision conflicts, import/export/reset),
build validation (51 points, ranks, prerequisites, role consistency, verification rules), the draft talent catalog and the 27 draft builds
with their installer, the **balance** of the seed quiz (`tests/test_balance.py`), and the **static edition**: the JavaScript engine against
the Python engine and the live API (`tests/test_static_parity.py`, needs `node`, skipped without it) and the site builder
(`tests/test_build_static.py`).

The interface tests need a browser; paste a script into the browser console:

* **Local app**: with the server running and a **freshly loaded** page, paste [tests/ui_smoke.js](tests/ui_smoke.js) (about a minute). It checks that
  all 30 questions open with the right controls for their type, answers survive navigation, the result cannot be revealed early,
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
app/validation.py   cross-reference checks for a whole configuration
app/public.py       the participant view (questions, builds) shared by the API and the static export
app/static_export.py  exports a configuration as the data file of the static site
app/builds.py       build validation and presentation
app/database.py     SQLite schema and transactions
app/repository.py   configuration storage, revisions, backups
app/static/         browser interface (plain ES modules, no build step); engine.js is the in-browser scoring engine
catalog/            draft Forever talent catalog and 27 draft builds, their build scripts, installer and reconciliation ledger
tools/balance.py    balance report / parity / tuning (developer tool, needs numpy: requirements-dev.txt)
tools/build_static.py  builds the static website into ./site
.github/workflows/  GitHub Pages publishing workflow
tests/              pytest suites and the browser smoke tests
data/               created at first run: oracle.db and backups/
```

Quiz answers are held only in the browser tab and are never stored by the server.
