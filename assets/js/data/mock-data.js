// SAIA Dashboard - Mock Data and Constants

const mockAlerts = [
    { id: 'ALT-2024-001', clause: 'NCA-ACC-4.2.1', severity: 'Critical', status: 'Open', assignedTo: 'Ahmed Al-Saud', timestamp: '2024-10-21 14:32' },
    { id: 'ALT-2024-002', clause: 'SAMA-ENC-3.1.5', severity: 'High', status: 'Investigating', assignedTo: 'Fatima Hassan', timestamp: '2024-10-21 13:15' },
    { id: 'ALT-2024-003', clause: 'CST-LOG-2.3.2', severity: 'Medium', status: 'Open', assignedTo: 'Mohammed Ali', timestamp: '2024-10-21 12:48' },
    { id: 'ALT-2024-004', clause: 'IA-AUD-5.1.1', severity: 'Low', status: 'Resolved', assignedTo: 'Sara Abdullah', timestamp: '2024-10-21 11:22' },
    { id: 'ALT-2024-005', clause: 'NCA-NET-6.2.3', severity: 'Critical', status: 'Open', assignedTo: 'Khaled Ibrahim', timestamp: '2024-10-21 10:55' },
    { id: 'ALT-2024-006', clause: 'SAMA-ACC-1.4.2', severity: 'High', status: 'Investigating', assignedTo: 'Noura Fahad', timestamp: '2024-10-21 09:30' },
    { id: 'ALT-2024-007', clause: 'CST-SEC-4.5.1', severity: 'Medium', status: 'Resolved', assignedTo: 'Omar Rashid', timestamp: '2024-10-21 08:15' },
    { id: 'ALT-2024-008', clause: 'NCA-DAT-3.2.4', severity: 'Low', status: 'Open', assignedTo: 'Layla Mansour', timestamp: '2024-10-20 16:40' }
];

const kpiData = {
    activeAlerts: 27,
    resolvedCases: 142,
    pendingReports: 8,
    avgResponseTime: '2.4h'
};

const severityData = {
    labels: ['Critical', 'High', 'Medium', 'Low'],
    values: [12, 35, 28, 15],
    colors: ['#f44336', '#ff9800', '#ffc107', '#4caf50']
};

const confusionMatrixData = {
    truePositive: 128,
    falsePositive: 19,
    trueNegative: 854,
    falseNegative: 12,
    labels: {
        predicted: ['Threat', 'No Threat'],
        actual: ['Threat', 'No Threat']
    }
};

const regulatoryFrameworks = {
    NCA: {
        name: 'National Cybersecurity Authority',
        clauses: [
            'NCA-ACC-4.2.1 - Access Control',
            'NCA-NET-6.2.3 - Network Security',
            'NCA-DAT-3.2.4 - Data Protection'
        ]
    },
    SAMA: {
        name: 'Saudi Arabian Monetary Authority',
        clauses: [
            'SAMA-ENC-3.1.5 - Encryption Requirements',
            'SAMA-ACC-1.4.2 - Account Management'
        ]
    },
    CST: {
        name: 'Communications and Space Technology',
        clauses: [
            'CST-LOG-2.3.2 - Log Retention',
            'CST-SEC-4.5.1 - Security Controls'
        ]
    },
    IA: {
        name: 'Internal Audit',
        clauses: [
            'IA-AUD-5.1.1 - Audit Trail'
        ]
    }
};

// Workflow data for Use Case 1: Review Audit Report
const workflowUseCase1 = {
    nodes: [
        { id: 'login', label: 'Log In', x: 150, y: 100 },
        { id: 'reports', label: 'Open Reports', x: 350, y: 100 },
        { id: 'generate', label: 'Generate Clause-based\nCompliance Report', x: 600, y: 100 },
        { id: 'validate', label: 'Validate Data\nCompleteness', x: 350, y: 220 },
        { id: 'missing', label: 'Display Missing\nSource Details', x: 350, y: 320 },
        { id: 'map', label: 'Map Events to Clauses\n(NCA/SAMA/CST/IA)', x: 600, y: 220 },
        { id: 'export', label: 'Export Report\n(PDF/CSV + Report ID)', x: 600, y: 320 }
    ],
    edges: [
        { from: 'login', to: 'reports' },
        { from: 'reports', to: 'generate' },
        { from: 'generate', to: 'validate', label: '«include»' },
        { from: 'generate', to: 'map', label: '«include»' },
        { from: 'validate', to: 'missing', label: '«extend»' },
        { from: 'map', to: 'export' },
        { from: 'export', to: 'generate' }
    ]
};

// Workflow data for Use Case 2: Manage Rules
const workflowUseCase2 = {
    nodes: [
        { id: 'open', label: 'Open Rule\nManagement', x: 200, y: 100 },
        { id: 'create', label: 'Create / Edit Rule', x: 400, y: 100 },
        { id: 'map', label: 'Map Rule to Clause\n(NCA / SAMA)', x: 650, y: 100 },
        { id: 'validate', label: 'Validate Syntax', x: 400, y: 220 },
        { id: 'error', label: 'Show Error\nNotification', x: 650, y: 220 },
        { id: 'publish', label: 'Publish Rule', x: 400, y: 320 },
        { id: 'version', label: 'Version Rule\n(change notes, author)', x: 650, y: 320 }
    ],
    edges: [
        { from: 'open', to: 'create' },
        { from: 'create', to: 'map', label: '«include»' },
        { from: 'create', to: 'validate', label: '«include»' },
        { from: 'validate', to: 'error', label: '«extend»' },
        { from: 'validate', to: 'publish' },
        { from: 'publish', to: 'version', label: '«include»' }
    ]
};

// Workflow data for Use Case 3: Handle Alerts
const workflowUseCase3 = {
    nodes: [
        { id: 'open', label: 'Open Alerts', x: 150, y: 100 },
        { id: 'review', label: 'Review Alert', x: 350, y: 100 },
        { id: 'acknowledge', label: 'Acknowledge', x: 550, y: 100 },
        { id: 'comment', label: 'Add Comment', x: 350, y: 220 },
        { id: 'group', label: 'Group Related Alerts\ninto Case', x: 350, y: 320 },
        { id: 'resolve', label: 'Resolve Alert / Case', x: 550, y: 220 },
        { id: 'evidence', label: 'Generate Evidence\nPack', x: 550, y: 320 },
        { id: 'overdue', label: 'Supervisor Flags\nOverdue', x: 750, y: 220 }
    ],
    edges: [
        { from: 'open', to: 'review' },
        { from: 'review', to: 'acknowledge' },
        { from: 'review', to: 'comment', label: '«include»' },
        { from: 'comment', to: 'group' },
        { from: 'acknowledge', to: 'resolve' },
        { from: 'resolve', to: 'overdue', label: '«extend»' },
        { from: 'resolve', to: 'evidence', label: '«include»' }
    ]
};

// Export data
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        mockAlerts,
        kpiData,
        severityData,
        confusionMatrixData,
        regulatoryFrameworks,
        workflowUseCase1,
        workflowUseCase2,
        workflowUseCase3
    };
}