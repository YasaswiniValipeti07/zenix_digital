import re

from rapidfuzz import fuzz


def normalize_username(username):
    """Normalize case and insignificant surrounding/embedded whitespace."""
    return re.sub(r"\s+", "", username.strip().removeprefix("@")).casefold()


def similarity_key(username):
    """Ignore spaces and underscores for similarity, not official-account identity."""
    return re.sub(r"[\s_]+", "", normalize_username(username))


def parse_official_accounts(value):
    return [account.strip() for account in re.split(r"[,\n\r]+", value) if account.strip()]


def assess_username(candidate, brand_name, official_accounts):
    official_keys = {normalize_username(item) for item in official_accounts}
    candidate_key = normalize_username(candidate)
    if candidate_key in official_keys:
        return {
            "similarity_score": None,
            "risk_status": "official",
            "review_status": "reviewed",
            "explanation": "Exact registered official username; excluded from suspicious matches.",
        }

    references = [brand_name, *official_accounts]
    best_reference, score = max(
        (
            (reference, fuzz.ratio(similarity_key(candidate), similarity_key(reference)))
            for reference in references
        ),
        key=lambda match: match[1],
    )
    score = round(score)
    if score >= 85:
        risk_status = "high"
        explanation = f"Strong character-level similarity to '{best_reference}'; human review is recommended."
    elif score >= 65:
        risk_status = "possible"
        explanation = f"Some character-level similarity to '{best_reference}'; check the profile context."
    else:
        risk_status = "low"
        explanation = f"Low character-level similarity to '{best_reference}'."

    return {
        "similarity_score": score,
        "risk_status": risk_status,
        "review_status": "pending",
        "explanation": explanation,
    }