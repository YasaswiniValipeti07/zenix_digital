
brand_name = "NovaPay"

official_accounts = [
    "novapay",
    "novapay_india"
]

candidate_account = "novapaay"

print("Checking account:", candidate_account)

if candidate_account.lower() in official_accounts:
    print("Status: OFFICIAL")
else:
    print("Status: NEEDS REVIEW")