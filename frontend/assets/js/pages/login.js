// SAIA Login Page - Authentication Logic

const DEMO_USERS = [
    { username: 'admin',      password: 'admin123', role: 'Administrator',      name: 'Admin User' },
    { username: 'auditor',    password: 'audit123', role: 'Auditor',            name: 'Audit User' },
    { username: 'compliance', password: 'comp123',  role: 'Compliance Officer', name: 'Compliance Officer' },
    { username: 'demo',       password: 'demo',     role: 'Demo User',          name: 'Demo User' }
];

document.getElementById('togglePassword')?.addEventListener('click', function() {
    const input = document.getElementById('password');
    const type  = input.getAttribute('type') === 'password' ? 'text' : 'password';
    input.setAttribute('type', type);
});

function showMessage(message, type = 'error') {
    document.querySelector('.login-message')?.remove();
    const div = document.createElement('div');
    div.className = `login-message ${type}`;
    div.textContent = message;
    const form = document.getElementById('loginForm');
    form.insertBefore(div, form.firstChild);
    setTimeout(() => { div.style.opacity = '0'; setTimeout(() => div.remove(), 300); }, 5000);
}

document.getElementById('loginForm')?.addEventListener('submit', function(e) {
    e.preventDefault();
    const username   = document.getElementById('username').value.trim();
    const password   = document.getElementById('password').value;
    const rememberMe = document.getElementById('rememberMe').checked;
    if (!username || !password) { showMessage('Please enter both username and password'); return; }
    const user = DEMO_USERS.find(u => u.username.toLowerCase() === username.toLowerCase() && u.password === password);
    if (user) {
        showMessage('Login successful! Redirecting...', 'success');
        const data = { username: user.username, role: user.role, name: user.name, loginTime: new Date().toISOString() };
        if (rememberMe) localStorage.setItem('saia_user', JSON.stringify(data));
        else sessionStorage.setItem('saia_user', JSON.stringify(data));
        setTimeout(() => window.location.href = 'index.html', 1500);
    } else {
        showMessage('Invalid username or password.');
        document.getElementById('password').value = '';
        document.getElementById('password').focus();
    }
});

window.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('saia_user') || sessionStorage.getItem('saia_user')) {
        window.location.href = 'index.html'; return;
    }
    const hint = document.createElement('div');
    hint.style.cssText = 'margin-top:1.5rem;padding:1rem;background:rgba(33,150,243,0.1);border:1px solid var(--accent-blue);border-radius:8px;font-size:0.85rem;color:var(--text-secondary);';
    hint.innerHTML = '<strong style="color:var(--accent-blue);display:block;margin-bottom:0.5rem;">Demo Credentials:</strong><div style="display:grid;gap:0.25rem;"><div><strong>Admin:</strong> admin / admin123</div><div><strong>Auditor:</strong> auditor / audit123</div><div><strong>Compliance:</strong> compliance / comp123</div><div><strong>Demo:</strong> demo / demo</div></div>';
    document.querySelector('.login-card').appendChild(hint);
});

document.addEventListener('keydown', function(e) {
    if (e.altKey && e.key === 'd') {
        e.preventDefault();
        document.getElementById('username').value = 'demo';
        document.getElementById('password').value = 'demo';
        showMessage('Demo credentials filled. Press Enter to login.', 'success');
    }
});
