// SAIA Dashboard - Main JavaScript

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeKPIs();
    initializeAlertsTable();
    initializeCharts();
    initializeWorkflow();
    initializePageSpecific();
    simulateRealTimeUpdates();
});

// Sidebar Toggle
function initializeSidebar() {
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (menuToggle && sidebar && mainContent) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            sidebar.classList.toggle('active');
            mainContent.classList.toggle('expanded');
        });
    }
}

// Update KPI Values with Animation
function initializeKPIs() {
    if (document.getElementById('activeAlerts')) {
        animateValue('activeAlerts', 0, kpiData.activeAlerts, 1000);
    }
    if (document.getElementById('resolvedCases')) {
        animateValue('resolvedCases', 0, kpiData.resolvedCases, 1200);
    }
    if (document.getElementById('pendingReports')) {
        animateValue('pendingReports', 0, kpiData.pendingReports, 800);
    }
    if (document.getElementById('avgResponseTime')) {
        document.getElementById('avgResponseTime').textContent = kpiData.avgResponseTime;
    }
}

function animateValue(id, start, end, duration) {
    const element = document.getElementById(id);
    if (!element) return;
    
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= end) {
            element.textContent = Math.round(end);
            clearInterval(timer);
        } else {
            element.textContent = Math.round(current);
        }
    }, 16);
}

// Render Alerts Table
function initializeAlertsTable() {
    const tbody = document.getElementById('alertsTableBody');
    if (!tbody) return;
    
    renderAlertsTable(mockAlerts);
    
    const severityFilter = document.getElementById('severityFilter');
    if (severityFilter) {
        severityFilter.addEventListener('change', function() {
            const selectedSeverity = this.value;
            
            if (selectedSeverity === 'all') {
                renderAlertsTable(mockAlerts);
            } else {
                const filteredAlerts = mockAlerts.filter(alert => 
                    alert.severity === selectedSeverity
                );
                renderAlertsTable(filteredAlerts);
            }
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
            <td><span class="status-badge ${alert.status.toLowerCase().replace(' ', '-')}">${alert.status}</span></td>
            <td>${alert.assignedTo}</td>
            <td>${alert.timestamp}</td>
        `;
        tbody.appendChild(row);
    });
}

// Initialize Charts
function initializeCharts() {
    if (typeof renderCharts === 'function') {
        renderCharts();
    }
}

// Initialize Workflow Diagram
function initializeWorkflow() {
    if (typeof renderWorkflowDiagram === 'function') {
        renderWorkflowDiagram();
    }
}

// Initialize Page-Specific Features
function initializePageSpecific() {
    const path = window.location.pathname;
    
    if (path.includes('rules.html')) {
        if (typeof initializeRulesManagement === 'function') {
            initializeRulesManagement();
        }
    } else if (path.includes('alerts.html')) {
        if (typeof initializeAlertsManagement === 'function') {
            initializeAlertsManagement();
        }
    } else if (path.includes('reports.html')) {
        initializeReportsPage();
    }
}

// Reports Page Initialization
function initializeReportsPage() {
    const reportForm = document.getElementById('reportForm');
    if (!reportForm) return;
    
    reportForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const framework = document.getElementById('framework').value;
        const dateRange = document.getElementById('dateRange').value;
        const format = document.getElementById('format').value;
        
        console.log('Generating report:', { framework, dateRange, format });
        
        // Simulate report generation
        const reportId = 'RPT-' + Math.floor(Math.random() * 10000);
        alert(`Report Generated Successfully!\n\nReport ID: ${reportId}\nFramework: ${framework === 'all' ? 'All Frameworks' : framework}\nDate Range: Last ${dateRange} days\nFormat: ${format.toUpperCase()}\n\nDownloading...`);
    });
    
    // Download buttons for recent reports
    document.querySelectorAll('.report-item .btn-secondary').forEach(btn => {
        btn.addEventListener('click', function() {
            const reportName = this.parentElement.querySelector('h4').textContent;
            console.log('Downloading report:', reportName);
            alert(`Downloading: ${reportName}`);
        });
    });
}

// Simulate Real-Time Updates
function simulateRealTimeUpdates() {
    setInterval(() => {
        const activeAlertsEl = document.getElementById('activeAlerts');
        if (activeAlertsEl) {
            const change = Math.floor(Math.random() * 3) - 1;
            kpiData.activeAlerts = Math.max(0, kpiData.activeAlerts + change);
            activeAlertsEl.textContent = kpiData.activeAlerts;
            
            const notificationBadge = document.querySelector('.notification-badge');
            if (notificationBadge) {
                const currentNotifications = parseInt(notificationBadge.textContent);
                if (change > 0) {
                    notificationBadge.textContent = currentNotifications + 1;
                }
            }
        }
    }, 10000);
}

// Handle window resize for charts
window.addEventListener('resize', function() {
    if (typeof renderCharts === 'function') {
        renderCharts();
    }
    if (typeof renderWorkflowDiagram === 'function') {
        renderWorkflowDiagram();
    }
});

// Table row click handler
document.addEventListener('click', function(e) {
    if (e.target.closest('.alerts-table tbody tr')) {
        const row = e.target.closest('tr');
        const alertId = row.querySelector('td strong').textContent;
        console.log('Alert clicked:', alertId);
    }
});

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeSidebar,
        initializeKPIs,
        initializeAlertsTable,
        renderAlertsTable,
        initializeCharts,
        initializeWorkflow,
        initializePageSpecific,
        simulateRealTimeUpdates
    };
}