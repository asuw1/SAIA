// SAIA Dashboard - Chart Rendering Functions

function renderSeverityChart() {
    const canvas = document.getElementById('severityChart');
    if (!canvas) return;
    
    const container = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    
    const dpr = window.devicePixelRatio || 1;
    canvas.width = container.offsetWidth * dpr;
    canvas.height = container.offsetHeight * dpr;
    canvas.style.width = container.offsetWidth + 'px';
    canvas.style.height = container.offsetHeight + 'px';
    ctx.scale(dpr, dpr);
    
    const width = container.offsetWidth;
    const height = container.offsetHeight;
    
    const total = severityData.values.reduce((a, b) => a + b, 0);
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;
    
    let currentAngle = -Math.PI / 2;
    
    // Draw pie slices
    severityData.values.forEach((value, index) => {
        const sliceAngle = (value / total) * 2 * Math.PI;
        
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
        ctx.lineTo(centerX, centerY);
        ctx.fillStyle = severityData.colors[index];
        ctx.fill();
        
        ctx.strokeStyle = '#1a2235';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        currentAngle += sliceAngle;
    });
    
    // Reset angle for labels
    currentAngle = -Math.PI / 2;
    
    // Draw labels with connecting lines
    severityData.values.forEach((value, index) => {
        const sliceAngle = (value / total) * 2 * Math.PI;
        const labelAngle = currentAngle + sliceAngle / 2;
        const labelRadius = radius + 50;
        const labelX = centerX + Math.cos(labelAngle) * labelRadius;
        const labelY = centerY + Math.sin(labelAngle) * labelRadius;
        
        const lineStartX = centerX + Math.cos(labelAngle) * (radius + 5);
        const lineStartY = centerY + Math.sin(labelAngle) * (radius + 5);
        const lineEndX = centerX + Math.cos(labelAngle) * (radius + 40);
        const lineEndY = centerY + Math.sin(labelAngle) * (radius + 40);
        
        // Draw connecting line
        ctx.strokeStyle = severityData.colors[index];
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineStartY);
        ctx.lineTo(lineEndX, lineEndY);
        ctx.stroke();
        
        // Draw label text
        ctx.fillStyle = '#e4e6eb';
        ctx.font = 'bold 14px Segoe UI';
        ctx.textAlign = 'center';
        ctx.fillText(severityData.labels[index], labelX, labelY - 5);
        
        ctx.font = '12px Segoe UI';
        ctx.fillStyle = '#b0b3b8';
        ctx.fillText(`${value} alerts`, labelX, labelY + 10);
        
        currentAngle += sliceAngle;
    });
}

function renderConfusionMatrix() {
    const canvas = document.getElementById('confusionMatrix');
    if (!canvas) return;
    
    const container = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    
    const dpr = window.devicePixelRatio || 1;
    canvas.width = container.offsetWidth * dpr;
    canvas.height = container.offsetHeight * dpr;
    canvas.style.width = container.offsetWidth + 'px';
    canvas.style.height = container.offsetHeight + 'px';
    ctx.scale(dpr, dpr);
    
    const width = container.offsetWidth;
    const height = container.offsetHeight;
    
    const matrix = [
        [confusionMatrixData.truePositive, confusionMatrixData.falsePositive],
        [confusionMatrixData.falseNegative, confusionMatrixData.trueNegative]
    ];
    
    const maxValue = Math.max(...matrix.flat());
    const padding = 70;
    const matrixSize = Math.min(width - padding * 2, height - padding * 1.8);
    const cellSize = matrixSize / 2;
    const startX = (width - cellSize * 2) / 2;
    const startY = (height - cellSize * 2) / 2 + 10;
    
    const colors = [
        ['#00c853', '#f44336'],
        ['#ff9800', '#4caf50']
    ];
    
    // Draw matrix cells
    for (let row = 0; row < 2; row++) {
        for (let col = 0; col < 2; col++) {
            const x = startX + col * cellSize;
            const y = startY + row * cellSize;
            const value = matrix[row][col];
            const intensity = value / maxValue;
            
            const color = colors[row][col];
            ctx.fillStyle = color + Math.round(intensity * 255).toString(16).padStart(2, '0');
            ctx.fillRect(x, y, cellSize - 4, cellSize - 4);
            
            ctx.strokeStyle = '#2d3748';
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, cellSize - 4, cellSize - 4);
            
            // Draw value
            ctx.fillStyle = '#e4e6eb';
            ctx.font = 'bold 36px Segoe UI';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(value, x + cellSize / 2 - 2, y + cellSize / 2 - 10);
            
            // Draw label
            ctx.font = '11px Segoe UI';
            ctx.fillStyle = '#b0b3b8';
            const labels = [
                ['True Positive', 'False Positive'],
                ['False Negative', 'True Negative']
            ];
            ctx.fillText(labels[row][col], x + cellSize / 2 - 2, y + cellSize / 2 + 20);
        }
    }
    
    // Draw axis labels
    ctx.fillStyle = '#e4e6eb';
    ctx.font = 'bold 13px Segoe UI';
    ctx.textAlign = 'center';
    ctx.fillText('PREDICTED', width / 2, startY - 35);
    
    ctx.save();
    ctx.translate(startX - 45, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('ACTUAL', 0, 0);
    ctx.restore();
    
    // Draw category labels
    ctx.font = '12px Segoe UI';
    ctx.fillStyle = '#b0b3b8';
    ctx.fillText('Threat', startX + cellSize / 2 - 2, startY - 15);
    ctx.fillText('No Threat', startX + cellSize * 1.5 - 2, startY - 15);
    
    ctx.save();
    ctx.translate(startX - 25, startY + cellSize / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Threat', 0, 0);
    ctx.restore();
    
    ctx.save();
    ctx.translate(startX - 25, startY + cellSize * 1.5);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('No Threat', 0, 0);
    ctx.restore();
    
    // Calculate and display metrics
    const total = matrix.flat().reduce((a, b) => a + b, 0);
    const accuracy = ((matrix[0][0] + matrix[1][1]) / total * 100).toFixed(1);
    const precision = (matrix[0][0] / (matrix[0][0] + matrix[0][1]) * 100).toFixed(1);
    const recall = (matrix[0][0] / (matrix[0][0] + matrix[1][0]) * 100).toFixed(1);
    
    ctx.font = '11px Segoe UI';
    ctx.fillStyle = '#b0b3b8';
    ctx.textAlign = 'left';
    const metricsY = startY + cellSize * 2 + 20;
    ctx.fillText(`Accuracy: ${accuracy}%  |  Precision: ${precision}%  |  Recall: ${recall}%`, startX, metricsY);
}

function renderCharts() {
    renderSeverityChart();
    renderConfusionMatrix();
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        renderSeverityChart,
        renderConfusionMatrix,
        renderCharts
    };
}