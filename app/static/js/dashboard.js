let trendChart = null;
let statusChart = null;
let autoRefreshTimer = null;
let isAutoRefresh = true;

const trendLabels = [];
const trendTotalData = [];
const trendErrorData = [];

document.addEventListener("DOMContentLoaded", () => {
    initCharts();
    fetchStats();
    startAutoRefresh();
    
    const toggleBtn = document.getElementById("toggle-refresh-btn");
    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            isAutoRefresh = !isAutoRefresh;
            toggleBtn.textContent = isAutoRefresh ? "Auto-Refresh: ON" : "Auto-Refresh: OFF";
            toggleBtn.className = isAutoRefresh ? "btn btn-primary" : "btn btn-outline";
            if (isAutoRefresh) {
                startAutoRefresh();
                showToast("Auto-refresh enabled (every 3s)");
            } else {
                clearInterval(autoRefreshTimer);
                showToast("Auto-refresh paused");
            }
        });
    }
});

function startAutoRefresh() {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => {
        if (isAutoRefresh) {
            fetchStats();
        }
    }, 3000);
}

function initCharts() {
    const trendCtx = document.getElementById("trendChart");
    if (trendCtx) {
        trendChart = new Chart(trendCtx.getContext("2d"), {
            type: "line",
            data: {
                labels: trendLabels,
                datasets: [
                    {
                        label: "Total Requests",
                        data: trendTotalData,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.1)",
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2,
                        pointRadius: 2
                    },
                    {
                        label: "Failed Requests (4xx/5xx)",
                        data: trendErrorData,
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239, 68, 68, 0.15)",
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2,
                        pointRadius: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: "#94a3b8", font: { size: 11 } }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { color: "rgba(255, 255, 255, 0.05)" }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: "#64748b", font: { size: 10 } },
                        grid: { color: "rgba(255, 255, 255, 0.05)" }
                    }
                }
            }
        });
    }

    const statusCtx = document.getElementById("statusChart");
    if (statusCtx) {
        statusChart = new Chart(statusCtx.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: ["2xx Success", "3xx Redirect", "4xx Client Error", "5xx Server Error"],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: ["#10b981", "#3b82f6", "#f59e0b", "#ef4444"],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#94a3b8", font: { size: 11 } }
                    }
                },
                cutout: "70%"
            }
        });
    }
}

async function fetchStats() {
    try {
        const response = await fetch("/api/monitoring/stats");
        if (!response.ok) return;
        const data = await response.json();
        renderDashboard(data);
    } catch (err) {
        console.error("Failed to fetch telemetry:", err);
    }
}

function renderDashboard(data) {
    // 1. Status Banner
    const banner = document.getElementById("status-banner");
    const statusText = document.getElementById("status-text");
    const statusDesc = document.getElementById("status-desc");
    const dot = document.getElementById("status-dot");
    
    if (statusText) statusText.textContent = data.service_status;
    if (statusDesc) {
        statusDesc.textContent = `Host CPU: ${data.system.cpu_percent}% | RAM: ${data.system.memory_percent}% | SQLite Ping: ${data.system.db_ping_ms}ms | Uptime: ${data.system.uptime_seconds}s`;
    }
    if (dot) {
        dot.style.backgroundColor = data.status_color;
        dot.style.boxShadow = `0 0 10px ${data.status_color}`;
    }
    if (banner) {
        banner.style.borderColor = data.status_color;
    }

    // 2. KPI Cards
    setText("kpi-uptime", `${data.uptime_pct}%`);
    setText("kpi-latency", `${data.avg_duration_ms} ms`);
    setText("kpi-p95", `P95: ${data.p95_duration_ms} ms`);
    setText("kpi-total-reqs", data.total_requests);
    setText("kpi-failed-reqs", data.failed_requests);
    setText("kpi-error-rate", `${data.error_rate}%`);
    setText("kpi-alerts-count", data.active_alerts_count);

    // 3. Update Charts
    updateCharts(data);

    // 4. Update Recent Telemetry Table
    renderTelemetryTable(data.recent_logs);

    // 5. Update Recent Alerts Table
    renderAlertsTable(data.recent_alerts);
}

function updateCharts(data) {
    const timeLabel = new Date().toLocaleTimeString();

    if (trendChart) {
        trendLabels.push(timeLabel);
        trendTotalData.push(data.total_requests);
        trendErrorData.push(data.failed_requests);

        if (trendLabels.length > 15) {
            trendLabels.shift();
            trendTotalData.shift();
            trendErrorData.shift();
        }
        trendChart.update("none");
    }

    if (statusChart && data.status_distribution) {
        statusChart.data.datasets[0].data = [
            data.status_distribution["2xx"] || 0,
            data.status_distribution["3xx"] || 0,
            data.status_distribution["4xx"] || 0,
            data.status_distribution["5xx"] || 0
        ];
        statusChart.update("none");
    }
}

