// AgencyOS Design System Tokens
export const colors = {
	'aos-bg': '#0f0f13',
	'aos-surface': '#1c1c21',
	'aos-primary': '#6961ff',
	'aos-accent': '#20B2AA',
	'aos-primary-hover': '#5851d8',
	'aos-glass-border': 'rgba(255, 255, 255, 0.08)',
	'aos-glass-bg': 'rgba(28, 28, 33, 0.7)',
} as const;

export const glassPanel = `
	background: rgba(20, 20, 25, 0.65);
	backdrop-filter: blur(20px);
	-webkit-backdrop-filter: blur(20px);
	border: 1px solid rgba(255, 255, 255, 0.08);
`;

export const glassSidebar = `
	background: rgba(15, 15, 20, 0.85);
	backdrop-filter: blur(24px);
	-webkit-backdrop-filter: blur(24px);
	border-right: 1px solid rgba(255, 255, 255, 0.08);
`;

export type NavItem = {
	label: string;
	href: string;
	icon: string;
	badge?: number;
};

// D1: read-only cross-ecosystem dashboard is now the AgencyOS landing surface.
// Mock-only pages (Control Center, Notifications, Analytics, Multitask,
// Knowledge Base, Proposals, Departments) are de-navved here — their component
// files remain for a follow-up cleanup; they are simply no longer linked.
export const navItems: NavItem[] = [
	{ label: 'Dashboard', href: '/agencyos', icon: 'dashboard' },
	{ label: 'Chat', href: '/agencyos/chat', icon: 'chat_bubble' },
	{ label: 'Voice', href: '/agencyos/voice', icon: 'graphic_eq' },
	{ label: 'Settings', href: '/agencyos/settings', icon: 'settings' },
];

/** OpenWebUI features integrated into AgencyOS nav */
export const toolItems: NavItem[] = [
	{ label: 'New Chat', href: '/', icon: 'add_comment' },
	{ label: 'Search', href: '/', icon: 'search' },
	{ label: 'Notes', href: '/', icon: 'sticky_note_2' },
	{ label: 'Workspace', href: '/workspace', icon: 'workspaces' },
];
