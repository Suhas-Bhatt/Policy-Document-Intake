const state = {
  token: localStorage.getItem("access_token") || null,
  username: localStorage.getItem("username") || null,
  role: localStorage.getItem("role") || null,
};

function updateSessionStatus() {
  const el = document.getElementById("session-status");
  const logoutBtn = document.getElementById("logout-btn");
  const loginSection = document.getElementById("login-section");
  const appSections = document.querySelectorAll(".app-section");
  if (state.token) {
    el.textContent = state.username ? `🟢 ${state.username} (${state.role})` : "🟢 Logged in";
    el.className = "pill pill-active";
    logoutBtn.hidden = false;
    loginSection.hidden = true;
    appSections.forEach((section) => { section.hidden = false; });
  } else {
    el.textContent = "Not logged in";
    el.className = "pill pill-muted";
    logoutBtn.hidden = true;
    loginSection.hidden = false;
    appSections.forEach((section) => { section.hidden = true; });
  }
}

function resetForms() {
  document.querySelectorAll(".output").forEach((el) => {
    el.textContent = "";
    el.className = "output";
  });
  document.querySelectorAll(".app-section form").forEach((form) => form.reset());
}

function logout() {
  state.token = null;
  state.username = null;
  state.role = null;
  localStorage.removeItem("access_token");
  localStorage.removeItem("username");
  localStorage.removeItem("role");
  updateSessionStatus();
  resetForms();
  showOutput("login-output", "Logged out");
}

function authHeaders(extra = {}) {
  if (!state.token) return extra;
  return { ...extra, Authorization: `Bearer ${state.token}` };
}

function showOutput(elementId, data, isError = false) {
  const el = document.getElementById(elementId);
  el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  el.className = `output ${isError ? "error" : "success"}`;
}

async function callApi(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw { status: response.status, body };
  }
  return body;
}

function withLoading(button, loadingText) {
  const original = button.textContent;
  button.disabled = true;
  button.classList.add("is-loading");
  button.textContent = loadingText;
  return () => {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.textContent = original;
  };
}

async function performLogin(username, role) {
  const result = await callApi("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, role }),
  });
  state.token = result.access_token;
  state.username = username;
  state.role = role;
  localStorage.setItem("access_token", state.token);
  localStorage.setItem("username", username);
  localStorage.setItem("role", role);
  updateSessionStatus();
  return result;
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = document.getElementById("login-username").value;
  const role = document.getElementById("login-role").value;
  const restore = withLoading(document.getElementById("login-submit-btn"), "Logging in…");
  try {
    const result = await performLogin(username, role);
    console.log("Login response:", result);
    showOutput("login-output", "Login successful");
  } catch (err) {
    console.error("Login failed:", err.body || err);
    showOutput("login-output", err.body || err, true);
  } finally {
    restore();
  }
});

document.getElementById("skip-login-btn").addEventListener("click", async () => {
  const restore = withLoading(document.getElementById("skip-login-btn"), "Signing in…");
  try {
    const result = await performLogin("guest", "agent");
    console.log("Guest login response:", result);
    const outputEl = document.getElementById("login-output");
    outputEl.innerHTML = "Signed in as <strong>guest</strong> — explore freely.";
    outputEl.className = "output success";
  } catch (err) {
    console.error("Guest login failed:", err.body || err);
    showOutput("login-output", err.body || err, true);
  } finally {
    restore();
  }
});

const FIELD_LABELS = {
  document_id: "Document ID",
  customer_id: "Customer ID",
  policy_id: "Policy ID",
  document_type: "Document Type",
  policy_number: "Policy Number",
  effective_date: "Effective Date",
  raw_text_excerpt: "Raw Text Excerpt",
};

