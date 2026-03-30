// SAIA Dashboard - Rules Management Logic

function initializeRulesManagement() {
    const ruleForm  = document.getElementById('ruleForm');
    const validateBtn = document.getElementById('validateBtn');
    const result    = document.getElementById('validationResult');
    if (!ruleForm) return;

    if (validateBtn) {
        validateBtn.addEventListener('click', function() {
            try {
                JSON.parse(document.getElementById('ruleLogic').value);
                result.className = 'validation-result success';
                result.innerHTML = '✓ Rule syntax is valid! You can now publish this rule.';
            } catch (e) {
                result.className = 'validation-result error';
                result.innerHTML = `✗ Syntax Error: ${e.message}`;
            }
        });
    }

    ruleForm.addEventListener('submit', function(e) {
        e.preventDefault();
        try {
            JSON.parse(document.getElementById('ruleLogic').value);
            const name = document.getElementById('ruleName').value;
            result.className = 'validation-result success';
            result.innerHTML = `✓ Rule "${name}" published successfully! (Version 1.0)`;
            setTimeout(() => { ruleForm.reset(); result.style.display = 'none'; }, 2000);
        } catch (e) {
            result.className = 'validation-result error';
            result.innerHTML = '✗ Cannot publish: Invalid JSON in rule logic';
        }
    });

    document.querySelectorAll('.rule-item').forEach(item => {
        const name = item.querySelector('h4').textContent;
        item.querySelector('.btn-icon[title="Edit"]')?.addEventListener('click',    () => alert(`Opening editor for: ${name}`));
        item.querySelector('.btn-icon[title="Test"]')?.addEventListener('click',    () => alert(`Test results for: ${name}\n\n✓ 15/15 pass\n✓ No false positives\n✓ < 50ms`));
        item.querySelector('.btn-icon[title="History"]')?.addEventListener('click', () => alert(`Version History for: ${name}\n\nv2.1 - 2024-10-15 (Current)\nv2.0 - 2024-09-20\nv1.0 - 2024-06-01`));
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initializeRulesManagement };
}
