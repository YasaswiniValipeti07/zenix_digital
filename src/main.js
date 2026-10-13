import "./style.css";

const configuredApiBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const apiBase = configuredApiBase || (import.meta.env.DEV ? "/api" : "");
const state = { brands: [], results: [], totalResults: 0, health: null };
const pageTitles = {
  overview: "Security overview",
  brands: "Brand inventory",
  investigations: "Investigation center",
};

const element = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

async function api(path, options = {}) {
  if (!apiBase) {
    throw new Error("Set VITE_API_BASE_URL to your deployed Render API URL in Vercel.");
  }
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `The API returned HTTP ${response.status}.`);
  }
  return body;
}

function notify(message, kind = "success") {
  const notice = element("notice");
  notice.textContent = message;
  notice.className = `notice ${kind}`;
  notice.hidden = false;
  window.clearTimeout(notify.timeout);
  notify.timeout = window.setTimeout(() => { notice.hidden = true; }, 6000);
}

function showPage(page) {
  const activePage = pageTitles[page] ? page : "overview";
  document.querySelectorAll("[data-page]").forEach((section) => {
    section.hidden = section.dataset.page !== activePage;
  });
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.classList.toggle("active", link.dataset.nav === activePage);
  });
  element("page-title").textContent = pageTitles[activePage];
}

function riskLabel(status) {
  return ({
    official: "Official asset",
    high: "High similarity",
    possible: "Possible match",
    low: "Low similarity",
  })[status] || status || "Unknown";
}

function renderResults(target, results) {
  if (!results.length) {
    target.innerHTML = '<p class="empty-state">No analyses saved yet. Submit a candidate to start a review queue.</p>';
    return;
  }
  const canReview = target.id === "all-results";
  target.innerHTML = `<table><thead><tr><th>Candidate</th><th>Brand</th><th>Type</th><th>Assessment</th><th>Review</th><th>Saved</th>${canReview ? "<th>Update</th>" : ""}</tr></thead><tbody>${results.map((result) => {
    const brand = state.brands.find((item) => String(item.id) === String(result.brand_id));
    return `<tr>
      <td><strong>${escapeHtml(result.candidate_display_name || result.candidate_username || "Submitted asset")}</strong><small>${escapeHtml(result.candidate_username || result.package_id || "")}</small></td>
      <td>${escapeHtml(brand?.brand_name || `Brand ${result.brand_id}`)}</td>
      <td>${escapeHtml(result.asset_type || "social")}</td>
      <td><span class="badge risk-${escapeHtml(result.risk_status)}">${escapeHtml(riskLabel(result.risk_status))}</span><small>${result.risk_score == null ? "No score" : `Risk score ${escapeHtml(result.risk_score)}`}</small></td>
      <td>${escapeHtml((result.review_status || "pending").replaceAll("_", " "))}</td>
      <td>${escapeHtml(result.created_at ? new Date(result.created_at).toLocaleDateString() : "—")}</td>
      ${canReview ? `<td><div class="review-controls"><select aria-label="Review status for candidate ${escapeHtml(result.candidate_username)}" data-review-select="${escapeHtml(result.id)}"><option value="pending" ${result.review_status === "pending" ? "selected" : ""}>Pending</option><option value="under_review" ${result.review_status === "under_review" ? "selected" : ""}>Under review</option><option value="reviewed" ${result.review_status === "reviewed" ? "selected" : ""}>Reviewed</option></select><button class="button button-light review-save" type="button" data-review-id="${escapeHtml(result.id)}">Save</button></div></td>` : ""}
    </tr>`;
  }).join("")}</tbody></table>`;
  if (canReview) {
    target.querySelectorAll("[data-review-id]").forEach((button) => {
      button.addEventListener("click", async () => {
        const select = target.querySelector(`[data-review-select="${button.dataset.reviewId}"]`);
        button.disabled = true;
        try {
          await api("/results/update-review-status", {
            method: "POST",
            body: JSON.stringify({
              result_id: button.dataset.reviewId,
              review_status: select.value,
              return_to: "investigations",
            }),
          });
          notify("Review status updated.");
          await refreshData();
        } catch (error) {
          notify(error.message, "error");
        } finally {
          button.disabled = false;
        }
      });
    });
  }
}

