/**
 * AgencyOS Stores — Central state management
 */
import { writable, derived } from 'svelte/store';
import type { OnboardingAnswers } from '$lib/apis/agencyos';

// ── Navigation & UI ──────────────────────────────────────────
export const agencyNavCollapsed = writable(false);
export const agencyNavMobile = writable(false);

// ── Departments ──────────────────────────────────────────────
export interface Department {
	id: string;
	name: string;
	icon: string;
	gradient: string;
	description: string;
	status: 'active' | 'inactive' | 'setup';
	agentCount: number;
	model?: string;
}

const defaultDepartments: Department[] = [
	{ id: 'sales', name: 'Sales & Admin', icon: 'trending_up', gradient: 'from-blue-500 to-indigo-600', description: 'Revenue, leads, and admin tasks', status: 'active', agentCount: 2 },
	{ id: 'customer', name: 'Customer Success', icon: 'support_agent', gradient: 'from-green-400 to-emerald-600', description: 'Support tickets and satisfaction', status: 'active', agentCount: 1 },
	{ id: 'backoffice', name: 'Back Office', icon: 'business_center', gradient: 'from-orange-400 to-red-500', description: 'Finance, HR, and operations', status: 'setup', agentCount: 0 },
];

export const departments = writable<Department[]>(defaultDepartments);

// ── Notifications ────────────────────────────────────────────
export interface Notification {
	id: string;
	title: string;
	body: string;
	dept: string;
	icon: string;
	time: string;
	read: boolean;
	type: 'info' | 'action' | 'alert';
}

export const notifications = writable<Notification[]>([]);
export const unreadCount = derived(notifications, ($n) => $n.filter((x) => !x.read).length);

// ── Proposals (Delegated Actions) ────────────────────────────
export type ProposalStatus = 'pending' | 'approved' | 'rejected' | 'expired';

export interface Proposal {
	id: string;
	title: string;
	dept: string;
	description: string;
	status: ProposalStatus;
	createdAt: string;
	priority: 'low' | 'medium' | 'high' | 'critical';
	actions: { label: string; type: 'primary' | 'danger' | 'secondary' }[];
}

export const proposals = writable<Proposal[]>([]);
export const pendingProposals = derived(proposals, ($p) => $p.filter((x) => x.status === 'pending'));

// ── Chat / Active Department ─────────────────────────────────
export const activeDeptId = writable<string | null>(null);
export const activeDept = derived([departments, activeDeptId], ([$depts, $id]) =>
	$depts.find((d) => d.id === $id) ?? null
);

// ── Onboarding ───────────────────────────────────────────────
/** Mirror of the SERVER-side gate (org.settings.onboarding.completed), hydrated by
 * LockScreen. Kept as a store so in-app surfaces can read it synchronously, but it is no
 * longer the source of truth — GET /orgs/{id}/onboarding is. */
export const onboardingComplete = writable(false);
export const onboardingStep = writable(0);

/** Draft answers while the wizard is in flight, shared across the step routes (each step
 * is its own page, so a store is the only thing that survives the navigation). Durable
 * storage is the backend: the final step POSTs these and they are persisted into
 * org.settings + seeded into Contexta. */
export const onboardingAnswers = writable<OnboardingAnswers>({});

/** Reset the draft so a re-entered wizard never shows a previous run's answers. */
export const resetOnboardingAnswers = () => onboardingAnswers.set({});

// ── Organization Context ─────────────────────────────────────
export interface OrgContext {
	id: string;
	name: string;
	slug: string;
	plan: string;
}

export const activeOrg = writable<OrgContext | null>(null);
export const activeOrgId = derived(activeOrg, ($org) => $org?.id ?? '');
