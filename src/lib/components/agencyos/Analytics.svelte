<script lang="ts">
	import { departments, proposals } from '$lib/stores/agencyos';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	// Derive KPIs from store data
	$: totalProposals = $proposals.length;
	$: approvedCount = $proposals.filter(p => p.status === 'approved').length;
	$: successRate = totalProposals > 0 ? ((approvedCount / totalProposals) * 100).toFixed(1) : '0.0';
	$: activeDepts = $departments.filter(d => d.status === 'active').length;

	$: kpis = [
		{ label: 'Total AI Actions', value: String(totalProposals || '0'), change: '+12.5%', icon: 'bolt', iconBg: 'bg-[#6961ff]/10', iconColor: 'text-[#6961ff]' },
		{ label: 'Active Departments', value: String(activeDepts), change: `${activeDepts}/${$departments.length}`, icon: 'domain', iconBg: 'bg-indigo-500/10', iconColor: 'text-indigo-500' },
		{ label: 'Approval Rate', value: `${successRate}%`, change: '+0.2%', icon: 'check_circle', iconBg: 'bg-emerald-500/10', iconColor: 'text-emerald-500' },
	];

	const taskDist = [
		{ label: 'Drafting', pct: 45, opacity: '' },
		{ label: 'Research', pct: 32, opacity: '/60' },
		{ label: 'Coding', pct: 23, opacity: '/30' },
	];

	// Purge-safe bar opacity classes
	const BAR_CLASSES: Record<string, string> = {
		'': 'bg-[#6961ff]',
		'/60': 'bg-[#6961ff]/60',
		'/30': 'bg-[#6961ff]/30',
	};

	// Derive recent processes from proposals
	$: recentProcesses = $proposals.slice(0, 4).map(p => ({
		name: `${p.dept} Agent`,
		action: p.title,
		status: p.status === 'approved' ? 'Success' : p.status === 'pending' ? 'Pending' : p.status,
		statusColor: p.status === 'approved' ? 'green' : p.status === 'pending' ? 'yellow' : 'red',
		time: p.createdAt,
	}));
</script>