function renderDocumentPanel(item, { panelId, statusId, gridId, includeIdentifiers = false }) {
  const panel = document.getElementById(panelId);
  const statusEl = document.getElementById(statusId);
  const grid = document.getElementById(gridId);
  panel.hidden = false;

  const status = item.status || "UNKNOWN";
  statusEl.textContent = status;
  statusEl.className = "extraction-status" +
    (status === "PROCESSED" ? " is-processed" : status === "FAILED" ? " is-failed" : "");

  const extracted = item.extracted_data || {};
  const rows = includeIdentifiers
    ? [
        ["document_id", item.document_id],
        ["customer_id", item.customer_id],
        ["policy_id", item.policy_id],
        ["document_type", item.document_type],
        ["policy_number", extracted.policy_number],
        ["effective_date", extracted.effective_date],
        ["raw_text_excerpt", extracted.raw_text_excerpt],
      ]
    : [
        ["document_type", item.document_type],
        ["policy_number", extracted.policy_number],
        ["effective_date", extracted.effective_date],
        ["raw_text_excerpt", extracted.raw_text_excerpt],
      ];

  grid.innerHTML = "";
  for (const [key, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = FIELD_LABELS[key];
    const dd = document.createElement("dd");
    if (value) {
      dd.textContent = value;
    } else {
      dd.textContent = status === "PROCESSED" || status === "FAILED" ? "Not found" : "Waiting for extraction…";
      dd.className = "muted";
    }
    grid.appendChild(dt);
    grid.appendChild(dd);
  }

  if (status === "FAILED" && item.error_details) {
    const dt = document.createElement("dt");
    dt.textContent = "Error";
    const dd = document.createElement("dd");
    dd.textContent = item.error_details;
    grid.appendChild(dt);
    grid.appendChild(dd);
  }
}

function renderExtraction(item) {
  renderDocumentPanel(item, { panelId: "upload-extraction", statusId: "extraction-status", gridId: "extraction-grid" });
}

async function pollDocumentStatus(documentId, attempt = 0) {
  const MAX_ATTEMPTS = 20;
  const POLL_INTERVAL_MS = 3000;

  try {
    const item = await callApi(`/api/documents/${encodeURIComponent(documentId)}/status`, {
      headers: authHeaders(),
    });
    renderExtraction(item);

    if (item.status === "PROCESSED" || item.status === "FAILED") {
      return;
    }
  } catch (err) {
    console.error("Status poll failed:", err.body || err);
  }

  if (attempt < MAX_ATTEMPTS) {
    setTimeout(() => pollDocumentStatus(documentId, attempt + 1), POLL_INTERVAL_MS);
  }
}

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("upload-file");
  const customerId = document.getElementById("upload-customer").value;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("customer_id", customerId);

  document.getElementById("upload-extraction").hidden = true;
  const restore = withLoading(event.target.querySelector("button[type=submit]"), "Uploading…");

  try {
    const result = await callApi("/api/documents/upload", {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
    showOutput("upload-output", result);
    document.getElementById("status-document-id").value = result.document_id || "";
    if (result.document_id) {
      pollDocumentStatus(result.document_id);
    }
  } catch (err) {
    showOutput("upload-output", err.body || err, true);
  } finally {
    restore();
  }
});

document.getElementById("csv-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("csv-upload-file");

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  const restore = withLoading(event.target.querySelector("button[type=submit]"), "Importing…");

  try {
    const result = await callApi("/api/documents/bulk-upload", {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
    console.log("Bulk import response:", result);
    showOutput("csv-upload-output", `File Uploaded successfully (${result.rows_queued} rows queued for Snowflake load)`);
  } catch (err) {
    console.error("Bulk import failed:", err.body || err);
    showOutput("csv-upload-output", err.body || err, true);
  } finally {
    restore();
  }
});

document.getElementById("status-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const documentId = document.getElementById("status-document-id").value;
  document.getElementById("status-extraction").hidden = true;
  document.getElementById("status-output").textContent = "";
  document.getElementById("status-output").className = "output";
  const restore = withLoading(event.target.querySelector("button[type=submit]"), "Checking…");
  try {
    const result = await callApi(`/api/documents/${encodeURIComponent(documentId)}/status`, {
      headers: authHeaders(),
    });
    renderDocumentPanel(result, {
      panelId: "status-extraction",
      statusId: "status-extraction-status",
      gridId: "status-extraction-grid",
      includeIdentifiers: true,
    });
  } catch (err) {
    showOutput("status-output", err.body || err, true);
  } finally {
    restore();
  }
});

const POLICY_FIELD_LABELS = {
  POLICY_ID: "Policy ID",
  CUSTOMER_ID: "Customer ID",
  POLICY_TYPE: "Policy Type",
  PRODUCT_NAME: "Product Name",
  EFFECTIVE_DATE: "Effective Date",
  STATUS: "Status",
  UPDATED_AT: "Updated At",
};

function formatSnowflakeDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return isNaN(d) ? value : d.toLocaleString();
}

