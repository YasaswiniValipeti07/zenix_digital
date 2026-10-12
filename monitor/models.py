from django.db import models
from django.db.models.functions import Lower


class Brand(models.Model):
    brand_name = models.CharField(max_length=100)
    official_accounts = models.TextField()
    official_urls = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("brand_name"), name="unique_brand_name_case_insensitive"
            ),
        ]

    def __str__(self):
        return self.brand_name


class OfficialAppAsset(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="official_apps")
    app_name = models.CharField(max_length=120)
    publisher = models.CharField(max_length=120, blank=True)
    package_id = models.CharField(max_length=180, blank=True)
    listing_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("brand__brand_name", "app_name")

    def __str__(self):
        return f"{self.app_name} — {self.brand.brand_name}"


class MonitoringResult(models.Model):
    class AssetType(models.TextChoices):
        SOCIAL = "social", "Social profile"
        APP = "app", "App listing"

    class RiskStatus(models.TextChoices):
        OFFICIAL = "official", "Official account"
        HIGH = "high", "High similarity — review"
        POSSIBLE = "possible", "Possible match — review"
        LOW = "low", "Low similarity"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        REVIEWED = "reviewed", "Reviewed"

    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name="monitoring_results"
    )
    asset_type = models.CharField(
        max_length=8, choices=AssetType.choices, default=AssetType.SOCIAL
    )
    candidate_username = models.CharField(max_length=30)
    candidate_display_name = models.CharField(max_length=160, blank=True, default="")
    candidate_description = models.TextField(blank=True, default="")
    publisher = models.CharField(max_length=160, blank=True, default="")
    package_id = models.CharField(max_length=180, blank=True, default="")
    listing_url = models.URLField(max_length=500, blank=True, default="")
    source = models.CharField(max_length=80, default="manual", blank=True)
    similarity_score = models.PositiveSmallIntegerField(null=True, blank=True)
    risk_score = models.PositiveSmallIntegerField(null=True, blank=True)
    confidence_score = models.PositiveSmallIntegerField(null=True, blank=True)
    detected_signals = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    risk_status = models.CharField(max_length=12, choices=RiskStatus.choices)
    review_status = models.CharField(
        max_length=12,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    explanation = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    @property
    def risk_classification(self):
        return {
            self.RiskStatus.OFFICIAL: "Official asset — excluded",
            self.RiskStatus.HIGH: "High Priority Review",
            self.RiskStatus.POSSIBLE: "Needs Review",
            self.RiskStatus.LOW: "Low Risk",
        }.get(self.risk_status, self.get_risk_status_display())

    def __str__(self):
        return f"{self.candidate_username} ({self.get_risk_status_display()})"