<script lang="ts">
	import { activeDeptId, activeDept, proposals, type Proposal, activeOrgId } from '$lib/stores/agencyos';
	import { user } from '$lib/stores';
	import { sendChiefChat, sendDepartmentChat, type Proposal as ApiProposal } from '$lib/apis/agencyos';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import VoiceMode from '$lib/components/agencyos/VoiceMode.svelte';

	let voiceModeOpen = false;

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
	let sidebarOpen = false;
	let loading = false;
	let messages: ChatMessage[] = [];
	let chatId: string | undefined;


	const personas = [
		{ id: 'chief', label: 'Chief AI', icon: 'psychology' },
		{ id: 'sales', label: 'Sales', icon: 'trending_up' },
		{ id: 'customer', label: 'Customer', icon: 'support_agent' },
		{ id: 'backoffice', label: 'Back Office', icon: 'inventory_2' }
	];

	$: if (!$activeDeptId) $activeDeptId = 'chief';

	const threads = [
		{ id: '1', title: 'Q3 Strategy Draft', subtitle: 'Analyzing the data...', icon: 'smart_toy', active: true, time: '' },
		{ id: '2', title: 'Lead Gen Sequence', subtitle: 'Email 3 draft ready', icon: 'campaign', active: false, time: '2h' },
		{ id: '3', title: 'Invoice Automation', subtitle: 'Updated workflow settings', icon: 'receipt_long', active: false, time: 'Yesterday' },
		{ id: '4', title: 'HR Policy Review', subtitle: 'Feedback incorporated', icon: 'groups', active: false, time: 'Mon' }
	];

	function formatTime() {
		return new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	}

	function mapApiProposal(apiProposal: ApiProposal): Proposal {
		const mappedStatus: Proposal['status'] =
			apiProposal.status === 'pending' || apiProposal.status === 'approved' || apiProposal.status === 'rejected'
				? apiProposal.status
				: 'rejected';

		return {
			id: apiProposal.id,
			title: apiProposal.title,
			dept: apiProposal.department_id || 'chief',
			description: apiProposal.description,
			status: mappedStatus,
			createdAt: 'Just now',
			priority: apiProposal.risk_level,
			actions: [
				{ label: 'Approve', type: 'primary' },
				{ label: 'Reject', type: 'danger' },
				{ label: 'View Details', type: 'secondary' }
			] as Proposal['actions']
		};
	}

	async function sendMessage() {
		const trimmed = messageInput.trim();
		if (!trimmed || loading) return;

		const authToken = (($user as { token?: string } | undefined)?.token ?? localStorage.token) as
			| string
			| undefined;
		const currentUserId = $user?.id ?? 'anonymous';
		if (!authToken) return;

		const userMessage: ChatMessage = {
			id: crypto.randomUUID(),
			role: 'user',
			content: trimmed,
			time: formatTime()
		};

		messages = [...messages, userMessage];
		messageInput = '';
		loading = true;

		try {
			const conversation_history = [...messages]
				.slice(-10)
				.map((msg) => ({ role: msg.role === 'user' ? 'user' : 'assistant', content: msg.content }));

			const payload = {
				message: trimmed,
				user_id: currentUserId,
				chat_id: chatId,
				conversation_history
			};

			const response =
				$activeDeptId === 'chief'
					? await sendChiefChat(authToken, $activeOrgId, payload)
					: await sendDepartmentChat(authToken, $activeOrgId, $activeDeptId ?? 'chief', payload);

			chatId = response.proposals?.[0]?.chat_id ?? chatId;

			messages = [
				...messages,
				{
					id: crypto.randomUUID(),
					role: 'ai',
					persona: currentPersonaLabel,
					content: response.content,
					time: formatTime()
				}
			];

			if (response.proposals?.length) {
				const mapped = response.proposals.map(mapApiProposal);
				proposals.update((existing) => {
					const existingById = new Map(existing.map((item) => [item.id, item]));
					for (const item of mapped) existingById.set(item.id, item);
					return Array.from(existingById.values());
				});
			}
		} catch (error) {
			messages = [
				...messages,
				{
					id: crypto.randomUUID(),
					role: 'ai',
					persona: currentPersonaLabel,
					content: 'Sorry — I hit an error sending that message. Please try again.',
					time: formatTime()
				}
			];
			console.error(error);
		} finally {
			loading = false;
		}
	}

	function handleSubmit(event: SubmitEvent) {
		event.preventDefault();
		sendMessage();
	}

	$: currentPersonaLabel = $activeDept?.name ?? 'Chief AI';
	$: placeholder = loading ? `Waiting for ${currentPersonaLabel}...` : `Message ${currentPersonaLabel}...`;
</script>

