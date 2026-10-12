
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BrandRegistrationForm, CandidateScanForm, ReviewStatusForm
from .detection import analyze_candidate
from .models import Brand, MonitoringResult
from .risk import parse_official_accounts


def dashboard_context(brand_form=None, scan_form=None):
    brands = Brand.objects.annotate(
        result_count=Count("monitoring_results", distinct=True)
    ).order_by("brand_name")
    results = MonitoringResult.objects.select_related("brand")
    context = {
        "brands": brands,
        "results": results[:50],
        "registered_brand_count": Brand.objects.count(),
        "accounts_checked_count": results.count(),
        "official_account_count": sum(
            len(parse_official_accounts(value))
            for value in Brand.objects.values_list("official_accounts", flat=True)
        ),
        "accounts_needing_review_count": results.filter(
            risk_status__in=[
                MonitoringResult.RiskStatus.HIGH,
                MonitoringResult.RiskStatus.POSSIBLE,
            ],
            review_status__in=[
                MonitoringResult.ReviewStatus.PENDING,
                MonitoringResult.ReviewStatus.UNDER_REVIEW,
            ],
        ).count(),
        "high_priority_count": results.filter(
            risk_status=MonitoringResult.RiskStatus.HIGH
        ).count(),
        "possible_match_count": results.filter(
            risk_status=MonitoringResult.RiskStatus.POSSIBLE
        ).count(),
        "low_risk_count": results.filter(
            risk_status=MonitoringResult.RiskStatus.LOW
        ).count(),
        "recent_results": results[:6],
        "brand_form": brand_form or BrandRegistrationForm(),
        "scan_form": scan_form or CandidateScanForm(),
    }
    return context


def home(request):
    return render(request, "index.html", dashboard_context())


@require_POST
def register_brand(request):
    return_to_brands = request.POST.get("return_to") == "brands"
    form = BrandRegistrationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the highlighted brand details.")
        if return_to_brands:
            from .portal import brand_inventory

            return brand_inventory(request, brand_form=form)
        return render(
            request,
            "index.html",
            dashboard_context(brand_form=form),
        )

    try:
        with transaction.atomic():
            brand = Brand.objects.create(**form.cleaned_data)
    except IntegrityError:
        messages.error(request, "This brand is already registered.")
    else:
        messages.success(request, f"{brand.brand_name} was registered successfully.")
    return redirect("brand_inventory" if return_to_brands else "home")


@require_POST
def scan_usernames(request):
    form = CandidateScanForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the highlighted scan details.")
        if request.POST.get("return_to") == "social":
            from .portal import social_monitoring

            return social_monitoring(request, scan_form=form)
        return render(
            request,
            "index.html",
            dashboard_context(scan_form=form),
        )

    brand = form.cleaned_data["brand"]
    with transaction.atomic():
        for username in form.cleaned_data["candidate_usernames"]:
            assessment = analyze_candidate(brand, {
                "asset_type": MonitoringResult.AssetType.SOCIAL,
                "username": username,
                "source": "manual",
            })
            MonitoringResult.objects.create(
                brand=brand,
                **assessment,
            )
    messages.success(
        request,
        f"Checked {len(form.cleaned_data['candidate_usernames'])} username(s) for {brand.brand_name}.",
    )
    return redirect("social_monitoring" if request.POST.get("return_to") == "social" else "home")


@require_POST
def update_review_status(request, result_id):
    result = get_object_or_404(MonitoringResult, pk=result_id)
    form = ReviewStatusForm(request.POST)
    if form.is_valid():
        result.review_status = form.cleaned_data["review_status"]
        result.save(update_fields=["review_status"])
        messages.success(request, f"Review status updated for @{result.candidate_username}.")
    else:
        messages.error(request, "Choose a valid review status.")
    destinations = {
        "home": "home", "investigations": "investigation_center",
        "social": "social_monitoring", "apps": "app_intelligence",
    }
    return redirect(destinations.get(request.POST.get("return_to"), "home"))