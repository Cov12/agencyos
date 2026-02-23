<script lang="ts">
	import { departments, proposals, pendingProposals } from '$lib/stores/agencyos';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	const DEPT_ICONS: Record<string, string> = {
		sales: '💼', customer: '🤝', backoffice: '📋',
	};

	const PRIORITY_COLORS: Record<string, string> = {
		low: 'green', medium: 'yellow', high: 'red', critical: 'red',
	};

	const STATUS_COLORS: Record<string, string> = {
		pending: 'yellow', approved: 'green', rejected: 'red', expired: 'purple',
	};

	$: approvedCount = $proposals.filter((p) => p.status === 'approved').length;
	$: rejectedCount = $proposals.filter((p) => p.status === 'rejected').length;
</script>

<div class="mx-auto max-w-5xl space-y-6 p-6">
	<!-- Org Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold text-white">AgencyOS</h1>
			<p class="text-sm text-slate-400">Organization Dashboard</p>
		</div>
		<div class="flex items-center gap-4 text-sm">
			<div class="text-center">
				<p class="text-2xl font-bold text-yellow-500">{$pendingProposals.length}</p>
				<p class="text-xs text-slate-500">Pending</p>
			</div>
			<div class="text-center">
				<p class="text-2xl font-bold text-green-500">{approvedCount}</p>
				<p class="text-xs text-slate-500">Approved</p>
			</div>
			<div class="text-center">
				<p class="text-2xl font-bold text-red-500">{rejectedCount}</p>
				<p class="text-xs text-slate-500">Rejected</p>
			</div>
		</div>
	</div>

	<!-- Departments Grid -->
	<div>
		<h2 class="mb-3 text-lg font-semibold text-white">Departments</h2>
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each $departments as dept}
				<div class="rounded-xl border border-white/10 bg-white/5 p-4 transition-colors hover:border-white/20">
					<div class="flex items-center gap-3">
						<span class="text-2xl">{DEPT_ICONS[dept.id] ?? '🏢'}</span>
						<div>
							<h3 class="font-medium text-white">{dept.name}</h3>
							<StatusBadge label={dept.status} color={dept.status === 'active' ? 'green' : 'yellow'} />
						</div>
					</div>
					<p class="mt-2 text-sm text-slate-400">{dept.description}</p>
					<div class="mt-3 flex items-center gap-2 text-xs text-slate-500">
						<MaterialIcon icon="smart_toy" size={14} />
						<span>{dept.agentCount} agent{dept.agentCount !== 1 ? 's' : ''}</span>
					</div>
				</div>
			{/each}
		</div>
	</div>

	<!-- Recent Proposals -->
	<div>
		<h2 class="mb-3 text-lg font-semibold text-white">Recent Proposals</h2>
		{#if $proposals.length === 0}
			<p class="text-sm text-slate-400">No proposals yet.</p>
		{:else}
			<div class="overflow-hidden rounded-xl border border-white/10">
				<table class="w-full text-sm">
					<thead class="bg-white/5">
						<tr>
							<th class="px-4 py-2 text-left font-medium text-slate-400">Proposal</th>
							<th class="px-4 py-2 text-left font-medium text-slate-400">Priority</th>
							<th class="px-4 py-2 text-left font-medium text-slate-400">Status</th>
							<th class="px-4 py-2 text-right font-medium text-slate-400">When</th>
						</tr>
					</thead>
					<tbody>
						{#each $proposals.slice(0, 10) as proposal}
							<tr class="border-t border-white/5 hover:bg-white/5 transition-colors">
								<td class="px-4 py-2.5">
									<span class="font-medium text-white">{proposal.title}</span>
								</td>
								<td class="px-4 py-2.5">
									<StatusBadge label={proposal.priority} color={PRIORITY_COLORS[proposal.priority]} />
								</td>
								<td class="px-4 py-2.5">
									<StatusBadge label={proposal.status} color={STATUS_COLORS[proposal.status]} />
								</td>
								<td class="px-4 py-2.5 text-right text-slate-400">
									{proposal.createdAt}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
