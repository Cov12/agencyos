<script lang="ts">
	import { onMount, getContext, createEventDispatcher } from 'svelte';
	import { getProposals, reviewProposal, type Proposal } from '$lib/apis/agencyos';
	import { user } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ProposalDetail from './ProposalDetail.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let orgId: string = '';
	export let filterStatus: string = 'pending';
	export let filterDepartment: string = '';

	let proposals: Proposal[] = [];
	let loading = true;
	let selectedProposal: Proposal | null = null;
	let total = 0;

	const RISK_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
		low: { bg: 'bg-green-500/10', text: 'text-green-600 dark:text-green-400', dot: 'bg-green-500' },
		medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-600 dark:text-yellow-400', dot: 'bg-yellow-500' },
		high: { bg: 'bg-orange-500/10', text: 'text-orange-600 dark:text-orange-400', dot: 'bg-orange-500' },
		critical: { bg: 'bg-red-500/10', text: 'text-red-600 dark:text-red-400', dot: 'bg-red-500' }
	};

	const STATUS_STYLES: Record<string, string> = {
		pending: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
		approved: 'bg-green-500/10 text-green-600 dark:text-green-400',
		rejected: 'bg-red-500/10 text-red-600 dark:text-red-400',
		executed: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
		failed: 'bg-red-500/10 text-red-600 dark:text-red-400'
	};

	const DEPT_NAMES: Record<string, string> = {
		sales_admin: 'Sales & Admin',
		customer: 'Customer Success',
		back_office: 'Back Office',
		chief: 'Chief AI'
	};

	async function loadProposals() {
		loading = true;
		try {
			const token = localStorage.getItem('token') ?? '';
			const res = await getProposals(token, orgId, {
				status: filterStatus || undefined,
				department_id: filterDepartment || undefined,
				limit: 50
			});
			proposals = res.proposals;
			total = res.total;
		} catch (err) {
			console.error('Failed to load proposals:', err);
		} finally {
			loading = false;
		}
	}

	async function handleReview(proposalId: string, status: 'approved' | 'rejected', note: string = '') {
		try {
			const token = localStorage.getItem('token') ?? '';
			const userId = $user?.id ?? '';
			await reviewProposal(token, proposalId, orgId, userId, {
				status,
				review_note: note
			});
			await loadProposals();
			selectedProposal = null;
			dispatch('reviewed', { proposalId, status });
		} catch (err) {
			console.error('Failed to review proposal:', err);
		}
	}

	function formatTimestamp(ts: number): string {
		const date = new Date(ts);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffH = Math.floor(diffMs / 3600000);

		if (diffH < 1) return 'Just now';
		if (diffH < 24) return `${diffH}h ago`;
		if (diffH < 48) return 'Yesterday';
		return date.toLocaleDateString();
	}

	onMount(() => {
		if (orgId) loadProposals();
	});

	$: if (orgId && (filterStatus !== undefined || filterDepartment !== undefined)) {
		loadProposals();
	}
</script>

<div class="flex h-full flex-col">
	<!-- Header -->
	<div class="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
		<div class="flex items-center gap-2">
			<h2 class="text-lg font-semibold">Approval Inbox</h2>
			{#if total > 0}
				<span class="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-600 dark:text-yellow-400">
					{total}
				</span>
			{/if}
		</div>

		<!-- Filters -->
		<div class="flex items-center gap-2">
			<select
				bind:value={filterStatus}
				class="rounded-lg border border-gray-200 bg-transparent px-2 py-1 text-sm dark:border-gray-700"
			>
				<option value="">All Status</option>
				<option value="pending">Pending</option>
				<option value="approved">Approved</option>
				<option value="rejected">Rejected</option>
			</select>
		</div>
	</div>

	<!-- Proposal List -->
	<div class="flex-1 overflow-y-auto">
		{#if loading}
			<div class="flex items-center justify-center py-12">
				<div class="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
			</div>
		{:else if proposals.length === 0}
			<div class="flex flex-col items-center justify-center py-12 text-gray-500 dark:text-gray-400">
				<svg class="mb-3 h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
						d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				<p class="text-sm">No proposals to review</p>
			</div>
		{:else}
			{#each proposals as proposal}
				<button
					class="flex w-full items-start gap-3 border-b border-gray-100 px-4 py-3 text-left transition-colors
						hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50"
					on:click={() => (selectedProposal = proposal)}
				>
					<!-- Risk indicator -->
					<div class="mt-1.5">
						<div class="h-2.5 w-2.5 rounded-full {RISK_COLORS[proposal.risk_level]?.dot ?? 'bg-gray-400'}" />
					</div>

					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<span class="font-medium truncate">{proposal.title}</span>
						</div>
						<div class="mt-1 flex items-center gap-2 text-xs">
							<span class="rounded-full px-2 py-0.5 {RISK_COLORS[proposal.risk_level]?.bg ?? ''} {RISK_COLORS[proposal.risk_level]?.text ?? ''}">
								{proposal.risk_level}
							</span>
							<span class="rounded-full px-2 py-0.5 {STATUS_STYLES[proposal.status] ?? ''}">
								{proposal.status}
							</span>
							<span class="text-gray-400">
								{DEPT_NAMES[proposal.department_id] ?? proposal.department_id}
							</span>
						</div>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
							{proposal.description}
						</p>
					</div>

					<span class="mt-1 shrink-0 text-xs text-gray-400">
						{formatTimestamp(proposal.created_at)}
					</span>
				</button>
			{/each}
		{/if}
	</div>
</div>

<!-- Proposal Detail Modal -->
{#if selectedProposal}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" on:click={() => (selectedProposal = null)}>
		<div class="w-full max-w-2xl" on:click|stopPropagation>
			<ProposalDetail
				proposal={selectedProposal}
				{orgId}
				on:approve={(e) => handleReview(e.detail.id, 'approved', e.detail.note)}
				on:reject={(e) => handleReview(e.detail.id, 'rejected', e.detail.note)}
				on:close={() => (selectedProposal = null)}
			/>
		</div>
	</div>
{/if}
