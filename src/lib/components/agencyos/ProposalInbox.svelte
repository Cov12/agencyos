<script lang="ts">
	import { proposals, pendingProposals, type Proposal } from '$lib/stores/agencyos';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';
	import { onMount } from 'svelte';

	// Seed with demo data if store is empty
	const demoProposals: Proposal[] = [
		{
			id: '1', title: 'Approve $5,000 Software Subscription', dept: 'backoffice',
			description: 'Finance Ops detected a recurring annual payment for "Enterprise Cloud Services". This amount exceeds the auto-approval threshold of $1,000.',
			status: 'pending', createdAt: '2m ago', priority: 'high',
			actions: [
				{ label: 'Approve', type: 'primary' },
				{ label: 'Reject', type: 'danger' },
				{ label: 'View Details', type: 'secondary' },
			],
		},
		{
			id: '2', title: 'Draft Contract for Acme Corp', dept: 'backoffice',
			description: 'Legal Eagle AI has prepared a standard NDA and Service Agreement for the new Acme Corp partnership.',
			status: 'pending', createdAt: '15m ago', priority: 'medium',
			actions: [
				{ label: 'Approve', type: 'primary' },
				{ label: 'Reject', type: 'danger' },
				{ label: 'Preview PDF', type: 'secondary' },
			],
		},
		{
			id: '3', title: 'Send Outreach Email to 50 Leads', dept: 'sales',
			description: 'SalesBot Alpha identified 50 high-intent leads from LinkedIn. Proposed action is to send the "Q4 Introduction" sequence.',
			status: 'pending', createdAt: '1h ago', priority: 'low',
			actions: [
				{ label: 'Approve Batch', type: 'primary' },
				{ label: 'Reject', type: 'danger' },
				{ label: 'View List', type: 'secondary' },
			],
		},
		{
			id: '4', title: 'Schedule Q4 Planning Meeting', dept: 'customer',
			description: 'Assistant AI found a common slot for all department heads on Nov 1st at 10:00 AM.',
			status: 'pending', createdAt: '3h ago', priority: 'low',
			actions: [
				{ label: 'Approve', type: 'primary' },
				{ label: 'Reject', type: 'danger' },
			],
		},
	];

	onMount(() => {
		if ($proposals.length === 0) {
			proposals.set(demoProposals);
		}
	});

	const PRIORITY_COLORS: Record<string, string> = {
		critical: 'red',
		high: 'red',
		medium: 'yellow',
		low: 'green',
	};

	const PROPOSAL_ICONS: Record<string, { icon: string; bg: string; color: string }> = {
		backoffice: { icon: 'account_balance_wallet', bg: 'bg-indigo-500/10', color: 'text-[#6961ff]' },
		sales: { icon: 'send', bg: 'bg-purple-500/10', color: 'text-purple-500' },
		customer: { icon: 'calendar_month', bg: 'bg-teal-500/10', color: 'text-teal-500' },
	};

	function getProposalIcon(dept: string) {
		return PROPOSAL_ICONS[dept] ?? { icon: 'description', bg: 'bg-white/10', color: 'text-white/60' };
	}

	function approveProposal(id: string) {
		proposals.update((p) => p.map((x) => x.id === id ? { ...x, status: 'approved' as const } : x));
	}

	function rejectProposal(id: string) {
		proposals.update((p) => p.map((x) => x.id === id ? { ...x, status: 'rejected' as const } : x));
	}
</script>

<div class="w-full h-full flex overflow-hidden bg-[#0f0f13]">
	<div class="flex-1 flex flex-col h-full min-w-0">
		<!-- Header -->
		<header class="h-14 sm:h-16 border-b border-white/5 flex items-center justify-between px-4 sm:px-8 bg-black/20 backdrop-blur-sm sticky top-0 z-10">
			<div class="flex items-center gap-3">
				<div class="flex flex-col">
					<h1 class="text-base sm:text-xl font-bold text-white tracking-tight">Pending Proposals</h1>
					<span class="text-[10px] sm:text-xs text-slate-500">
						{$pendingProposals.length} item{$pendingProposals.length !== 1 ? 's' : ''} require your attention
					</span>
				</div>
			</div>
			<div class="flex items-center gap-1.5 sm:gap-3">
				<button class="p-1.5 sm:p-2 rounded-lg hover:bg-white/5 text-slate-400 transition-colors">
					<MaterialIcon icon="filter_list" size={22} />
				</button>
				<button class="p-1.5 sm:p-2 rounded-lg hover:bg-white/5 text-slate-400 transition-colors">
					<MaterialIcon icon="sort" size={22} />
				</button>
			</div>
		</header>

		<!-- List Content -->
		<div class="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
			<div class="space-y-4 sm:space-y-6">
				{#each $proposals as proposal}
					<div class="group relative bg-white/5 border border-white/5 rounded-xl p-4 sm:p-5 shadow-sm hover:shadow-md transition-all duration-200 hover:border-white/10 {proposal.status !== 'pending' ? 'opacity-50' : ''}">
						<!-- Risk + Time -->
						<div class="flex flex-wrap items-center gap-2 mb-3 sm:absolute sm:top-5 sm:right-5 sm:mb-0">
							<StatusBadge
								label="{proposal.priority.charAt(0).toUpperCase() + proposal.priority.slice(1)} Risk"
								color={PRIORITY_COLORS[proposal.priority]}
								size="md"
							/>
							<span class="text-xs text-slate-400 font-medium py-1">{proposal.createdAt}</span>
						</div>

						<div class="flex items-start gap-3 sm:gap-4">
							<div class="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl {getProposalIcon(proposal.dept).bg} border border-white/10 flex items-center justify-center flex-shrink-0">
								<MaterialIcon icon={getProposalIcon(proposal.dept).icon} size={22} class={getProposalIcon(proposal.dept).color} />
							</div>
							<div class="flex-1 min-w-0 sm:pr-24">
								<h3 class="text-sm sm:text-base font-bold text-white truncate mb-1">{proposal.title}</h3>
								<p class="text-xs sm:text-sm text-slate-500 mb-3 line-clamp-2">{proposal.description}</p>

								{#if proposal.status === 'pending'}
									<div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3">
										{#each proposal.actions as action}
											{#if action.type === 'primary'}
												<button
													class="flex items-center justify-center px-4 py-2 bg-[#6961ff] hover:bg-[#5851d8] text-white text-sm font-semibold rounded-lg shadow-sm shadow-[#6961ff]/30 transition-all active:scale-95 w-full sm:w-auto"
													on:click={() => approveProposal(proposal.id)}
												>
													<MaterialIcon icon="check" size={18} class="mr-2" />
													{action.label}
												</button>
											{:else if action.type === 'danger'}
												<button
													class="flex items-center justify-center px-4 py-2 bg-white/5 border border-white/10 hover:bg-red-500/20 text-slate-300 hover:text-red-400 text-sm font-semibold rounded-lg transition-all active:scale-95 w-full sm:w-auto"
													on:click={() => rejectProposal(proposal.id)}
												>
													<MaterialIcon icon="close" size={18} class="mr-2" />
													{action.label}
												</button>
											{:else}
												<button class="sm:ml-auto text-slate-400 hover:text-[#6961ff] text-xs font-medium flex items-center justify-center gap-1 transition-colors py-2 sm:py-0">
													{action.label}
													<MaterialIcon icon="arrow_forward" size={14} />
												</button>
											{/if}
										{/each}
									</div>
								{:else}
									<StatusBadge
										label={proposal.status === 'approved' ? 'Approved' : 'Rejected'}
										color={proposal.status === 'approved' ? 'green' : 'red'}
										size="md"
									/>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>
