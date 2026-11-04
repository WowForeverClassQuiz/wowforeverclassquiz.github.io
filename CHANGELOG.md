# Changelog

The version shown on the first page is `APP_VERSION` in [app/version.py](app/version.py). The scoring rules carry their own
`algorithm_version` (currently 1.3.0), which changes only when the arithmetic or the seed weights do.

## 1.6.0 · 2026-11-03

* **Confidence mode**, now the default: the Oracle picks each question to learn the most and stops once it is 90% sure of one specialization (after at least 10
  questions, at most 30), with a certainty meter while you answer. Short, medium and long are still there.
* Every result reports the model's confidence in its recommendation.
* **docs/oracle-math.pdf**: the mathematics behind the selections, with tables of the relevant numbers (rebuild with `python tools/build_math_pdf.py`).
* The administrator can change the minimum and maximum number of questions, the confidence threshold and the model's sharpness (Profiles & Settings).

## 1.5.0 · 2026-11-03

* Class pages and specialization pages: what each class does, the traits that define each specialization, its role and gear, and its build.
  Open them from the first page, the "Also in the stars" cards or the Classes link; page through with Previous/Next or the arrow keys.
* Share your result: a short blurb (class, specialization, your class scores, a link to take the quiz) you can copy with one click.
* Every class is now chosen equally often under random answers, at every quiz length (within about 0.3 percentage points).
* Question 3 became a "spend six points" question.
* The build no longer shows its source or a "how this was put together" note.
* The first page shows who developed it, the version, the build number and the date.

## 1.4.0 · 2026-11-03

* Short (10), medium (20) and long (30) quizzes, with a "Sharpen it" button to add the next length's questions.

## 1.3.0 · 2026-11-03

* Ranking and spend-six-points questions; far fewer pick-two questions.
* Builds drawn as the three talent trees, with a note on how current the talent data is.
* Role-in-dungeons-and-raids and gear guides for all 27 specializations; class and spell icons.
* The draft talent data and 27 draft builds ship with the application.

## 1.2.0 · 2026-11-03

* Balanced so every specialization is chosen at least 20% of the time within its class under random answers.
* A static edition of the quiz that runs entirely in the browser, published with GitHub Pages.

## 1.1.0 · 2026-11-03

* Thirty questions: one-to-ten agreement scales and pick-two questions, with direct specialization weights.
* "What the class does" paragraphs on the result.

## 1.0.0 · 2026-11-03

* The local quiz, the administrative dashboard, the REST API and the scoring engine.