<div class="w-full h-full flex bg-gradient-to-br from-[#2d2b42] to-[#0f0f13] relative overflow-hidden">
	<!-- Background Decor -->
	<div class="absolute inset-0 pointer-events-none overflow-hidden">
		<div class="absolute top-[-20%] left-[-10%] w-[50vw] h-[50vw] bg-[#6961ff]/20 rounded-full blur-[120px] mix-blend-screen opacity-40"></div>
		<div class="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-[#20B2AA]/10 rounded-full blur-[100px] mix-blend-screen opacity-30"></div>
	</div>

	<!-- Mobile sidebar overlay -->
	{#if sidebarOpen}
		<button class="fixed inset-0 bg-black/50 z-30 md:hidden" on:click={() => (sidebarOpen = false)} aria-label="Close sidebar"></button>
	{/if}

	<!-- Thread Sidebar -->
	<aside
		class="fixed md:relative w-[280px] lg:w-[320px] flex-shrink-0 flex flex-col h-full z-40 md:z-20 transition-transform duration-200 md:translate-x-0"
		class:translate-x-0={sidebarOpen}
		class:-translate-x-full={!sidebarOpen}
		style="background: rgba(15, 15, 20, 0.95); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border-right: 1px solid rgba(255, 255, 255, 0.08);"
	>
		<div class="h-14 flex items-center px-4 gap-3 border-b border-white/[0.08]">
			<div class="flex gap-2">
				<div class="w-3 h-3 rounded-full bg-[#FF5F57]"></div>
				<div class="w-3 h-3 rounded-full bg-[#FEBC2E]"></div>
				<div class="w-3 h-3 rounded-full bg-[#28C840]"></div>
			</div>
			<div class="text-xs font-semibold tracking-wide text-white/50 ml-2 uppercase">AgencyOS</div>
			<button class="ml-auto md:hidden min-h-[44px] min-w-[44px] flex items-center justify-center text-white/50" on:click={() => (sidebarOpen = false)}>
				<MaterialIcon icon="close" size={20} />
			</button>
		</div>

		<div class="px-3 py-3">
			<div class="relative">
				<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-white/40 text-[18px]">search</span>
				<input class="w-full bg-white/5 border border-white/5 rounded-lg py-2.5 pl-9 pr-3 text-sm text-white placeholder-white/30 focus:outline-none focus:ring-1 focus:ring-[#6961ff]/50 focus:bg-white/10 transition-all" placeholder="Search threads..." />
			</div>
		</div>

		<div class="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
			<div class="px-3 py-2 text-xs font-medium text-white/40 uppercase tracking-wider mb-1">Recent</div>
			{#each threads as thread}
				<button class="w-full flex items-center gap-3 px-3 py-3 min-h-[48px] rounded-lg text-left group transition-all {thread.active ? 'bg-[#6961ff]/20 border border-[#6961ff]/20' : 'hover:bg-white/5 border border-transparent'}">
					<div class="w-8 h-8 rounded-full {thread.active ? 'bg-gradient-to-br from-indigo-500 to-purple-600' : 'bg-white/10'} flex items-center justify-center flex-shrink-0">
						<MaterialIcon icon={thread.icon} size={16} class="text-white{thread.active ? '' : '/70'}" />
					</div>
					<div class="flex-1 min-w-0">
						<h4 class="text-sm font-medium text-white{thread.active ? '' : '/90'} truncate">{thread.title}</h4>
						<p class="text-xs {thread.active ? 'text-[#6961ff]/80' : 'text-white/40'} truncate">{thread.subtitle}</p>
					</div>
					{#if thread.time}
						<span class="text-[10px] text-white/30 whitespace-nowrap flex-shrink-0">{thread.time}</span>
					{/if}
				</button>
			{/each}
		</div>
	</aside>

	<!-- Main Chat Area -->
	<main class="flex-1 flex flex-col relative z-10 min-w-0">
		<!-- Top bar with hamburger + persona switcher -->
		<div class="absolute top-0 left-0 right-0 z-20 flex items-center justify-center py-3 px-3 sm:px-6 bg-gradient-to-b from-[rgba(20,20,25,0.9)] to-transparent h-20 sm:h-24 pointer-events-none">
			<!-- Mobile hamburger -->
			<button
				class="pointer-events-auto absolute left-3 top-3 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl text-white/60 hover:text-white hover:bg-white/10 transition-all md:hidden"
				on:click={() => (sidebarOpen = true)}
			>
				<MaterialIcon icon="menu" size={24} />
			</button>

			<div class="bg-[#1c1c21]/80 backdrop-blur-md rounded-xl p-1 inline-flex shadow-lg ring-1 ring-white/10 pointer-events-auto overflow-x-auto max-w-[calc(100vw-6rem)] sm:max-w-none scrollbar-hide">
				{#each personas as persona}
					<button
						class="px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 sm:gap-2 whitespace-nowrap min-h-[40px]
							{$activeDeptId === persona.id ? 'bg-[#6961ff] text-white shadow-sm' : 'text-white/60 hover:text-white'}"
						on:click={() => ($activeDeptId = persona.id)}
					>
						<MaterialIcon icon={persona.icon} size={18} />
						<span class="hidden sm:inline">{persona.label}</span>
					</button>
				{/each}
			</div>
		</div>

		<!-- Messages -->
		<div class="flex-1 overflow-y-auto px-3 sm:px-6 md:px-12 pt-24 sm:pt-28 pb-28 sm:pb-32 flex flex-col gap-4 sm:gap-6">
			<div class="flex justify-center">
				<span class="text-xs font-medium text-white/30 bg-white/5 px-3 py-1 rounded-full">Today, 10:23 AM</span>
			</div>

			{#each messages as msg}
				{#if msg.role === 'ai'}
					<div class="flex gap-2.5 sm:gap-4 items-start max-w-[95%] sm:max-w-[85%]">
						<div class="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg border border-white/10">
							<MaterialIcon icon="smart_toy" size={18} class="text-white" />
						</div>
						<div class="flex flex-col gap-1 min-w-0">
							<span class="text-xs text-white/50 ml-1 font-medium">{msg.persona}</span>
							<div class="bg-[#2a2a35] text-slate-200 p-3 sm:p-4 rounded-2xl rounded-tl-none shadow-md border border-white/5 leading-relaxed text-sm sm:text-[15px] break-words">
								<p>{msg.content}</p>
								{#if msg.dataCard}
									<div class="bg-black/20 rounded-xl p-3 border border-white/5 mt-3 mb-2">
										<div class="flex justify-between items-end mb-2 gap-2">
											<div class="text-xs text-white/60 truncate">{msg.dataCard.label}</div>
											<div class="text-base sm:text-lg font-bold text-[#20B2AA] flex items-center gap-1 flex-shrink-0">
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
								<div class="flex flex-wrap gap-2 mt-1 ml-1">
									{#each msg.actions as action}
										<button class="px-3 py-2 min-h-[44px] rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 text-xs text-white/70 transition-colors">
											{action}
										</button>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{:else}
					<div class="flex gap-2.5 sm:gap-4 items-end justify-end max-w-[95%] sm:max-w-[85%] self-end">
						<div class="flex flex-col gap-1 items-end min-w-0">
							<div class="bg-[#6961ff] text-white p-3 sm:p-4 rounded-2xl rounded-tr-none shadow-lg shadow-[#6961ff]/20 leading-relaxed text-sm sm:text-[15px] break-words">
								{msg.content}
							</div>
							<span class="text-xs text-white/30 mr-1">Read {msg.time}</span>
						</div>
					</div>
				{/if}
			{/each}
		</div>

		<!-- Input Area -->
		<div class="absolute bottom-0 left-0 right-0 px-3 sm:px-6 md:px-12 pb-4 sm:pb-6 pt-2 flex justify-center bg-gradient-to-t from-[#0f0f13] via-[#0f0f13]/80 to-transparent">
			<form class="w-full max-w-3xl" on:submit={handleSubmit}>
				<GlassPanel opacity={0.7} blur={12} borderOpacity={0.1} class="w-full p-2 shadow-2xl flex items-end gap-1.5 sm:gap-2 ring-1 ring-white/10">
					<button type="button" class="h-11 w-11 flex items-center justify-center rounded-xl text-white/50 hover:text-white hover:bg-white/10 transition-all mb-0.5 flex-shrink-0">
						<MaterialIcon icon="add_circle" />
					</button>
					<textarea
						bind:value={messageInput}
						class="flex-1 bg-transparent border-0 text-white placeholder-white/40 focus:ring-0 resize-none py-3 max-h-32 text-sm sm:text-base leading-normal min-w-0"
						{placeholder}
						rows="1"
						disabled={loading}
						on:keydown={(e) => {
							if (e.key === 'Enter' && !e.shiftKey) {
								e.preventDefault();
								sendMessage();
							}
						}}
					></textarea>
					<div class="flex items-center gap-1.5 sm:gap-2 mb-0.5 flex-shrink-0">
						<button type="button" class="relative h-11 w-11 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 transition-all" on:click={() => (voiceModeOpen = true)}>
							<MaterialIcon icon="mic" class="text-[#20B2AA]" />
						</button>
						<button type="submit" disabled={loading || !messageInput.trim()} class="h-11 w-11 flex items-center justify-center rounded-xl bg-[#6961ff] hover:bg-[#5851d8] text-white transition-all shadow-lg shadow-[#6961ff]/20 disabled:opacity-50 disabled:cursor-not-allowed">
							<MaterialIcon icon={loading ? 'hourglass_top' : 'arrow_upward'} size={20} />
						</button>
					</div>
				</GlassPanel>
			</form>
		</div>
	</main>
</div>

{#if voiceModeOpen}
	<VoiceMode onDismiss={() => (voiceModeOpen = false)} />
{/if}

<style>
	.scrollbar-hide::-webkit-scrollbar { display: none; }
	.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>