function renderPolicyLookup(policy) {
  const grid = document.getElementById("policy-grid");
  grid.hidden = false;
  grid.innerHTML = "";

  const rows = [
    ["POLICY_ID", policy.POLICY_ID],
    ["CUSTOMER_ID", policy.CUSTOMER_ID],
    ["POLICY_TYPE", policy.POLICY_TYPE],
    ["PRODUCT_NAME", policy.PRODUCT_NAME],
    ["EFFECTIVE_DATE", formatSnowflakeDate(policy.EFFECTIVE_DATE)],
    ["STATUS", policy.STATUS],
    ["UPDATED_AT", formatSnowflakeDate(policy.UPDATED_AT)],
  ];

  for (const [key, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = POLICY_FIELD_LABELS[key];
    const dd = document.createElement("dd");
    if (key === "STATUS" && value) {
      dd.innerHTML = `<span class="status-chip ${value}">${value}</span>`;
    } else {
      dd.textContent = value || "—";
      if (!value) dd.className = "muted";
    }
    grid.appendChild(dt);
    grid.appendChild(dd);
  }
}

document.getElementById("policy-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const policyId = document.getElementById("policy-id").value;
  document.getElementById("policy-grid").hidden = true;
  document.getElementById("policy-output").textContent = "";
  document.getElementById("policy-output").className = "output";
  const restore = withLoading(event.target.querySelector("button[type=submit]"), "Looking up…");
  try {
    const result = await callApi(`/api/policies/${encodeURIComponent(policyId)}`, {
      headers: authHeaders(),
    });
    renderPolicyLookup(result);
  } catch (err) {
    showOutput("policy-output", err.body || err, true);
  } finally {
    restore();
  }
});

function renderSearchResults(payload) {
  const tableWrap = document.getElementById("search-table-wrap");
  const tbody = document.getElementById("search-table-body");
  const emptyEl = document.getElementById("search-empty");
  tbody.innerHTML = "";

  if (!payload.results || payload.results.length === 0) {
    tableWrap.hidden = true;
    emptyEl.hidden = false;
    return;
  }

  emptyEl.hidden = true;
  tableWrap.hidden = false;
  for (const row of payload.results) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.DOCUMENT_ID || "—"}</td>
      <td>${row.POLICY_ID || "—"}</td>
      <td>${row.CUSTOMER_ID || "—"}</td>
      <td>${row.DOCUMENT_TYPE || "—"}</td>
      <td><span class="status-chip ${row.STATUS}">${row.STATUS || "—"}</span></td>
      <td>${formatSnowflakeDate(row.UPDATED_AT) || "—"}</td>
    `;
    tbody.appendChild(tr);
  }
}

document.getElementById("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("search-query").value;
  document.getElementById("search-table-wrap").hidden = true;
  document.getElementById("search-empty").hidden = true;
  document.getElementById("search-output").textContent = "";
  document.getElementById("search-output").className = "output";
  const restore = withLoading(event.target.querySelector("button[type=submit]"), "Searching…");
  try {
    const result = await callApi(`/api/search?q=${encodeURIComponent(query)}`, {
      headers: authHeaders(),
    });
    renderSearchResults(result);
  } catch (err) {
    showOutput("search-output", err.body || err, true);
  } finally {
    restore();
  }
});

document.getElementById("logout-btn").addEventListener("click", logout);

updateSessionStatus();
