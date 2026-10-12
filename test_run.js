const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

// Start the node server
const server = spawn("node", ["index.js"], {
  cwd: "C:/Users/user/OneDrive/Desktop/digital-risk-protection",
  stdio: "pipe",
  env: { ...process.env, SUPABASE_URL: "https://test.supabase.co", SUPABASE_ANON_KEY: "test-key" }
});

let serverReady = false;
let attempts = 0;

server.stdout.on("data", (data) => {
  const output = data.toString();
  if (output.includes("Sentinel API running")) {
    serverReady = true;
    console.log("Server started successfully");
  }
  if (!serverReady) {
    console.log("Server output:", output.substring(0, 200));
  }
});

server.stderr.on("data", (data) => {
  console.error("Server error:", data.toString().substring(0, 200));
});

setTimeout(() => {
  if (serverReady) {
    // Test health endpoint
    const req = http.request({
      hostname: "localhost",
      port: 3000,
      path: "/",
      method: "GET",
      timeout: 3000
    }, (res) => {
      let body = "";
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => {
        console.log("Health check response:", body);
        server.kill();
        process.exit(0);
      });
    });
    req.on("error", (e) => {
      console.error("Request error:", e.message);
      server.kill();
      process.exit(1);
    });
    req.end();
  } else {
    console.log("Server did not ready in time");
    server.kill();
    process.exit(1);
  }
}, 5000);

server.on("error", (e) => {
  console.error("Server process error:", e.message);
  process.exit(1);
}, 2000);