function renderTelemetryTable(logs) {
    const tbody = document.getElementById("telemetry-table-body");
    if (!tbody || !logs) return;

    if (logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 24px;">No telemetry logs recorded yet. Run a simulation above.</td></tr>`;
        return;
    }

    tbody.innerHTML = logs.map(log => {
        let statusBadgeClass = "status-2xx";
        if (log.status_code >= 500) statusBadgeClass = "status-5xx";
        else if (log.status_code >= 400) statusBadgeClass = "status-4xx";
        else if (log.status_code >= 300) statusBadgeClass = "status-3xx";

        return `
            <tr>
                <td><span style="font-family: var(--font-mono); color: var(--text-muted);">${log.timestamp}</span></td>
                <td><span style="font-weight: 700; color: #93c5fd;">${log.method}</span></td>
                <td><code style="color: var(--text-primary); font-size: 11px;">${log.path}</code></td>
                <td><span class="badge-status ${statusBadgeClass}">${log.status_code}</span></td>
                <td><span style="font-family: var(--font-mono); font-weight: 600;">${log.duration_ms} ms</span></td>
                <td><span style="color: var(--text-muted); font-size: 11px;">${log.client_ip}</span></td>
                <td>
                    ${log.is_error ? 
                        `<button class="btn btn-outline" style="padding: 3px 8px; font-size: 11px; border-color: rgba(239, 68, 68, 0.4); color: #f87171;" onclick="openRCA('${log.request_id}')">🔍 View RCA</button>` : 
                        `<span style="color: var(--color-success); font-size: 11px;">✓ OK</span>`
                    }
                </td>
            </tr>
        `;
    }).join("");
}

