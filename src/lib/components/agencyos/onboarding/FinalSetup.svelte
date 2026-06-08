<script lang="ts">
	import { goto } from '$app/navigation';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	export let step: number;

	const teamMembers = [
		{ title: 'Marketing Director', focus: 'Growth & Social', icon: 'trending_up' },
		{ title: 'Sales Lead', focus: 'Leads & CRM', icon: 'support_agent' },
		{ title: 'Ops Manager', focus: 'Workflow & Logic', icon: 'inventory_2' }
	];

	function goBack() {
		goto('/agencyos/onboarding/step3');
	}

	function launch() {
		goto('/agencyos');
	}
</script>

<section class="relative min-h-screen overflow-hidden bg-[#0f0f13] px-4 py-8 text-slate-100 sm:px-6 md:py-10">
	<div class="pointer-events-none absolute -left-20 -top-24 h-80 w-80 rounded-full bg-[#6961ff]/20 blur-3xl"></div>
	<div class="pointer-events-none absolute -bottom-16 -right-16 h-96 w-96 rounded-full bg-[#6961ff]/10 blur-3xl"></div>

	<div class="relative mx-auto w-full max-w-5xl">
		<div class="mb-8 flex flex-col items-center gap-4 md:mb-12">
			<div class="flex items-center gap-2 text-xl font-bold text-[#6961ff]">
				<MaterialIcon icon="auto_awesome" size={30} />
				<span>AgencyOS</span>
			</div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#6961ff]">Step {step} of 4</p>
			<div class="flex w-full max-w-md items-center gap-4">
				<div class="h-1.5 flex-1 rounded-full bg-[#6961ff]"></div>
				<div class="h-1.5 flex-1 rounded-full bg-[#6961ff]"></div>
				<div class="h-1.5 flex-1 rounded-full bg-[#6961ff]"></div>
				<div class="relative h-1.5 flex-1 rounded-full bg-[#6961ff] shadow-[0_0_18px_rgba(105,97,255,0.6)]">
					<div class="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6961ff]">Final Step</div>
				</div>
			</div>
		</div>

		<GlassPanel blur={24} opacity={0.68} borderOpacity={0.08} rounded="rounded-2xl" class="relative overflow-hidden p-6 shadow-2xl sm:p-8 md:p-12">
			<div class="pointer-events-none absolute inset-0 bg-gradient-to-br from-[#6961ff]/10 via-transparent to-transparent"></div>

			<div class="relative z-10 flex flex-col items-center text-center">
				<header class="mb-9 md:mb-12">
					<h1 class="text-3xl font-bold tracking-tight sm:text-4xl">Your Elite Team is Ready.</h1>
					<p class="mx-auto mt-4 max-w-2xl text-base text-slate-400 sm:text-lg">Meet your Chief AI and the specialized agents tailored for your agency’s goals.</p>
				</header>

				<div class="mb-10 md:mb-14">
					<div class="relative inline-block">
						<div class="absolute inset-0 scale-125 rounded-full border border-[#6961ff]/20"></div>
						<div class="absolute inset-0 scale-150 rounded-full border border-[#6961ff]/10"></div>
						<div class="relative flex h-28 w-28 items-center justify-center rounded-full bg-gradient-to-tr from-[#6961ff] to-[#8b85ff] p-1 shadow-[0_0_42px_-10px_rgba(105,97,255,0.7)] sm:h-32 sm:w-32 md:h-40 md:w-40">
							<div class="flex h-full w-full items-center justify-center rounded-full border-4 border-[#0f0f13] bg-[#151520]">
								<MaterialIcon icon="smart_toy" size={60} class="text-[#20B2AA]" />
							</div>
							<div class="absolute bottom-2 right-2 flex h-6 w-6 items-center justify-center rounded-full border-2 border-[#0f0f13] bg-emerald-500">
								<div class="h-2 w-2 animate-pulse rounded-full bg-white"></div>
							</div>
						</div>
					</div>
					<div class="mt-6">
						<h3 class="text-2xl font-bold">Chief AI</h3>
						<p class="mt-1 text-xs font-medium uppercase tracking-[0.18em] text-[#6961ff]">General Superintendent</p>
						<div class="mt-2 flex items-center justify-center gap-2 text-sm text-emerald-400">
							<MaterialIcon icon="sensors" size={16} />
							<span>System Online</span>
						</div>
					</div>
				</div>

				<div class="mb-8 grid w-full grid-cols-1 gap-4 sm:grid-cols-2 md:mb-12 md:grid-cols-3 md:gap-6">
					{#each teamMembers as member}
						<div class="flex flex-col items-center rounded-lg border border-white/10 bg-white/5 p-5 transition-colors hover:bg-white/10">
							<div class="mb-4 flex h-16 w-16 items-center justify-center rounded-xl border border-white/10 bg-slate-800">
								<MaterialIcon icon={member.icon} size={30} class="text-[#20B2AA]" />
							</div>
							<h4 class="text-sm font-semibold">{member.title}</h4>
							<p class="mt-1 text-[10px] uppercase tracking-[0.14em] text-slate-400">{member.focus}</p>
							<StatusBadge label="ACTIVATED" color="green" class="mt-3" />
						</div>
					{/each}
				</div>

				<div class="flex w-full flex-col items-center justify-center gap-4 sm:flex-row">
					<button on:click={goBack} class="flex items-center gap-2 rounded-lg px-8 py-3 font-medium text-slate-400 transition-all hover:bg-white/5 hover:text-white">
						<MaterialIcon icon="arrow_back" size={16} />
						Back
					</button>
					<button on:click={launch} class="flex w-full items-center justify-center gap-3 rounded-lg bg-[#6961ff] px-8 py-3 font-bold text-white shadow-lg shadow-[#6961ff]/30 transition-all hover:scale-[1.01] hover:bg-[#6961ff]/90 sm:w-auto md:px-12 md:py-4">
						Launch Your Organization
						<MaterialIcon icon="rocket_launch" size={18} />
					</button>
				</div>

				<p class="mt-8 flex items-center gap-2 text-xs text-slate-500">
					<MaterialIcon icon="shield" size={14} />
					All agents are running on secure, private AgencyOS instances.
				</p>
			</div>
		</GlassPanel>
	</div>
</section>
