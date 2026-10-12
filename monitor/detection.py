"""Explainable, local heuristic threat triage; no external AI calls are made."""

import re
from urllib.parse import urlsplit

from rapidfuzz import fuzz

from .models import MonitoringResult
from .risk import normalize_username, parse_official_accounts, similarity_key


# Weights can be tuned centrally. Signals are normalized and capped before aggregation.
SIGNAL_WEIGHTS = {
    "username_similarity": 0.75,
    "display_name_similarity": 0.40,
    "brand_keyword": 0.15,
    "description_similarity": 0.20,
    "publisher_mismatch": 0.25,
    "package_mismatch": 0.35,
    "url_mismatch": 0.20,
    "lookalike_pattern": 0.15,
}
BRAND_KEYWORDS = {
    "support", "help", "security", "official", "verify", "verification",
    "customer", "service", "account", "team", "care", "login", "secure",
}
RISK_THRESHOLDS = {"high_priority": 65, "needs_review": 30}


def _text(value):
    return re.sub(r"\s+", " ", (value or "")).strip()


def _compact(value):
    return re.sub(r"[^a-z0-9]", "", _text(value).casefold())


def _domain(value):
    try:
        return (urlsplit(value if "://" in value else f"https://{value}").hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _similarity(candidate, reference):
    candidate_key = similarity_key(candidate)
    reference_key = similarity_key(reference)
    if not candidate_key or not reference_key:
        return 0
    return max(
        fuzz.ratio(candidate_key, reference_key),
        fuzz.WRatio(candidate_key, reference_key),
    )


def _signal(code, label, value, evidence):
    return {"code": code, "label": label, "value": round(float(value)), "weight": SIGNAL_WEIGHTS[code], "evidence": evidence}


def official_match(candidate, brand):
    """Return the official-match reason before any risk signals are calculated."""
    username = _text(candidate.get("username"))
    known_usernames = {normalize_username(x) for x in parse_official_accounts(brand.official_accounts)}
    if username and normalize_username(username) in known_usernames:
        return "Username exactly matches a registered official account."

    candidate_url = _text(candidate.get("listing_url") or candidate.get("url"))
    candidate_domain = _domain(candidate_url) if candidate_url else ""
    if candidate_domain:
        for official_url in re.split(r"[,\n\r]+", brand.official_urls or ""):
            official_domain = _domain(official_url.strip())
            if official_domain and candidate_domain == official_domain:
                return f"URL host matches registered official host {official_domain}."

    if candidate.get("asset_type") == MonitoringResult.AssetType.APP:
        package = _text(candidate.get("package_id")).casefold()
        publisher = _text(candidate.get("publisher")).casefold()
        for asset in brand.official_apps.all():
            if package and asset.package_id and package == asset.package_id.casefold():
                return f"Package identifier exactly matches registered official app {asset.package_id}."
            if candidate_url and asset.listing_url and candidate_url.rstrip("/").casefold() == asset.listing_url.rstrip("/").casefold():
                return "Listing URL exactly matches a registered official app listing."
            if not package and publisher and asset.publisher and publisher == asset.publisher.casefold() and _compact(candidate.get("app_name")) == _compact(asset.app_name):
                return f"App name and publisher match registered official app {asset.app_name}."
    return ""


def analyze_candidate(brand, candidate):
    """Analyze one submitted/imported record and return fields suitable for persistence."""
    asset_type = candidate.get("asset_type", MonitoringResult.AssetType.SOCIAL)
    official_reason = official_match({**candidate, "asset_type": asset_type}, brand)
    candidate_name = _text(candidate.get("username") or candidate.get("app_name"))
    display_name = _text(candidate.get("display_name") or candidate.get("app_name"))
    description = _text(candidate.get("description"))
    signals = []
    evidence = []
    if official_reason:
        evidence.append({"kind": "official_exclusion", "detail": official_reason})
        return {
            "asset_type": asset_type,
            "candidate_username": candidate_name[:30] or "official-asset",
            "candidate_display_name": display_name[:160],
            "candidate_description": description,
            "publisher": _text(candidate.get("publisher"))[:160],
            "package_id": _text(candidate.get("package_id"))[:180],
            "listing_url": _text(candidate.get("listing_url") or candidate.get("url"))[:500],
            "source": _text(candidate.get("source") or "manual")[:80],
            "similarity_score": None,
            "risk_score": 0,
            "confidence_score": 100,
            "risk_status": MonitoringResult.RiskStatus.OFFICIAL,
            "review_status": MonitoringResult.ReviewStatus.REVIEWED,
            "explanation": official_reason[:255],
            "detected_signals": [],
            "evidence": evidence,
        }

    brand_names = [brand.brand_name]
    official_usernames = parse_official_accounts(brand.official_accounts)
    brand_names.extend(official_usernames)
    best_username_score = max((_similarity(candidate_name, ref) for ref in brand_names), default=0)
    if best_username_score >= 35:
        signals.append(_signal("username_similarity", "Username / app-name similarity", best_username_score, f"Closest comparison against this brand's registered names: {round(best_username_score)}% character similarity."))

    name_score = max((_similarity(display_name, ref) for ref in [brand.brand_name, *official_usernames]), default=0)
    if display_name and name_score >= 45:
        signals.append(_signal("display_name_similarity", "Display-name similarity", name_score, f"Submitted display/app name resembles a registered brand reference ({round(name_score)}%)."))

    combined_text = f"{candidate_name} {display_name} {description}".casefold()
    matched_keywords = sorted(keyword for keyword in BRAND_KEYWORDS if re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", combined_text))
    if matched_keywords:
        signals.append(_signal("brand_keyword", "Brand-support language", 68, "Brand-sensitive terms present: " + ", ".join(matched_keywords) + "."))

    if description:
        description_score = _similarity(description, brand.brand_name)
        if description_score >= 55:
            signals.append(_signal("description_similarity", "Description similarity", description_score, f"Description has textual similarity to the brand name ({round(description_score)}%); context is not verified."))

    if asset_type == MonitoringResult.AssetType.APP:
        official_apps = list(brand.official_apps.all())
        package_id = _text(candidate.get("package_id")).casefold()
        publisher = _text(candidate.get("publisher")).casefold()
        known_packages = {x.package_id.casefold() for x in official_apps if x.package_id}
        known_publishers = {x.publisher.casefold() for x in official_apps if x.publisher}
        if package_id and known_packages and package_id not in known_packages:
            signals.append(_signal("package_mismatch", "Package identifier differs", 100, "Candidate package identifier differs from the registered official app identifiers."))
        if publisher and known_publishers and publisher not in known_publishers:
            signals.append(_signal("publisher_mismatch", "Publisher differs", 85, "Candidate publisher differs from registered official app publishers."))
        listing_domain = _domain(candidate.get("listing_url"))
        official_domains = {_domain(x.listing_url) for x in official_apps if x.listing_url}
        if listing_domain and official_domains and listing_domain not in official_domains:
            signals.append(_signal("url_mismatch", "Listing host differs", 70, f"Candidate listing host {listing_domain} is not among official app listing hosts."))

    compact = _compact(candidate_name)
    if compact and candidate_name and re.search(r"[._-]{2,}|[0-9]", candidate_name):
        pattern_score = 55 if any(char.isdigit() for char in candidate_name) else 40
        signals.append(_signal("lookalike_pattern", "Look-alike formatting", pattern_score, "Extra punctuation or digits may warrant a closer look; this is not proof of impersonation."))

    # Normalize signal values before applying configured weights. A score is a triage aid.
    risk_score = round(min(100, sum(item["value"] * item["weight"] for item in signals)))
    if risk_score >= RISK_THRESHOLDS["high_priority"]:
        status = MonitoringResult.RiskStatus.HIGH
        classification = "High Priority Review"
    elif risk_score >= RISK_THRESHOLDS["needs_review"]:
        status = MonitoringResult.RiskStatus.POSSIBLE
        classification = "Needs Review"
    else:
        status = MonitoringResult.RiskStatus.LOW
        classification = "Low Risk"

    supplied_fields = sum(bool(_text(candidate.get(key))) for key in ("username", "display_name", "description", "publisher", "package_id", "listing_url"))
    confidence = min(95, 35 + supplied_fields * 10 + len(signals) * 5)
    if supplied_fields <= 1:
        confidence = min(confidence, 45)
    reason = "; ".join(item["label"] for item in signals) or "No strong similarity or risk signals were found in the supplied fields."
    evidence.extend({"kind": item["code"], "detail": item["evidence"]} for item in signals)
    evidence.append({"kind": "limitation", "detail": "Local heuristic analysis of submitted fields only; profile authenticity and intent have not been verified."})
    return {
        "asset_type": asset_type,
        "candidate_username": (candidate_name or "candidate")[:30],
        "candidate_display_name": display_name[:160],
        "candidate_description": description,
        "publisher": _text(candidate.get("publisher"))[:160],
        "package_id": _text(candidate.get("package_id"))[:180],
        "listing_url": _text(candidate.get("listing_url") or candidate.get("url"))[:500],
        "source": _text(candidate.get("source") or "manual")[:80],
        "similarity_score": round(best_username_score),
        "risk_score": risk_score,
        "confidence_score": confidence,
        "risk_status": status,
        "review_status": MonitoringResult.ReviewStatus.PENDING if status != MonitoringResult.RiskStatus.LOW else MonitoringResult.ReviewStatus.PENDING,
        "explanation": f"{classification}: {reason}"[:255],
        "detected_signals": signals,
        "evidence": evidence,
    }
