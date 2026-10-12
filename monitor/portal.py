"""Additional connected product pages and safe, manual/import-based workflows."""

import csv
import io
import re

from django.contrib import messages
from django.db import transaction
from django import forms
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .detection import RISK_THRESHOLDS, analyze_candidate
from .forms import (
    BrandRegistrationForm,
    CandidateScanForm,
    CandidateCsvUploadForm,
    OfficialAppAssetForm,
    ReportFilterForm,
    ThreatAnalysisForm,
    clean_usernames,
)
from .models import Brand, MonitoringResult, OfficialAppAsset
from .risk import parse_official_accounts

PAGE_TEMPLATE = "monitor/workspace.html"


def _context(page, **extra):
    context = {
        "page": page,
        "brands": Brand.objects.order_by("brand_name"),
        "registered_brand_count": Brand.objects.count(),
        "accounts_checked_count": MonitoringResult.objects.count(),
        "official_account_count": sum(
            len(parse_official_accounts(brand.official_accounts))
            for brand in Brand.objects.only("official_accounts")
        ),
        "accounts_needing_review_count": MonitoringResult.objects.filter(
            risk_status__in=[MonitoringResult.RiskStatus.HIGH, MonitoringResult.RiskStatus.POSSIBLE],
            review_status__in=[MonitoringResult.ReviewStatus.PENDING, MonitoringResult.ReviewStatus.UNDER_REVIEW],
        ).count(),
        "high_priority_count": MonitoringResult.objects.filter(
            risk_status=MonitoringResult.RiskStatus.HIGH
        ).count(),
        "possible_match_count": MonitoringResult.objects.filter(
            risk_status=MonitoringResult.RiskStatus.POSSIBLE
        ).count(),
        "low_risk_count": MonitoringResult.objects.filter(
            risk_status=MonitoringResult.RiskStatus.LOW
        ).count(),
        "recent_results": MonitoringResult.objects.select_related("brand")[:6],
        "review_status_choices": MonitoringResult.ReviewStatus.choices,
        "local_analysis_only": True,
    }
    context.update(extra)
    return context


def brand_inventory(request, brand_form=None):
    return render(request, PAGE_TEMPLATE, _context(
        "brands", brand_form=brand_form or BrandRegistrationForm(), official_app_form=OfficialAppAssetForm(),
        official_apps=OfficialAppAsset.objects.select_related("brand"),
        results=MonitoringResult.objects.select_related("brand")[:100],
    ))


def threat_detection(request):
    return render(request, PAGE_TEMPLATE, _context(
        "detection", analysis_form=ThreatAnalysisForm(),
        recent_results=MonitoringResult.objects.select_related("brand")[:25],
    ))


def social_monitoring(request, scan_form=None):
    return render(request, PAGE_TEMPLATE, _context(
        "social", scan_form=scan_form or CandidateScanForm(),
        import_form=CandidateCsvUploadForm(initial={"asset_type": MonitoringResult.AssetType.SOCIAL}),
        results=MonitoringResult.objects.filter(asset_type=MonitoringResult.AssetType.SOCIAL).select_related("brand")[:100],
    ))


def app_intelligence(request):
    return render(request, PAGE_TEMPLATE, _context(
        "apps", official_apps=OfficialAppAsset.objects.select_related("brand"),
        import_form=CandidateCsvUploadForm(initial={"asset_type": MonitoringResult.AssetType.APP}),
        results=MonitoringResult.objects.filter(asset_type=MonitoringResult.AssetType.APP).select_related("brand")[:100],
    ))


def investigation_center(request):
    return render(request, PAGE_TEMPLATE, _context(
        "investigations", results=MonitoringResult.objects.exclude(
            risk_status=MonitoringResult.RiskStatus.OFFICIAL
        ).select_related("brand")[:100],
    ))


