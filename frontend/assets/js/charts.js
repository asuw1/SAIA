/**
 * SAIA V4 Charts Module
 * Uses Chart.js for rendering various visualizations
 */

const ChartColors = {
    critical: '#ef4444',
    high: '#f97316',
    medium: '#f59e0b',
    low: '#06b6d4',
    success: '#10b981',
    primary: '#3b82f6',
    secondary: '#6b7280',
    text: '#f3f4f6',
    border: '#374151'
};

/**
 * Render Anomaly Score Distribution Histogram
 */
async function renderAnomalyHistogram(containerId, data = null) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Load data from API if not provided
    if (!data) {
        try {
            data = await saia.getAnomalyDistribution();
        } catch (error) {
            console.error('Error loading anomaly distribution:', error);
            return;
        }
    }

    const ctx = container.querySelector('canvas') || (() => {
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        return canvas;
    })();

    // Destroy existing chart if it exists
    if (ctx.chart instanceof Chart) {
        ctx.chart.destroy();
    }

    const chartConfig = {
        type: 'bar',
        data: {
            labels: data.labels || ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100'],
            datasets: [
                {
                    label: 'Normal Events',
                    data: data.normal || [120, 150, 140, 110, 90, 70, 40, 20, 10, 5],
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: ChartColors.success,
                    borderWidth: 1
                },
                {
                    label: 'Anomalies',
                    data: data.anomalies || [5, 8, 12, 18, 25, 35, 45, 55, 70, 120],
                    backgroundColor: 'rgba(239, 68, 68, 0.6)',
                    borderColor: ChartColors.critical,
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: ChartColors.text,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: ChartColors.text,
                    bodyColor: ChartColors.text,
                    borderColor: ChartColors.primary,
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: { color: ChartColors.text },
                    grid: { color: ChartColors.border, drawBorder: false },
                    title: {
                        display: true,
                        text: 'Anomaly Score',
                        color: ChartColors.text
                    }
                },
                y: {
                    ticks: { color: ChartColors.text },
                    grid: { color: ChartColors.border },
                    title: {
                        display: true,
                        text: 'Event Count',
                        color: ChartColors.text
                    }
                }
            }
        }
    };

    ctx.chart = new Chart(ctx, chartConfig);
}

/**
 * Render Precision/Recall Tracker Line Chart
 */
async function renderPrecisionTracker(containerId, data = null) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Load data from API if not provided
    if (!data) {
        try {
            data = await saia.getPrecisionRecall();
        } catch (error) {
            console.error('Error loading precision/recall data:', error);
            return;
        }
    }

    const ctx = container.querySelector('canvas') || (() => {
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        return canvas;
    })();

    // Destroy existing chart if it exists
    if (ctx.chart instanceof Chart) {
        ctx.chart.destroy();
    }

    const days = data.dates || ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'];
    const precision = data.precision || [0.92, 0.94, 0.91, 0.93, 0.95, 0.94, 0.96];
    const recall = data.recall || [0.88, 0.89, 0.91, 0.90, 0.92, 0.93, 0.94];

    const chartConfig = {
        type: 'line',
        data: {
            labels: days,
            datasets: [
                {
                    label: 'Precision',
                    data: precision,
                    borderColor: ChartColors.primary,
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: ChartColors.primary,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7
                },
                {
                    label: 'Recall',
                    data: recall,
                    borderColor: ChartColors.success,
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: ChartColors.success,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7
                },
                {
                    label: 'Target (0.95)',
                    data: Array(days.length).fill(0.95),
                    borderColor: ChartColors.medium,
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    tension: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: ChartColors.text,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: ChartColors.text,
                    bodyColor: ChartColors.text,
                    borderColor: ChartColors.primary,
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + (context.parsed.y * 100).toFixed(1) + '%';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: ChartColors.text },
                    grid: { color: ChartColors.border, drawBorder: false }
                },
                y: {
                    ticks: { color: ChartColors.text, callback: v => (v * 100).toFixed(0) + '%' },
                    grid: { color: ChartColors.border },
                    min: 0,
                    max: 1
                }
            }
        }
    };

    ctx.chart = new Chart(ctx, chartConfig);
}

/**
 * Render Alerts By Domain Pie Chart
 */
