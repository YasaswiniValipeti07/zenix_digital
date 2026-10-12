
from django.urls import path
from . import portal, views

urlpatterns = [
    path("", views.home, name="home"),
    path("brands/", portal.brand_inventory, name="brand_inventory"),
    path("brands/register/", views.register_brand, name="register_brand"),
    path("brands/apps/register/", portal.register_official_app, name="register_official_app"),
    path("scan/", views.scan_usernames, name="scan_usernames"),
    path("detection/", portal.threat_detection, name="threat_detection"),
    path("detection/analyze/", portal.analyze_threat, name="analyze_threat"),
    path("social/", portal.social_monitoring, name="social_monitoring"),
    path("apps/", portal.app_intelligence, name="app_intelligence"),
    path("imports/csv/", portal.import_candidates, name="import_candidates"),
    path("investigations/", portal.investigation_center, name="investigation_center"),
    path("reports/", portal.reports, name="reports"),
    path("reports/export.csv", portal.export_report_csv, name="export_report_csv"),
    path("settings/", portal.settings_integrations, name="settings_integrations"),
    path("results/<int:result_id>/review/", views.update_review_status, name="update_review_status"),
]