function renderAlertsTable(alerts) {
    const tbody = document.getElementById("alerts-table-body");
    if (!tbody || !alerts) return;

    if (alerts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding: 20px;">No alerts triggered. System operating normally.</td></tr>`;
        return;
    }

    tbody.innerHTML = alerts.map(a => {
        const isResolved = a.status === "RESOLVED";
        return `
            <tr>
                <td><span style="font-family: var(--font-mono); font-size: 11px;">${a.created_at}</span></td>
                <td><span class="badge-status severity-${a.severity}">${a.severity}</span></td>
                <td><strong>${a.title}</strong></td>
                <td><span style="font-size: 11px; color: var(--text-secondary);">${a.channels_notified}</span></td>
                <td>
                    <span style="font-size: 11px; font-weight: 600; color: ${isResolved ? 'var(--color-success)' : 'var(--color-danger)'};">
                        ${a.status}
                    </span>
                </td>
                <td>
                    <button class="btn btn-outline" style="padding: 3px 8px; font-size: 11px;" onclick="openAlertDetails('${a.alert_id}')">
                        Inspect
                    </button>
                    ${!isResolved ? `
                        <button class="btn btn-primary" style="padding: 3px 8px; font-size: 11px; margin-left: 4px;" onclick="resolveAlert('${a.alert_id}')">
                            Resolve
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join("");
}

async function runSimulation(scenario) {
    showToast(`Triggering test: ${scenario}...`);
    try {
        if (scenario === "500-error") {
            await fetch("/simulate-error?error_kind=math");
            showToast("500 Server Error simulated & recorded!", "danger");
        } else if (scenario === "timeout") {
            showToast("Executing >3s timeout request (waiting 3.5s)...");
            await fetch("/simulate-timeout?delay_seconds=3.5");
            showToast("SLA Timeout (>3s) triggered and logged!", "warning");
        } else if (scenario === "auth-failure") {
            await fetch("/secure-data", { headers: { "Authorization": "Bearer invalid-tampered-token" } });
            showToast("401 Unauthorized Failure triggered!", "warning");
        } else if (scenario === "rate-limit") {
            await fetch("/simulate-rate-limit?force_breach=true");
            showToast("429 Rate Limit Failure triggered!", "warning");
        } else if (scenario === "health-failure") {
            await fetch("/simulate-health-failure");
            showToast("503 Service Health Failure recorded!", "danger");
        } else if (scenario === "downtime") {
            await fetch("/simulate-downtime");
            showToast("503 API Downtime recorded!", "danger");
        } else if (scenario === "error-rate") {
            showToast("Sending failure burst to trip error-rate alert...");
            for (let i = 0; i < 8; i++) {
                await fetch("/simulate-error?error_kind=math");
            }
            showToast("Increased failure rate burst complete!", "warning");
        } else if (scenario === "burst-traffic") {
            showToast("Sending 20 healthy API requests...");
            const endpoints = ["/health", "/users", "/products"];
            for (let i = 0; i < 20; i++) {
                const ep = endpoints[i % endpoints.length];
                fetch(ep);
            }
            showToast("20 healthy requests dispatched!", "success");
        }
        setTimeout(fetchStats, 600);
    } catch (err) {
        console.warn("Simulation call response:", err);
        setTimeout(fetchStats, 600);
    }
}

async function openRCA(requestId) {
    try {
        const resp = await fetch(`/api/monitoring/rca/${requestId}`);
        if (!resp.ok) {
            showToast("Failed to fetch RCA diagnostics", "danger");
            return;
        }
        const data = await resp.json();
        
        document.getElementById("rca-modal-title").textContent = `Root Cause Analysis — ${data.method} ${data.path}`;
        
        const content = document.getElementById("rca-modal-body");
        content.innerHTML = `
            <div class="rca-box ${data.status_code >= 500 ? 'rca-critical' : 'rca-warning'}">
                <h4 style="margin-bottom: 6px; font-size: 14px;"><strong>${data.analysis.title}</strong></h4>
                <p style="font-size: 13px; color: var(--text-primary); margin-bottom: 8px;">${data.analysis.summary}</p>
                <div style="font-size: 11px; color: var(--text-muted); display: flex; gap: 16px;">
                    <span>Status: <strong>${data.status_code}</strong></span>
                    <span>Duration: <strong>${data.duration_ms} ms</strong></span>
                    <span>Rule: <strong>${data.analysis.rule_name}</strong></span>
                </div>
            </div>

            <h4 style="font-size: 13px; margin: 16px 0 6px 0; color: #93c5fd;">🛠️ Recommended Remediation</h4>
            <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border-color); border-radius: 6px; padding: 12px; font-size: 12px; line-height: 1.6; white-space: pre-wrap;">${data.analysis.recommendation}</div>

            ${data.error_traceback ? `
                <h4 style="font-size: 13px; margin: 16px 0 6px 0; color: #f87171;">Captured Stack Trace:</h4>
                <pre class="code-block">${data.error_traceback}</pre>
            ` : ''}

            <div style="margin-top: 16px; font-size: 11px; color: var(--text-muted);">
                Request ID: <code>${data.request_id}</code> | Client IP: <code>${data.client_ip}</code>
            </div>
        `;

        document.getElementById("rca-modal").style.display = "flex";
    } catch (e) {
        showToast("Error loading RCA modal: " + e, "danger");
    }
}

async function openAlertDetails(alertId) {
    try {
        const resp = await fetch("/api/monitoring/alerts");
        const alerts = await resp.json();
        const alert = alerts.find(a => a.alert_id === alertId);
        if (!alert) return;

        let previewObj = null;
        try {
            previewObj = JSON.parse(alert.notification_preview);
        } catch (_) {}

        document.getElementById("rca-modal-title").textContent = `Incident Alert: ${alert.alert_id}`;
        
        const content = document.getElementById("rca-modal-body");
        content.innerHTML = `
            <div class="rca-box ${alert.severity === 'CRITICAL' ? 'rca-critical' : 'rca-warning'}">
                <div style="display:flex; justify-content:space-between; margin-bottom: 6px;">
                    <span class="badge-status severity-${alert.severity}">${alert.severity}</span>
                    <span style="font-size: 11px; color: var(--text-muted);">${alert.created_at}</span>
                </div>
                <h3 style="margin-bottom: 6px; font-size: 15px;">${alert.title}</h3>
                <p style="font-size: 13px;">${alert.description}</p>
            </div>

            <h4 style="font-size: 13px; margin: 12px 0 6px 0; color: #93c5fd;">Root Cause Analysis</h4>
            <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border-color); border-radius: 6px; padding: 12px; font-size: 12px;">
                ${alert.rca_summary}
            </div>

            <h4 style="font-size: 13px; margin: 12px 0 6px 0; color: #34d399;">Action Items & Runbook</h4>
            <pre class="code-block" style="color: #6ee7b7;">${alert.rca_recommendation}</pre>

            <h4 style="font-size: 13px; margin: 12px 0 6px 0; color: #f59e0b;">Notification Dispatch Preview (Slack & Email)</h4>
            <pre class="code-block" style="max-height: 200px; overflow-y: auto;">${previewObj ? JSON.stringify(previewObj.slack_payload, null, 2) : 'No preview available'}</pre>
        `;

        document.getElementById("rca-modal").style.display = "flex";
    } catch (e) {
        showToast("Error inspecting alert: " + e, "danger");
    }
}

async function resolveAlert(alertId) {
    try {
        const resp = await fetch(`/api/monitoring/alerts/${alertId}/resolve`, { method: "POST" });
        if (resp.ok) {
            showToast(`Alert ${alertId} marked as RESOLVED`, "success");
            fetchStats();
        }
    } catch (e) {
        showToast("Failed to resolve alert", "danger");
    }
}

function closeModal() {
    document.getElementById("rca-modal").style.display = "none";
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    
    const toast = document.createElement("div");
    toast.className = "toast";
    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "warning") icon = "⚠️";
    if (type === "danger") icon = "🚨";

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}
