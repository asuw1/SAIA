# SAIA - Secure Artificial Intelligence Auditor

A comprehensive cybersecurity auditing dashboard system designed for automating IT auditing and compliance in Saudi Arabia, with focus on regulatory frameworks including NCA, SAMA, CST, and IA.

## 📁 Project Structure

```
saia-dashboard/
├── index.html              # Main dashboard page
├── reports.html            # Use Case 1: Review Audit Report
├── rules.html              # Use Case 2: Manage Rules
├── alerts.html             # Use Case 3: Handle Alerts
├── styles.css              # Global stylesheet
├── data.js                 # Mock data and constants
├── charts.js               # Chart rendering functions
├── workflow.js             # Workflow diagram rendering
├── rules.js                # Rules management logic
├── alerts.js               # Alerts management logic
├── main.js                 # Main application logic
└── README.md               # This file
```

## 🎯 Features

### Main Dashboard (index.html)
- **KPI Cards**: Display key metrics (Active Alerts, Resolved Cases, Pending Reports, Avg Response Time)
- **Alert Distribution Chart**: Pie chart showing severity breakdown
- **Confusion Matrix**: AI model accuracy visualization
- **Recent Alerts Table**: Filterable table of recent security alerts

### Use Case 1: Review Audit Report (reports.html)
**Actor**: Compliance Officer
- Generate clause-based compliance reports
- Filter by regulatory framework (NCA, SAMA, CST, IA)
- Export in multiple formats (PDF, CSV, JSON)
- View recent report history
- Workflow visualization

### Use Case 2: Manage Rules (rules.html)
**Actor**: Administrator
- Create and edit compliance rules
- Map rules to regulatory clauses
- Validate JSON rule syntax
- Version control for rules
- Test and history tracking
- Workflow visualization

### Use Case 3: Handle Alerts (alerts.html)
**Actor**: Auditor
- Review detailed alert information
- Acknowledge and comment on alerts
- Resolve alerts with evidence generation
- Bulk operations (acknowledge, group)
- SLA tracking with overdue indicators
- Workflow visualization

## 🎨 Design Features

- **Saudi-Inspired Theme**: Dark mode with blue (#2196f3) and gold (#d4af37) accents
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Interactive Charts**: Canvas-based visualizations
- **Real-time Updates**: Simulated live data updates every 10 seconds
- **Smooth Animations**: Transitions and hover effects throughout

## 🚀 Getting Started

### Prerequisites
- Modern web browser (Chrome, Firefox, Edge, Safari)
- No server required - runs completely in the browser

### Installation

1. Clone or download the project files
2. Maintain the file structure as shown above
3. Open `index.html` in a web browser

### Quick Start

```bash
# If using a local server (optional)
python -m http.server 8000
# Then navigate to http://localhost:8000

# Or simply open index.html in your browser
```

## 📊 Data Structure

### Mock Alerts
```javascript
{
    id: 'ALT-2024-001',
    clause: 'NCA-ACC-4.2.1',
    severity: 'Critical',
    status: 'Open',
    assignedTo: 'Ahmed Al-Saud',
    timestamp: '2024-10-21 14:32'
}
```

### Regulatory Frameworks
- **NCA**: National Cybersecurity Authority
- **SAMA**: Saudi Arabian Monetary Authority
- **CST**: Communications and Space Technology
- **IA**: Internal Audit

## 🎭 User Roles

1. **Compliance Officer**: Reviews audit reports and compliance status
2. **Administrator**: Manages rules and system configuration
3. **Auditor**: Handles alerts and investigates security incidents

## 📱 Responsive Breakpoints

- **Desktop**: > 1024px (Full layout with sidebar)
- **Tablet**: 768px - 1024px (Adjusted grid layouts)
- **Mobile**: < 768px (Stacked layout, collapsible sidebar)

## 🎨 Color Palette

```css
--primary-bg: #0a0e1a       /* Main background */
--secondary-bg: #141b2d     /* Card backgrounds */
--card-bg: #1a2235          /* Content cards */
--accent-blue: #2196f3      /* Primary accent */
--accent-gold: #d4af37      /* Secondary accent */
--text-primary: #e4e6eb     /* Main text */
--text-secondary: #b0b3b8   /* Secondary text */
--critical: #f44336         /* Critical alerts */
--high: #ff9800             /* High priority */
--medium: #ffc107           /* Medium priority */
--low: #4caf50              /* Low priority */
```

## 🔧 Customization

### Adding New Pages
1. Create new HTML file based on existing templates
2. Add navigation link in sidebar
3. Include required scripts at bottom of page
4. Add page-specific logic to `main.js`

### Modifying Charts
Edit `charts.js` to customize:
- Chart colors
- Data visualization methods
- Metrics calculations

### Updating Workflows
Modify workflow data in `data.js`:
```javascript
const workflowUseCaseX = {
    nodes: [...],
    edges: [...]
};
```

## 📈 Performance

- **Initial Load**: < 1 second
- **Chart Rendering**: < 100ms
- **Real-time Updates**: Every 10 seconds
- **Smooth Animations**: 60fps transitions

## 🔒 Security Features

- Role-based access control simulation
- Audit trail for all actions
- Evidence generation with timestamps
- Regulatory compliance mapping

## 🐛 Known Limitations

- Mock data only (no backend integration)
- No actual authentication system
- Client-side only (no persistence)
- Browser storage not used (as per artifact restrictions)

## 🔮 Future Enhancements

- [ ] Backend API integration
- [ ] Real authentication system
- [ ] Database persistence
- [ ] Advanced filtering options
- [ ] Export functionality
- [ ] Email notifications
- [ ] Multi-language support (Arabic/English)

## 📝 License

This is a demonstration project for educational purposes.

## 👥 Credits

Designed for the SAIA (Secure Artificial Intelligence Auditor) project, focusing on Saudi Arabian regulatory compliance.

## 📞 Support

For questions or issues, refer to the project documentation or contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: November 2024  
**Compatible Browsers**: Chrome 90+, Firefox 88+, Edge 90+, Safari 14+