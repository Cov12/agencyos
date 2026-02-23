<script lang="ts">
	import { departments, activeDeptId, activeDept } from '$lib/stores/agencyos';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';

	interface ChatMessage {
		id: string;
		role: 'ai' | 'user';
		persona?: string;
		content: string;
		time: string;
		actions?: string[];
		dataCard?: { label: string; value: string; progress: number; months: string[] };
	}

	let messageInput = '';

	const personas = [
		{ id: 'chief', label: 'Chief AI', icon: 'psychology' },
		{ id: 'sales', label: 'Sales', icon: 'trending_up' },
		{ id: 'customer', label: 'Customer', icon: 'support_agent' },
		{ id: 'backoffice', label: 'Back Office', icon: 'inventory_2' },
	];

	// Default to chief if no dept selected
	$: if (!$activeDeptId) $activeDeptId = 'chief';

	const threads = [
		{ id: '1', title: 'Q3 Strategy Draft', subtitle: 'Analyzing the data...', icon: 'smart_toy', active: true, time: '' },
		{ id: '2', title: 'Lead Gen Sequence', subtitle: 'Email 3 draft ready', icon: 'campaign', active: false, time: '2h' },
		{ id: '3', title: 'Invoice Automation', subtitle: 'Updated workflow settings', icon: 'receipt_long', active: false, time: 'Yesterday' },
		{ id: '4', title: 'HR Policy Review', subtitle: 'Feedback incorporated', icon: 'groups', active: false, time: 'Mon' },
	];

	const messages: ChatMessage[] = [
		{
			id: '1', role: 'ai', persona: 'Chief AI',
			content: 'Good morning, Alex. I\'ve reviewed your request for the Q3 strategy draft. Would you like to focus on aggressive market expansion or retention optimization first?',
			time: '10:23 AM',
		},
		{
			id: '2', role: 'user',
			content: 'Generate a Q3 sales forecast based on last month\'s leads. Let\'s assume a 15% increase in conversion rate.',
			time: '10:25 AM',
		},
		{
			id: '3', role: 'ai', persona: 'Chief AI',
			content: 'Based on a 15% conversion rate increase in June and the new marketing spend, here is the projection for Q3:',
			time: '10:26 AM',
			actions: ['Yes, by region', 'Export to PDF'],
			dataCard: { label: 'Projected Revenue', value: '$1.2M', progress: 75, months: ['July', 'Aug', 'Sept'] },
		},
	];

	$: currentPersonaLabel = $activeDept?.name ?? 'Chief AI';
	$: placeholder = `Message ${currentPersonaLabel}...`;
</script>

