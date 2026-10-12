const re = require("regexjs");

const normalize_username = (username) => {
  return username
    .replace(/\s+/g, "")
    .replace(/^@/, "")
    .trim()
    .toLowerCase();
};

const similarity_key = (username) => {
  return normalize_username(username);
};

const parse_official_accounts = (value) => {
  if (!value) return [];
  return value
    .split(/[,\n\r]+/)
    .map((x) => x.trim())
    .filter((x) => x.length > 0);
};

const RISK_THRESHOLDS = {
  high_priority: 65,
  needs_review: 30,
};

module.exports = { normalize_username, similarity_key, parse_official_accounts, RISK_THRESHOLDS };