<div class="w-full h-full overflow-y-auto">
	<div class="p-8 max-w-6xl mx-auto">
		<div class="flex justify-between items-end mb-8">
			<div>
				<h2 class="text-3xl font-bold text-white tracking-tight">Analytics Overview</h2>
				<p class="text-slate-400 mt-1">Real-time performance data for your agency agents.</p>
			</div>
			<div class="flex items-center gap-3">
				<button class="bg-white/5 border border-white/10 px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 hover:bg-white/10 transition-colors text-white">
					<MaterialIcon icon="calendar_today" size={18} />
					Last 30 Days
				</button>
				<button class="bg-[#6961ff] text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-lg shadow-[#6961ff]/20 hover:brightness-110 transition-all">
					Refresh Data
				</button>
			</div>
		</div>

		<!-- KPIs -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
			{#each kpis as kpi}
				<GlassPanel class="p-6" opacity={0.5} borderOpacity={0.1}>
					<div class="flex justify-between items-start mb-4">
						<div class="p-2 {kpi.iconBg} rounded-lg">
							<MaterialIcon icon={kpi.icon} class={kpi.iconColor} />
						</div>
						<StatusBadge label={kpi.change} color="green" size="md" />
					</div>
					<p class="text-slate-400 text-sm font-medium">{kpi.label}</p>
					<h3 class="text-3xl font-bold text-white mt-1">{kpi.value}</h3>
				</GlassPanel>
			{/each}
		</div>

		<!-- Charts -->
		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
			<GlassPanel class="lg:col-span-2 p-6" opacity={0.5} borderOpacity={0.1}>
				<div class="flex justify-between items-center mb-8">
					<div>
						<h4 class="text-lg font-bold text-white">AI Activity Over Time</h4>
						<p class="text-xs text-slate-500">Processing volume per weekday</p>
					</div>
					<div class="flex items-center gap-1.5 text-xs font-medium text-slate-500">
						<div class="size-2 rounded-full bg-[#6961ff]"></div> Activity
					</div>
				</div>
				<div class="h-[280px] w-full relative">
					<svg class="w-full h-full" viewBox="0 0 800 280">
						<defs>
							<linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
								<stop offset="0%" stop-color="#6961ff" stop-opacity="0.2" />
								<stop offset="100%" stop-color="#6961ff" stop-opacity="0" />
							</linearGradient>
						</defs>
						<path d="M0,200 Q100,180 200,220 T400,120 T600,150 T800,50 L800,280 L0,280 Z" fill="url(#chartGradient)" />
						<path d="M0,200 Q100,180 200,220 T400,120 T600,150 T800,50" fill="none" stroke="#6961ff" stroke-width="4" stroke-linecap="round" />
						<circle cx="200" cy="220" r="5" fill="#6961ff" stroke="white" stroke-width="2" />
						<circle cx="400" cy="120" r="5" fill="#6961ff" stroke="white" stroke-width="2" />
						<circle cx="800" cy="50" r="5" fill="#6961ff" stroke="white" stroke-width="2" />
					</svg>
					<div class="flex justify-between mt-4 px-2">
						{#each ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as day}
							<span class="text-[11px] font-bold text-slate-400">{day}</span>
						{/each}
					</div>
				</div>
			</GlassPanel>

			<GlassPanel class="p-6 flex flex-col" opacity={0.5} borderOpacity={0.1}>
				<h4 class="text-lg font-bold text-white mb-1">Task Distribution</h4>
				<p class="text-xs text-slate-500 mb-8">Workload volume by type</p>
				<div class="space-y-6 flex-1 flex flex-col justify-center">
					{#each taskDist as task}
						<div>
							<div class="flex justify-between items-center mb-2">
								<span class="text-sm font-medium text-slate-300">{task.label}</span>
								<span class="text-sm font-bold text-white">{task.pct}%</span>
							</div>
							<div class="h-2 w-full bg-white/5 rounded-full overflow-hidden">
								<div class="{BAR_CLASSES[task.opacity]} h-full rounded-full" style="width: {task.pct}%"></div>
							</div>
						</div>
					{/each}
				</div>
				<button class="mt-8 w-full py-2.5 rounded-lg border border-white/10 text-xs font-bold text-slate-400 hover:bg-white/5 transition-colors">
					VIEW DETAILED BREAKDOWN
				</button>
			</GlassPanel>
		</div>

		<!-- Recent Processes -->
		<GlassPanel class="mt-8 overflow-hidden" opacity={0.5} borderOpacity={0.1}>
			<div class="p-6 border-b border-white/10 flex justify-between items-center">
				<h4 class="text-lg font-bold text-white">Recent AI Processes</h4>
				<button class="text-[#6961ff] text-xs font-bold">VIEW ALL</button>
			</div>
			{#if recentProcesses.length === 0}
				<div class="p-6 text-center text-sm text-slate-400">No processes yet.</div>
			{:else}
				<div class="divide-y divide-white/5">
					{#each recentProcesses as proc}
						<div class="px-6 py-4 flex items-center gap-4">
							<div class="size-10 rounded-full overflow-hidden bg-slate-800 shrink-0 flex items-center justify-center">
								<MaterialIcon icon="smart_toy" class="text-[#6961ff]" />
							</div>
							<div class="flex-1 min-w-0">
								<p class="text-sm font-bold text-white truncate">{proc.name}</p>
								<p class="text-xs text-slate-500">{proc.action}</p>
							</div>
							<div class="text-right">
								<StatusBadge label={proc.status} color={proc.statusColor} />
								<p class="text-[10px] text-slate-500 uppercase mt-1">{proc.time}</p>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</GlassPanel>
	</div>
</div>