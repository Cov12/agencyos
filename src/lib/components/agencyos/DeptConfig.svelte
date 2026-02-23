<script lang="ts">
	import { departments, activeDeptId, activeDept } from '$lib/stores/agencyos';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	let sidebarOpen = false;
	let activeTab = 'overview';
	let autoPropose = 85;
	let requireApproval = 60;
	let temperature = 70;
	let selectedModel = 'GPT-4o (Default)';
	let systemPrompt = `You are the lead AI Agent for the Sales & Admin department. Your core directive is to optimize response times for inbound leads while maintaining a 100% professional tone. You have access to the company pricing guide and CRM. When dealing with quotes above $50k, always defer to the department head for final approval.`;

	const tabs = ['Overview', 'Knowledge Base', 'Tools & Permissions', 'Delegation Rules', 'AI Config'];

	function toggleSidebar() { sidebarOpen = !sidebarOpen; }

	$: currentDeptName = $activeDept?.name ?? 'Select Department';
</script>

<div class="w-full h-full flex overflow-hidden relative"
	style="background: rgba(28, 28, 33, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05);"
>
	<!-- Mobile Overlay -->
	{#if sidebarOpen}
		<button class="fixed inset-0 bg-black/50 z-30 lg:hidden" on:click={toggleSidebar}></button>
	{/if}

	<!-- Sidebar -->
	<aside class="w-72 border-r border-white/5 flex flex-col bg-black/20 {sidebarOpen ? 'fixed inset-y-0 left-0 z-40' : 'hidden lg:flex'}">
		<div class="p-6 flex items-center gap-3">
			<div class="w-10 h-10 rounded-xl bg-[#6961ff] flex items-center justify-center">
				<MaterialIcon icon="deployed_code" class="text-white" />
			</div>
			<div>
				<h1 class="font-bold text-lg tracking-tight text-white">AgencyOS</h1>
				<p class="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Organization OS</p>
			</div>
		</div>

		<nav class="flex-1 px-4 py-2 space-y-1 overflow-y-auto">
			<p class="px-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">Departments</p>
			{#each $departments as dept}
				<button
					class="flex items-center justify-between px-3 py-2.5 rounded-lg w-full transition-all
						{dept.id === $activeDeptId ? 'bg-[#6961ff]/10 border border-[#6961ff]/20 text-white' : 'hover:bg-white/5 text-slate-400 hover:text-white border border-transparent'}"
					on:click={() => ($activeDeptId = dept.id)}
				>
					<div class="flex items-center gap-3">
						<MaterialIcon icon={dept.icon} class="{dept.id === $activeDeptId ? 'text-[#6961ff]' : 'text-slate-500'}" size={20} />
						<span class="text-sm font-medium">{dept.name}</span>
					</div>
					<div class="w-2 h-2 rounded-full bg-[#20B2AA] {dept.status === 'active' ? 'animate-pulse' : 'opacity-40'}"></div>
				</button>
			{/each}
		</nav>

		<div class="p-4 border-t border-white/5">
			<button class="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-dashed border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 transition-all text-sm">
				<MaterialIcon icon="add_circle" size={16} />
				New Department
			</button>
		</div>
	</aside>

	<!-- Main -->
	<main class="flex-1 flex flex-col min-w-0">
		<header class="h-16 md:h-20 border-b border-white/5 flex items-center justify-between px-4 md:px-8 bg-black/10">
			<div class="flex items-center gap-3">
				<button on:click={toggleSidebar} class="lg:hidden p-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400">
					<MaterialIcon icon="menu" />
				</button>
				<div>
					<h2 class="text-lg md:text-xl font-bold text-white tracking-tight">{currentDeptName}</h2>
					<p class="text-xs md:text-sm text-slate-400">Configure agents and knowledge for this department</p>
				</div>
			</div>
			<div class="flex items-center gap-2 md:gap-4">
				<button class="hidden sm:flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-white font-semibold text-sm border border-white/5">
					<MaterialIcon icon="play_circle" size={20} />
					Test Agent
				</button>
				<button class="flex items-center gap-2 px-3 md:px-5 py-2 md:py-2.5 rounded-xl bg-[#6961ff] hover:bg-[#6961ff]/90 text-white font-bold text-sm shadow-lg shadow-[#6961ff]/20">
					<MaterialIcon icon="save" size={20} />
					<span class="hidden sm:inline">Save Changes</span>
				</button>
			</div>
		</header>

		<!-- Tabs -->
		<div class="px-4 md:px-8 border-b border-white/5 bg-black/5 overflow-x-auto">
			<div class="flex gap-4 md:gap-8 min-w-max">
				{#each tabs as tab}
					{@const tabId = tab.toLowerCase().replace(/ & | /g, '-')}
					<button
						class="py-4 text-sm font-semibold transition-colors border-b-2
							{activeTab === tabId ? 'text-[#6961ff] border-[#6961ff] font-bold' : 'text-slate-400 hover:text-slate-200 border-transparent'}"
						on:click={() => (activeTab = tabId)}
					>
						{tab}
					</button>
				{/each}
			</div>
		</div>

		<!-- Content -->
		<div class="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 md:space-y-8">
			<!-- Agent Card -->
			<div class="grid grid-cols-12 gap-6">
				<div class="col-span-12 lg:col-span-7 p-4 md:p-6 rounded-2xl bg-white/5 border border-white/5 flex flex-col sm:flex-row items-start gap-4 md:gap-6">
					<div class="relative">
						<div class="w-24 h-24 rounded-2xl bg-gradient-to-br from-[#6961ff] to-purple-600 flex items-center justify-center">
							<MaterialIcon icon="smart_toy" size={40} class="text-white" />
						</div>
						<div class="absolute -bottom-2 -right-2">
							<StatusBadge label={$activeDept?.status === 'active' ? 'Active' : 'Setup'} color={$activeDept?.status === 'active' ? 'green' : 'yellow'} size="md" />
						</div>
					</div>
					<div class="flex-1">
						<h3 class="text-xl font-bold text-white">Agent Smith</h3>
						<p class="text-slate-400 text-sm">Department Head Agent • Lead Negotiator</p>
						<div class="mt-4 flex flex-wrap gap-4">
							<div class="px-3 py-1.5 rounded-lg bg-black/30 border border-white/5 flex items-center gap-2">
								<MaterialIcon icon="bolt" size={16} class="text-[#6961ff]" />
								<span class="text-xs font-medium text-white">94% Efficiency</span>
							</div>
							<div class="px-3 py-1.5 rounded-lg bg-black/30 border border-white/5 flex items-center gap-2">
								<MaterialIcon icon="check_circle" size={16} class="text-[#20B2AA]" />
								<span class="text-xs font-medium text-white">1,284 Tasks Completed</span>
							</div>
						</div>
					</div>
				</div>

				<div class="col-span-12 lg:col-span-5 grid grid-cols-2 gap-4">
					<div class="p-5 rounded-2xl bg-white/5 border border-white/5 flex flex-col justify-between">
						<span class="text-slate-500 text-xs font-bold uppercase tracking-wider">Uptime</span>
						<div class="mt-2">
							<span class="text-2xl font-black text-white">99.9%</span>
							<p class="text-[10px] text-[#20B2AA] font-medium mt-1">Status: Stable</p>
						</div>
					</div>
					<div class="p-5 rounded-2xl bg-white/5 border border-white/5 flex flex-col justify-between">
						<span class="text-slate-500 text-xs font-bold uppercase tracking-wider">Avg Response</span>
						<div class="mt-2">
							<span class="text-2xl font-black text-white">1.4s</span>
							<p class="text-[10px] text-[#6961ff] font-medium mt-1">Fast Processing</p>
						</div>
					</div>
				</div>
			</div>

			<!-- Delegation -->
			<div class="space-y-4">
				<h3 class="text-lg font-bold text-white flex items-center gap-2">
					<MaterialIcon icon="rule" class="text-[#6961ff]" />
					Delegation Thresholds
				</h3>
				<div class="p-6 rounded-2xl bg-white/5 border border-white/5 space-y-8">
					<div class="space-y-4">
						<div class="flex justify-between items-center">
							<label class="text-sm font-semibold text-slate-200">Auto-propose Threshold</label>
							<span class="text-sm font-bold text-[#6961ff] bg-[#6961ff]/10 px-3 py-1 rounded-full">{autoPropose}% Confidence</span>
						</div>
						<input type="range" bind:value={autoPropose} class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#6961ff]" />
					</div>
					<div class="space-y-4">
						<div class="flex justify-between items-center">
							<label class="text-sm font-semibold text-slate-200">Require Approval Threshold</label>
							<span class="text-sm font-bold text-[#6961ff] bg-[#6961ff]/10 px-3 py-1 rounded-full">{requireApproval}% Confidence</span>
						</div>
						<input type="range" bind:value={requireApproval} class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#6961ff]" />
					</div>
				</div>
			</div>

			<!-- AI Config -->
			<div class="space-y-4">
				<h3 class="text-lg font-bold text-white flex items-center gap-2">
					<MaterialIcon icon="psychology" class="text-[#6961ff]" />
					AI Engine Configuration
				</h3>
				<div class="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
					<div class="lg:col-span-1 space-y-4">
						<div>
							<label class="block text-xs font-bold text-slate-500 uppercase mb-2">Model Selection</label>
							<select bind:value={selectedModel} class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-[#6961ff] focus:ring-0 text-white">
								<option>GPT-4o (Default)</option>
								<option>Claude 3.5 Sonnet</option>
								<option>Llama 3 (Experimental)</option>
							</select>
						</div>
						<div>
							<div class="flex justify-between mb-2">
								<label class="text-xs font-bold text-slate-500 uppercase">Temperature</label>
								<span class="text-xs font-bold text-[#6961ff]">{(temperature / 100).toFixed(1)}</span>
							</div>
							<input type="range" bind:value={temperature} min="0" max="100" class="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#6961ff]" />
						</div>
					</div>
					<div class="lg:col-span-2">
						<label class="block text-xs font-bold text-slate-500 uppercase mb-2">System Prompt Preview</label>
						<textarea
							bind:value={systemPrompt}
							class="w-full bg-[#6961ff]/5 border border-white/10 rounded-xl p-4 text-xs font-mono text-slate-400 h-32 focus:ring-0 resize-none leading-relaxed focus:border-[#6961ff]/50"
							spellcheck="false"
						></textarea>
					</div>
				</div>
			</div>
		</div>

		<footer class="h-10 border-t border-white/5 bg-black/20 flex items-center justify-between px-6 shrink-0">
			<div class="flex items-center gap-4 text-[10px] font-medium text-slate-500">
				<div class="flex items-center gap-1.5">
					<div class="w-1.5 h-1.5 rounded-full bg-[#20B2AA]"></div>
					<span>Engine: Synchronized</span>
				</div>
			</div>
			<div class="text-[10px] font-medium text-slate-600">AgencyOS v2.4.1 (Stable)</div>
		</footer>
	</main>
</div>
