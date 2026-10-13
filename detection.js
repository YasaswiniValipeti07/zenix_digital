const fuzzball = require("fuzzball");

const { normalize_username, similarity_key, parse_official_accounts, RISK_THRESHOLDS } = require("./risk.js");

const _text = (value) => {
  return (value || "").replace(/\s+/g, " ").trim();
};

const _compact = (value) => {
  return (value || "").replace(/[^a-z0-9]/gi, "").toLowerCase();
};

const _domain = (value) => {
  if (!value) return "";
  try {
    const urlStr = value.includes("://") ? value : `https://${value}`;
    const match = urlStr.match(/^https?:\/\/(www\.)?([^/\?]+)/i);
    if (match) {
      return match[2].toLowerCase().replace(/^www\./, "");
    }
  } catch (e) {}
  return "";
};

const _similarity = (candidate, reference) => {
  const candidate_key = similarity_key(candidate);
  const reference_key = similarity_key(reference);
  if (!candidate_key || !reference_key) return 0;
  return Math.max(
    fuzzball.ratio(candidate_key, reference_key),
    fuzzball.WRatio(candidate_key, reference_key)
  );
};

const _signal = (code, label, value, evidence) => {
  return { code, label, value: Math.round(parseFloat(value)), weight: SIGNAL_WEIGHTS[code], evidence };
};

const SIGNAL_WEIGHTS = {
  "username_similarity": 0.75,
  "display_name_similarity": 0.40,
  "brand_keyword": 0.15,
  "description_similarity": 0.20,
  "publisher_mismatch": 0.25,
  "package_mismatch": 0.35,
  "url_mismatch": 0.20,
  "lookalike_pattern": 0.15,
};

const BRAND_KEYWORDS = {
  support: "support",
  help: "help",
  security: "security",
  official: "official",
  verify: "verify",
  verification: "verification",
  customer: "customer",
  service: "service",
  account: "account",
  team: "team",
  care: "care",
  login: "login",
  secure: "secure",
};

const official_match = (candidate, brand) => {
  const username = _text(candidate.username);
  const known_usernames = new Set(
    parse_official_accounts(brand.official_accounts).map((x) => normalize_username(x))
  );
  if (username && known_usernames.has(normalize_username(username))) {
    return "Username exactly matches a registered official account.";
  }

  const candidate_url = _text(candidate.listing_url || candidate.url || "");
  if (candidate_url) {
    const candidate_domain = _domain(candidate_url);
    if (candidate_domain) {
      const official_urls = (brand.official_urls || "").split(/[,\n\r]+/);
      for (const official_url of official_urls) {
        const official_domain = _domain(official_url.trim());
        if (official_domain && candidate_domain === official_domain) {
          return `URL host matches registered official host ${official_domain}.`;
        }
      }
    }
  }

  if (candidate.asset_type === "app") {
    const package_val = _text(candidate.package_id).toLowerCase();
    const publisher = _text(candidate.publisher).toLowerCase();
  }

  return "";
};

