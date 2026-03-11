// SAIA Dashboard - Chart Rendering Functions

function renderSeverityChart() {
    const canvas = document.getElementById('severityChart');
    if (!canvas) return;
    const container = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = container.offsetWidth * dpr;
    canvas.height = container.offsetHeight * dpr;
    canvas.style.width  = container.offsetWidth + 'px';
    canvas.style.height = container.offsetHeight + 'px';
    ctx.scale(dpr, dpr);
    const width = container.offsetWidth, height = container.offsetHeight;
    const total = severityData.values.reduce((a, b) => a + b, 0);
    const centerX = width / 2, centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;
    let angle = -Math.PI / 2;
    severityData.values.forEach((value, i) => {
        const slice = (value / total) * 2 * Math.PI;
        ctx.beginPath(); ctx.arc(centerX, centerY, radius, angle, angle + slice);
        ctx.lineTo(centerX, centerY); ctx.fillStyle = severityData.colors[i]; ctx.fill();
        ctx.strokeStyle = '#1a2235'; ctx.lineWidth = 2; ctx.stroke();
        angle += slice;
    });
    angle = -Math.PI / 2;
    severityData.values.forEach((value, i) => {
        const slice = (value / total) * 2 * Math.PI;
        const la = angle + slice / 2;
        const lx = centerX + Math.cos(la) * (radius + 50);
        const ly = centerY + Math.sin(la) * (radius + 50);
        ctx.strokeStyle = severityData.colors[i]; ctx.lineWidth = 2; ctx.beginPath();
        ctx.moveTo(centerX + Math.cos(la) * (radius + 5), centerY + Math.sin(la) * (radius + 5));
        ctx.lineTo(centerX + Math.cos(la) * (radius + 40), centerY + Math.sin(la) * (radius + 40));
        ctx.stroke();
        ctx.fillStyle = '#e4e6eb'; ctx.font = 'bold 14px Segoe UI'; ctx.textAlign = 'center';
        ctx.fillText(severityData.labels[i], lx, ly - 5);
        ctx.font = '12px Segoe UI'; ctx.fillStyle = '#b0b3b8';
        ctx.fillText(`${value} alerts`, lx, ly + 10);
        angle += slice;
    });
}

function renderConfusionMatrix() {
    const canvas = document.getElementById('confusionMatrix');
    if (!canvas) return;
    const container = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = container.offsetWidth * dpr;
    canvas.height = container.offsetHeight * dpr;
    canvas.style.width  = container.offsetWidth + 'px';
    canvas.style.height = container.offsetHeight + 'px';
    ctx.scale(dpr, dpr);
    const width = container.offsetWidth, height = container.offsetHeight;
    const matrix = [[confusionMatrixData.truePositive, confusionMatrixData.falsePositive],
                    [confusionMatrixData.falseNegative, confusionMatrixData.trueNegative]];
    const maxVal = Math.max(...matrix.flat());
    const cellSize = Math.min(width - 140, height - 126) / 2;
    const startX = (width - cellSize * 2) / 2, startY = (height - cellSize * 2) / 2 + 10;
    const colors = [['#00c853','#f44336'],['#ff9800','#4caf50']];
    const lbls   = [['True Positive','False Positive'],['False Negative','True Negative']];
    for (let r = 0; r < 2; r++) for (let c = 0; c < 2; c++) {
        const x = startX + c * cellSize, y = startY + r * cellSize;
        ctx.fillStyle = colors[r][c] + Math.round(matrix[r][c] / maxVal * 255).toString(16).padStart(2,'0');
        ctx.fillRect(x, y, cellSize - 4, cellSize - 4);
        ctx.strokeStyle = '#2d3748'; ctx.lineWidth = 2; ctx.strokeRect(x, y, cellSize - 4, cellSize - 4);
        ctx.fillStyle = '#e4e6eb'; ctx.font = 'bold 36px Segoe UI'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(matrix[r][c], x + cellSize/2 - 2, y + cellSize/2 - 10);
        ctx.font = '11px Segoe UI'; ctx.fillStyle = '#b0b3b8';
        ctx.fillText(lbls[r][c], x + cellSize/2 - 2, y + cellSize/2 + 20);
    }
    ctx.fillStyle = '#e4e6eb'; ctx.font = 'bold 13px Segoe UI'; ctx.textAlign = 'center';
    ctx.fillText('PREDICTED', width/2, startY - 35);
    ctx.save(); ctx.translate(startX - 45, height/2); ctx.rotate(-Math.PI/2); ctx.fillText('ACTUAL', 0, 0); ctx.restore();
    ctx.font = '12px Segoe UI'; ctx.fillStyle = '#b0b3b8';
    ctx.fillText('Threat', startX + cellSize/2 - 2, startY - 15);
    ctx.fillText('No Threat', startX + cellSize*1.5 - 2, startY - 15);
    ctx.save(); ctx.translate(startX-25, startY+cellSize/2);  ctx.rotate(-Math.PI/2); ctx.fillText('Threat',    0, 0); ctx.restore();
    ctx.save(); ctx.translate(startX-25, startY+cellSize*1.5); ctx.rotate(-Math.PI/2); ctx.fillText('No Threat',0, 0); ctx.restore();
    const total = matrix.flat().reduce((a,b)=>a+b,0);
    const acc = ((matrix[0][0]+matrix[1][1])/total*100).toFixed(1);
    const prec = (matrix[0][0]/(matrix[0][0]+matrix[0][1])*100).toFixed(1);
    const rec  = (matrix[0][0]/(matrix[0][0]+matrix[1][0])*100).toFixed(1);
    ctx.font='11px Segoe UI'; ctx.fillStyle='#b0b3b8'; ctx.textAlign='left';
    ctx.fillText(`Accuracy: ${acc}%  |  Precision: ${prec}%  |  Recall: ${rec}%`, startX, startY+cellSize*2+20);
}

function renderCharts() { renderSeverityChart(); renderConfusionMatrix(); }

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderSeverityChart, renderConfusionMatrix, renderCharts };
}
