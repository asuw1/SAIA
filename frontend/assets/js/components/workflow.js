// SAIA Dashboard - Workflow Diagram Rendering

function renderWorkflowDiagram() {
    const canvas = document.getElementById('workflowCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    canvas.style.width  = canvas.offsetWidth + 'px';
    canvas.style.height = canvas.offsetHeight + 'px';
    ctx.scale(dpr, dpr);
    const width = canvas.offsetWidth, height = canvas.offsetHeight;
    let workflowData;
    const path = window.location.pathname;
    if (path.includes('reports'))    workflowData = workflowUseCase1;
    else if (path.includes('rules')) workflowData = workflowUseCase2;
    else if (path.includes('alerts'))workflowData = workflowUseCase3;
    else return;
    ctx.fillStyle = '#141b2d'; ctx.fillRect(0, 0, width, height);
    workflowData.edges.forEach(edge => {
        const from = workflowData.nodes.find(n => n.id === edge.from);
        const to   = workflowData.nodes.find(n => n.id === edge.to);
        if (!from || !to) return;
        if (edge.label && (edge.label.includes('include') || edge.label.includes('extend'))) {
            ctx.setLineDash([5,5]); ctx.strokeStyle = '#d4af37';
        } else { ctx.setLineDash([]); ctx.strokeStyle = '#2196f3'; }
        ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(to.x, to.y); ctx.stroke();
        const angle = Math.atan2(to.y - from.y, to.x - from.x);
        ctx.beginPath();
        ctx.moveTo(to.x, to.y);
        ctx.lineTo(to.x - 10 * Math.cos(angle - Math.PI/6), to.y - 10 * Math.sin(angle - Math.PI/6));
        ctx.moveTo(to.x, to.y);
        ctx.lineTo(to.x - 10 * Math.cos(angle + Math.PI/6), to.y - 10 * Math.sin(angle + Math.PI/6));
        ctx.stroke();
        if (edge.label) {
            ctx.fillStyle = '#b0b3b8'; ctx.font = '10px Segoe UI'; ctx.textAlign = 'center';
            ctx.fillText(edge.label, (from.x + to.x)/2, (from.y + to.y)/2 - 5);
        }
    });
    ctx.setLineDash([]);
    workflowData.nodes.forEach(node => {
        const nw = 120, nh = 60, r = 10;
        const x = node.x - nw/2, y = node.y - nh/2;
        ctx.fillStyle = '#1a2235'; ctx.strokeStyle = '#2196f3'; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x+r,y); ctx.lineTo(x+nw-r,y); ctx.arcTo(x+nw,y,x+nw,y+r,r);
        ctx.lineTo(x+nw,y+nh-r); ctx.arcTo(x+nw,y+nh,x+nw-r,y+nh,r);
        ctx.lineTo(x+r,y+nh); ctx.arcTo(x,y+nh,x,y+nh-r,r);
        ctx.lineTo(x,y+r); ctx.arcTo(x,y,x+r,y,r); ctx.closePath();
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#e4e6eb'; ctx.font = 'bold 12px Segoe UI'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const lines = node.label.split('\n');
        const lh = 14, sy = node.y - (lines.length - 1) * lh / 2;
        lines.forEach((line, i) => ctx.fillText(line, node.x, sy + i * lh));
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderWorkflowDiagram };
}
