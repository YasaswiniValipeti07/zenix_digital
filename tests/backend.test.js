const { after, test } = require("node:test");
const assert = require("node:assert/strict");

const previousSupabaseUrl = process.env.SUPABASE_URL;
const previousSupabaseKey = process.env.SUPABASE_ANON_KEY;
const previousNodeEnv = process.env.NODE_ENV;
delete process.env.SUPABASE_URL;
delete process.env.SUPABASE_ANON_KEY;
process.env.NODE_ENV = "test";
const app = require("../index");
const { analyze_candidate } = require("../detection");

const server = app.listen(0);
const baseUrl = `http://127.0.0.1:${server.address().port}`;

after(() => {
  server.close();
  if (previousSupabaseUrl === undefined) delete process.env.SUPABASE_URL;
  else process.env.SUPABASE_URL = previousSupabaseUrl;
  if (previousSupabaseKey === undefined) delete process.env.SUPABASE_ANON_KEY;
  else process.env.SUPABASE_ANON_KEY = previousSupabaseKey;
  if (previousNodeEnv === undefined) delete process.env.NODE_ENV;
  else process.env.NODE_ENV = previousNodeEnv;
});

test("health endpoint reports backend and database configuration status", async () => {
  const response = await fetch(`${baseUrl}/health`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    status: "ok",
    database_configured: false,
  });
});

test("API explains missing database configuration", async () => {
  const response = await fetch(`${baseUrl}/brands`);
  assert.equal(response.status, 503);
  assert.match((await response.json()).error, /SUPABASE_URL/);
});

test("CORS allows the local Vite origin and rejects unknown browser origins", async () => {
  const allowed = await fetch(`${baseUrl}/health`, {
    headers: { Origin: "http://localhost:5173" },
  });
  assert.equal(allowed.headers.get("access-control-allow-origin"), "http://localhost:5173");

  const denied = await fetch(`${baseUrl}/health`, {
    headers: { Origin: "https://untrusted.example" },
  });
  assert.equal(denied.status, 403);
});

test("single-field candidate assessment returns a confidence score", () => {
  const result = analyze_candidate(
    { brand_name: "NovaPay", official_accounts: "novapay" },
    { asset_type: "social", username: "novapay_support" },
  );
  assert.equal(typeof result.confidence_score, "number");
  assert.ok(result.confidence_score <= 45);
});
