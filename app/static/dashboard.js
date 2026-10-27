const token = localStorage.getItem("access_token");
const username = localStorage.getItem("username");
const role = localStorage.getItem("role");

function updateSessionStatus() {
  const el = document.getElementById("session-status");
  const logoutBtn = document.getElementById("logout-btn");
  if (token) {
    el.textContent = username ? `🟢 ${username} (${role})` : "🟢 Logged in";
    el.className = "pill pill-active";
    logoutBtn.hidden = false;
  } else {
    el.textContent = "Not logged in";
    el.className = "pill pill-muted";
    logoutBtn.hidden = true;
  }
}

function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("username");
  localStorage.removeItem("role");
  window.location.href = "/";
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  return isNaN(d) ? value : d.toLocaleDateString();
}

function renderStats(totalDocuments, rows) {
  const grid = document.getElementById("stat-grid");
  const byStatus = {};
  for (const row of rows) {
    const status = row.STATUS || "UNKNOWN";
    byStatus[status] = (byStatus[status] || 0) + row.DOCUMENT_COUNT;
  }

  const tiles = [
    ["Total Documents", totalDocuments],
    ["Processed", byStatus.PROCESSED || 0],
    ["Failed", byStatus.FAILED || 0],
    ["Uploaded (Pending)", byStatus.UPLOADED || 0],
  ];

  grid.innerHTML = "";
  for (const [label, value] of tiles) {
    const tile = document.createElement("div");
    tile.className = "stat-tile";
    tile.innerHTML = `<div class="stat-label">${label}</div><div class="stat-value">${value}</div>`;
    grid.appendChild(tile);
  }
}

function renderTable(rows) {
  const tbody = document.getElementById("dashboard-table-body");
  const emptyEl = document.getElementById("dashboard-empty");
  tbody.innerHTML = "";

  if (!rows.length) {
    emptyEl.hidden = false;
    return;
  }
  emptyEl.hidden = true;

  const sorted = [...rows].sort((a, b) => new Date(b.PROCESSING_DAY) - new Date(a.PROCESSING_DAY));
  for (const row of sorted) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDate(row.PROCESSING_DAY)}</td>
      <td>${row.DOCUMENT_TYPE || "—"}</td>
      <td><span class="status-chip ${row.STATUS}">${row.STATUS}</span></td>
      <td>${row.DOCUMENT_COUNT}</td>
    `;
    tbody.appendChild(tr);
  }
}

function setRefreshing(isRefreshing) {
  const btn = document.getElementById("refresh-btn");
  btn.disabled = isRefreshing;
  btn.textContent = isRefreshing ? "Refreshing…" : "Refresh";
}

function renderDemoBadge(isDemo) {
  const badge = document.getElementById("demo-badge");
  badge.hidden = !isDemo;
}

function renderLastUpdated() {
  const el = document.getElementById("last-updated");
  el.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

async function loadDashboard() {
  const outputEl = document.getElementById("dashboard-output");
  outputEl.textContent = "";
  outputEl.className = "output";
  setRefreshing(true);

  try {
    const response = await fetch("/api/dashboard", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
      throw { status: response.status, body };
    }

    renderDemoBadge(body.demo_data);
    renderStats(body.total_documents, body.rows);
    renderTable(body.rows);
    renderLastUpdated();
  } catch (err) {
    console.error("Dashboard load failed:", err.body || err);
    outputEl.textContent = JSON.stringify(err.body || err, null, 2);
    outputEl.className = "output error";
  } finally {
    setRefreshing(false);
  }
}

document.getElementById("logout-btn").addEventListener("click", logout);
document.getElementById("refresh-btn").addEventListener("click", loadDashboard);

updateSessionStatus();

if (!token) {
  document.getElementById("login-required-card").hidden = false;
} else {
  document.getElementById("dashboard-content").hidden = false;
  loadDashboard();
}
