<script lang="ts">
	import { goto } from '$app/navigation';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	export let step: number;

	type Tool = {
		id: string;
		name: string;
		description: string;
		icon: string;
		category: 'Email & Communication' | 'CRM & Sales';
		connected: boolean;
	};

	let tools: Tool[] = [
		{ id: 'gmail', name: 'Gmail', description: 'Sync emails & threads', icon: 'mail', category: 'Email & Communication', connected: false },
		{ id: 'outlook', name: 'Outlook', description: 'Business mail sync', icon: 'mark_email_read', category: 'Email & Communication', connected: true },
		{ id: 'slack', name: 'Slack', description: 'Channel notifications', icon: 'tag', category: 'Email & Communication', connected: false },
		{ id: 'salesforce', name: 'Salesforce', description: 'Lead management sync', icon: 'cloud', category: 'CRM & Sales', connected: false },
		{ id: 'hubspot', name: 'HubSpot', description: 'Marketing automation', icon: 'hub', category: 'CRM & Sales', connected: false },
		{ id: 'notion', name: 'Notion', description: 'Project wiki & notes', icon: 'description', category: 'CRM & Sales', connected: false }
	];

	$: connectedCount = tools.filter((tool) => tool.connected).length;
	$: progressPercent = Math.round((step / 4) * 100);

	function toggleTool(id: string) {
		tools = tools.map((tool) => (tool.id === id ? { ...tool, connected: !tool.connected } : tool));
	}

	function goBack() {
		goto('/agencyos/onboarding/step2');
	}

	function goNext() {
		goto('/agencyos/onboarding/step4');
	}
</script>

<section class="relative min-h-screen overflow-hidden bg-[#0f0f13] px-4 py-7 text-slate-100 sm:px-6 md:py-10">
	<div class="pointer-events-none fixed -left-20 -top-20 h-80 w-80 rounded-full bg-[#6961ff]/20 blur-3xl"></div>
	<div class="pointer-events-none fixed -bottom-20 -right-16 h-96 w-96 rounded-full bg-[#20B2AA]/10 blur-3xl"></div>

	<div class="relative z-10 mx-auto w-full max-w-5xl">
		<header class="mb-6 flex items-center justify-between md:mb-8">
			<div class="flex items-center gap-3">
				<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-[#6961ff]">
					<MaterialIcon icon="rocket_launch" size={20} class="text-white" />
				</div>
				<p class="text-xl font-bold tracking-tight">AgencyOS</p>
			</div>
			<div class="flex items-center gap-3">
				<button class="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white">
					<MaterialIcon icon="help" size={20} />
				</button>
				<button class="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white">
					<MaterialIcon icon="settings" size={20} />
				</button>
			</div>
		</header>

		<GlassPanel blur={24} opacity={0.68} borderOpacity={0.08} rounded="rounded-2xl" class="overflow-hidden shadow-2xl">
			<div class="border-b border-white/10 p-5 sm:p-6 md:p-8">
				<div class="mb-5 flex items-start justify-between gap-4">
					<div>
						<p class="text-xs font-bold uppercase tracking-[0.2em] text-[#6961ff]">Step {step} of 4</p>
						<h1 class="mt-1 text-2xl font-black tracking-tight sm:text-3xl">Connect Your Workflow</h1>
						<p class="mt-2 text-slate-400">Sync your existing tools to power up your workspace.</p>
					</div>
					<div class="hidden h-16 w-16 items-center justify-center rounded-full border border-[#6961ff]/30 text-xs font-bold text-white md:flex">
						{progressPercent}%
					</div>
				</div>
				<div class="flex h-1.5 w-full gap-2">
					<div class="h-full flex-1 rounded-full bg-[#6961ff]"></div>
					<div class="h-full flex-1 rounded-full bg-[#6961ff]"></div>
					<div class="h-full flex-1 rounded-full bg-[#6961ff] shadow-[0_0_15px_rgba(105,97,255,0.5)]"></div>
					<div class="h-full flex-1 rounded-full bg-slate-700/60"></div>
				</div>
			</div>

			<div class="max-h-[58vh] space-y-7 overflow-y-auto p-4 sm:p-6 md:p-8">
				{#each ['Email & Communication', 'CRM & Sales'] as section}
					<div>
						<h3 class="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">{section}</h3>
						<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
							{#each tools.filter((tool) => tool.category === section) as tool}
								<div class="rounded-lg border border-white/10 bg-white/5 p-4 transition-all hover:-translate-y-0.5 hover:bg-white/[0.07]">
									<div class="mb-4 flex items-start justify-between">
										<div class="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-900/80 text-[#20B2AA]">
											<MaterialIcon icon={tool.icon} size={24} />
										</div>
										{#if tool.connected}
											<MaterialIcon icon="check_circle" size={18} class="text-emerald-400" />
										{:else}
											<MaterialIcon icon="info" size={18} class="text-slate-500" />
										{/if}
									</div>
									<h4 class="text-lg font-bold text-white">{tool.name}</h4>
									<p class="mt-1 text-sm text-slate-400">{tool.description}</p>
									<div class="mt-4">
										{#if tool.connected}
											<button
												on:click={() => toggleTool(tool.id)}
												class="flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 py-2 text-sm font-bold text-emerald-400 transition-all"
											>
												<MaterialIcon icon="check" size={14} />
												Connected
											</button>
										{:else}
											<button
												on:click={() => toggleTool(tool.id)}
												class="flex w-full items-center justify-center gap-2 rounded-lg border border-[#6961ff]/20 bg-[#6961ff]/10 py-2 text-sm font-bold text-[#6961ff] transition-all hover:bg-[#6961ff]/20"
											>
												Connect
											</button>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>

			<div class="flex flex-col items-center justify-between gap-3 border-t border-white/10 bg-black/20 p-4 sm:flex-row sm:p-6 md:p-8">
				<button on:click={goBack} class="flex items-center gap-2 px-6 py-3 text-sm font-semibold text-slate-400 transition-colors hover:text-white">
					<MaterialIcon icon="arrow_back" size={16} />
					Back
				</button>
				<div class="flex w-full items-center justify-end gap-3 sm:w-auto sm:gap-4">
					<StatusBadge label={`${connectedCount}/${tools.length} connected`} color="cyan" class="hidden sm:inline-flex" />
					<button on:click={goNext} class="flex w-full items-center justify-center gap-2 rounded-lg bg-[#6961ff] px-8 py-3 font-bold text-white shadow-lg shadow-[#6961ff]/30 transition-all hover:bg-[#6961ff]/90 sm:w-auto">
						Continue
						<MaterialIcon icon="arrow_forward" size={16} class="transition-transform group-hover:translate-x-1" />
					</button>
				</div>
			</div>
		</GlassPanel>
	</div>
</section>
