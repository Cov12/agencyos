<script lang="ts">
	import { proposals, type Proposal, type ProposalStatus } from '$lib/stores/agencyos';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import ProposalDetail from './ProposalDetail.svelte';

	let filterStatus: ProposalStatus | '' = 'pending';
	let selectedProposal: Proposal | null = null;

	const RISK_COLORS: Record<string, string> = {
		low: 'green', medium: 'yellow', high: 'orange', critical: 'red',
	};

	const STATUS_COLORS: Record<string, string> = {
		pending: 'yellow', approved: 'green', rejected: 'red', expired: 'purple',
	};

	function handleReview(id: string, status: 'approved' | 'rejected') {
		proposals.update((p) => p.map((x) => x.id === id ? { ...x, status } : x));
		selectedProposal = null;
	}

	$: filtered = filterStatus
		? $proposals.filter((p) => p.status === filterStatus)
		: $proposals;
</script>

<div class="flex h-full flex-col bg-[#0f0f13]">
	<!-- Header -->
	<div class="flex items-center justify-between border-b border-white/5 px-4 py-3">
		<div class="flex items-center gap-2">
			<h2 class="text-lg font-semibold text-white">Approval Inbox</h2>
			{#if $proposals.filter(p => p.status === 'pending').length > 0}
				<StatusBadge label="{String($proposals.filter(p => p.status === 'pending').length)}" color="yellow" size="md" />
			{/if}
		</div>

		<select
			bind:value={filterStatus}
			class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-sm text-white focus:ring-0 focus:border-[#6961ff]"
		>
			<option value="">All Status</option>
			<option value="pending">Pending</option>
			<option value="approved">Approved</option>
			<option value="rejected">Rejected</option>
		</select>
	</div>

	<!-- Proposal List -->
	<div class="flex-1 overflow-y-auto">
		{#if filtered.length === 0}
			<div class="flex flex-col items-center justify-center py-12 text-slate-400">
				<MaterialIcon icon="check_circle" size={48} class="mb-3 text-slate-600" />
				<p class="text-sm">No proposals to review</p>
			</div>
		{:else}
			{#each filtered as proposal}
				<button
					class="flex w-full items-start gap-3 border-b border-white/5 px-4 py-3 text-left transition-colors hover:bg-white/5"
					on:click={() => (selectedProposal = proposal)}
				>
					<div class="mt-1.5">
						<div class="h-2.5 w-2.5 rounded-full {
							proposal.priority === 'critical' || proposal.priority === 'high' ? 'bg-red-500' :
							proposal.priority === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
						}" />
					</div>
					<div class="flex-1 min-w-0">
						<span class="font-medium text-white truncate block">{proposal.title}</span>
						<div class="mt-1 flex items-center gap-2 text-xs">
							<StatusBadge label="{proposal.priority}" color={RISK_COLORS[proposal.priority]} />
							<StatusBadge label="{proposal.status}" color={STATUS_COLORS[proposal.status]} />
							<span class="text-slate-500">{proposal.dept}</span>
						</div>
						<p class="mt-1 text-xs text-slate-400 line-clamp-2">{proposal.description}</p>
					</div>
					<span class="mt-1 shrink-0 text-xs text-slate-500">{proposal.createdAt}</span>
				</button>
			{/each}
		{/if}
	</div>
</div>

{#if selectedProposal}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" on:click={() => (selectedProposal = null)}>
		<div class="w-full max-w-2xl" on:click|stopPropagation>
			<ProposalDetail
				proposal={selectedProposal}
				on:approve={(e) => handleReview(e.detail.id, 'approved')}
				on:reject={(e) => handleReview(e.detail.id, 'rejected')}
				on:close={() => (selectedProposal = null)}
			/>
		</div>
	</div>
{/if}