const analyze_candidate = (brand, candidate) => {
  const asset_type = candidate.asset_type || "social";
  const official_reason = official_match({ ...candidate, asset_type }, brand);
  const candidate_name = _text(candidate.username || candidate.app_name || "");
  const display_name = _text(candidate.display_name || candidate.app_name || "");
  const description = _text(candidate.description);
  const signals = [];
  const evidence = [];

  if (official_reason) {
    evidence.push({ kind: "official_exclusion", detail: official_reason });
    return {
      asset_type,
      candidate_username: candidate_name.length > 30 ? candidate_name.substring(0, 30) : candidate_name || "official-asset",
      candidate_display_name: display_name.length > 160 ? display_name.substring(0, 160) : display_name,
      candidate_description: description,
      publisher: (_text(candidate.publisher) || "").length > 160 ? _text(candidate.publisher).substring(0, 160) : _text(candidate.publisher) || "",
      package_id: (_text(candidate.package_id) || "").length > 180 ? _text(candidate.package_id).substring(0, 180) : _text(candidate.package_id) || "",
      listing_url: (_text(candidate.listing_url || candidate.url || "") || "").length > 500 ? _text(candidate.listing_url || candidate.url || "").substring(0, 500) : _text(candidate.listing_url || candidate.url || "") || "",
      source: (_text(candidate.source) || "manual").length > 80 ? _text(candidate.source).substring(0, 80) : _text(candidate.source) || "manual",
      similarity_score: null,
      risk_score: 0,
      confidence_score: 100,
      risk_status: "official",
      review_status: "reviewed",
      explanation: official_reason.length > 255 ? official_reason.substring(0, 255) : official_reason,
      detected_signals: [],
      evidence: evidence,
    };
  }

  const brand_names = [brand.brand_name];
  const official_usernames = parse_official_accounts(brand.official_accounts);
  brand_names.push(...official_usernames);
  const best_username_score = Math.max(
    ...(brand_names.map((ref) => _similarity(candidate_name, ref)).filter((s) => s !== null).concat([0])),
    0
  );

  if (best_username_score >= 35) {
    signals.push(_signal(
      "username_similarity",
      "Username / app-name similarity",
      best_username_score,
      `Closest comparison against this brand's registered names: ${Math.round(best_username_score)}% character similarity.`
    ));
  }

  const name_score = Math.max(
    ...(brand_names.map((ref) => _similarity(display_name, ref)).filter((s) => s !== null).concat([0])),
    0
  );
  if (display_name && name_score >= 45) {
    signals.push(_signal(
      "display_name_similarity",
      "Display-name similarity",
      name_score,
      `Submitted display/app name resembles a registered brand reference (${Math.round(name_score)}%).`
    ));
  }

  const combined_text = `${candidate_name} ${display_name} ${description}`.toLowerCase();
  const matched_keywords = Object.keys(BRAND_KEYWORDS).filter((keyword) => {
    const regex = new RegExp(`(?<!${keyword})${keyword}(?!${keyword})`, "i");
    return regex.test(combined_text);
  });
  if (matched_keywords.length > 0) {
    signals.push(_signal(
      "brand_keyword",
      "Brand-support language",
      68,
      `Brand-sensitive terms present: ${matched_keywords.join(", ")}.`
    ));
  }

  if (description) {
    const description_score = _similarity(description, brand.brand_name);
    if (description_score >= 55) {
      signals.push(_signal(
        "description_similarity",
        "Description similarity",
        description_score,
        `Description has textual similarity to the brand name (${Math.round(description_score)}%); context is not verified.`
      ));
    }
  }

  if (asset_type === "app") {
    const package_id = _text(candidate.package_id).toLowerCase();
    const publisher = _text(candidate.publisher).toLowerCase();
    if (package_id) {
      signals.push(_signal(
        "package_mismatch",
        "Package identifier differs",
        100,
        "Candidate package identifier differs from the registered official app identifiers."
      ));
    }
    if (publisher) {
      signals.push(_signal(
        "publisher_mismatch",
        "Publisher differs",
        85,
        "Candidate publisher differs from registered official app publishers."
      ));
    }
    const listing_domain = _domain(candidate.listing_url);
    if (listing_domain) {
      signals.push(_signal(
        "url_mismatch",
        "Listing host differs",
        70,
        `Candidate listing host ${listing_domain} is not among official app listing hosts.`
      ));
    }
  }

  const compact = _compact(candidate_name);
  if (compact && candidate_name && /[._-]{2,}|[0-9]/.test(candidate_name)) {
    const pattern_score = candidate_name.match(/\d/) ? 55 : 40;
    signals.push(_signal(
      "lookalike_pattern",
      "Look-alike formatting",
      pattern_score,
      "Extra punctuation or digits may warrant a closer look; this is not proof of impersonation."
    ));
  }

  // Normalize signal values before applying configured weights
  const risk_score = Math.round(Math.min(100, sum_signal_values(signals)));
  let risk_status, classification;
  if (risk_score >= RISK_THRESHOLDS.high_priority) {
    risk_status = "high";
    classification = "High Priority Review";
  } else if (risk_score >= RISK_THRESHOLDS.needs_review) {
    risk_status = "possible";
    classification = "Needs Review";
  } else {
    risk_status = "low";
    classification = "Low Risk";
  }

  const supplied_fields = [
    candidate.username,
    candidate.app_name,
    candidate.display_name,
    candidate.description,
    candidate.publisher,
    candidate.package_id,
    candidate.listing_url,
  ].filter((value) => _text(value).length > 0).length;
  let confidence = Math.min(95, 35 + supplied_fields * 10 + signals.length * 5);
  if (supplied_fields <= 1) {
    confidence = Math.min(confidence, 45);
  }

  const reason = signals.length > 0 ? signals.map((s) => s.label).join("; ") : "No strong similarity or risk signals were found in the supplied fields.";
  const detailed_evidence = [
    ...signals.map((s) => ({ kind: s.code, detail: s.evidence })),
    { kind: "limitation", detail: "Local heuristic analysis of submitted fields only; profile authenticity and intent have not been verified." }
  ];

  return {
    asset_type,
    candidate_username: candidate_name.length > 30 ? candidate_name.substring(0, 30) : candidate_name,
    candidate_display_name: display_name.length > 160 ? display_name.substring(0, 160) : display_name,
    candidate_description: description,
    publisher: (_text(candidate.publisher) || "").length > 160 ? _text(candidate.publisher).substring(0, 160) : _text(candidate.publisher) || "",
    package_id: (_text(candidate.package_id) || "").length > 180 ? _text(candidate.package_id).substring(0, 180) : _text(candidate.package_id) || "",
    listing_url: (_text(candidate.listing_url || candidate.url || "") || "").length > 500 ? _text(candidate.listing_url || candidate.url || "").substring(0, 500) : _text(candidate.listing_url || candidate.url || "") || "",
    source: (_text(candidate.source) || "manual").length > 80 ? _text(candidate.source).substring(0, 80) : _text(candidate.source) || "manual",
    similarity_score: Math.round(best_username_score),
    risk_score,
    confidence_score: confidence,
    risk_status,
    review_status: risk_status !== "low" ? "pending" : "pending",
    explanation: `${classification}: ${reason}`.substring(0, 255),
    detected_signals: signals,
    evidence: detailed_evidence,
  };
};

const sum_signal_values = (signals) => {
  return signals.reduce((sum, signal) => sum + signal.value * signal.weight, 0);
};

module.exports = { analyze_candidate, RISK_THRESHOLDS, BRAND_KEYWORDS, SIGNAL_WEIGHTS, official_match };