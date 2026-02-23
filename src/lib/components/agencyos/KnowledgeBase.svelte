<script lang="ts">
	import { departments } from '$lib/stores/agencyos';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	// Derive silos from departments store
	$: silos = $departments.map(dept => ({
		name: `${dept.name} Silo`,
		desc: `Knowledge base for ${dept.description.toLowerCase()}.`,
		docs: `${Math.floor(Math.random() * 500 + 50)} documents`,
		status: dept.status === 'active' ? 'Live Sync' : 'Pending Setup',
		statusColor: dept.status === 'active' ? 'green' : 'yellow',
		icon: dept.icon,
		gradient: dept.gradient,
	}));

	$: stats = [
		{ label: 'Total Documents', value: '—', change: '—', icon: 'description', iconBg: 'bg-blue-900/20', iconColor: 'text-blue-500' },
		{ label: 'Active Silos', value: String($departments.filter(d => d.status === 'active').length), icon: 'dns', iconBg: 'bg-purple-900/20', iconColor: 'text-purple-500' },
		{ label: 'Total Departments', value: String($departments.length), icon: 'domain', iconBg: 'bg-orange-900/20', iconColor: 'text-orange-500' },
	];

	let activeFilter = 'All Knowledge';

	const sidebarItems = [
		{ label: 'All Knowledge', icon: 'folder_open' },
		{ label: 'Shared', icon: 'group' },
	];

	$: deptSidebarItems = $departments.map(d => ({ label: `${d.name} Silo`, icon: d.icon }));
	$: allSidebarItems = [...sidebarItems, ...deptSidebarItems];
</script>

