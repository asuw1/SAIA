/**
 * SAIA V4 API Client
 * Handles all communication with the SAIA backend API
 */

class SAIAClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.token = null;
        this.user = null;
        this.listeners = {};

        // Try to load token and user from sessionStorage
        const storedUser = sessionStorage.getItem('saia_user');
        const storedToken = sessionStorage.getItem('saia_token');
        if (storedUser) {
            this.user = JSON.parse(storedUser);
        }
        if (storedToken) {
            this.token = storedToken;
        }
    }

    /**
     * Base request method - handles all API calls
     */
    async request(method, endpoint, data = null, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const config = {
            method,
            headers,
            ...options
        };

        if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);

            if (response.status === 401) {
                this.token = null;
                this.user = null;
                sessionStorage.removeItem('saia_token');
                sessionStorage.removeItem('saia_user');
                window.location.href = '/login.html';
                return null;
            }

            if (!response.ok) {
                const error = await response.json().catch(() => ({ message: response.statusText }));
                throw new Error(error.message || response.statusText);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * Authentication Endpoints
     */

    async login(username, password) {
        const response = await this.request('POST', '/api/auth/login', {
            username,
            password
        });

        if (response && response.access_token) {
            this.token = response.access_token;
            this.user = response.user;
            sessionStorage.setItem('saia_token', this.token);
            sessionStorage.setItem('saia_user', JSON.stringify(this.user));
        }

        return response;
    }

    async register(username, password, email, fullName) {
        const response = await this.request('POST', '/api/auth/register', {
            username,
            password,
            email,
            full_name: fullName
        });

        return response;
    }

    async logout() {
        this.token = null;
        this.user = null;
        sessionStorage.removeItem('saia_token');
        sessionStorage.removeItem('saia_user');
    }

    /**
     * Alerts Endpoints
     */

    async getAlerts(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/alerts?${queryString}` : '/api/alerts';
        return await this.request('GET', endpoint);
    }

    async getAlert(id) {
        return await this.request('GET', `/api/alerts/${id}`);
    }

    async updateAlert(id, data) {
        return await this.request('PUT', `/api/alerts/${id}`, data);
    }

    async submitFeedback(id, data) {
        return await this.request('POST', `/api/alerts/${id}/feedback`, data);
    }

    async assignAlert(id, assignedTo) {
        return await this.request('PATCH', `/api/alerts/${id}`, {
            assigned_to: assignedTo
        });
    }

    async markAlertTruePositive(id) {
        return await this.request('PATCH', `/api/alerts/${id}`, {
            status: 'investigating'
        });
    }

    async markAlertFalsePositive(id, reason = '') {
        return await this.request('PATCH', `/api/alerts/${id}`, {
            status: 'false_positive',
            fp_reason: reason
        });
    }

    /**
     * Rules Endpoints
     */

    async getRules(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/rules?${queryString}` : '/api/rules';
        return await this.request('GET', endpoint);
    }

    async getRule(id) {
        return await this.request('GET', `/api/rules/${id}`);
    }

    async createRule(data) {
        return await this.request('POST', '/api/rules', data);
    }

    async updateRule(id, data) {
        return await this.request('PUT', `/api/rules/${id}`, data);
    }

    async publishRule(id) {
        return await this.request('POST', `/api/rules/${id}/publish`, {});
    }

    async testRule(id, data) {
        return await this.request('POST', `/api/rules/${id}/test`, data);
    }

    /**
     * Cases Endpoints
     */

    async getCases(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/cases?${queryString}` : '/api/cases';
        return await this.request('GET', endpoint);
    }

    async getCase(id) {
        return await this.request('GET', `/api/cases/${id}`);
    }

    async createCase(data) {
        return await this.request('POST', '/api/cases', data);
    }

    async updateCase(id, data) {
        return await this.request('PUT', `/api/cases/${id}`, data);
    }

    async generateNarrative(id) {
        return await this.request('POST', `/api/cases/${id}/generate-narrative`, {});
    }

    async approveNarrative(id) {
        return await this.request('POST', `/api/cases/${id}/approve-narrative`, {});
    }

    async generateEvidencePack(id) {
        return await this.request('POST', `/api/cases/${id}/evidence-pack`, {});
    }

    /**
     * Reports Endpoints
     */

    async getReports(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/reports?${queryString}` : '/api/reports';
        return await this.request('GET', endpoint);
    }

    async generateReport(data) {
        return await this.request('POST', '/api/reports', data);
    }

    async downloadReport(id) {
        return `${this.baseUrl}/api/reports/${id}/download`;
    }

    /**
     * Dashboard/Analytics Endpoints
     */

    async getDashboardStats() {
        return await this.request('GET', '/api/dashboard/stats');
    }

    async getAnomalyDistribution(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/analytics/anomaly-distribution?${queryString}` : '/api/analytics/anomaly-distribution';
        return await this.request('GET', endpoint);
    }

    async getPrecisionRecall(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/analytics/precision-recall?${queryString}` : '/api/analytics/precision-recall';
        return await this.request('GET', endpoint);
    }

    async getAlertsByDomain(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/analytics/alerts-by-domain?${queryString}` : '/api/analytics/alerts-by-domain';
        return await this.request('GET', endpoint);
    }

    async getAlertsBySeverity(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/api/analytics/alerts-by-severity?${queryString}` : '/api/analytics/alerts-by-severity';
        return await this.request('GET', endpoint);
    }

    async getModelHealth() {
        return await this.request('GET', '/api/analytics/model-health');
    }

    /**
     * Chat Endpoints
     */

    async createChatSession() {
        return await this.request('POST', '/api/chat/sessions', {});
    }

    async sendChatMessage(sessionId, message) {
        return await this.request('POST', `/api/chat/sessions/${sessionId}/messages`, {
            message
        });
    }

    /**
     * File Upload Endpoints
     */

    async uploadLogs(file) {
        const formData = new FormData();
        formData.append('file', file);

        return await fetch(`${this.baseUrl}/api/logs/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        }).then(response => response.json());
    }

    /**
     * User/Admin Endpoints
     */

    async getUsers() {
        return await this.request('GET', '/api/users');
    }

    async getUser(id) {
        return await this.request('GET', `/api/users/${id}`);
    }

    async updateUser(id, data) {
        return await this.request('PUT', `/api/users/${id}`, data);
    }

    async createUser(data) {
        return await this.request('POST', '/api/users', data);
    }

    /**
     * WebSocket Connection
     */

    connectWebSocket(onMessage) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            if (this.token) {
                this.ws.send(JSON.stringify({
                    type: 'authenticate',
                    token: this.token
                }));
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessage) onMessage(data);

                // Dispatch custom event for other components
                const customEvent = new CustomEvent('socketMessage', { detail: data });
                document.dispatchEvent(customEvent);
            } catch (error) {
                console.error('WebSocket message parsing error:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            // Attempt to reconnect after delay
            setTimeout(() => this.connectWebSocket(onMessage), 5000);
        };
    }

    disconnectWebSocket() {
        if (this.ws) {
            this.ws.close();
        }
    }

    /**
     * Event Listener Management
     */

    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    off(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        }
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }

    /**
     * Server-Sent Events (Chat Streaming)
     */

    async *streamChatResponse(sessionId, message) {
        const response = await fetch(`${this.baseUrl}/api/chat/sessions/${sessionId}/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`
            },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data) {
                            try {
                                yield JSON.parse(data);
                            } catch (e) {
                                yield { text: data };
                            }
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SAIAClient;
}

// Create global instance
const saia = new SAIAClient();
