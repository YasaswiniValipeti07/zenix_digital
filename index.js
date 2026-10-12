const express = require("express");
const { createClient } = require("@supabase/supabase-js");
const csvStringify = require("csv-stringify/sync");
const fs = require("fs");
const path = require("path");

const app = express();
const port = process.env.PORT || 3000;

const supabaseUrl = process.env.SUPABASE_URL || "https://your-project.supabase.co";
const supabaseKey = process.env.SUPABASE_ANON_KEY || "your-anon-key";
const supabase = createClient(supabaseUrl, supabaseKey);

app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
  if (req.method === "OPTIONS") {
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    return res.status(204).end();
  }
  next();
});

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
app.get("/", (req, res) => {
  res.json({
    name: "Digital Risk Protection API",
    status: "running",
    version: "2.0.0",
    database: "Supabase",
  });
});

// ---------------------------------------------------------------------------
// Brands routes
// ---------------------------------------------------------------------------

// GET /brands - list all brands with counts
app.get("/brands", async (req, res) => {
  try {
    const { data: brands, error } = await supabase
      .from("brands")
      .select("id, brand_name, official_accounts, official_urls, created_at");

    if (error) throw error;

    // Get result counts per brand
    const brandIds = brands.map((b) => b.id);
    let resultCounts = {};
    if (brandIds.length > 0) {
      const { count, error: countError } = await supabase
        .from("monitoring_results")
        .select("brand", { count: "exact", head: true })
        .in("brand", brandIds);
      if (!countError) {
        brands.forEach((b) => (resultCounts[b.id] = count || 0));
      }
    }

    const result = brands.map((b) => ({
      id: b.id,
      brand_name: b.brand_name,
      official_accounts: b.official_accounts,
      official_urls: b.official_urls,
      registered_at: b.created_at,
      checks_saved: resultCounts[b.id] || 0,
    }));

    res.json(result);
  } catch (err) {
    console.error("Error fetching brands:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /brands/register - register a new brand
app.post("/brands/register", async (req, res) => {
  try {
    const { brand_name, official_accounts, official_urls } = req.body;

    if (!brand_name) {
      return res.status(400).json({ error: "Brand name is required" });
    }

    // Check if brand already exists (case-insensitive)
    const { data: existing, error: checkError } = await supabase
      .from("brands")
      .select("id")
      .ilike("brand_name", brand_name)
      .single();

    if (checkError && checkError.code !== "PGRST116") throw checkError;
    if (existing) {
      return res.status(409).json({ error: "This brand is already registered." });
    }

    const { data, error } = await supabase
      .from("brands")
      .insert([{ brand_name, official_accounts: official_accounts || "", official_urls: official_urls || "" }])
      .select()
      .single();

    if (error) throw error;
    res.json({ success: true, brand: data });
  } catch (err) {
    console.error("Error registering brand:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /brands/apps/register - register official app
app.post("/brands/apps/register", async (req, res) => {
  try {
    const { brand_id, app_name, publisher, package_id, listing_url } = req.body;

    if (!brand_id || !app_name) {
      return res.status(400).json({ error: "Brand ID and app name are required" });
    }

    const { data, error } = await supabase
      .from("official_apps")
      .insert([
        { brand_id, app_name, publisher: publisher || "", package_id: package_id || "", listing_url: listing_url || "" },
      ])
      .select()
      .single();

    if (error) throw error;
    res.json({ success: true, asset: data });
  } catch (err) {
    console.error("Error registering official app:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Monitoring results routes
// ---------------------------------------------------------------------------

// GET /results - list all monitoring results with filters
app.get("/results", async (req, res) => {
  try {
    let query = supabase.from("monitoring_results").select("*", { count: "exact" });

    // Filter by brand
    if (req.query.brand) {
      query = query.eq("brand", req.query.brand);
    }

    // Filter by asset type
    if (req.query.asset_type) {
      query = query.eq("asset_type", req.query.asset_type);
    }

    // Filter by risk status
    if (req.query.risk_status) {
      query = query.eq("risk_status", req.query.risk_status);
    }

    // Filter by review status
    if (req.query.review_status) {
      query = query.eq("review_status", req.query.review_status);
    }

    // Date range filters
    if (req.query.start_date) {
      query = query.gte("created_at", req.query.start_date);
    }
    if (req.query.end_date) {
      query = query.lte("created_at", req.query.end_date);
    }

    // Order by created_at desc
    query = query.order("created_at", { ascending: false });

    const { data: results, error, count } = await query;

    if (error) throw error;

    res.json({
      results,
      count: count || 0,
    });
  } catch (err) {
    console.error("Error fetching results:", err);
    res.status(500).json({ error: err.message });
  }
});

// GET /results/recent - recent results
app.get("/results/recent", async (req, res) => {
  try {
    const { data: results, error } = await supabase
      .from("monitoring_results")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(6);

    if (error) throw error;
    res.json(results);
  } catch (err) {
    console.error("Error fetching recent results:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /results - create a new monitoring result (from analysis)
app.post("/results", async (req, res) => {
  try {
    const resultData = req.body;

    const { data, error } = await supabase
      .from("monitoring_results")
      .insert([resultData])
      .select()
      .single();

    if (error) throw error;
    res.json({ success: true, result: data });
  } catch (err) {
    console.error("Error creating result:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /results/scan - scan usernames for a brand
app.post("/results/scan", async (req, res) => {
  try {
    const { brand_id, usernames, asset_type } = req.body;

    if (!brand_id || !usernames || !Array.isArray(usernames)) {
      return res.status(400).json({ error: "brand_id and usernames array are required" });
    }

    // Get brand info
    const { data: brand, error: brandError } = await supabase.from("brands").select("*").eq("id", brand_id).single();
    if (brandError) throw brandError;

    const createdResults = [];

    for (const username of usernames) {
      // Run the analysis (local heuristic)
      const assessment = analyzeCandidate(brand, {
        asset_type: asset_type || "social",
        username,
        source: "manual",
      });

      const { data, error } = await supabase
        .from("monitoring_results")
        .insert([assessment])
        .select()
        .single();

      if (error) throw error;
      createdResults.push(data);
    }

    res.json({
      success: true,
      checked: createdResults.length,
      results: createdResults,
    });
  } catch (err) {
    console.error("Error scanning usernames:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /results/update-review-status - update review status
app.post("/results/update-review-status", async (req, res) => {
  try {
    const { result_id, review_status, return_to } = req.body;

    if (!result_id || !review_status) {
      return res.status(400).json({ error: "result_id and review_status are required" });
    }

    const { data, error } = await supabase
      .from("monitoring_results")
      .update({ review_status })
      .eq("id", result_id)
      .select()
      .single();

    if (error) throw error;

    const destinations = {
      home: "results",
      investigations: "investigation_center",
      social: "results?asset_type=social",
      apps: "results?asset_type=apps",
    };

    const redirectUrl = destinations[return_to] || "results";

    res.json({
      success: true,
      result: data,
      redirectUrl,
    });
  } catch (err) {
    console.error("Error updating review status:", err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Detection / risk analysis logic (ported from Django)
// ---------------------------------------------------------------------------

// Import the risk assessment functions
const { normalize_username, similarity_key, parse_official_accounts, RISK_THRESHOLDS } = require("./risk.js");
const { analyze_candidate } = require("./detection.js");

// POST /analyze - analyze a candidate username/app
app.post("/analyze", async (req, res) => {
  try {
    const { brand_id, asset_type, username, app_name, display_name, description, publisher, package_id, listing_url } = req.body;

    if (!brand_id) {
      return res.status(400).json({ error: "brand_id is required" });
    }

    // Get brand info
    const { data: brand, error: brandError } = await supabase.from("brands").select("*").eq("id", brand_id).single();
    if (brandError) throw brandError;

    const candidate = {
      asset_type: asset_type || "social",
      username: username || "",
      app_name: app_name || "",
      display_name: display_name || "",
      description: description || "",
      publisher: publisher || "",
      package_id: package_id || "",
      listing_url: listing_url || "",
      source: "manual",
    };

    const result = analyze_candidate(brand, candidate);

    // Save result to database
    const { data, error } = await supabase
      .from("monitoring_results")
      .insert([
        {
          brand_id,
          asset_type: result.asset_type,
          candidate_username: result.candidate_username,
          candidate_display_name: result.candidate_display_name,
          candidate_description: result.candidate_description,
          publisher: result.publisher,
          package_id: result.package_id,
          listing_url: result.listing_url,
          source: result.source,
          similarity_score: result.similarity_score,
          risk_score: result.risk_score,
          confidence_score: result.confidence_score,
          risk_status: result.risk_status,
          review_status: result.review_status,
          explanation: result.explanation,
          detected_signals: result.detected_signals,
          evidence: result.evidence,
        },
      ])
      .select()
      .single();

    if (error) throw error;
    res.json({ success: true, result: data });
  } catch (err) {
    console.error("Error analyzing candidate:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /import/csv - import candidates from CSV
app.post("/import/csv", async (req, res) => {
  try {
    const { brand_id, asset_type, csvContent } = req.body;

    if (!brand_id || !asset_type) {
      return res.status(400).json({ error: "brand_id and asset_type are required" });
    }

    // Get brand info
    const { data: brand, error: brandError } = await supabase.from("brands").select("*").eq("id", brand_id).single();
    if (brandError) throw brandError;

    // Parse CSV
    const records = parseCsv(csvContent, asset_type);

    if (records.length === 0) {
      return res.status(400).json({ error: "No valid candidate records found in CSV" });
    }

    const createdResults = [];

    for (const candidate of records) {
      const assessment = analyzeCandidate(brand, {
        ...candidate,
        asset_type,
        source: "csv-import",
      });

      const { data, error } = await supabase
        .from("monitoring_results")
        .insert([assessment])
        .select()
        .single();

      if (error) throw error;
      createdResults.push(data);
    }

    res.json({
      success: true,
      imported: createdResults.length,
      results: createdResults,
    });
  } catch (err) {
    console.error("Error importing CSV:", err);
    res.status(500).json({ error: err.message });
  }
});

// Helper: parse CSV content
function parseCsv(csvContent, assetType) {
  try {
    const records = [];
    const rows = csvParse(csvContent, { headers: true, skip_empty_lines: true, trim: true });

    for (const row of rows) {
      const record = {};

      if (assetType === "social") {
        record.username = row.username || "";
        record.display_name = row.display_name || "";
        record.description = row.description || "";
      } else {
        record.app_name = row.app_name || "";
        record.publisher = row.publisher || "";
        record.package_id = row.package_id || "";
        record.description = row.description || "";
        record.listing_url = row.listing_url || "";
      }

      if (Object.values(record).some((v) => v && v.toString().length > 0)) {
        records.push(record);
      }
    }

    return records;
  } catch (e) {
    throw new Error(`CSV parse error: ${e.message}`);
  }
}

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

app.listen(port, () => {
  console.log(`🚀 Sentinel API running at http://localhost:${port}`);
  console.log(`📊 Database: Supabase`);
  console.log(`🔍 Fuzzy matching: fuzzball`);
});

module.exports = app;