<div class="w-full h-full flex overflow-hidden">
	<!-- Sidebar -->
	<div class="w-[260px] flex-shrink-0 border-r border-white/10 flex-col justify-between hidden lg:flex"
		style="background: rgba(17, 33, 32, 0.85); backdrop-filter: blur(12px);"
	>
		<div>
			<div class="h-14 flex items-center px-5 gap-2">
				<div class="w-3 h-3 rounded-full bg-[#FF5F57]"></div>
				<div class="w-3 h-3 rounded-full bg-[#FEBC2E]"></div>
				<div class="w-3 h-3 rounded-full bg-[#28C840]"></div>
			</div>
			<div class="px-3 py-2 flex flex-col gap-1">
				<div class="px-3 py-1 mb-2">
					<h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Library</h2>
				</div>
				{#each allSidebarItems as item}
					{@const isActive = item.label === activeFilter}
					<button
						class="flex items-center gap-3 px-3 py-2 rounded-lg transition-all w-full text-left {isActive ? 'bg-white/5 shadow-sm border border-white/5' : 'hover:bg-white/5 border border-transparent'}"
						on:click={() => activeFilter = item.label}
					>
						<MaterialIcon icon={item.icon} size={20} class="{isActive ? 'text-[#20B2AA]' : 'text-slate-500'}" />
						<span class="text-sm font-medium {isActive ? 'text-slate-100' : 'text-slate-400'}">{item.label}</span>
					</button>
				{/each}
			</div>
		</div>
		<div class="p-4">
			<GlassPanel class="p-4" opacity={0.4}>
				<div class="flex items-center gap-2 mb-2">
					<MaterialIcon icon="cloud_sync" size={18} class="text-[#20B2AA]" />
					<span class="text-xs font-bold text-slate-200">Storage Used</span>
				</div>
				<div class="w-full bg-slate-700 rounded-full h-1.5 mb-2 overflow-hidden">
					<div class="bg-[#20B2AA] h-1.5 rounded-full" style="width: 75%"></div>
				</div>
				<div class="flex justify-between text-[10px] text-slate-400">
					<span>45 GB</span>
					<span>60 GB Limit</span>
				</div>
			</GlassPanel>
		</div>
	</div>

	<!-- Main Content -->
	<div class="flex-1 flex flex-col overflow-hidden">
		<div class="h-16 border-b border-white/5 flex items-center justify-between px-8 bg-black/20 backdrop-blur-sm shrink-0">
			<div class="flex items-center gap-2 text-sm text-slate-400">
				<span>AgencyOS</span>
				<MaterialIcon icon="chevron_right" size={16} />
				<span class="font-semibold text-white">Knowledge Base Silos</span>
			</div>
			<div class="flex items-center gap-3">
				<div class="relative">
					<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-[20px]">search</span>
					<input class="pl-10 pr-4 py-2 w-64 bg-white/5 border border-white/10 rounded-full text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#20B2AA]/50 placeholder:text-slate-400" placeholder="Search knowledge..." />
				</div>
				<button class="bg-[#20B2AA] hover:bg-[#20B2AA]/80 text-slate-900 font-semibold text-sm px-4 py-2 rounded-full flex items-center gap-2 transition-all shadow-sm">
					<MaterialIcon icon="add" size={20} />
					<span>New Silo</span>
				</button>
			</div>
		</div>

		<div class="flex-1 overflow-y-auto p-8">
			<div class="mb-8">
				<h1 class="text-3xl font-bold text-white tracking-tight mb-2">Knowledge Silos</h1>
				<p class="text-slate-400 max-w-2xl">Manage your organization's segmented data environments.</p>
			</div>

			<!-- Stats -->
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-10">
				{#each stats as stat}
					<div class="bg-[#1a2c2b] p-5 rounded-2xl border border-white/5 flex flex-col justify-between h-32">
						<div class="flex items-center justify-between">
							<span class="text-sm font-medium text-slate-400">{stat.label}</span>
							<div class="w-8 h-8 rounded-full {stat.iconBg} flex items-center justify-center">
								<MaterialIcon icon={stat.icon} size={20} class={stat.iconColor} />
							</div>
						</div>
						<div>
							<span class="text-3xl font-bold text-white tracking-tight">{stat.value}</span>
							{#if stat.change}
								<div class="flex items-center gap-1 mt-1">
									<span class="text-xs text-slate-400">{stat.change}</span>
								</div>
							{/if}
						</div>
					</div>
				{/each}
			</div>

			<!-- Silo Cards -->
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-12">
				{#each silos as silo}
					<div class="group bg-[#1a2c2b] rounded-[24px] p-6 border border-white/5 hover:border-[#20B2AA]/50 transition-all duration-300 cursor-pointer relative overflow-hidden">
						<div class="flex justify-between items-start mb-6 relative z-10">
							<div class="w-16 h-14 relative transform transition-transform group-hover:scale-110 duration-300">
								<div class="absolute inset-0 bg-gradient-to-br {silo.gradient} rounded-lg shadow-lg flex items-center justify-center border-t border-white/20">
									<MaterialIcon icon={silo.icon} size={28} class="text-white drop-shadow-md" />
								</div>
							</div>
							<button class="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center text-slate-400 transition-colors">
								<MaterialIcon icon="more_horiz" />
							</button>
						</div>
						<div class="relative z-10">
							<h3 class="text-xl font-bold text-white mb-1 group-hover:text-[#20B2AA] transition-colors">{silo.name}</h3>
							<p class="text-sm text-slate-400 mb-6 line-clamp-2">{silo.desc}</p>
							<div class="flex items-center justify-between border-t border-white/5 pt-4">
								<div class="flex flex-col">
									<span class="text-xs text-slate-400 font-medium uppercase tracking-wider mb-1">Sources</span>
									<span class="text-sm font-semibold text-slate-200">{silo.docs}</span>
								</div>
								<div class="flex flex-col items-end">
									<span class="text-xs text-slate-400 font-medium uppercase tracking-wider mb-1">Status</span>
									<StatusBadge label={silo.status} color={silo.statusColor} size="md" />
								</div>
							</div>
						</div>
					</div>
				{/each}

				<!-- New Silo -->
				<div class="group border-2 border-dashed border-slate-700 rounded-[24px] p-6 flex flex-col items-center justify-center min-h-[220px] hover:border-[#20B2AA] hover:bg-[#20B2AA]/5 transition-all cursor-pointer">
					<div class="w-14 h-14 rounded-full bg-white/5 flex items-center justify-center mb-4 group-hover:bg-[#20B2AA] group-hover:text-slate-900 transition-colors text-slate-400">
						<MaterialIcon icon="add" size={32} />
					</div>
					<h3 class="text-lg font-bold text-slate-400 group-hover:text-[#20B2AA]">Create New Silo</h3>
					<p class="text-xs text-slate-400 mt-2 text-center max-w-[200px]">Connect Google Drive, Slack, or upload files directly.</p>
				</div>
			</div>
		</div>
	</div>
</div>