// SAIA Dashboard - Rules Management Logic

function initializeRulesManagement() {
    const ruleForm = document.getElementById('ruleForm');
    const validateBtn = document.getElementById('validateBtn');
    const validationResult = document.getElementById('validationResult');
    
    if (!ruleForm) return;
    
    // Validate button handler
    if (validateBtn) {
        validateBtn.addEventListener('click', function() {
            const ruleLogic = document.getElementById('ruleLogic').value;
            
            try {
                // Attempt to parse JSON
                JSON.parse(ruleLogic);
                
                validationResult.className = 'validation-result success';
                validationResult.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline; margin-right: 8px;">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    Rule syntax is valid! You can now publish this rule.
                `;
            } catch (error) {
                validationResult.className = 'validation-result error';
                validationResult.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline; margin-right: 8px;">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="15" y1="9" x2="9" y2="15"></line>
                        <line x1="9" y1="9" x2="15" y2="15"></line>
                    </svg>
                    Syntax Error: ${error.message}
                `;
            }
        });
    }
    
    // Form submission handler
    ruleForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = {
            name: document.getElementById('ruleName').value,
            framework: document.getElementById('ruleFramework').value,
            clause: document.getElementById('clauseRef').value,
            severity: document.getElementById('severity').value,
            description: document.getElementById('ruleDescription').value,
            logic: document.getElementById('ruleLogic').value
        };
        
        try {
            // Validate JSON logic
            JSON.parse(formData.logic);
            
            // Simulate rule creation
            console.log('Creating rule:', formData);
            
            // Show success message
            validationResult.className = 'validation-result success';
            validationResult.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline; margin-right: 8px;">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Rule "${formData.name}" has been successfully published! (Version 1.0)
            `;
            
            // Reset form after 2 seconds
            setTimeout(() => {
                ruleForm.reset();
                validationResult.style.display = 'none';
            }, 2000);
            
        } catch (error) {
            validationResult.className = 'validation-result error';
            validationResult.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline; margin-right: 8px;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
                Cannot publish: Invalid JSON syntax in rule logic
            `;
        }
    });
    
    // Rule item action handlers
    document.querySelectorAll('.rule-item').forEach(item => {
        const editBtn = item.querySelector('.btn-icon[title="Edit"]');
        const testBtn = item.querySelector('.btn-icon[title="Test"]');
        const historyBtn = item.querySelector('.btn-icon[title="History"]');
        
        if (editBtn) {
            editBtn.addEventListener('click', function() {
                const ruleName = item.querySelector('h4').textContent;
                console.log('Editing rule:', ruleName);
                alert(`Opening editor for: ${ruleName}`);
            });
        }
        
        if (testBtn) {
            testBtn.addEventListener('click', function() {
                const ruleName = item.querySelector('h4').textContent;
                console.log('Testing rule:', ruleName);
                alert(`Running tests for: ${ruleName}\n\nTest Results:\n✓ Pass: 15/15 test cases\n✓ No false positives detected\n✓ Performance: < 50ms`);
            });
        }
        
        if (historyBtn) {
            historyBtn.addEventListener('click', function() {
                const ruleName = item.querySelector('h4').textContent;
                console.log('Viewing history for rule:', ruleName);
                alert(`Version History for: ${ruleName}\n\nv2.1 - 2024-10-15 (Current)\nv2.0 - 2024-09-20\nv1.3 - 2024-08-10\nv1.0 - 2024-06-01`);
            });
        }
    });
}

// Export function
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeRulesManagement
    };
}