function renderBrands() {
  const list = element("brand-list");
  if (!state.brands.length) {
    list.innerHTML = '<p class="empty-state">No brands registered. Add one from the overview.</p>';
    return;
  }
  list.innerHTML = state.brands.map((brand) => `<article class="brand-row">
    <div class="brand-avatar">${escapeHtml(brand.brand_name.slice(0, 1).toUpperCase())}</div>
    <div class="brand-details"><h3>${escapeHtml(brand.brand_name)}</h3><p>${escapeHtml(brand.official_accounts || "No official usernames registered")}</p><small>${escapeHtml(brand.official_urls || "No official URLs registered")}</small></div>
    <div class="brand-count"><strong>${escapeHtml(brand.checks_saved || 0)}</strong><small>saved checks</small></div>
  </article>`).join("");
}

function renderBrandSelect() {
  const select = element("analysis-brand");
  const selected = select.value;
  select.innerHTML = state.brands.length
    ? `<option value="">Choose a brand</option>${state.brands.map((brand) => `<option value="${escapeHtml(brand.id)}">${escapeHtml(brand.brand_name)}</option>`).join("")}`
    : '<option value="">Register or load a brand first</option>';
  if (state.brands.some((brand) => String(brand.id) === selected)) select.value = selected;
}

function updateStats() {
  const officialAccounts = state.brands.reduce((total, brand) => total + (brand.official_accounts || "").split(/[,\n\r]+/).filter((account) => account.trim()).length, 0);
  const awaitingReview = state.results.filter((result) =>
    ["high", "possible"].includes(result.risk_status) &&
    ["pending", "under_review"].includes(result.review_status),
  ).length;
  element("brand-count").textContent = state.brands.length;
  element("result-count").textContent = state.totalResults;
  element("review-count").textContent = awaitingReview;
  element("handle-count").textContent = officialAccounts;
}

async function refreshData() {
  const status = element("connection-status");
  status.className = "status-pill pending";
  status.innerHTML = "<i></i> Connecting";
  try {
    state.health = await api("/health");
    status.className = `status-pill ${state.health.database_configured ? "connected" : "pending"}`;
    status.innerHTML = `<i></i> ${state.health.database_configured ? "API connected" : "Database not configured"}`;
  } catch (error) {
    status.className = "status-pill offline";
    status.innerHTML = "<i></i> API unavailable";
    notify(error.message, "error");
    return;
  }

  try {
    const [brands, results] = await Promise.all([
      api("/brands"),
      api("/results"),
    ]);
    state.brands = brands;
    state.results = results.results || [];
    state.totalResults = results.count || 0;
    renderBrandSelect();
    renderBrands();
    renderResults(element("recent-results"), state.results.slice(0, 6));
    renderResults(element("all-results"), state.results);
    updateStats();
  } catch (error) {
    notify(error.message, "error");
    element("brand-list").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
    element("recent-results").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
    element("all-results").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

document.querySelectorAll("[data-nav]").forEach((link) => {
  link.addEventListener("click", () => showPage(link.dataset.nav));
});
window.addEventListener("hashchange", () => showPage(location.hash.slice(1)));
showPage(location.hash.slice(1));

element("refresh-button").addEventListener("click", refreshData);

element("brand-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const submit = event.currentTarget.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const response = await api("/brands/register", {
      method: "POST",
      body: JSON.stringify({
        brand_name: form.get("brand_name"),
        official_accounts: form.get("official_accounts"),
        official_urls: form.get("official_urls"),
      }),
    });
    event.currentTarget.reset();
    notify(`${response.brand.brand_name} was registered.`);
    await refreshData();
  } catch (error) {
    notify(error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

element("asset-type").addEventListener("change", (event) => {
  const isApp = event.currentTarget.value === "app";
  element("username-field").hidden = isApp;
  element("app-name-field").hidden = !isApp;
  element("username-field").querySelector("input").required = !isApp;
  element("app-name-field").querySelector("input").required = isApp;
  document.querySelectorAll(".app-fields").forEach((field) => { field.hidden = !isApp; });
});

element("analysis-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  const submit = event.currentTarget.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const response = await api("/analyze", {
      method: "POST",
      body: JSON.stringify(values),
    });
    notify(`Analysis saved: ${riskLabel(response.result.risk_status)}.`);
    event.currentTarget.reset();
    element("asset-type").dispatchEvent(new Event("change"));
    await refreshData();
  } catch (error) {
    notify(error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

refreshData();
