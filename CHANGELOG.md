# Changelog

The version shown on the first page is `APP_VERSION` in [app/version.py](app/version.py). The scoring rules carry their own
`algorithm_version` (currently 1.7.0), which changes only when the arithmetic or the seed weights do.

## 1.9.0 · 2026-11-04

* **Tiebreaker questions (q75 to q103)**, asked only in confidence mode, force a decision between the finalists. There are seventeen for groups of three specializations (the three specializations of each class, and eight groups that share a role, such as the three tanks: "do you trust more in the light to guard, the structure and workmanship of steel, or the strength of the wild?" and, for a Paladin, "retribution, judgement or forgiveness?") and twelve two-way questions for the closest pairs of finalists.
* A tiebreaker is asked only when its finalists together hold at least 80% of the probability, so it appears when the reading has narrowed to those candidates and never earlier. Two of three finalists are enough, so a three-way question also serves when only the top two are left. The share is a setting (Profiles & Settings), and a question's finalists can be edited through the API or an exported configuration.
* In simulation the tiebreakers are asked in about half of all readings and save up to half a question, with no change in accuracy.
* The scoring algorithm is 1.7.0, because confidence mode now chooses among the eligible questions. Scores for the same answers are unchanged.

## 1.8.0 · 2026-11-04

* **The confidence counts more than one specialization.** The Oracle's confidence is the model's probability for the recommended specialization plus half credit for probability on other specializations of the same class and half credit for those with a similar role (tank, healer, melee damage, ranged damage). A person whose three Mage specializations are all gaining, or who sits between Protection Paladin and Protection Warrior, is now told the Oracle is fairly sure. The class, specialization and role probabilities are shown beside the figure, in the quiz and on the result, and an administrator can change both credits in Profiles & Settings (0 and 0 gives the old measure).
* **Twenty-four class-separating personality questions (q51 to q74)**, asked only in confidence mode: ten choices, seven rankings and seven six-point splits in which every answer belongs to a different class, so a person torn among their three leading classes has to choose among them. Every trio of classes now has at least four questions that tell all three apart, up from two.
* The confidence meter now moves when you go on to the next question, not when you choose an answer.
* The scoring algorithm is 1.6.0, because confidence mode stops on the new measure. Scores for the same answers are unchanged.

## 1.7.2 · 2026-11-04

* The front page says each thing once. The Confidence card gives the limit ("Up to 30 questions") and the stopping rule with its 90% once, and the line under the cards no longer repeats them.

## 1.7.1 · 2026-11-04

* Published sites no longer serve stale files after a deploy. Every file the page loads (styles, scripts, quiz data) is requested with a hash of the build, so a browser that cached the previous version fetches the new files and never mixes new data with old code. The page itself can still be up to ten minutes old.

## 1.7.0 · 2026-11-03

* **No minimum number of questions** in confidence mode: the Oracle stops as soon as it is 90% sure of one specialization, and still never asks more than 30. An administrator can set a minimum in Profiles & Settings.
* **Twenty more questions (q31 to q50), asked only in confidence mode.** Two for each class (a choice and a ranking or six-point split) tell that class's three specializations apart, and a role question and a distance question cut across all classes. The short, medium and long quizzes are unchanged. The Question Editor has a new "Confidence mode only" choice under "Asked in".
* Simulated respondents now need about 6 questions on average, down from about 16, and almost none run to the limit. If people answer less consistently than the model assumes the stated confidence overshoots; the maths document shows by how much.
* Six other ways of choosing the next question were tried, including ones that aim at the leading specialization. None needed fewer questions than information gain, so the rule is unchanged.
* The maths document has new sections on respondents who are less consistent than assumed, the question-choice comparison and why the pool has fifty questions.
* The scoring algorithm is now 1.5.0 because confidence mode asks different questions. Scores and results for the same answers are unchanged.

## 1.6.1 · 2026-11-03

* Reworded text throughout the quiz, the result page, the share blurb, the notes the API returns, the README and the maths document. The contrast phrasing, the slash alternatives and the dash separators are gone.
* Specializations now read the way players say them, as in "Feral Combat Druid", and a role such as "Melee Damage or Tank" uses a word where it had a slash.
* The default share blurb changed with the wording. A share format an administrator saved earlier is left as it was.

## 1.6.0 · 2026-11-03

* **Confidence mode**, now the default: the Oracle picks each question to learn the most and stops once it is 90% sure of one specialization (after at least 10
  questions, at most 30), with a certainty meter while you answer. Short, medium and long are still there.
* Every result reports the model's confidence in its recommendation.
* **docs/oracle-math.pdf**: the mathematics behind the selections, with tables of the relevant numbers (rebuild with `python tools/build_math_pdf.py`).
* The administrator can change the minimum and maximum number of questions, the confidence threshold and the model's sharpness (Profiles & Settings).

## 1.5.0 · 2026-11-03

* Class pages and specialization pages: what each class does, the traits that define each specialization, its role and gear, and its build.
  Open them from the first page, the "Also in the stars" cards or the Classes link; page through with Previous and Next or the arrow keys.
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