<div class="w-full h-full flex bg-gradient-to-br from-[#2d2b42] to-[#0f0f13] relative overflow-hidden">
	<!-- Background Decor -->
	<div class="absolute inset-0 pointer-events-none overflow-hidden">
		<div class="absolute top-[-20%] left-[-10%] w-[50vw] h-[50vw] bg-[#6961ff]/20 rounded-full blur-[120px] mix-blend-screen opacity-40"></div>
		<div class="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-[#20B2AA]/10 rounded-full blur-[100px] mix-blend-screen opacity-30"></div>
	</div>

	<!-- Thread Sidebar -->
	<aside class="w-full md:w-[280px] lg:w-[320px] flex-shrink-0 flex flex-col h-full z-20 hidden md:flex"
		style="background: rgba(15, 15, 20, 0.85); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border-right: 1px solid rgba(255, 255, 255, 0.08);"
	>
		<div class="h-16 flex items-center px-5 gap-4 border-b border-white/[0.08]">
			<div class="flex gap-2">
				<div class="w-3 h-3 rounded-full bg-[#FF5F57]"></div>
				<div class="w-3 h-3 rounded-full bg-[#FEBC2E]"></div>
				<div class="w-3 h-3 rounded-full bg-[#28C840]"></div>
			</div>
			<div class="text-xs font-semibold tracking-wide text-white/50 ml-2 uppercase">AgencyOS</div>
		</div>

		<div class="px-4 py-4">
			<div class="relative">
				<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-white/40 text-[18px]">search</span>
				<input class="w-full bg-white/5 border border-white/5 rounded-lg py-2 pl-9 pr-3 text-sm text-white placeholder-white/30 focus:outline-none focus:ring-1 focus:ring-[#6961ff]/50 focus:bg-white/10 transition-all" placeholder="Search threads..." />
			</div>
		</div>

		<div class="flex-1 overflow-y-auto px-3 pb-4 space-y-1">
			<div class="px-3 py-2 text-xs font-medium text-white/40 uppercase tracking-wider mb-1">Recent</div>
			{#each threads as thread}
				<button class="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left group transition-all {thread.active ? 'bg-[#6961ff]/20 border border-[#6961ff]/20' : 'hover:bg-white/5 border border-transparent'}">
					<div class="w-8 h-8 rounded-full {thread.active ? 'bg-gradient-to-br from-indigo-500 to-purple-600' : 'bg-white/10'} flex items-center justify-center flex-shrink-0">
						<MaterialIcon icon={thread.icon} size={16} class="text-white{thread.active ? '' : '/70'}" />
					</div>
					<div class="flex-1 min-w-0">
						<h4 class="text-sm font-medium text-white{thread.active ? '' : '/90'} truncate">{thread.title}</h4>
						<p class="text-xs {thread.active ? 'text-[#6961ff]/80' : 'text-white/40'} truncate">{thread.subtitle}</p>
					</div>
					{#if thread.time}
						<span class="text-[10px] text-white/30 whitespace-nowrap">{thread.time}</span>
					{/if}
				</button>
			{/each}
		</div>
	</aside>

	<!-- Main Chat Area -->
	<main class="flex-1 flex flex-col relative z-10">
		<!-- Persona Switcher (wired to store) -->
		<div class="absolute top-0 left-0 right-0 z-20 flex justify-center py-4 px-6 bg-gradient-to-b from-[rgba(20,20,25,0.9)] to-transparent h-24 pointer-events-none">
			<div class="bg-[#1c1c21]/80 backdrop-blur-md rounded-xl p-1 inline-flex shadow-lg ring-1 ring-white/10 pointer-events-auto">
				{#each personas as persona}
					<button
						class="px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2
							{$activeDeptId === persona.id ? 'bg-[#6961ff] text-white shadow-sm' : 'text-white/60 hover:text-white'}"
						on:click={() => ($activeDeptId = persona.id)}
					>
						<MaterialIcon icon={persona.icon} size={18} />
						{persona.label}
					</button>
				{/each}
			</div>
		</div>

		<!-- Messages -->
		<div class="flex-1 overflow-y-auto px-6 md:px-12 pt-28 pb-32 flex flex-col gap-6">
			<div class="flex justify-center">
				<span class="text-xs font-medium text-white/30 bg-white/5 px-3 py-1 rounded-full">Today, 10:23 AM</span>
			</div>

			{#each messages as msg}
				{#if msg.role === 'ai'}
					<div class="flex gap-4 items-start max-w-[85%]">
						<div class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg border border-white/10">
							<MaterialIcon icon="smart_toy" size={20} class="text-white" />
						</div>
						<div class="flex flex-col gap-1">
							<span class="text-xs text-white/50 ml-1 font-medium">{msg.persona}</span>
							<div class="bg-[#2a2a35] text-slate-200 p-4 rounded-2xl rounded-tl-none shadow-md border border-white/5 leading-relaxed text-[15px]">
								<p>{msg.content}</p>
								{#if msg.dataCard}
									<div class="bg-black/20 rounded-xl p-3 border border-white/5 mt-3 mb-2">
										<div class="flex justify-between items-end mb-2">
											<div class="text-xs text-white/60">{msg.dataCard.label}</div>
											<div class="text-lg font-bold text-[#20B2AA] flex items-center gap-1">
												{msg.dataCard.value}
												<MaterialIcon icon="arrow_upward" size={16} />
											</div>
										</div>
										<div class="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
											<div class="h-full bg-[#20B2AA] rounded-full" style="width: {msg.dataCard.progress}%"></div>
										</div>
										<div class="flex justify-between text-[10px] text-white/40 mt-1">
											{#each msg.dataCard.months as month}
												<span>{month}</span>
											{/each}
										</div>
									</div>
								{/if}
							</div>
							{#if msg.actions}
								<div class="flex gap-2 mt-1 ml-1">
									{#each msg.actions as action}
										<button class="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 text-xs text-white/70 transition-colors">
											{action}
										</button>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{:else}
					<div class="flex gap-4 items-end justify-end max-w-[85%] self-end">
						<div class="flex flex-col gap-1 items-end">
							<div class="bg-[#6961ff] text-white p-4 rounded-2xl rounded-tr-none shadow-lg shadow-[#6961ff]/20 leading-relaxed text-[15px]">
								{msg.content}
							</div>
							<span class="text-xs text-white/30 mr-1">Read {msg.time}</span>
						</div>
					</div>
				{/if}
			{/each}
		</div>

		<!-- Input Area -->
		<div class="absolute bottom-6 left-0 right-0 px-6 md:px-12 flex justify-center">
			<GlassPanel opacity={0.7} blur={12} borderOpacity={0.1} class="w-full max-w-3xl p-2 shadow-2xl flex items-end gap-2 ring-1 ring-white/10">
				<button class="h-10 w-10 flex items-center justify-center rounded-xl text-white/50 hover:text-white hover:bg-white/10 transition-all mb-0.5">
					<MaterialIcon icon="add_circle" />
				</button>
				<textarea
					bind:value={messageInput}
					class="flex-1 bg-transparent border-0 text-white placeholder-white/40 focus:ring-0 resize-none py-3 max-h-32 text-base leading-normal"
					{placeholder}
					rows="1"
				></textarea>
				<div class="flex items-center gap-2 mb-0.5">
					<button class="relative h-10 w-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 transition-all">
						<MaterialIcon icon="mic" class="text-[#20B2AA]" />
					</button>
					<button class="h-10 w-10 flex items-center justify-center rounded-xl bg-[#6961ff] hover:bg-[#5851d8] text-white transition-all shadow-lg shadow-[#6961ff]/20">
						<MaterialIcon icon="arrow_upward" size={20} />
					</button>
				</div>
			</GlassPanel>
		</div>
	</main>
</div>
