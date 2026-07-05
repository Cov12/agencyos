/**
 * Dashboard Provider Registry (Dashboard D1)
 * ------------------------------------------
 * The cross-ecosystem dashboard is a SHELL: `CrossEcosystemDashboard.svelte`
 * iterates `dashboardWidgets`, calls each descriptor's `load()` with the
 * current (token, orgId, subAccountId), and renders its `component` inside a
 * GlassPanel with the loaded data.
 *
 * ► ADDING A WIDGET (this is the whole extension story — no dashboard rewrite):
 *     1. Build a `.svelte` component under ./widgets that takes a `data` prop.
 *     2. Append one `DashboardWidget` descriptor to `dashboardWidgets` below.
 *   D2 (WorkPipe widgets) and D4 (Cortex widgets) plug in exactly this way.
 *
 * ► READ-ONLY CONTRACT: a widget's `load()` MUST call only read (get-prefixed)
 *   endpoints from `$lib/apis/agencyos`. Never call a mutation (create, update,
 *   select, approve, reject, sync, …) from the dashboard — it is view-only.
 */
import type { ComponentType } from 'svelte';
import { getOrganization, getOrgSubAccounts } from '$lib/apis/agencyos';
import OrganizationWidget from './widgets/OrganizationWidget.svelte';
import SubAccountsWidget from './widgets/SubAccountsWidget.svelte';

export type DashboardWidget = {
	/** Stable unique key — used for keyed rendering + per-widget state. */
	id: string;
	/** Panel heading shown in the widget's GlassPanel. */
	title: string;
	/** Material Symbols icon name for the panel heading. */
	icon: string;
	/** Grid columns to span on large screens (1–3). Defaults to 1. */
	span?: number;
	/**
	 * Fetches the widget's data. MUST be read-only (get* endpoints only).
	 * @param subAccountId active scope; `null` means the Business (org-wide) view.
	 */
	load: (token: string, orgId: string, subAccountId: string | null) => Promise<unknown>;
	/** Svelte component rendered with `data={<load() result>}`. */
	component: ComponentType;
};

export const dashboardWidgets: DashboardWidget[] = [
	{
		id: 'organization',
		title: 'Organization',
		icon: 'corporate_fare',
		span: 1,
		load: (token, orgId) => getOrganization(token, orgId),
		component: OrganizationWidget
	},
	{
		id: 'sub-accounts',
		title: 'Sub-accounts',
		icon: 'workspaces',
		span: 1,
		load: (token, orgId) => getOrgSubAccounts(token, orgId),
		component: SubAccountsWidget
	}
];
