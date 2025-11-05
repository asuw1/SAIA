// SAIA Dashboard - Alerts Management Logic

function initializeAlertsManagement() {
    // Bulk acknowledge button
    const bulkAcknowledge = document.getElementById('bulkAcknowledge');
    if (bulkAcknowledge) {
        bulkAcknowledge.addEventListener('click', function() {
            const checkedAlerts = document.querySelectorAll('.alert-checkbox:checked');
            if (checkedAlerts.length === 0) {
                alert('Please select at least one alert to acknowledge.');
                return;
            }
            
            console.log(`Acknowledging ${checkedAlerts.length} alerts`);
            alert(`Successfully acknowledged ${checkedAlerts.length} alert(s)`);
            
            // Uncheck all checkboxes
            checkedAlerts.forEach(checkbox => checkbox.checked = false);
        });
    }
    
    // Group related button
    const groupRelated = document.getElementById('groupRelated');
    if (groupRelated) {
        groupRelated.addEventListener('click', function() {
            const checkedAlerts = document.querySelectorAll('.alert-checkbox:checked');
            if (checkedAlerts.length < 2) {
                alert('Please select at least 2 alerts to group into a case.');
                return;
            }
            
            const caseId = 'CASE-' + Math.floor(Math.random() * 10000);
            console.log(`Creating case ${caseId} with ${checkedAlerts.length} alerts`);
            alert(`Successfully created ${caseId} with ${checkedAlerts.length} related alerts`);
            
            // Uncheck all checkboxes
            checkedAlerts.forEach(checkbox => checkbox.checked = false);
        });
    }
    
    // Alert action handlers
    document.querySelectorAll('.alert-card').forEach(card => {
        // Acknowledge button
        const acknowledgeBtn = card.querySelector('.btn-action.acknowledge');
        if (acknowledgeBtn) {
            acknowledgeBtn.addEventListener('click', function() {
                const alertId = card.querySelector('.alert-id-section h4').textContent;
                console.log('Acknowledging alert:', alertId);
                
                const statusBadge = card.querySelector('.status-badge');
                statusBadge.textContent = 'Investigating';
                statusBadge.className = 'status-badge investigating';
                
                alert(`Alert ${alertId} has been acknowledged and marked as "Investigating"`);
            });
        }
        
        // Comment button
        const commentBtn = card.querySelector('.btn-action.comment');
        if (commentBtn) {
            commentBtn.addEventListener('click', function() {
                const alertId = card.querySelector('.alert-id-section h4').textContent;
                const comment = prompt(`Add comment for ${alertId}:`);
                
                if (comment && comment.trim()) {
                    console.log('Adding comment to alert:', alertId, comment);
                    
                    // Create comment element
                    let commentsSection = card.querySelector('.alert-comments');
                    if (!commentsSection) {
                        commentsSection = document.createElement('div');
                        commentsSection.className = 'alert-comments';
                        card.querySelector('.alert-body').appendChild(commentsSection);
                    }
                    
                    const commentDiv = document.createElement('div');
                    commentDiv.className = 'comment';
                    commentDiv.innerHTML = `
                        <div class="comment-header">
                            <strong>Current User</strong>
                            <span>Just now</span>
                        </div>
                        <p>${comment}</p>
                    `;
                    
                    commentsSection.appendChild(commentDiv);
                }
            });
        }
        
        // Resolve button
        const resolveBtn = card.querySelector('.btn-action.resolve');
        if (resolveBtn) {
            resolveBtn.addEventListener('click', function() {
                const alertId = card.querySelector('.alert-id-section h4').textContent;
                const resolution = prompt(`Resolution notes for ${alertId}:`);
                
                if (resolution && resolution.trim()) {
                    console.log('Resolving alert:', alertId, resolution);
                    
                    const statusBadge = card.querySelector('.status-badge');
                    statusBadge.textContent = 'Resolved';
                    statusBadge.className = 'status-badge resolved';
                    
                    // Change card styling
                    card.style.opacity = '0.7';
                    card.style.borderLeftColor = '#00c853';
                    
                    alert(`Alert ${alertId} has been resolved successfully`);
                }
            });
        }
        
        // Evidence button
        const evidenceBtn = card.querySelector('.btn-action.evidence');
        if (evidenceBtn) {
            evidenceBtn.addEventListener('click', function() {
                const alertId = card.querySelector('.alert-id-section h4').textContent;
                console.log('Generating evidence pack for:', alertId);
                
                // Simulate evidence generation
                setTimeout(() => {
                    const evidenceId = 'EVD-' + Math.floor(Math.random() * 10000);
                    alert(`Evidence Pack Generated:\n\nID: ${evidenceId}\nAlert: ${alertId}\nTimestamp: ${new Date().toLocaleString()}\nFormat: PDF\n\nDownload ready!`);
                }, 1000);
            });
        }
    });
    
    // Filter handlers
    const statusFilter = document.querySelector('.toolbar-right select:first-child');
    const severityFilter = document.querySelector('.toolbar-right select:last-child');
    
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            console.log('Filtering by status:', this.value);
            filterAlerts();
        });
    }
    
    if (severityFilter) {
        severityFilter.addEventListener('change', function() {
            console.log('Filtering by severity:', this.value);
            filterAlerts();
        });
    }
}

function filterAlerts() {
    const statusFilter = document.querySelector('.toolbar-right select:first-child');
    const severityFilter = document.querySelector('.toolbar-right select:last-child');
    
    const selectedStatus = statusFilter ? statusFilter.value : 'all';
    const selectedSeverity = severityFilter ? severityFilter.value : 'all';
    
    document.querySelectorAll('.alert-card').forEach(card => {
        const cardStatus = card.querySelector('.status-badge').textContent.toLowerCase().trim();
        const cardSeverity = card.querySelector('.severity-badge').textContent.toLowerCase().trim();
        
        const statusMatch = selectedStatus === 'all' || cardStatus === selectedStatus.toLowerCase();
        const severityMatch = selectedSeverity === 'all' || cardSeverity === selectedSeverity.toLowerCase();
        
        if (statusMatch && severityMatch) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// Export function
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeAlertsManagement,
        filterAlerts
    };
}