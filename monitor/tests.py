from django.test import Client, TestCase
from django.urls import reverse

from django.core.files.uploadedfile import SimpleUploadedFile
from .forms import CandidateScanForm, ThreatAnalysisForm
from .models import Brand, MonitoringResult, OfficialAppAsset
from .risk import assess_username, normalize_username, similarity_key
from .detection import analyze_candidate


class RiskAssessmentTests(TestCase):
	def test_official_username_is_excluded_before_scoring(self):
		result = assess_username("@NOVAPAY_SUPPORT", "NovaPay", ["novapay_support"])

		self.assertEqual(result["risk_status"], MonitoringResult.RiskStatus.OFFICIAL)
		self.assertIsNone(result["similarity_score"])
		self.assertEqual(result["review_status"], MonitoringResult.ReviewStatus.REVIEWED)

	def test_similar_username_is_flagged_for_human_review(self):
		result = assess_username("novapaay", "NovaPay", ["novapay_support"])

		self.assertEqual(result["risk_status"], MonitoringResult.RiskStatus.HIGH)
		self.assertGreaterEqual(result["similarity_score"], 85)
		self.assertIn("human review", result["explanation"])

	def test_underscore_variation_is_compared_after_separator_normalization(self):
		result = assess_username("nova_pay", "NovaPay", ["novapay_support"])

		self.assertEqual(result["risk_status"], MonitoringResult.RiskStatus.HIGH)
		self.assertEqual(result["similarity_score"], 100)

	def test_matches_official_usernames_as_well_as_brand_name(self):
		result = assess_username("novapay_supp0rt", "NovaPay", ["novapay_support"])

		self.assertEqual(result["risk_status"], MonitoringResult.RiskStatus.HIGH)
		self.assertIn("novapay_support", result["explanation"])

	def test_normalization_keeps_official_identity_distinct_but_ignores_separators_for_score(self):
		self.assertEqual(normalize_username(" @Nova Pay "), "novapay")
		self.assertEqual(similarity_key("Nova_Pay"), "novapay")
		self.assertNotEqual(normalize_username("Nova_Pay"), normalize_username("NovaPay"))

	def test_unrelated_username_gets_low_similarity(self):
		result = assess_username("gardenrecipes", "NovaPay", ["novapay_support"])

		self.assertEqual(result["risk_status"], MonitoringResult.RiskStatus.LOW)
		self.assertLess(result["similarity_score"], 65)

	def test_username_length_limit_is_per_candidate(self):
		brand = Brand.objects.create(brand_name="LengthCheck", official_accounts="")
		valid_form = CandidateScanForm(data={
			"brand": brand.pk,
			"candidate_usernames": "a" * 30,
		})
		invalid_form = CandidateScanForm(data={
			"brand": brand.pk,
			"candidate_usernames": "a" * 31,
		})

		self.assertTrue(valid_form.is_valid(), valid_form.errors)
		self.assertFalse(invalid_form.is_valid())
		self.assertIn("candidate_usernames", invalid_form.errors)

	def test_local_detector_is_explainable_and_limits_confidence(self):
		brand = Brand.objects.create(brand_name="Northstar", official_accounts="northstar")
		result = analyze_candidate(brand, {"asset_type": "social", "username": "northstar_security"})

		self.assertGreater(result["risk_score"], 0)
		self.assertLessEqual(result["risk_score"], 100)
		self.assertTrue(result["detected_signals"])
		self.assertTrue(any(item["kind"] == "limitation" for item in result["evidence"]))
		self.assertLessEqual(result["confidence_score"], 45)

	def test_official_url_and_app_identifiers_are_excluded_before_scoring(self):
		brand = Brand.objects.create(
			brand_name="Northstar", official_accounts="northstar",
			official_urls="https://northstar.example",
		)
		OfficialAppAsset.objects.create(
			brand=brand, app_name="Northstar", publisher="Northstar Ltd",
			package_id="com.northstar.mobile", listing_url="https://store.example/northstar",
		)
		url_result = analyze_candidate(brand, {"asset_type": "social", "username": "northstar_news", "listing_url": "https://www.northstar.example/news"})
		app_result = analyze_candidate(brand, {"asset_type": "app", "app_name": "Northstar", "package_id": "com.northstar.mobile"})

		self.assertEqual(url_result["risk_status"], MonitoringResult.RiskStatus.OFFICIAL)
		self.assertEqual(app_result["risk_status"], MonitoringResult.RiskStatus.OFFICIAL)
		self.assertIsNone(app_result["similarity_score"])


