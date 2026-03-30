/**
 * SAIA V4 — Shared Navigation & App Shell
 * Handles: auth guard, user info, active nav, theme toggle, mobile sidebar
 */

(function () {
  'use strict';

  // ── Auth helpers ──────────────────────────────────────────────────────────
  function getCurrentUser() {
    try {
      return JSON.parse(sessionStorage.getItem('saia_user') || localStorage.getItem('saia_user') || 'null');
    } catch { return null; }
  }

  function isAuthenticated() {
    return !!(sessionStorage.getItem('saia_token') || localStorage.getItem('saia_token') || getCurrentUser());
  }

  function logout() {
    if (confirm('Are you sure you want to logout?')) {
      sessionStorage.clear();
      localStorage.removeItem('saia_user');
      localStorage.removeItem('saia_token');
      // Resolve login path from wherever we are
      const depth = window.location.pathname.split('/').filter(Boolean).length;
      const prefix = window.location.pathname.includes('/pages/') ? '../' : '';
      window.location.href = prefix + 'login.html';
    }
  }

  // ── Theme ─────────────────────────────────────────────────────────────────
  function getTheme() {
    return localStorage.getItem('saia_theme') || 'light';
  }
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('saia_theme', theme);
  }
  function toggleTheme() {
    applyTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }
  // Apply immediately to avoid flash
  applyTheme(getTheme());

  // ── Nav structure ─────────────────────────────────────────────────────────
  // Determine prefix based on whether we're in /pages/ sub-dir
  function getPrefix() {
    return window.location.pathname.includes('/pages/') ? '../' : '';
  }

  const NAV_ITEMS = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      href: 'index.html',
      match: ['index.html', '/'],
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`
    },
    {
      id: 'alerts',
      label: 'Alerts',
      href: 'pages/alerts.html',
      match: ['alerts.html'],
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
    },
    {
      id: 'rules',
      label: 'Detection Rules',
      href: 'pages/rules.html',
      match: ['rules.html'],
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M8.46 8.46a5 5 0 0 0 0 7.07"/></svg>`
    },
    {
      id: 'cases',
      label: 'Cases',
      href: 'pages/cases.html',
      match: ['cases.html'],
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 3h-2a2 2 0 0 0-2 2v2H8V5a2 2 0 0 0-2-2H4"/></svg>`
    },
    {
      id: 'reports',
      label: 'Reports',
      href: 'pages/reports.html',
      match: ['reports.html'],
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>`
    },
    {
      id: 'chat',
      label: 'AI Assistant',
      href: 'pages/chat.html',
      match: ['chat.html'],
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`
    },
    {
      id: 'admin',
      label: 'Admin',
      href: 'pages/admin.html',
      match: ['admin.html'],
      adminOnly: true,
      icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`
    },
  ];

  // ── Build sidebar nav ─────────────────────────────────────────────────────
  function buildNav(user) {
    const prefix = getPrefix();
    const currentPath = window.location.pathname;

    const navEl = document.querySelector('.sidebar-nav');
    if (!navEl) return;

    navEl.innerHTML = NAV_ITEMS.map(item => {
      // Hide admin link for non-admins
      if (item.adminOnly && user?.role !== 'Administrator') return '';

      // Determine active state
      const isActive = item.match.some(m => currentPath.endsWith(m) || currentPath.endsWith(m.replace('pages/', '')));

      // Build correct href
      let href;
      if (item.id === 'dashboard') {
        href = prefix + 'index.html';
      } else {
        // If we're at root, use pages/xxx.html; if in /pages/, just xxx.html
        if (prefix === '') {
          href = item.href; // already has 'pages/'
        } else {
          href = item.href.replace('pages/', ''); // strip prefix, we're already in /pages/
        }
      }

      return `<a href="${href}" class="nav-item ${isActive ? 'active' : ''}">
        ${item.icon}
        <span>${item.label}</span>
      </a>`;
    }).join('');
  }

  // ── Build topbar ──────────────────────────────────────────────────────────
  function buildTopbar(user) {
    // User info
    const roleEl = document.querySelector('.user-role');
    const nameEl = document.querySelector('.user-name');
    const avatarEl = document.querySelector('.user-avatar');

    if (user) {
      const displayName = user.name || user.username || 'User';
      const initials = displayName.split(' ').map(n => n[0]).join('').toUpperCase().substr(0, 2);
      if (roleEl)   roleEl.textContent  = user.role || 'User';
      if (nameEl)   nameEl.textContent  = displayName;
      if (avatarEl) avatarEl.textContent = initials;
    }

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', logout);

    // Theme toggle in topbar
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', toggleTheme);
    }

    // Mobile menu toggle
    const menuBtn = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    if (menuBtn && sidebar) {
      menuBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
      // Close sidebar on outside click
      document.addEventListener('click', e => {
        if (!sidebar.contains(e.target) && !menuBtn.contains(e.target)) {
          sidebar.classList.remove('open');
        }
      });
    }
  }

  // ── Inject theme toggle button into topbar ─────────────────────────────────
  function injectThemeToggle() {
    const navRight = document.querySelector('.nav-right');
    if (!navRight || document.getElementById('themeToggle')) return;

    const btn = document.createElement('button');
    btn.id = 'themeToggle';
    btn.className = 'theme-toggle';
    btn.title = 'Toggle dark mode';
    btn.innerHTML = `
      <svg class="icon-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/>
        <line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/>
        <line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </svg>
      <svg class="icon-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>`;
    btn.addEventListener('click', toggleTheme);

    // Insert before notification button
    const notifBtn = navRight.querySelector('.notification-btn');
    if (notifBtn) {
      navRight.insertBefore(btn, notifBtn);
    } else {
      navRight.prepend(btn);
    }
  }

  // ── Toast (shared utility) ────────────────────────────────────────────────
  window.showToast = function(msg, type = 'info', duration = 4000) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateX(20px)'; toast.style.transition = '0.3s'; setTimeout(() => toast.remove(), 300); }, duration);
  };

  // ── Animate count-up ──────────────────────────────────────────────────────
  window.animateValue = function(id, start, end, duration) {
    const el = document.getElementById(id);
    if (!el) return;
    const range = end - start;
    const startTime = performance.now();
    function update(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(start + range * ease).toLocaleString();
      if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
  };

  // ── Format helpers ────────────────────────────────────────────────────────
  window.formatNumber = n => Number(n).toLocaleString();
  window.formatDate = d => d ? new Date(d).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

  // ── Init ──────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    // Don't run on login page
    if (document.body.classList.contains('login-body')) {
      // Handle login page theme toggle
      const loginThemeBtn = document.getElementById('loginThemeToggle');
      if (loginThemeBtn) loginThemeBtn.addEventListener('click', toggleTheme);
      return;
    }

    // Auth guard
    if (!isAuthenticated()) {
      const prefix = getPrefix();
      window.location.href = prefix + 'login.html';
      return;
    }

    const user = getCurrentUser();
    buildNav(user);
    injectThemeToggle();
    buildTopbar(user);
  });

})();