async function renderAlertsByDomain(containerId, data = null) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Load data from API if not provided
    if (!data) {
        try {
            data = await saia.getAlertsByDomain();
        } catch (error) {
            console.error('Error loading alerts by domain:', error);
            return;
        }
    }

    const ctx = container.querySelector('canvas') || (() => {
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        return canvas;
    })();

    // Destroy existing chart if it exists
    if (ctx.chart instanceof Chart) {
        ctx.chart.destroy();
    }

    const chartConfig = {
        type: 'doughnut',
        data: {
            labels: data.labels || ['NCA', 'SAMA', 'CST', 'IA', 'Other'],
            datasets: [{
                data: data.values || [35, 25, 20, 15, 5],
                backgroundColor: [
                    ChartColors.primary,
                    ChartColors.critical,
                    ChartColors.medium,
                    ChartColors.success,
                    ChartColors.secondary
                ],
                borderColor: '#111827',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: ChartColors.text,
                        font: { size: 12 },
                        padding: 15
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: ChartColors.text,
                    bodyColor: ChartColors.text,
                    borderColor: ChartColors.primary,
                    borderWidth: 1
                }
            }
        }
    };

    ctx.chart = new Chart(ctx, chartConfig);
}

/**
 * Render Alerts By Severity Bar Chart
 */
async function renderAlertsBySeverity(containerId, data = null) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Load data from API if not provided
    if (!data) {
        try {
            data = await saia.getAlertsBySeverity();
        } catch (error) {
            console.error('Error loading alerts by severity:', error);
            return;
        }
    }

    const ctx = container.querySelector('canvas') || (() => {
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        return canvas;
    })();

    // Destroy existing chart if it exists
    if (ctx.chart instanceof Chart) {
        ctx.chart.destroy();
    }

    const chartConfig = {
        type: 'bar',
        data: {
            labels: data.labels || ['Critical', 'High', 'Medium', 'Low'],
            datasets: [{
                label: 'Number of Alerts',
                data: data.values || [45, 78, 92, 156],
                backgroundColor: [
                    ChartColors.critical,
                    ChartColors.high,
                    ChartColors.medium,
                    ChartColors.low
                ],
                borderColor: 'transparent',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: ChartColors.text,
                    bodyColor: ChartColors.text,
                    borderColor: ChartColors.primary,
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: { color: ChartColors.text },
                    grid: { color: ChartColors.border, drawBorder: false }
                },
                y: {
                    ticks: { color: ChartColors.text },
                    grid: { display: false }
                }
            }
        }
    };

    ctx.chart = new Chart(ctx, chartConfig);
}

/**
 * Render Timeline Visualization
 */
function renderTimeline(containerId, events) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = '';

    const timeline = document.createElement('div');
    timeline.className = 'timeline';
    timeline.style.cssText = `
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 20px 0;
    `;

    events.forEach((event, index) => {
        const item = document.createElement('div');
        item.style.cssText = `
            display: flex;
            gap: 20px;
        `;

        const dot = document.createElement('div');
        dot.style.cssText = `
            width: 12px;
            height: 12px;
            background: linear-gradient(135deg, #3b82f6, #06b6d4);
            border-radius: 50%;
            margin-top: 5px;
            flex-shrink: 0;
        `;

        const line = document.createElement('div');
        line.style.cssText = `
            position: absolute;
            left: 5px;
            top: 20px;
            bottom: -20px;
            width: 2px;
            background: rgba(59, 130, 246, 0.2);
        `;

        const content = document.createElement('div');
        content.style.cssText = `
            flex: 1;
            padding-bottom: 20px;
        `;

        const time = document.createElement('div');
        time.style.cssText = `
            font-size: 12px;
            color: #9ca3af;
            margin-bottom: 5px;
        `;
        time.textContent = event.timestamp;

        const description = document.createElement('div');
        description.style.cssText = `
            font-size: 14px;
            color: #f3f4f6;
            font-weight: 500;
        `;
        description.textContent = event.description;

        content.appendChild(time);
        content.appendChild(description);

        if (index < events.length - 1) {
            item.style.position = 'relative';
            item.appendChild(line);
        }

        item.appendChild(dot);
        item.appendChild(content);
        timeline.appendChild(item);
    });

    container.appendChild(timeline);
}

/**
 * Utility: Get color for severity
 */
function getSeverityColor(severity) {
    const colors = {
        'Critical': ChartColors.critical,
        'critical': ChartColors.critical,
        'High': ChartColors.high,
        'high': ChartColors.high,
        'Medium': ChartColors.medium,
        'medium': ChartColors.medium,
        'Low': ChartColors.low,
        'low': ChartColors.low
    };
    return colors[severity] || ChartColors.secondary;
}

/**
 * Utility: Format number with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        renderAnomalyHistogram,
        renderPrecisionTracker,
        renderAlertsByDomain,
        renderAlertsBySeverity,
        renderTimeline,
        getSeverityColor,
        formatNumber
    };
}
