# SAIA V4 Frontend

Complete vanilla HTML/CSS/JavaScript frontend for the SAIA (Secure Artificial Intelligence Auditor) security platform.

## Architecture Overview

The frontend is built as a single-page application with multiple views, featuring:
- Dark professional cybersecurity dashboard aesthetic
- Real-time data visualization using Chart.js
- AI-powered chat assistant with streaming responses
- WebSocket support for real-time alerts
- Comprehensive form management and modals
- Role-based navigation (Admin, Auditor, Compliance Officer)

## Directory Structure

```
frontend/
├── index.html                 # Main dashboard
├── login.html                 # Authentication
├── assets/
│   ├── css/
│   │   └── style.css         # Consolidated stylesheet (dark theme)
│   ├── js/
│   │   ├── api.js            # API client (SAIAClient class)
│   │   ├── charts.js         # Chart.js visualizations
│   │   ├── chat.js           # Chat assistant functionality
│   │   ├── utils.js          # Common utilities & helpers
│   │   ├── data/
│   │   │   └── mock-data.js  # Mock data for demo
│   │   ├── pages/
│   │   │   ├── dashboard.js  # Dashboard page logic
│   │   │   ├── alerts.js     # Alerts page logic
│   │   │   ├── rules.js      # Rules page logic
│   │   │   └── login.js      # Login logic
│   │   └── components/
│   │       ├── charts.js     # Chart components
│   │       └── workflow.js   # Workflow diagrams
│   └── img/
│       └── (logos, icons)
└── pages/
    ├── alerts.html           # Alerts list and management
    ├── alert-detail.html     # Single alert detail view
    ├── rules.html            # Rules management
    ├── cases.html            # Cases management
    ├── reports.html          # Reports generation
    ├── chat.html             # Full-page chat interface
    └── admin.html            # Admin panel (users, roles, settings)
```

## Key Features

### 1. Authentication
- **File**: `login.html`
- Demo credentials for testing
- Session-based authentication via sessionStorage
- JWT token support
- Auto-redirect to login if not authenticated

### 2. Dashboard (`index.html`)
- KPI cards: Active Alerts, Resolved Cases, Pending Reports, Response Time
- Real-time charts:
  - Anomaly Score Distribution histogram
  - Precision/Recall tracker line chart
  - Alerts by Domain pie chart
  - Severity Distribution bar chart
- Recent Alerts table with filtering
- Model health metrics
- WebSocket integration for real-time updates

### 3. Alerts Management (`pages/alerts.html`)
- Filterable alerts table
- Severity, Status, Domain, Source filters
- Search functionality
- Pagination
- Bulk actions (assign, change status)
- Click-through to detail view

### 4. Alert Detail (`pages/alert-detail.html`)
- Comprehensive alert information
- AI Assessment panel
  - Violation detected
  - Confidence score
  - Primary/Secondary controls
  - Reasoning and recommendations
  - False positive likelihood
- Detection Details with feature analysis
- Triggered Rules list
- Source Events timeline
- Comments section
- Quick actions (assign, TP/FP, create case)

### 5. Rules Management (`pages/rules.html`)
- Rules list with filtering
- Create/Edit rule forms
- Field checks builder
- Aggregation configuration
- Dry-run testing capability
- Publish/activate (admin only)
- Clause reference mapping

### 6. Cases Management (`pages/cases.html`)
- Active cases listing
- Case detail view
- Narrative generation
- Evidence pack creation
- Alert grouping

### 7. Reports (`pages/reports.html`)
- Compliance framework selection (NCA, SAMA, CST, IA)
- Date range selection
- Multiple output formats (PDF, CSV, JSON)
- Report generation and download
- Historical reports listing

### 8. AI Assistant (`pages/chat.html`)
- Full-page chat interface
- Streaming responses via SSE
- Session management
- Message history
- Source citations (clickable links to alerts/rules/cases)
- Suggested prompts
- Markdown rendering

### 9. Admin Panel (`pages/admin.html`)
- Users management (create, edit, delete)
- Role configuration
- System settings
- Audit logs viewing
- Admin-only access control

## CSS Theming

The `assets/css/style.css` file contains:

### Color Scheme (Dark Professional)
```css
--bg-darkest: #0a0e17    /* Page background */
--bg-dark: #111827       /* Primary surface */
--bg-secondary: #1f2937  /* Secondary surface */
--bg-tertiary: #374151   /* Tertiary surface */

--text-primary: #f3f4f6    /* Main text */
--text-secondary: #d1d5db  /* Secondary text */
--text-tertiary: #9ca3af   /* Tertiary text */

--accent-blue: #3b82f6     /* Primary accent */
--accent-green: #10b981    /* Success/Resolved */
--accent-red: #ef4444      /* Critical/Error */
--accent-amber: #f59e0b    /* Warning/Medium */
```

