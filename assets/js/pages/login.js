// SAIA Login Page - Authentication Logic

// Demo users for testing
const DEMO_USERS = [
    { username: 'admin', password: 'admin123', role: 'Administrator', name: 'Admin User' },
    { username: 'auditor', password: 'audit123', role: 'Auditor', name: 'Audit User' },
    { username: 'compliance', password: 'comp123', role: 'Compliance Officer', name: 'Compliance Officer' },
    { username: 'demo', password: 'demo', role: 'Demo User', name: 'Demo User' }
];

// Toggle password visibility
document.getElementById('togglePassword')?.addEventListener('click', function() {
    const passwordInput = document.getElementById('password');
    const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
    passwordInput.setAttribute('type', type);

    // Toggle icon
    this.querySelector('svg').innerHTML = type === 'password'
        ? '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>'
        : '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
});

// Show message function
function showMessage(message, type = 'error') {
    const existingMessage = document.querySelector('.login-message');
    if (existingMessage) {
        existingMessage.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `login-message ${type}`;
    messageDiv.textContent = message;

    const form = document.getElementById('loginForm');
    form.insertBefore(messageDiv, form.firstChild);

    // Auto-hide after 5 seconds
    setTimeout(() => {
        messageDiv.style.opacity = '0';
        setTimeout(() => messageDiv.remove(), 300);
    }, 5000);
}

// Handle form submission
document.getElementById('loginForm')?.addEventListener('submit', function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const rememberMe = document.getElementById('rememberMe').checked;

    // Validate inputs
    if (!username || !password) {
        showMessage('Please enter both username and password', 'error');
        return;
    }

    // Check credentials against demo users
    const user = DEMO_USERS.find(u =>
        u.username.toLowerCase() === username.toLowerCase() && u.password === password
    );

    if (user) {
        // Successful login
        showMessage('Login successful! Redirecting...', 'success');

        // Store user session
        const userData = {
            username: user.username,
            role: user.role,
            name: user.name,
            loginTime: new Date().toISOString()
        };

        if (rememberMe) {
            localStorage.setItem('saia_user', JSON.stringify(userData));
            localStorage.setItem('saia_remember', 'true');
        } else {
            sessionStorage.setItem('saia_user', JSON.stringify(userData));
        }

        // Simulate loading and redirect
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1500);
    } else {
        // Failed login
        showMessage('Invalid username or password. Please try again.', 'error');

        // Clear password field
        document.getElementById('password').value = '';
        document.getElementById('password').focus();
    }
});

// Auto-fill demo credentials hint
window.addEventListener('DOMContentLoaded', function() {
    // Check if user is already logged in
    const storedUser = localStorage.getItem('saia_user') || sessionStorage.getItem('saia_user');
    if (storedUser) {
        // Redirect to dashboard if already logged in
        window.location.href = 'index.html';
        return;
    }

    // Add demo credentials hint
    const loginCard = document.querySelector('.login-card');
    const demoHint = document.createElement('div');
    demoHint.style.cssText = `
        margin-top: 1.5rem;
        padding: 1rem;
        background: rgba(33, 150, 243, 0.1);
        border: 1px solid var(--accent-blue);
        border-radius: 8px;
        font-size: 0.85rem;
        color: var(--text-secondary);
    `;
    demoHint.innerHTML = `
        <strong style="color: var(--accent-blue); display: block; margin-bottom: 0.5rem;">Demo Credentials:</strong>
        <div style="display: grid; gap: 0.25rem;">
            <div><strong>Admin:</strong> admin / admin123</div>
            <div><strong>Auditor:</strong> auditor / audit123</div>
            <div><strong>Compliance:</strong> compliance / comp123</div>
            <div><strong>Demo:</strong> demo / demo</div>
        </div>
    `;
    loginCard.appendChild(demoHint);
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Alt + D to auto-fill demo credentials
    if (e.altKey && e.key === 'd') {
        e.preventDefault();
        document.getElementById('username').value = 'demo';
        document.getElementById('password').value = 'demo';
        showMessage('Demo credentials filled. Press Enter to login.', 'success');
    }
});

// Input field animations
document.querySelectorAll('.form-control').forEach(input => {
    input.addEventListener('focus', function() {
        this.parentElement.style.borderColor = 'var(--accent-blue)';
    });

    input.addEventListener('blur', function() {
        this.parentElement.style.borderColor = 'var(--border-color)';
    });
});
