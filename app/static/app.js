// Router, theme toggle and boot sequence.
import { h, clear, errorList } from "./ui.js";
import { state, setRevision } from "./state.js";
import { STATIC } from "./api.js";

const ADMIN_TABS = [
  ["questions", "Question Editor"],
  ["inspector", "Scoring Inspector"],
  ["simulate", "Simulation"],
  ["profiles", "Profiles"],
  ["builds", "Build Editor"],
  ["config", "Configuration"],
];

const LOADERS = {
  "": () => import("./views/quiz.js"),
  "specs": () => import("./views/specs.js"),
  "admin/questions": () => import("./views/editor.js"),
  "admin/inspector": () => import("./views/inspector.js"),
  "admin/simulate": () => import("./views/simulate.js"),
  "admin/profiles": () => import("./views/profiles.js"),
  "admin/builds": () => import("./views/builds.js"),
  "admin/config": () => import("./views/config.js"),
};

const view = document.getElementById("view");
const adminNav = document.getElementById("adminnav");
let navToken = 0;

let routeArgs = [];

/** The route name (a key of LOADERS) and, for specialization pages, the class and specialization ids that follow it. */
function currentRoute() {
  const raw = location.hash.replace(/^#\/?/, "").replace(/\/$/, "");
  const [first, ...rest] = raw.split("/");
  routeArgs = [];
  if (first === "specs") { routeArgs = rest; return "specs"; }
  if (STATIC) return "";                         // the static edition has the participant pages only
  if (raw === "admin") return "admin/questions";
  return raw in LOADERS ? raw : "";
}

let lastRoute = null;
async function route() {
  const name = currentRoute();
  if (state.dirtyGuard && name !== lastRoute && !state.dirtyGuard()) {
    history.replaceState(null, "", "#/" + lastRoute);
    return;
  }
  state.dirtyGuard = null;
  lastRoute = name;
  const mine = ++navToken;
  const isAdmin = name.startsWith("admin/");

  const section = isAdmin ? "admin" : name === "specs" ? "specs" : "quiz";
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === section) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  adminNav.hidden = !isAdmin;
  if (isAdmin) {
    clear(adminNav).append(...ADMIN_TABS.map(([slug, label]) =>
      h("a", { href: `#/admin/${slug}`, "aria-current": name === `admin/${slug}` ? "page" : null }, label)));
  } else {
    setRevision(null);
  }
  view.classList.toggle("narrow", name === "" || name === "specs");
  document.title = (isAdmin ? ADMIN_TABS.find(([s]) => `admin/${s}` === name)[1] + " · " : "") + "Forever Character Oracle";

  clear(view).append(h("p", { class: "muted" }, "Loading…"));
  try {
    const mod = await LOADERS[name]();
    if (mine !== navToken) return;
    clear(view);
    await mod.render(view, routeArgs);
  } catch (err) {
    if (mine !== navToken) return;
    clear(view).append(h("div", { class: "card" }, h("h2", {}, "Something went wrong"), errorList(err),
      h("button", { class: "btn", type: "button", onclick: route }, "Try again")));
  }
  if (mine === navToken) window.scrollTo(0, 0);
}

// ---- theme ------------------------------------------------------------------------------------
const THEMES = ["auto", "light", "dark"];
function applyTheme(mode) {
  if (mode === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = mode;
  document.getElementById("theme-toggle").textContent = `Theme: ${mode}`;
}
let theme = "auto";
try { theme = localStorage.getItem("oracleTheme") || "auto"; } catch { /* storage unavailable */ }
applyTheme(THEMES.includes(theme) ? theme : "auto");
document.getElementById("theme-toggle").addEventListener("click", () => {
  theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
  try { localStorage.setItem("oracleTheme", theme); } catch { /* ignore */ }
  applyTheme(theme);
});

if (STATIC) document.querySelectorAll('[data-nav="admin"]').forEach((a) => a.remove());
window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => { if (state.dirtyGuard && !state.dirtyGuard(true)) { e.preventDefault(); e.returnValue = ""; } });
route();
