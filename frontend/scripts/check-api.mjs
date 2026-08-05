/*
 * API contract check — run against a live backend:
 *
 *   node scripts/check-api.mjs            # defaults to http://localhost:8000
 *   API=http://host:8000 node scripts/check-api.mjs
 *
 * Why this exists: the frontend's paths were written from a spec, and six of
 * them were plausible-but-wrong (/workspaces/{id}/report instead of
 * /report/{id}, POST /jobs/{id}/cancel instead of DELETE /jobs/{id}). Zod
 * validates response *shape*, but a 404 never reaches Zod — so shape validation
 * alone cannot catch a wrong URL. This walks the real OpenAPI schema and
 * asserts every path the client uses actually exists with the right method.
 */

const API = process.env.API || "http://localhost:8000";

/* Every (method, path template) pair the client calls. Keep in sync with src/api/*.ts */
const CALLS = [
  ["GET", "/health"],
  ["GET", "/workspaces"],
  ["GET", "/workspaces/{workspace_id}"],
  ["DELETE", "/workspaces/{workspace_id}"],
  ["POST", "/add"],
  ["POST", "/batch"],
  ["GET", "/jobs"],
  ["GET", "/jobs/{job_id}"],
  ["DELETE", "/jobs/{job_id}"],
  ["POST", "/chat"],
  ["GET", "/messages/{workspace_id}"],
  ["GET", "/claims/{workspace_id}"],
  ["GET", "/themes/{workspace_id}"],
  ["GET", "/report/{workspace_id}"],
];

let spec;
try {
  const res = await fetch(`${API}/openapi.json`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  spec = await res.json();
} catch (err) {
  console.error(`Could not reach ${API}/openapi.json — is the backend running?`);
  console.error(String(err.message ?? err));
  process.exit(2);
}

const available = new Set();
for (const [path, ops] of Object.entries(spec.paths ?? {})) {
  for (const method of Object.keys(ops)) {
    available.add(`${method.toUpperCase()} ${path}`);
  }
}

let failed = 0;
for (const [method, path] of CALLS) {
  const key = `${method} ${path}`;
  if (available.has(key)) {
    console.log(`  ok    ${key}`);
  } else {
    failed++;
    console.log(`  FAIL  ${key}  — not in the backend's OpenAPI schema`);
    const near = [...available].filter((a) =>
      a.toLowerCase().includes(path.split("/")[1]?.toLowerCase() ?? "")
    );
    if (near.length) console.log(`        did you mean: ${near.join(", ")}`);
  }
}

console.log(
  `\n${CALLS.length - failed}/${CALLS.length} client paths match the backend.`
);

/* Also check the response shapes the UI depends on, since a renamed field is
   just as breaking as a wrong path and equally invisible until render. */
const SHAPE_CHECKS = [
  ["/health", ["status", "auth_required", "queue_depth"]],
  ["/workspaces", ["workspaces"]],
  ["/jobs", ["queue_depth", "jobs"]],
];

for (const [path, keys] of SHAPE_CHECKS) {
  try {
    const res = await fetch(API + path);
    const body = await res.json();
    const missing = keys.filter((k) => !(k in body));
    if (missing.length) {
      failed++;
      console.log(`  FAIL  GET ${path} missing field(s): ${missing.join(", ")}`);
    } else {
      console.log(`  ok    GET ${path} shape`);
    }
  } catch {
    failed++;
    console.log(`  FAIL  GET ${path} did not return JSON`);
  }
}

process.exit(failed ? 1 : 0);
