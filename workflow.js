// SAIA Dashboard - Workflow Diagram Rendering

function renderWorkflowDiagram() {
    const canvas = document.getElementById('workflowCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    
    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    canvas.style.width = canvas.offsetWidth + 'px';
    canvas.style.height = canvas.offsetHeight + 'px';
    ctx.scale(dpr, dpr);
    
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    
    // Determine which workflow to render based on page
    let workflowData;
    if (window.location.pathname.includes('reports')) {
        workflowData = workflowUseCase1;
    } else if (window.location.pathname.includes('rules')) {
        workflowData = workflowUseCase2;
    } else if (window.location.pathname.includes('alerts')) {
        workflowData = workflowUseCase3;
    } else {
        return;
    }
    
    // Clear canvas
    ctx.fillStyle = '#141b2d';
    ctx.fillRect(0, 0, width, height);
    
    // Draw edges first (so they appear behind nodes)
    ctx.strokeStyle = '#2196f3';
    ctx.lineWidth = 2;
    ctx.setLineDash([]);
    
    workflowData.edges.forEach(edge => {
        const fromNode = workflowData.nodes.find(n => n.id === edge.from);
        const toNode = workflowData.nodes.find(n => n.id === edge.to);
        
        if (fromNode && toNode) {
            ctx.beginPath();
            ctx.moveTo(fromNode.x, fromNode.y);
            ctx.lineTo(toNode.x, toNode.y);
            
            // Use dashed line for include/extend relationships
            if (edge.label && (edge.label.includes('include') || edge.label.includes('extend'))) {
                ctx.setLineDash([5, 5]);
                ctx.strokeStyle = '#d4af37';
            } else {
                ctx.setLineDash([]);
                ctx.strokeStyle = '#2196f3';
            }
            
            ctx.stroke();
            
            // Draw arrow head
            const angle = Math.atan2(toNode.y - fromNode.y, toNode.x - fromNode.x);
            const arrowLength = 10;
            ctx.beginPath();
            ctx.moveTo(toNode.x, toNode.y);
            ctx.lineTo(
                toNode.x - arrowLength * Math.cos(angle - Math.PI / 6),
                toNode.y - arrowLength * Math.sin(angle - Math.PI / 6)
            );
            ctx.moveTo(toNode.x, toNode.y);
            ctx.lineTo(
                toNode.x - arrowLength * Math.cos(angle + Math.PI / 6),
                toNode.y - arrowLength * Math.sin(angle + Math.PI / 6)
            );
            ctx.stroke();
            
            // Draw edge label if exists
            if (edge.label) {
                const midX = (fromNode.x + toNode.x) / 2;
                const midY = (fromNode.y + toNode.y) / 2;
                
                ctx.fillStyle = '#b0b3b8';
                ctx.font = '10px Segoe UI';
                ctx.textAlign = 'center';
                ctx.fillText(edge.label, midX, midY - 5);
            }
        }
    });
    
    // Reset line dash
    ctx.setLineDash([]);
    
    // Draw nodes
    workflowData.nodes.forEach(node => {
        const nodeWidth = 120;
        const nodeHeight = 60;
        const x = node.x - nodeWidth / 2;
        const y = node.y - nodeHeight / 2;
        
        // Draw node background
        ctx.fillStyle = '#1a2235';
        ctx.strokeStyle = '#2196f3';
        ctx.lineWidth = 2;
        
        // Rounded rectangle
        const radius = 10;
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + nodeWidth - radius, y);
        ctx.arcTo(x + nodeWidth, y, x + nodeWidth, y + radius, radius);
        ctx.lineTo(x + nodeWidth, y + nodeHeight - radius);
        ctx.arcTo(x + nodeWidth, y + nodeHeight, x + nodeWidth - radius, y + nodeHeight, radius);
        ctx.lineTo(x + radius, y + nodeHeight);
        ctx.arcTo(x, y + nodeHeight, x, y + nodeHeight - radius, radius);
        ctx.lineTo(x, y + radius);
        ctx.arcTo(x, y, x + radius, y, radius);
        ctx.closePath();
        
        ctx.fill();
        ctx.stroke();
        
        // Draw node label
        ctx.fillStyle = '#e4e6eb';
        ctx.font = 'bold 12px Segoe UI';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        // Handle multi-line labels
        const lines = node.label.split('\n');
        const lineHeight = 14;
        const startY = node.y - (lines.length - 1) * lineHeight / 2;
        
        lines.forEach((line, index) => {
            ctx.fillText(line, node.x, startY + index * lineHeight);
        });
    });
}

// Export function
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        renderWorkflowDiagram
    };
}