### Severity Badges
- `critical`: Red (#ef4444)
- `high`: Orange (#f97316)
- `medium`: Amber (#f59e0b)
- `low`: Cyan (#06b6d4)

### Status Badges
- `open`: Blue (#3b82f6)
- `investigating`: Amber (#f59e0b)
- `resolved`: Green (#10b981)
- `false_positive`: Gray (#6b7280)

## JavaScript API

### SAIAClient (`assets/js/api.js`)

Main API client class with methods for all endpoints:

```javascript
// Authentication
await saia.login(username, password)
await saia.register(username, password, email, fullName)
await saia.logout()

// Alerts
await saia.getAlerts(params)
await saia.getAlert(id)
await saia.updateAlert(id, data)
await saia.submitFeedback(id, data)
await saia.assignAlert(id, assignedTo)

// Rules
await saia.getRules(params)
await saia.createRule(data)
await saia.publishRule(id)

// Cases
await saia.getCases(params)
await saia.createCase(data)
await saia.generateNarrative(id)

// Dashboard
await saia.getDashboardStats()
await saia.getAnomalyDistribution(params)
await saia.getPrecisionRecall(params)

// Chat
await saia.createChatSession()
await saia.sendChatMessage(sessionId, message)
async for (const chunk of saia.streamChatResponse(sessionId, message)) { }

// WebSocket
saia.connectWebSocket(onMessage)
saia.disconnectWebSocket()
```

### Chart Rendering (`assets/js/charts.js`)

Utility functions for Chart.js visualizations:

```javascript
renderAnomalyHistogram(containerId, data)
renderPrecisionTracker(containerId, data)
renderAlertsByDomain(containerId, data)
renderAlertsBySeverity(containerId, data)
renderTimeline(containerId, events)
```

### Chat Manager (`assets/js/chat.js`)

Handles chat sessions and streaming responses:

```javascript
// Global instance
const chatManager = new ChatManager()

// Initialize and send messages
await chatManager.initSession()
await chatManager.sendMessage(message)
chatManager.clearChat()

// Utility functions
function initializeChatUI()
```

### Utilities (`assets/js/utils.js`)

Common helper functions:

```javascript
// UI
showToast(message, type, duration)
createModal(title, content, actions)
createSkeleton(height, width)

// Date/Time
formatDate(date, format)
formatRelativeTime(date)

// Numbers
formatNumber(num)
formatPercent(num, decimals)

// Authentication
isAuthenticated()
getCurrentUser()
hasRole(role)
isAdmin()
requireAuth()

// Utilities
debounce(func, delay)
throttle(func, limit)
getUrlParam(name)
setUrlParam(name, value)
generateId(prefix)
isValidEmail(email)
isValidUrl(url)
formatFileSize(bytes)
```

## Data Flow

1. **Authentication**: Login page authenticates user, stores token in sessionStorage
2. **API Requests**: All requests go through SAIAClient with automatic JWT injection
3. **Real-time Updates**: WebSocket connection established on dashboard load
4. **Chat Streaming**: EventSource or fetch with ReadableStream for incremental responses
5. **Error Handling**: 401 responses automatically redirect to login

## Responsive Design

- Desktop-first design with mobile breakpoints at 1024px, 768px, 480px
- Sidebar collapses on mobile
- Chat panel becomes full-screen on mobile
- Table layout adapts with horizontal scroll on small screens
- All modals responsive with max-width constraints

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Requires ES6+ support

## Getting Started

### Development

```bash
# Serve files locally
python -m http.server 8080

# Access at http://localhost:8080
```

### Configuration

Update API base URL in `assets/js/api.js`:
```javascript
const saia = new SAIAClient('http://localhost:8000');
```

### Demo Credentials

- **Admin**: admin / admin123
- **Auditor**: auditor / audit123
- **Compliance**: compliance / comp123
- **Demo**: demo / demo

Keyboard shortcut: **Alt+D** fills demo credentials automatically.

## External Dependencies

### Chart.js
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
```

## API Integration

All endpoints expect responses in JSON format. Key endpoints:

### Alerts
- `GET /api/alerts` - List alerts
- `GET /api/alerts/{id}` - Get alert detail
- `PUT /api/alerts/{id}` - Update alert
- `POST /api/alerts/{id}/feedback` - Submit feedback

### Rules
- `GET /api/rules` - List rules
- `POST /api/rules` - Create rule
- `PUT /api/rules/{id}` - Update rule
- `POST /api/rules/{id}/publish` - Publish rule

### Chat
- `POST /api/chat/sessions` - Create chat session
- `POST /api/chat/sessions/{id}/messages` - Send message
- `POST /api/chat/sessions/{id}/stream` - Stream response

### WebSocket
- `ws://localhost:8000/ws` - Real-time connections

## Performance Optimization

- CSS custom properties for efficient theming
- Lazy chart rendering on tab switch
- Pagination for large tables
- Debounced search and filter inputs
- Minimal re-renders with vanilla JS
- Optimized animations with CSS transitions

## Accessibility

- Semantic HTML structure
- ARIA labels where needed
- Keyboard navigation support
- Focus indicators on interactive elements
- Color contrast meets WCAG standards

## Security

- XSS protection through content escaping
- CSRF tokens support (when needed)
- JWT authentication
- Session-based storage (not localStorage for sensitive data)
- Content Security Policy headers (recommended backend)

## Future Enhancements

- Offline mode with service workers
- Dark/Light theme toggle
- Customizable dashboard widgets
- Advanced analytics exports
- Mobile app (React Native)
- Accessibility improvements
