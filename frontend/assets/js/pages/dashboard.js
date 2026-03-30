// SAIA Dashboard - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeKPIs();
    initializeAlertsTable();
    initializeCharts();
    initializeWorkflow();
    initializePageSpecific();
    simulateRealTimeUpdates();
});

function initializeSidebar() {
    const menuToggle  = document.getElementById('menuToggle');
    const sidebar     = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    if (menuToggle && sidebar && mainContent) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            sidebar.classList.toggle('active');
            mainContent.classList.toggle('expanded');
        });
    }
}

function initializeKPIs() {
    if (document.getElementById('activeAlerts'))    animateValue('activeAlerts',    0, kpiData.activeAlerts,    1000);
    if (document.getElementById('resolvedCases'))   animateValue('resolvedCases',   0, kpiData.resolvedCases,   1200);
    if (document.getElementById('pendingReports'))  animateValue('pendingReports',  0, kpiData.pendingReports,  800);
    if (document.getElementById('avgResponseTime')) document.getElementById('avgResponseTime').textContent = kpiData.avgResponseTime;
}

function animateValue(id, start, end, duration) {
    const el = document.getElementById(id);
    if (!el) return;
    const increment = (end - start) / (duration / 16);
    let current = start;
    const timer = setInterval(() => {
        current += increment;
        if (current >= end) { el.textContent = Math.round(end); clearInterval(timer); }
        else el.textContent = Math.round(current);
    }, 16);
}

function initializeAlertsTable() {
    const tbody = document.getElementById('alertsTableBody');
    if (!tbody) return;
    renderAlertsTable(mockAlerts);
    const filter = document.getElementById('severityFilter');
    if (filter) {
        filter.addEventListener('change', function() {
            const filtered = this.value === 'all' ? mockAlerts : mockAlerts.filter(a => a.severity === this.value);
            renderAlertsTable(filtered);
        });
    }
}

function renderAlertsTable(alerts) {
    const tbody = document.getElementById('alertsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    alerts.forEach(alert => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${alert.id}</strong></td>
            <td>${alert.clause}</td>
            <td><span class="severity-badge ${alert.severity.toLowerCase()}">${alert.severity}</span></td>
            <td><span class="status-badge ${alert.status.toLowerCase().replace(' ','-')}">${alert.status}</span></td>
            <td>${alert.assignedTo}</td>
            <td>${alert.timestamp}</td>`;
        tbody.appendChild(row);
    });
}

function initializeCharts()   { if (typeof renderCharts === 'function') renderCharts(); }
function initializeWorkflow() { if (typeof renderWorkflowDiagram === 'function') renderWorkflowDiagram(); }

function initializePageSpecific() {
    const path = window.location.pathname;
    if (path.includes('rules.html')   && typeof initializeRulesManagement === 'function')  initializeRulesManagement();
    if (path.includes('alerts.html')  && typeof initializeAlertsManagement === 'function') initializeAlertsManagement();
    if (path.includes('reports.html')) initializeReportsPage();
}

function initializeReportsPage() {
    const form = document.getElementById('reportForm');
    if (!form) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const framework = document.getElementById('framework').value;
        const dateRange = document.getElementById('dateRange').value;
        const format    = document.getElementById('format').value;
        const reportId  = 'RPT-' + Math.floor(Math.random() * 10000);
        alert(`Report Generated!\n\nID: ${reportId}\nFramework: ${framework === 'all' ? 'All Frameworks' : framework}\nDate Range: Last ${dateRange} days\nFormat: ${format.toUpperCase()}`);
    });
    document.querySelectorAll('.report-item .btn-secondary').forEach(btn => {
        btn.addEventListener('click', function() {
            alert(`Downloading: ${this.parentElement.querySelector('h4').textContent}`);
        });
    });
}

function simulateRealTimeUpdates() {
    setInterval(() => {
        const el = document.getElementById('activeAlerts');
        if (el) {
            const change = Math.floor(Math.random() * 3) - 1;
            kpiData.activeAlerts = Math.max(0, kpiData.activeAlerts + change);
            el.textContent = kpiData.activeAlerts;
            const badge = document.querySelector('.notification-badge');
            if (badge && change > 0) badge.textContent = parseInt(badge.textContent) + 1;
        }
    }, 10000);
}

window.addEventListener('resize', function() {
    if (typeof renderCharts === 'function') renderCharts();
    if (typeof renderWorkflowDiagram === 'function') renderWorkflowDiagram();
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initializeSidebar, initializeKPIs, initializeAlertsTable, renderAlertsTable, initializeCharts, initializeWorkflow, initializePageSpecific, simulateRealTimeUpdates };
}
