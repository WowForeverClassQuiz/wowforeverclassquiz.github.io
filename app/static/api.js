// Thin client for the REST API. All scoring happens on the server; the UI only renders what it returns.
//
// The static edition (index.html carries <meta name="oracle-mode" content="static">) has no server: the same two participant
// calls, GET /quiz and POST /evaluate, are answered from data/oracle.json and the in-browser engine (engine.js). Everything
// else, i.e. the administration API, is not available there.
import { askToken } from "./ui.js";

export const STATIC = (document.querySelector('meta[name="oracle-mode"]') || {}).content === "static";
const BASE = "/api/v1";
let token = "";
try { token = sessionStorage.getItem("oracleAdminToken") || ""; } catch { /* storage unavailable */ }

export class ApiError extends Error {
  constructor(status, detail) {
    const d = detail && typeof detail === "object" && !Array.isArray(detail) ? detail : {};
    const msg = d.message || (Array.isArray(detail) ? detail.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ") : String(detail || `HTTP ${status}`));
    super(msg);
    this.status = status;
    this.code = d.code || "";
    this.errors = d.errors || (Array.isArray(detail) ? detail.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`) : []);
    this.detail = detail;
  }
}

let staticReady = null;
function loadStatic() {
  staticReady ||= (async () => {
    const [engine, res] = await Promise.all([import("./engine.js"), fetch(new URL("data/oracle.json", document.baseURI))]);
    if (!res.ok) throw new ApiError(res.status, { message: `The quiz data could not be loaded (HTTP ${res.status}).` });
    const data = await res.json();
    return { engine, data, compiled: engine.prepare(data) };
  })().catch((err) => { staticReady = null; throw err; });
  return staticReady;
}

async function staticApi(path, method, body) {
  const { engine, data, compiled } = await loadStatic();
  if (method === "GET" && path === "/quiz") return data.quiz;
  if (method === "GET" && path === "/classes") return data.classes;
  if (method === "GET" && path === "/version") return data.build;
  const spec = method === "GET" && /^\/specializations\/([^/]+)\/([^/]+)$/.exec(path);
  if (spec) {
    const key = `${spec[1]}/${spec[2]}`, page = data.specs[key];
    if (!page) throw new ApiError(404, { code: "not_found", message: `Unknown specialization '${key}'.` });
    return data.builds[key] ? { ...page, build: data.builds[key] } : page;
  }
  if (method === "POST" && path === "/adaptive/next") {
    try {
      return engine.adaptiveStatus(compiled, body.answers || {});
    } catch (err) {
      if (err instanceof engine.ScoringError) throw new ApiError(422, { code: err.code, message: err.message });
      throw err;
    }
  }
  if (method === "POST" && path === "/evaluate") {
    try {
      return engine.evaluate(compiled, body.answers, { length: body.length || "long" });
    } catch (err) {
      if (err instanceof engine.ScoringError) throw new ApiError(422, { code: err.code, message: err.message });
      throw err;
    }
  }
  throw new ApiError(404, { code: "static_edition", message: "The administration tools are only available when the Oracle runs locally." });
}

export async function api(path, { method = "GET", body, query, retry = true } = {}) {
  if (STATIC) return staticApi(path, method, body);
  let url = BASE + path;
  if (query) {
    const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    if ([...qs].length) url += "?" + qs;
  }
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  if (res.status === 401 && retry) {
    const entered = await askToken();
    if (entered) {
      token = entered;
      try { sessionStorage.setItem("oracleAdminToken", token); } catch { /* ignore */ }
      return api(path, { method, body, query, retry: false });
    }
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) throw new ApiError(res.status, data && data.detail !== undefined ? data.detail : data);
  return data;
}

export const get = (p, query) => api(p, { query });
export const post = (p, body) => api(p, { method: "POST", body });
export const patch = (p, body) => api(p, { method: "PATCH", body });
export const put = (p, body) => api(p, { method: "PUT", body });
export const del = (p, query) => api(p, { method: "DELETE", query });
