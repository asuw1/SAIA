// SAIA Dashboard - Alerts Management Logic

function initializeAlertsManagement() {
    const bulkAck = document.getElementById('bulkAcknowledge');
    if (bulkAck) {
        bulkAck.addEventListener('click', function() {
            const checked = document.querySelectorAll('.alert-checkbox:checked');
            if (!checked.length) { alert('Please select at least one alert.'); return; }
            alert(`Successfully acknowledged ${checked.length} alert(s)`);
            checked.forEach(cb => cb.checked = false);
        });
    }
    const groupRelated = document.getElementById('groupRelated');
    if (groupRelated) {
        groupRelated.addEventListener('click', function() {
            const checked = document.querySelectorAll('.alert-checkbox:checked');
            if (checked.length < 2) { alert('Please select at least 2 alerts to group.'); return; }
            const caseId = 'CASE-' + Math.floor(Math.random() * 10000);
            alert(`Created ${caseId} with ${checked.length} alerts`);
            checked.forEach(cb => cb.checked = false);
        });
    }
    document.querySelectorAll('.alert-card').forEach(card => {
        const getId = () => card.querySelector('.alert-id-section h4').textContent;
        const ackBtn = card.querySelector('.btn-action.acknowledge');
        if (ackBtn) ackBtn.addEventListener('click', function() {
            const badge = card.querySelector('.status-badge');
            badge.textContent = 'Investigating'; badge.className = 'status-badge investigating';
            alert(`Alert ${getId()} acknowledged`);
        });
        const commentBtn = card.querySelector('.btn-action.comment');
        if (commentBtn) commentBtn.addEventListener('click', function() {
            const comment = prompt(`Add comment for ${getId()}:`);
            if (!comment?.trim()) return;
            let section = card.querySelector('.alert-comments');
            if (!section) { section = document.createElement('div'); section.className = 'alert-comments'; card.querySelector('.alert-body').appendChild(section); }
            const div = document.createElement('div'); div.className = 'comment';
            div.innerHTML = `<div class="comment-header"><strong>Current User</strong><span>Just now</span></div><p>${comment}</p>`;
            section.appendChild(div);
        });
        const resolveBtn = card.querySelector('.btn-action.resolve');
        if (resolveBtn) resolveBtn.addEventListener('click', function() {
            const notes = prompt(`Resolution notes for ${getId()}:`);
            if (!notes?.trim()) return;
            const badge = card.querySelector('.status-badge');
            badge.textContent = 'Resolved'; badge.className = 'status-badge resolved';
            card.style.opacity = '0.7'; card.style.borderLeftColor = '#00c853';
            alert(`Alert ${getId()} resolved`);
        });
        const evidenceBtn = card.querySelector('.btn-action.evidence');
        if (evidenceBtn) evidenceBtn.addEventListener('click', function() {
            setTimeout(() => {
                alert(`Evidence Pack Generated:\nID: EVD-${Math.floor(Math.random()*10000)}\nAlert: ${getId()}\nFormat: PDF`);
            }, 1000);
        });
    });
    const statusFilter   = document.querySelector('.toolbar-right select:first-child');
    const severityFilter = document.querySelector('.toolbar-right select:last-child');
    if (statusFilter)   statusFilter.addEventListener('change',   filterAlerts);
    if (severityFilter) severityFilter.addEventListener('change', filterAlerts);
}

function filterAlerts() {
    const statusFilter   = document.querySelector('.toolbar-right select:first-child');
    const severityFilter = document.querySelector('.toolbar-right select:last-child');
    const selStatus   = statusFilter   ? statusFilter.value.toLowerCase()   : 'all';
    const selSeverity = severityFilter ? severityFilter.value.toLowerCase() : 'all';
    document.querySelectorAll('.alert-card').forEach(card => {
        const status   = card.querySelector('.status-badge').textContent.toLowerCase().trim();
        const severity = card.querySelector('.severity-badge').textContent.toLowerCase().trim();
        card.style.display = (selStatus === 'all' || status === selStatus) && (selSeverity === 'all' || severity === selSeverity) ? 'block' : 'none';
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initializeAlertsManagement, filterAlerts };
}