def reports(request):
    form = ReportFilterForm(request.GET)
    rows = _filtered_results(form)
    return render(request, PAGE_TEMPLATE, _context(
        "reports", report_form=form, report_results=rows[:500], report_count=rows.count(),
        high_count=rows.filter(risk_status=MonitoringResult.RiskStatus.HIGH).count(),
        possible_count=rows.filter(risk_status=MonitoringResult.RiskStatus.POSSIBLE).count(),
    ))


def _filtered_results(form):
    rows = MonitoringResult.objects.select_related("brand")
    if form.is_valid():
        if form.cleaned_data.get("brand"):
            rows = rows.filter(brand=form.cleaned_data["brand"])
        if form.cleaned_data.get("start_date"):
            rows = rows.filter(created_at__date__gte=form.cleaned_data["start_date"])
        if form.cleaned_data.get("end_date"):
            rows = rows.filter(created_at__date__lte=form.cleaned_data["end_date"])
    return rows


def export_report_csv(request):
    form = ReportFilterForm(request.GET)
    if not form.is_valid():
        messages.error(request, "Correct the report filters before exporting.")
        return redirect("reports")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="sentinel-risk-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Created UTC", "Brand", "Asset type", "Candidate", "Publisher", "Package ID", "Risk score", "Similarity", "Classification", "Review status", "Source", "Explanation"])
    for result in _filtered_results(form).iterator(chunk_size=500):
        values = [result.created_at.isoformat(), result.brand.brand_name,
                  result.get_asset_type_display(), result.candidate_username,
                  result.publisher, result.package_id, result.risk_score,
                  result.similarity_score, result.get_risk_status_display(),
                  result.get_review_status_display(), result.source, result.explanation]
        writer.writerow([_safe_csv_cell(value) for value in values])
    return response


def _safe_csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@require_POST
def analyze_threat(request):
    form = ThreatAnalysisForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the highlighted candidate details.")
        return render(request, PAGE_TEMPLATE, _context(
            "detection", analysis_form=form,
            recent_results=MonitoringResult.objects.select_related("brand")[:25],
        ))
    data = form.cleaned_data
    candidate = {
        "asset_type": data["asset_type"], "username": data["username"],
        "app_name": data["app_name"], "display_name": data["display_name"],
        "description": data["description"], "publisher": data["publisher"],
        "package_id": data["package_id"], "listing_url": data["listing_url"],
        "source": "manual",
    }
    result_fields = analyze_candidate(data["brand"], candidate)
    MonitoringResult.objects.create(brand=data["brand"], **result_fields)
    messages.success(request, "Local heuristic analysis saved. Review all signals as leads, not conclusions.")
    return redirect("app_intelligence" if data["asset_type"] == MonitoringResult.AssetType.APP else "social_monitoring")


@require_POST
def register_official_app(request):
    form = OfficialAppAssetForm(request.POST)
    if form.is_valid():
        asset = form.save()
        messages.success(request, f"Official app reference {asset.app_name} saved.")
    else:
        messages.error(request, "Official app details were not saved: " + "; ".join(
            f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()
        ))
    return redirect("brand_inventory")


