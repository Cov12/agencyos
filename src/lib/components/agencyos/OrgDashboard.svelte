<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		getOrganization,
		getDepartments,
		getProposals,
		getOrgMembers,
		getProposalStats,
		type Organization,
		type Department,
		type Proposal,
		type ProposalStats
	} from '$lib/apis/agencyos';

	const i18n = getContext('i18n');

	export let orgId: string = '';

	let org: Organization | null = null;
	let departments: Department[] = [];
	let recentProposals: Proposal[] = [];
	let stats: ProposalStats | null = null;
	let memberCount = 0;
	let loading = true;

	const DEPT_ICONS: Record<string, string> = {
		sales_admin: '💼',
		customer: '🤝',
		back_office: '📋'
	};

	const TIER_STYLES: Record<string, string> = {
		local: 'bg-green-500/20 text-green-400',
		mid: 'bg-blue-500/20 text-blue-400',
		premium: 'bg-purple-500/20 text-purple-400'
	};

	const RISK_DOT: Record<string, string> = {
		low: 'bg-green-500',
		medium: 'bg-yellow-500',
		high: 'bg-orange-500',
		critical: 'bg-red-500'
	};

	const STATUS_STYLES: Record<string, string> = {
		pending: 'text-yellow-600 dark:text-yellow-400',
		approved: 'text-green-600 dark:text-green-400',
		rejected: 'text-red-600 dark:text-red-400'
	};

	function formatTimestamp(ts: number): string {
		const date = new Date(ts);
		const now = new Date();
		const diffH = Math.floor((now.getTime() - date.getTime()) / 3600000);
		if (diffH < 1) return 'Just now';
		if (diffH < 24) return `${diffH}h ago`;
		return date.toLocaleDateString();
	}

	onMount(async () => {
		if (!orgId) return;
		const token = localStorage.getItem('token') ?? '';

		try {
			const [orgRes, deptRes, proposalRes, membersRes, statsRes] = await Promise.all([
				getOrganization(token, orgId),
				getDepartments(token, orgId),
				getProposals(token, orgId, { limit: 10 }),
				getOrgMembers(token, orgId),
				getProposalStats(token, orgId).catch(() => null)
			]);

			org = orgRes;
			departments = deptRes.departments;
			recentProposals = proposalRes.proposals;
			memberCount = membersRes.total;
			stats = statsRes;
		} catch (err) {
			console.error('Failed to load dashboard:', err);
		} finally {
			loading = false;
		}
	});
</script>

{#if loading}
	<div class="flex items-center justify-center py-20">
		<div class="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
	</div>
{:else if org}
	<div class="mx-auto max-w-5xl space-y-6 p-6">
		<!-- Org Header -->
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-bold">{org.name}</h1>
				<p class="text-sm text-gray-500 dark:text-gray-400">
					{org.slug} · {org.plan} plan · {memberCount} member{memberCount !== 1 ? 's' : ''}
				</p>
			</div>
			{#if stats}
				<div class="flex items-center gap-4 text-sm">
					<div class="text-center">
						<p class="text-2xl font-bold text-yellow-500">{stats.pending}</p>
						<p class="text-xs text-gray-500">Pending</p>
					</div>
					<div class="text-center">
						<p class="text-2xl font-bold text-green-500">{stats.approved}</p>
						<p class="text-xs text-gray-500">Approved</p>
					</div>
					<div class="text-center">
						<p class="text-2xl font-bold text-red-500">{stats.rejected}</p>
						<p class="text-xs text-gray-500">Rejected</p>
					</div>
				</div>
			{/if}
		</div>

		<!-- Departments Grid -->
		<div>
			<h2 class="mb-3 text-lg font-semibold">Departments</h2>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
				{#each departments as dept}
					<div class="rounded-xl border border-gray-200 p-4 transition-colors hover:border-gray-300 dark:border-gray-700 dark:hover:border-gray-600">
						<div class="flex items-center gap-3">
							<span class="text-2xl">{DEPT_ICONS[dept.slug] ?? '🏢'}</span>
							<div>
								<h3 class="font-medium">{dept.name}</h3>
								<span class="rounded-full px-2 py-0.5 text-xs {TIER_STYLES[dept.model_tier] ?? ''}">
									{dept.model_tier}
								</span>
							</div>
						</div>
						<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{dept.description}</p>
						<div class="mt-3 flex flex-wrap gap-1">
							{#each dept.capabilities.slice(0, 3) as cap}
								<span class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
									{cap.replace(/_/g, ' ')}
								</span>
							{/each}
							{#if dept.capabilities.length > 3}
								<span class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-400 dark:bg-gray-800">
									+{dept.capabilities.length - 3}
								</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Recent Proposals -->
		<div>
			<h2 class="mb-3 text-lg font-semibold">Recent Proposals</h2>
			{#if recentProposals.length === 0}
				<p class="text-sm text-gray-500 dark:text-gray-400">No proposals yet.</p>
			{:else}
				<div class="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Proposal</th>
								<th class="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Risk</th>
								<th class="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Status</th>
								<th class="px-4 py-2 text-right font-medium text-gray-500 dark:text-gray-400">When</th>
							</tr>
						</thead>
						<tbody>
							{#each recentProposals as proposal}
								<tr class="border-t border-gray-100 dark:border-gray-800">
									<td class="px-4 py-2.5">
										<span class="font-medium">{proposal.title}</span>
									</td>
									<td class="px-4 py-2.5">
										<div class="flex items-center gap-1.5">
											<div class="h-2 w-2 rounded-full {RISK_DOT[proposal.risk_level] ?? 'bg-gray-400'}" />
											<span class="capitalize">{proposal.risk_level}</span>
										</div>
									</td>
									<td class="px-4 py-2.5">
										<span class="capitalize {STATUS_STYLES[proposal.status] ?? ''}">{proposal.status}</span>
									</td>
									<td class="px-4 py-2.5 text-right text-gray-400">
										{formatTimestamp(proposal.created_at)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<!-- Org Settings Summary -->
		{#if org.settings && Object.keys(org.settings).length > 0}
			<div>
				<h2 class="mb-3 text-lg font-semibold">Settings</h2>
				<div class="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
					<dl class="grid grid-cols-2 gap-3 text-sm">
						{#each Object.entries(org.settings) as [key, value]}
							<div>
								<dt class="text-gray-500 dark:text-gray-400">{key.replace(/_/g, ' ')}</dt>
								<dd class="font-medium">{typeof value === 'boolean' ? (value ? 'Enabled' : 'Disabled') : value}</dd>
							</div>
						{/each}
					</dl>
				</div>
			</div>
		{/if}
	</div>
{:else}
	<div class="flex flex-col items-center justify-center py-20 text-gray-500">
		<p>Organization not found</p>
	</div>
{/if}