class DashboardAndRegistrationTests(TestCase):
	def test_registration_saves_to_database_and_redirects(self):
		response = self.client.post(
			reverse("register_brand"),
			{"brand_name": "NovaPay", "official_accounts": "@novapay, novapay_support"},
		)

		self.assertRedirects(response, reverse("home"))
		brand = Brand.objects.get(brand_name="NovaPay")
		self.assertEqual(brand.official_accounts, "novapay, novapay_support")
		self.assertContains(self.client.get(reverse("home")), "NovaPay")

	def test_duplicate_brand_registration_is_rejected_case_insensitively(self):
		Brand.objects.create(brand_name="NovaPay", official_accounts="novapay")

		self.client.post(
			reverse("register_brand"),
			{"brand_name": "novapay", "official_accounts": "other_handle"},
		)

		self.assertEqual(Brand.objects.count(), 1)

	def test_invalid_registration_input_is_rejected(self):
		response = self.client.post(
			reverse("register_brand"),
			{"brand_name": "   ", "official_accounts": "valid, bad username!"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["brand_form"].errors)
		self.assertEqual(Brand.objects.count(), 0)
		self.assertContains(response, "Brand name")

	def test_dashboard_counts_come_from_saved_records(self):
		brand = Brand.objects.create(
			brand_name="NovaPay", official_accounts="novapay, novapay_support"
		)
		MonitoringResult.objects.create(
			brand=brand,
			candidate_username="novapaay",
			similarity_score=93,
			risk_status=MonitoringResult.RiskStatus.HIGH,
			explanation="Similar username; review it.",
		)
		MonitoringResult.objects.create(
			brand=brand,
			candidate_username="novapay",
			similarity_score=None,
			risk_status=MonitoringResult.RiskStatus.OFFICIAL,
			review_status=MonitoringResult.ReviewStatus.REVIEWED,
			explanation="Registered official account.",
		)
		MonitoringResult.objects.create(
			brand=brand,
			candidate_username="novapay_help",
			similarity_score=88,
			risk_status=MonitoringResult.RiskStatus.HIGH,
			review_status=MonitoringResult.ReviewStatus.REVIEWED,
			explanation="Already reviewed.",
		)

		response = self.client.get(reverse("home"))

		self.assertEqual(response.context["registered_brand_count"], 1)
		self.assertEqual(response.context["accounts_checked_count"], 3)
		self.assertEqual(response.context["official_account_count"], 2)
		self.assertEqual(response.context["accounts_needing_review_count"], 1)

	def test_brand_registration_requires_csrf_token(self):
		csrf_client = Client(enforce_csrf_checks=True)

		response = csrf_client.post(
			reverse("register_brand"),
			{"brand_name": "NovaPay", "official_accounts": "novapay"},
		)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(Brand.objects.count(), 0)


class MonitoringWorkflowTests(TestCase):
	def setUp(self):
		self.brand = Brand.objects.create(
			brand_name="NovaPay", official_accounts="novapay, novapay_support"
		)

	def test_scan_persists_results_and_excludes_official_account(self):
		response = self.client.post(
			reverse("scan_usernames"),
			{
				"brand": self.brand.id,
				"candidate_usernames": "NOVAPAY\r\nnovapaay\r\nnova_pay, novapay_support\r\ngardenrecipes",
			},
		)

		self.assertRedirects(response, reverse("home"))
		self.assertEqual(MonitoringResult.objects.count(), 5)
		official = MonitoringResult.objects.get(candidate_username="NOVAPAY")
		similar = MonitoringResult.objects.get(candidate_username="novapaay")
		underscore_match = MonitoringResult.objects.get(candidate_username="nova_pay")
		official_support = MonitoringResult.objects.get(candidate_username="novapay_support")
		unrelated = MonitoringResult.objects.get(candidate_username="gardenrecipes")
		self.assertEqual(official.risk_status, MonitoringResult.RiskStatus.OFFICIAL)
		self.assertIsNone(official.similarity_score)
		self.assertEqual(similar.risk_status, MonitoringResult.RiskStatus.HIGH)
		self.assertEqual(underscore_match.similarity_score, 100)
		self.assertEqual(official_support.risk_status, MonitoringResult.RiskStatus.OFFICIAL)
		self.assertIsNone(official_support.similarity_score)
		self.assertEqual(unrelated.risk_status, MonitoringResult.RiskStatus.LOW)
		self.assertEqual(similar.brand_id, self.brand.id)

	def test_legacy_scanner_uses_persisted_explainable_engine(self):
		self.client.post(
			reverse("scan_usernames"),
			{"brand": self.brand.id, "candidate_usernames": "novapaay"},
		)
		result = MonitoringResult.objects.get(candidate_username="novapaay")

		self.assertIsNotNone(result.risk_score)
		self.assertTrue(result.detected_signals)
		self.assertTrue(result.evidence)
		self.assertEqual(result.source, "manual")

	def test_invalid_candidate_input_does_not_create_results(self):
		response = self.client.post(
			reverse("scan_usernames"),
			{"brand": self.brand.id, "candidate_usernames": "valid_name, <script>"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["scan_form"].errors)
		self.assertContains(response, "Invalid username &#x27;&lt;script&gt;&#x27;")
		self.assertEqual(MonitoringResult.objects.count(), 0)

	def test_missing_scan_fields_render_validation_feedback(self):
		response = self.client.post(reverse("scan_usernames"), {})

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["scan_form"].errors)
		self.assertEqual(MonitoringResult.objects.count(), 0)

	def test_review_status_can_be_updated_and_invalid_status_is_rejected(self):
		result = MonitoringResult.objects.create(
			brand=self.brand,
			candidate_username="novapaay",
			similarity_score=93,
			risk_status=MonitoringResult.RiskStatus.HIGH,
			explanation="Potential similarity.",
		)
		url = reverse("update_review_status", args=[result.id])

		for status in (
			MonitoringResult.ReviewStatus.UNDER_REVIEW,
			MonitoringResult.ReviewStatus.REVIEWED,
			MonitoringResult.ReviewStatus.PENDING,
		):
			response = self.client.post(url, {"review_status": status})
			self.assertRedirects(response, reverse("home"))
			result.refresh_from_db()
			self.assertEqual(result.review_status, status)

		self.client.post(url, {"review_status": "not-a-status"})
		result.refresh_from_db()
		self.assertEqual(result.review_status, MonitoringResult.ReviewStatus.PENDING)

	def test_review_update_rejects_get_requests(self):
		result = MonitoringResult.objects.create(
			brand=self.brand,
			candidate_username="novapaay",
			similarity_score=93,
			risk_status=MonitoringResult.RiskStatus.HIGH,
			explanation="Potential similarity.",
		)

		self.assertEqual(
			self.client.get(reverse("update_review_status", args=[result.id])).status_code,
			405,
		)

	def test_review_update_returns_to_valid_product_page(self):
		result = MonitoringResult.objects.create(
			brand=self.brand, candidate_username="novapaay", risk_status="high",
			explanation="Potential match", review_status="pending",
		)
		response = self.client.post(
			reverse("update_review_status", args=[result.id]),
			{"review_status": "under_review", "return_to": "investigations"},
		)
		self.assertRedirects(response, reverse("investigation_center"))
		queue_response = self.client.get(reverse("investigation_center"))
		self.assertEqual(queue_response.status_code, 200)
		self.assertContains(queue_response, "Potential match")

	def test_csv_import_rejects_invalid_username_without_creating_partial_records(self):
		data = b"username,display_name\nvalid_name,ok\ninvalid username,bad\n"
		response = self.client.post(reverse("import_candidates"), {
			"brand": self.brand.pk, "asset_type": "social",
			"csv_file": SimpleUploadedFile("bad.csv", data, content_type="text/csv"),
		}, follow=True)
		self.assertRedirects(response, reverse("social_monitoring"))
		self.assertEqual(MonitoringResult.objects.count(), 0)
		self.assertContains(response, "Invalid CSV username")


class ProductPagesAndImportsTests(TestCase):
	def setUp(self):
		self.brand = Brand.objects.create(brand_name="Northstar", official_accounts="northstar")

	def test_all_product_pages_render(self):
		for route in (
			"home", "brand_inventory", "threat_detection", "social_monitoring",
			"app_intelligence", "investigation_center", "reports", "settings_integrations",
		):
			with self.subTest(route=route):
				self.assertEqual(self.client.get(reverse(route)).status_code, 200)

	def test_portal_registration_preserves_inline_validation_and_form_values(self):
		response = self.client.post(reverse("register_brand"), {
			"return_to": "brands", "brand_name": " ",
			"official_accounts": "one_handle", "official_urls": "https://valid.example",
		})
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["brand_form"].errors)
		self.assertContains(response, "one_handle")
		self.assertEqual(Brand.objects.count(), 1)

	def test_portal_dashboard_counts_newline_separated_official_usernames(self):
		brand = Brand.objects.create(
			brand_name="LineBreakBrand", official_accounts="first_handle\r\nsecond_handle"
		)
		response = self.client.get(reverse("brand_inventory"))
		self.assertEqual(response.context["official_account_count"], 3)

	def test_social_candidate_analysis_saves_and_excludes_official(self):
		self.client.post(reverse("analyze_threat"), {
			"brand": self.brand.pk, "asset_type": "social", "username": "northstar",
		})
		result = MonitoringResult.objects.get(candidate_username="northstar")
		self.assertEqual(result.risk_status, MonitoringResult.RiskStatus.OFFICIAL)
		self.assertIsNone(result.similarity_score)

	def test_invalid_threat_candidate_is_not_saved(self):
		response = self.client.post(reverse("analyze_threat"), {
			"brand": self.brand.pk, "asset_type": "social", "username": "invalid username",
		})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(MonitoringResult.objects.count(), 0)

	def test_app_listing_persistence_and_official_package_exclusion(self):
		OfficialAppAsset.objects.create(
			brand=self.brand, app_name="Northstar App", publisher="Northstar",
			package_id="com.northstar.app",
		)
		self.client.post(reverse("analyze_threat"), {
			"brand": self.brand.pk, "asset_type": "app", "app_name": "Northstar App",
			"package_id": "com.northstar.app", "publisher": "Northstar",
		})
		result = MonitoringResult.objects.get(asset_type="app")
		self.assertEqual(result.risk_status, MonitoringResult.RiskStatus.OFFICIAL)
		self.assertEqual(result.package_id, "com.northstar.app")

	def test_csv_import_persists_local_analysis(self):
		data = b"username,display_name,description\nnorthstarr,Northstar Support,official customer help\nNORTHSTARR,Duplicate Row,duplicate should be dropped\n"
		response = self.client.post(reverse("import_candidates"), {
			"brand": self.brand.pk, "asset_type": "social",
			"csv_file": SimpleUploadedFile("candidates.csv", data, content_type="text/csv"),
		})
		self.assertRedirects(response, reverse("social_monitoring"))
		result = MonitoringResult.objects.get(candidate_username="northstarr")
		self.assertEqual(result.source, "csv-import")
		self.assertTrue(result.detected_signals)
		self.assertEqual(MonitoringResult.objects.filter(brand=self.brand, asset_type="social").count(), 1)

	def test_report_csv_uses_actual_records_and_neutralizes_formula_cells(self):
		MonitoringResult.objects.create(
			brand=self.brand, candidate_username="=HYPERLINK(\"bad\")",
			risk_status="low", explanation="Imported text",
		)
		response = self.client.get(reverse("export_report_csv"))
		self.assertEqual(response.status_code, 200)
		self.assertIn(b"'=HYPERLINK", response.content)

	def test_threat_form_rejects_bad_package_ids(self):
		form = ThreatAnalysisForm(data={
			"brand": self.brand.pk, "asset_type": "app", "app_name": "Some App",
			"package_id": "com.bad package",
		})
		self.assertFalse(form.is_valid())
		self.assertIn("package_id", form.errors)