def _read_candidate_csv(upload, asset_type):
    try:
        content = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    reader = csv.DictReader(io.StringIO(content, newline=""))
    headers = {header.strip().casefold() for header in (reader.fieldnames or []) if header}
    required = {"username"} if asset_type == MonitoringResult.AssetType.SOCIAL else {"app_name"}
    if not required.issubset(headers):
        raise ValueError("CSV requires column(s): " + ", ".join(sorted(required)))
    records = []
    seen = set()
    for row in reader:
        candidate = {(key or "").strip().casefold(): (value or "").strip() for key, value in row.items()}
        if not any(candidate.values()):
            continue
        candidate.update(asset_type=asset_type, source="csv-import")
        if asset_type == MonitoringResult.AssetType.SOCIAL:
            try:
                usernames = clean_usernames(candidate.get("username", ""), "CSV username")
            except forms.ValidationError as exc:
                raise ValueError("Invalid CSV username: " + "; ".join(exc.messages)) from exc
            if len(usernames) != 1:
                raise ValueError("Each social CSV row must have one valid username.")
            candidate["username"] = usernames[0]
            if len(candidate.get("display_name", "")) > 160 or len(candidate.get("description", "")) > 3000:
                raise ValueError("Social CSV display names are limited to 160 characters and descriptions to 3,000.")
        else:
            if not candidate.get("app_name") or len(candidate["app_name"]) > 120:
                raise ValueError("Each app CSV row needs an app name of at most 120 characters.")
            if len(candidate.get("publisher", "")) > 160 or len(candidate.get("package_id", "")) > 180 or len(candidate.get("description", "")) > 3000:
                raise ValueError("App CSV publisher/package/description fields exceed their allowed lengths.")
            if candidate.get("package_id") and not re.fullmatch(r"[A-Za-z0-9_.-]{2,180}", candidate["package_id"]):
                raise ValueError("App CSV package IDs may contain letters, numbers, dots, underscores, and hyphens.")
        if candidate.get("listing_url"):
            try:
                candidate["listing_url"] = forms.URLField(max_length=500).clean(candidate["listing_url"])
            except forms.ValidationError as exc:
                raise ValueError("Invalid CSV listing URL: " + "; ".join(exc.messages)) from exc
        if asset_type == MonitoringResult.AssetType.SOCIAL:
            identity = (asset_type, candidate["username"].casefold())
        else:
            package = candidate.get("package_id", "").casefold()
            identity = (asset_type, "package", package) if package else (
                asset_type,
                candidate.get("app_name", "").casefold(),
                candidate.get("publisher", "").casefold(),
                candidate.get("listing_url", "").casefold(),
            )
        if identity in seen:
            continue
        seen.add(identity)
        if len(records) >= 100:
            raise ValueError("Import a maximum of 100 candidate records at a time.")
        records.append(candidate)
    if not records:
        raise ValueError("No candidate rows were found in this CSV.")
    return records


@require_POST
def import_candidates(request):
    form = CandidateCsvUploadForm(request.POST, request.FILES)
    asset_type = request.POST.get("asset_type", MonitoringResult.AssetType.SOCIAL)
    destination = "social_monitoring" if asset_type == MonitoringResult.AssetType.SOCIAL else "app_intelligence"
    if not form.is_valid():
        messages.error(request, "Please correct the CSV import form.")
        return redirect(destination)
    brand = form.cleaned_data["brand"]
    asset_type = form.cleaned_data["asset_type"]
    destination = "social_monitoring" if asset_type == MonitoringResult.AssetType.SOCIAL else "app_intelligence"
    try:
        candidates = _read_candidate_csv(form.cleaned_data["csv_file"], asset_type)
    except (ValueError, csv.Error) as exc:
        messages.error(request, str(exc))
        return redirect(destination)
    with transaction.atomic():
        for candidate in candidates:
            result_fields = analyze_candidate(brand, candidate)
            MonitoringResult.objects.create(brand=brand, **result_fields)
    messages.success(request, f"Imported and locally analyzed {len(candidates)} record(s).")
    return redirect(destination)


def settings_integrations(request):
    return render(request, PAGE_TEMPLATE, _context(
        "settings",
        risk_thresholds=RISK_THRESHOLDS,
        integration_statuses=[
            {"name": "Social platform APIs", "status": "Not configured", "detail": "No authorized API adapter or credentials are configured."},
            {"name": "App-store APIs", "status": "Not configured", "detail": "No app listing provider adapter is configured."},
            {"name": "CSV intake", "status": "Available", "detail": "Reviewer-supplied CSV records can be analyzed locally."},
            {"name": "Generative AI provider", "status": "Not integrated", "detail": "The detector in this build uses local heuristics only."},
        ],
    ))
