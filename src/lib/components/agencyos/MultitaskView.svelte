<script lang="ts">
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	let chatInput = '';

	// KPI color map (Tailwind purge safe)
	const KPI_STYLES: Record<string, { badge: string; bar: string }> = {
		green:  { badge: 'bg-green-500/10 text-green-400', bar: 'bg-gradient-to-r from-green-500 to-green-400' },
		indigo: { badge: 'bg-indigo-500/10 text-indigo-400', bar: 'bg-gradient-to-r from-indigo-500 to-indigo-400' },
		orange: { badge: 'bg-orange-500/10 text-orange-400', bar: 'bg-gradient-to-r from-orange-500 to-orange-400' },
	};

	const kpis = [
		{ label: 'Total Revenue', value: '$48,290', change: '+12.5%', color: 'green', pct: 75 },
		{ label: 'Active Users', value: '12,402', change: '+5.2%', color: 'indigo', pct: 45 },
		{ label: 'Tasks Completed', value: '892', change: '-1.2%', color: 'orange', pct: 60 },
	];
</script>

<div class="w-full h-full flex gap-4 p-4 md:p-6 overflow-hidden">
	<!-- Left: Chat -->
	<section class="flex-1 rounded-2xl flex flex-col shadow-2xl overflow-hidden"
		style="background: rgba(30, 30, 36, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08);"
	>
		<div class="h-12 bg-[#2b2839]/50 border-b border-white/5 flex items-center justify-between px-4 shrink-0">
			<div class="flex items-center gap-2">
				<div class="w-3 h-3 rounded-full bg-[#FF5F57]"></div>
				<div class="w-3 h-3 rounded-full bg-[#FEBC2E]"></div>
				<div class="w-3 h-3 rounded-full bg-[#28C840]"></div>
			</div>
			<div class="flex items-center gap-2 opacity-70">
				<MaterialIcon icon="smart_toy" size={14} />
				<span class="text-xs font-semibold tracking-wide text-white">AgencyGPT</span>
			</div>
			<div class="w-10"></div>
		</div>

		<div class="flex-1 overflow-y-auto p-6 space-y-6 bg-[#1e1e24]/90">
			<div class="flex justify-center">
				<span class="text-[10px] font-medium text-slate-500 uppercase tracking-widest bg-[#2b2839]/50 px-3 py-1 rounded-full">Today</span>
			</div>

			<!-- AI Message -->
			<div class="flex gap-4 items-start max-w-[90%]">
				<div class="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 shadow-lg">
					<MaterialIcon icon="smart_toy" size={14} class="text-white" />
				</div>
				<div class="space-y-1">
					<div class="flex items-baseline gap-2">
						<span class="text-sm font-semibold text-white">AgencyGPT</span>
						<span class="text-xs text-slate-500">10:30 AM</span>
					</div>
					<div class="bg-[#2b2839] p-4 rounded-2xl rounded-tl-none text-sm text-slate-200 leading-relaxed border border-white/5">
						<p>Good morning! I've analyzed the Q3 performance metrics. We're seeing a <strong>15% increase</strong> in user retention across the mobile segment.</p>
						<p class="mt-2">Would you like me to generate a comparative report?</p>
					</div>
					<div class="flex gap-2 mt-2">
						<button class="px-3 py-1.5 bg-[#2b2839] hover:bg-white/10 border border-white/5 rounded-lg text-xs font-medium text-indigo-300 transition-colors">Generate Report</button>
						<button class="px-3 py-1.5 bg-[#2b2839] hover:bg-white/10 border border-white/5 rounded-lg text-xs font-medium text-indigo-300 transition-colors">Draft Strategy</button>
					</div>
				</div>
			</div>

			<!-- User Message -->
			<div class="flex gap-4 items-start justify-end max-w-[90%] ml-auto">
				<div class="space-y-1 items-end flex flex-col">
					<div class="bg-[#3713ec] p-4 rounded-2xl rounded-tr-none text-sm text-white leading-relaxed shadow-md shadow-[#3713ec]/20">
						<p>Let's focus on the comparative report first. Highlight the mobile growth specifically.</p>
					</div>
				</div>
			</div>

			<!-- Typing -->
			<div class="flex gap-4 items-end max-w-[90%]">
				<div class="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 shadow-lg mb-1">
					<MaterialIcon icon="smart_toy" size={14} class="text-white" />
				</div>
				<div class="bg-[#2b2839] px-4 py-3 rounded-2xl rounded-bl-none border border-white/5 flex items-center gap-1">
					<div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></div>
					<div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 75ms"></div>
					<div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
				</div>
			</div>
		</div>

		<!-- Input -->
		<div class="p-4 bg-[#2b2839]/30 backdrop-blur-md border-t border-white/5">
			<div class="relative flex items-center">
				<button class="absolute left-3 text-slate-400 hover:text-white transition-colors">
					<MaterialIcon icon="add_circle" />
				</button>
				<input bind:value={chatInput} class="w-full bg-[#1e1e24]/80 text-white placeholder-slate-500 rounded-xl py-3 pl-10 pr-12 focus:outline-none focus:ring-2 focus:ring-[#6961ff]/50 border border-white/5 text-sm" placeholder="Message AgencyGPT..." />
				<button class="absolute right-2 p-1.5 bg-[#3713ec] hover:bg-[#3713ec]/80 text-white rounded-lg transition-colors shadow-lg">
					<MaterialIcon icon="arrow_upward" size={18} />
				</button>
			</div>
		</div>
	</section>

	<!-- Divider -->
	<div class="w-2 flex flex-col justify-center items-center cursor-col-resize group hover:w-3 transition-all">
		<div class="h-16 w-1 rounded-full bg-white/10 group-hover:bg-[#6961ff]/50 transition-colors"></div>
	</div>

	<!-- Right: Analytics -->
	<section class="flex-1 rounded-2xl flex flex-col shadow-2xl overflow-hidden"
		style="background: rgba(30, 30, 36, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08);"
	>
		<div class="h-12 bg-[#2b2839]/50 border-b border-white/5 flex items-center justify-between px-4 shrink-0">
			<div class="flex items-center gap-2">
				<div class="w-3 h-3 rounded-full bg-[#FF5F57] opacity-50"></div>
				<div class="w-3 h-3 rounded-full bg-[#FEBC2E] opacity-50"></div>
				<div class="w-3 h-3 rounded-full bg-[#28C840] opacity-50"></div>
			</div>
			<div class="flex items-center gap-2 opacity-70">
				<MaterialIcon icon="monitoring" size={14} />
				<span class="text-xs font-semibold tracking-wide text-white">Performance</span>
			</div>
			<div class="flex items-center gap-3 text-slate-400">
				<MaterialIcon icon="refresh" size={16} class="cursor-pointer hover:text-white" />
				<MaterialIcon icon="more_horiz" size={16} class="cursor-pointer hover:text-white" />
			</div>
		</div>

		<div class="flex-1 overflow-y-auto bg-[#18181d] p-6">
			<!-- KPIs (purge-safe) -->
			<div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-6">
				{#each kpis as kpi}
					{@const styles = KPI_STYLES[kpi.color] ?? KPI_STYLES.green}
					<div class="bg-[#2b2839] p-4 rounded-xl border border-white/5 hover:border-[#6961ff]/30 transition-colors">
						<div class="flex justify-between items-start mb-2">
							<span class="text-xs font-medium text-slate-400">{kpi.label}</span>
							<span class="p-1 rounded {styles.badge} text-[10px] font-bold">{kpi.change}</span>
						</div>
						<h3 class="text-2xl font-bold text-white mb-1">{kpi.value}</h3>
						<div class="h-1 w-full bg-white/5 rounded-full overflow-hidden mt-2">
							<div class="{styles.bar} h-full rounded-full" style="width: {kpi.pct}%"></div>
						</div>
					</div>
				{/each}
			</div>

			<!-- Bar Chart -->
			<div class="bg-[#2b2839] rounded-xl border border-white/5 p-5 mb-6">
				<div class="flex items-center justify-between mb-6">
					<h4 class="text-sm font-semibold text-white">Revenue Overview</h4>
					<div class="flex bg-[#1e1e24] rounded-lg p-0.5 border border-white/5">
						<button class="px-3 py-1 text-[10px] font-medium rounded text-white bg-white/10 shadow-sm">Weekly</button>
						<button class="px-3 py-1 text-[10px] font-medium rounded text-slate-400">Monthly</button>
					</div>
				</div>
				<div class="h-48 w-full flex items-end gap-2 relative px-2">
					{#each [40, 65, 50, 85, 60, 75, 45] as h, i}
						<div class="flex-1 {i === 3 ? 'bg-[#3713ec] shadow-[0_0_15px_rgba(55,19,236,0.5)]' : 'bg-indigo-500/20 hover:bg-indigo-500/40'} rounded-t-sm transition-all" style="height: {h}%"></div>
					{/each}
				</div>
				<div class="flex justify-between mt-2 text-[10px] text-slate-500 uppercase font-medium px-2">
					{#each ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as day}
						<span>{day}</span>
					{/each}
				</div>
			</div>

			<!-- Transactions -->
			<div class="space-y-3">
				<h4 class="text-sm font-semibold text-white px-1">Recent Transactions</h4>
				<div class="bg-[#2b2839] rounded-xl border border-white/5 p-3 flex items-center justify-between hover:bg-white/5 transition-colors cursor-pointer">
					<div class="flex items-center gap-3">
						<div class="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center">
							<MaterialIcon icon="payments" size={16} class="text-blue-400" />
						</div>
						<div class="flex flex-col">
							<span class="text-xs font-medium text-white">Stripe Payout</span>
							<span class="text-[10px] text-slate-500">Today, 9:42 AM</span>
						</div>
					</div>
					<span class="text-xs font-medium text-green-400">+$1,250.00</span>
				</div>
				<div class="bg-[#2b2839] rounded-xl border border-white/5 p-3 flex items-center justify-between hover:bg-white/5 transition-colors cursor-pointer">
					<div class="flex items-center gap-3">
						<div class="w-8 h-8 rounded-full bg-purple-500/10 flex items-center justify-center">
							<MaterialIcon icon="cloud_upload" size={16} class="text-purple-400" />
						</div>
						<div class="flex flex-col">
							<span class="text-xs font-medium text-white">AWS Invoice</span>
							<span class="text-[10px] text-slate-500">Yesterday, 4:20 PM</span>
						</div>
					</div>
					<span class="text-xs font-medium text-slate-300">-$240.00</span>
				</div>
			</div>
		</div>
	</section>
</div>
