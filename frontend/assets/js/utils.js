/**
 * SAIA V4 Utilities
 * Common helper functions and utilities
 */

/**
 * Show toast notification
 */
function showToast(message, type = 'info', duration = 5000) {
    const container = document.querySelector('.toast-container') || (() => {
        const div = document.createElement('div');
        div.className = 'toast-container';
        document.body.appendChild(div);
        return div;
    })();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        'success': '✓',
        'error': '✕',
        'warning': '⚠',
        'info': 'ℹ'
    };

    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || 'ℹ'}</div>
        <div class="toast-content">
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close">&times;</button>
    `;

    container.appendChild(toast);

    // Close button handler
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.style.animation = 'slideInRight 300ms reverse';
        setTimeout(() => toast.remove(), 300);
    });

    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.animation = 'slideInRight 300ms reverse';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    }

    return toast;
}

/**
 * Format date/time
 */
function formatDate(date, format = 'short') {
    if (typeof date === 'string') {
        date = new Date(date);
    }

    if (!(date instanceof Date)) {
        return '';
    }

    const formats = {
        'short': date.toLocaleDateString('en-US'),
        'long': date.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }),
        'time': date.toLocaleTimeString('en-US'),
        'full': date.toLocaleString('en-US'),
        'iso': date.toISOString().split('T')[0]
    };

    return formats[format] || date.toString();
}

/**
 * Format datetime with relative time
 */
function formatRelativeTime(date) {
    if (typeof date === 'string') {
        date = new Date(date);
    }

    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    if (seconds < 604800) return Math.floor(seconds / 86400) + 'd ago';

    return formatDate(date, 'short');
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    if (typeof num !== 'number') {
        num = parseFloat(num);
    }
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format percentage
 */
function formatPercent(num, decimals = 1) {
    return (num * 100).toFixed(decimals) + '%';
}

/**
 * Debounce function
 */
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Throttle function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Check if user is authenticated
 */
function isAuthenticated() {
    return !!(sessionStorage.getItem('saia_token') || sessionStorage.getItem('saia_user'));
}

/**
 * Get current user from session
 */
function getCurrentUser() {
    const userJson = sessionStorage.getItem('saia_user');
    if (userJson) {
        try {
            return JSON.parse(userJson);
        } catch (e) {
            return null;
        }
    }
    return null;
}

/**
 * Check if user has specific role
 */
function hasRole(role) {
    const user = getCurrentUser();
    return user && user.role === role;
}

/**
 * Check if user is admin
 */
function isAdmin() {
    return hasRole('Administrator');
}

/**
 * Redirect to login if not authenticated
 */
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}

/**
 * Copy to clipboard
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard', 'success', 2000);
        return true;
    } catch (error) {
        console.error('Failed to copy:', error);
        showToast('Failed to copy', 'error');
        return false;
    }
}

/**
 * Stringify object for display
 */
function stringifyObject(obj, indent = 2) {
    return JSON.stringify(obj, null, indent);
}

/**
 * Parse JSON safely
 */
function parseJSON(str, defaultValue = null) {
    try {
        return JSON.parse(str);
    } catch (error) {
        return defaultValue;
    }
}

/**
 * Create query string from object
 */
function createQueryString(params) {
    return Object.entries(params)
        .filter(([, value]) => value !== null && value !== undefined && value !== '')
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        .join('&');
}

/**
 * Parse query string
 */
function parseQueryString(queryString) {
    const params = new URLSearchParams(queryString);
    const result = {};
    for (const [key, value] of params) {
        result[key] = value;
    }
    return result;
}

/**
 * Get URL parameter
 */
function getUrlParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

/**
 * Set URL parameter
 */
function setUrlParam(name, value) {
    const params = new URLSearchParams(window.location.search);
    params.set(name, value);
    window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
}

/**
 * Generate random ID
 */
function generateId(prefix = '') {
    return prefix + Math.random().toString(36).substr(2, 9);
}

/**
 * Validate email
 */
function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

/**
 * Validate URL
 */
function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

/**
 * Initialize sidebar toggle
 */
function initializeSidebar() {
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');

    if (menuToggle && sidebar && mainContent) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            sidebar.classList.toggle('active');
            mainContent.classList.toggle('expanded');
        });

        // Close sidebar on mobile when clicking a link
        if (window.innerWidth <= 768) {
            sidebar.querySelectorAll('a').forEach(link => {
                link.addEventListener('click', () => {
                    sidebar.classList.remove('active');
                    sidebar.classList.add('collapsed');
                    mainContent.classList.remove('expanded');
                });
            });
        }
    }
}

/**
 * Initialize navigation
 */
function initializeNavigation() {
    const user = getCurrentUser();
    const userRole = document.querySelector('.user-role');
    const userAvatar = document.querySelector('.user-avatar');

    if (user) {
        if (userRole) userRole.textContent = user.role || 'User';
        if (userAvatar) {
            const initials = (user.name || user.username)
                .split(' ')
                .map(n => n[0])
                .join('')
                .toUpperCase()
                .substr(0, 2);
            userAvatar.textContent = initials;
        }
    }

    // Set active nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('href') === currentPath ||
            currentPath.includes(item.getAttribute('href').split('/').pop())) {
            item.classList.add('active');
        }
    });
}

/**
 * Create loading skeleton
 */
function createSkeleton(height = '20px', width = '100%') {
    const div = document.createElement('div');
    div.className = 'skeleton';
    div.style.height = height;
    div.style.width = width;
    return div;
}

/**
 * Show loading spinner
 */
function showLoadingSpinner(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    spinner.style.margin = 'auto';
    container.appendChild(spinner);
}

/**
 * Clear loading spinner
 */
function clearLoadingSpinner(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const spinner = container.querySelector('.spinner');
    if (spinner) spinner.remove();
}

/**
 * Create modal dialog
 */
function createModal(title, content, actions = []) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';

    const modal = document.createElement('div');
    modal.className = 'modal';

    let html = `
        <div class="modal-header">
            <h2>${title}</h2>
            <button class="modal-close">&times;</button>
        </div>
        <div class="modal-body">${content}</div>
    `;

    if (actions.length > 0) {
        html += '<div class="modal-footer">';
        actions.forEach(action => {
            html += `<button class="btn ${action.className || 'btn-secondary'}" data-action="${action.id}">${action.label}</button>`;
        });
        html += '</div>';
    }

    modal.innerHTML = html;
    overlay.appendChild(modal);

    // Close handlers
    const closeBtn = modal.querySelector('.modal-close');
    closeBtn.addEventListener('click', () => overlay.remove());

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });

    // Action handlers
    actions.forEach(action => {
        const btn = modal.querySelector(`[data-action="${action.id}"]`);
        if (btn) {
            btn.addEventListener('click', () => {
                if (action.callback) action.callback();
                overlay.remove();
            });
        }
    });

    document.body.appendChild(overlay);
    return overlay;
}

/**
 * Animate value counter
 */
function animateValue(element, start, end, duration) {
    if (typeof element === 'string') {
        element = document.getElementById(element);
    }

    if (!element) return;

    const increment = (end - start) / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if (current >= end) {
            element.textContent = end;
            clearInterval(timer);
        } else {
            element.textContent = Math.round(current);
        }
    }, 16);
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Batch API requests
 */
async function batchRequests(requests, concurrent = 3) {
    const results = [];
    const queue = [...requests];

    async function processQueue() {
        while (queue.length > 0) {
            const request = queue.shift();
            try {
                const result = await request();
                results.push({ success: true, data: result });
            } catch (error) {
                results.push({ success: false, error });
            }
        }
    }

    const workers = Array(Math.min(concurrent, requests.length))
        .fill()
        .map(() => processQueue());

    await Promise.all(workers);
    return results;
}

/**
 * Wait/sleep
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Initialize all common features
 */
function initializeCommon() {
    // Check authentication
    if (!isAuthenticated() && !window.location.pathname.includes('login.html')) {
        // Redirect to login if not on login page
        if (!window.location.pathname.includes('login.html')) {
            // Check if we're on a page that requires auth
            const publicPages = ['/login.html', '/register.html'];
            if (!publicPages.some(page => window.location.pathname.includes(page))) {
                requireAuth();
            }
        }
    }

    // Initialize sidebar
    initializeSidebar();

    // Initialize navigation
    initializeNavigation();

    // Initialize keyboard shortcuts
    initializeKeyboardShortcuts();
}

/**
 * Initialize keyboard shortcuts
 */
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('[data-search]');
            if (searchInput) searchInput.focus();
        }

        // Ctrl/Cmd + /: Toggle chat
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            const chatPanel = document.querySelector('.chat-panel');
            if (chatPanel) {
                chatPanel.classList.toggle('active');
            }
        }

        // Escape: Close modals
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal-overlay.active');
            modals.forEach(modal => modal.remove());
        }
    });
}

/**
 * Export for modules
 */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showToast,
        formatDate,
        formatRelativeTime,
        formatNumber,
        formatPercent,
        debounce,
        throttle,
        isAuthenticated,
        getCurrentUser,
        hasRole,
        isAdmin,
        requireAuth,
        copyToClipboard,
        parseJSON,
        createQueryString,
        parseQueryString,
        getUrlParam,
        setUrlParam,
        generateId,
        isValidEmail,
        isValidUrl,
        initializeSidebar,
        initializeNavigation,
        createSkeleton,
        showLoadingSpinner,
        clearLoadingSpinner,
        createModal,
        animateValue,
        formatFileSize,
        batchRequests,
        sleep,
        initializeCommon
    };
}

// Auto-initialize on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCommon);
} else {
    initializeCommon();
}
