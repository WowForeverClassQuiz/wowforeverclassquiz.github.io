// Runs the browser scoring engine (app/static/engine.js) on a job read from stdin and prints the outcome as JSON.
// Used by tests/test_static_parity.py, which compares everything against the Python engine.
//
//   job = { numbers: [x, ...], sums: [[x, ...], ...], cases: [{ data, answers: [{...}, ...], length?: "short" | "medium" | "long" }, ...] }
//
// engine.js is loaded through a data: URL so node treats it as an ES module without a package.json.
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../app/static/engine.js", import.meta.url), "utf8");
const engine = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const job = JSON.parse(readFileSync(0, "utf8"));
const out = {};

if (job.numbers) {
  out.numbers = job.numbers.map((x) => [engine.pyRound(x, 9), engine.pyRound(x, 10), engine.signed(x), engine.formatG(x)]);
}
if (job.sums) out.sums = job.sums.map((xs) => engine.fsum(xs));
if (job.cases) {
  out.cases = job.cases.map(({ data, answers, length }) => {
    const compiled = engine.prepare(data);
    return answers.map((a) => {
      try {
        return engine.evaluate(compiled, a, { length: length || "long" });
      } catch (err) {
        if (err instanceof engine.ScoringError) return { error: err.code };
        throw err;
      }
    });
  });
}
process.stdout.write(JSON.stringify(out));
