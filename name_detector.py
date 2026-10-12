from rapidfuzz import fuzz

official_brand = "NovaPay"

# Official account usernames
official_accounts = [
    "novapay",
    "novapay_india"
]

candidate_accounts = [
    "novapay",
    "novapay_india",
    "novapaay",
    "nova_pay",
    "novapay_support",
    "best_cooking_tips"
]

for account in candidate_accounts:
    normalized = account.lower().replace(" ", "")

    # Step 1: Check official accounts first
    if normalized in official_accounts:
        print(account, "-> OFFICIAL")
        continue

    # Step 2: Compare with the official brand
    score = fuzz.ratio(
        official_brand.lower(),
        normalized.replace("_", "")
    )

    # Step 3: Assign a review status
    if score >= 85:
        status = "HIGH SIMILARITY - REVIEW"
    elif score >= 65:
        status = "POSSIBLE MATCH - REVIEW"
    else:
        status = "LOW SIMILARITY"

    print(account, "->", round(score, 1), "%", status)