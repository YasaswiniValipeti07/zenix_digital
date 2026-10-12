import re

from django import forms

from .models import Brand, MonitoringResult, OfficialAppAsset


USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._]{1,30}", re.ASCII)


def split_usernames(value):
    # Normalize Windows CRLF and legacy CR line endings before splitting.
    normalized_value = value.replace("\r\n", "\n").replace("\r", "\n")
    return [item.strip() for item in re.split(r"[,\n]+", normalized_value) if item.strip()]


def clean_usernames(value, field_label):
    usernames = []
    seen = set()
    for raw_username in split_usernames(value):
        username = raw_username.strip().removeprefix("@").strip()
        if not USERNAME_PATTERN.fullmatch(username):
            raise forms.ValidationError(
                f"Invalid username {username!r}. Use 1–30 letters, numbers, dots, or underscores."
            )
        key = username.casefold()
        if key not in seen:
            seen.add(key)
            usernames.append(username)
    return usernames


class BrandRegistrationForm(forms.Form):
    brand_name = forms.CharField(max_length=100, strip=True)
    official_accounts = forms.CharField(
        max_length=1500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Separate usernames with commas or new lines. The @ prefix is optional.",
    )
    official_urls = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional trusted URLs, one per line or separated by commas.",
    )

    def clean_brand_name(self):
        name = self.cleaned_data["brand_name"]
        if not name.strip():
            raise forms.ValidationError("Enter a brand name.")
        if Brand.objects.filter(brand_name__iexact=name).exists():
            raise forms.ValidationError("This brand is already registered.")
        return name

    def clean_official_accounts(self):
        value = self.cleaned_data["official_accounts"]
        usernames = clean_usernames(value, "Official accounts")
        return ", ".join(usernames)

    def clean_official_urls(self):
        value = self.cleaned_data["official_urls"].replace("\r", "")
        urls = [part.strip() for part in re.split(r"[,\n]+", value) if part.strip()]
        for url in urls:
            parsed = forms.URLField().clean(url)
            if not parsed.startswith(("https://", "http://")):
                raise forms.ValidationError("Official URLs must use HTTP or HTTPS.")
        return "\n".join(urls)


class CandidateScanForm(forms.Form):
    brand = forms.ModelChoiceField(queryset=Brand.objects.none())
    candidate_usernames = forms.CharField(
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter up to 100 usernames, separated by commas or new lines.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.order_by("brand_name")

    def clean_candidate_usernames(self):
        usernames = clean_usernames(
            self.cleaned_data["candidate_usernames"], "Candidate usernames"
        )
        if not usernames:
            raise forms.ValidationError("Enter at least one candidate username.")
        if len(usernames) > 100:
            raise forms.ValidationError("You can check up to 100 usernames at a time.")
        return usernames


class ReviewStatusForm(forms.Form):
    review_status = forms.ChoiceField(choices=MonitoringResult.ReviewStatus.choices)


class OfficialAppAssetForm(forms.ModelForm):
    class Meta:
        model = OfficialAppAsset
        fields = ("brand", "app_name", "publisher", "package_id", "listing_url")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.order_by("brand_name")

    def clean_package_id(self):
        return self.cleaned_data["package_id"].strip().casefold()


class ThreatAnalysisForm(forms.Form):
    brand = forms.ModelChoiceField(queryset=Brand.objects.none())
    asset_type = forms.ChoiceField(choices=MonitoringResult.AssetType.choices)
    username = forms.CharField(max_length=30, required=False)
    app_name = forms.CharField(max_length=120, required=False)
    display_name = forms.CharField(max_length=160, required=False)
    description = forms.CharField(max_length=3000, required=False, widget=forms.Textarea(attrs={"rows": 4}))
    publisher = forms.CharField(max_length=160, required=False)
    package_id = forms.CharField(max_length=180, required=False)
    listing_url = forms.URLField(max_length=500, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.order_by("brand_name")

    def clean(self):
        cleaned = super().clean()
        asset_type = cleaned.get("asset_type")
        if asset_type == MonitoringResult.AssetType.SOCIAL and not cleaned.get("username"):
            self.add_error("username", "Enter the candidate username.")
        if asset_type == MonitoringResult.AssetType.APP:
            if not cleaned.get("app_name"):
                self.add_error("app_name", "Enter the candidate app name.")
            if not any(cleaned.get(key) for key in ("publisher", "package_id", "listing_url")):
                raise forms.ValidationError("Provide publisher, package ID, or listing URL as comparison evidence.")
        return cleaned

    def clean_username(self):
        username = self.cleaned_data["username"].strip().removeprefix("@").strip()
        if username and not USERNAME_PATTERN.fullmatch(username):
            raise forms.ValidationError("Use 1–30 letters, numbers, dots, or underscores.")
        return username

    def clean_package_id(self):
        package_id = self.cleaned_data["package_id"].strip()
        if package_id and not re.fullmatch(r"[A-Za-z0-9_.-]{2,180}", package_id):
            raise forms.ValidationError("Package IDs may contain letters, numbers, dots, underscores, and hyphens.")
        return package_id


class CandidateCsvUploadForm(forms.Form):
    brand = forms.ModelChoiceField(queryset=Brand.objects.none())
    asset_type = forms.ChoiceField(choices=MonitoringResult.AssetType.choices)
    csv_file = forms.FileField(help_text="CSV columns: username, display_name, description; or app_name, publisher, package_id, description, listing_url.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.order_by("brand_name")

    def clean_csv_file(self):
        uploaded = self.cleaned_data["csv_file"]
        if uploaded.size > 1024 * 1024:
            raise forms.ValidationError("CSV files must be 1 MB or smaller.")
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a .csv file.")
        return uploaded


class ReportFilterForm(forms.Form):
    brand = forms.ModelChoiceField(queryset=Brand.objects.none(), required=False)
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.order_by("brand_name")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_date") and cleaned.get("end_date") and cleaned["start_date"] > cleaned["end_date"]:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned