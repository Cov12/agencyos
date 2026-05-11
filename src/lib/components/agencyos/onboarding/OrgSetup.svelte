<script lang="ts">
	import { goto } from '$app/navigation';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';

	export let step: number;

	let orgName = '';
	let industry = '';
	let logoName = '';

	const industryOptions = [
		{ value: 'creative', label: 'Creative Agency' },
		{ value: 'software', label: 'Software House' },
		{ value: 'marketing', label: 'Digital Marketing' },
		{ value: 'consulting', label: 'Consulting' },
		{ value: 'other', label: 'Other' }
	];

	function onLogoSelected(event: Event) {
		const target = event.target as HTMLInputElement;
		logoName = target.files?.[0]?.name ?? '';
	}

	function continueStep() {
		goto('/agencyos/onboarding/step2');
	}
</script>

<section class="relative min-h-screen overflow-hidden bg-[#0f0f13] px-4 py-8 text-slate-100 sm:px-6 md:py-10">
	<div class="pointer-events-none absolute -left-20 -top-24 h-80 w-80 rounded-full bg-[#6961ff]/20 blur-3xl"></div>
	<div class="pointer-events-none absolute -bottom-28 -right-24 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl"></div>

	<div class="relative mx-auto w-full max-w-2xl">
		<div class="mb-6 flex items-center justify-center gap-2 md:mb-8">
			<div class="flex h-10 w-10 items-center justify-center rounded-xl bg-[#6961ff] shadow-lg shadow-[#6961ff]/30">
				<MaterialIcon icon="rocket_launch" size={22} class="text-white" />
			</div>
			<p class="text-xl font-bold tracking-tight sm:text-2xl">Agency<span class="text-[#6961ff]">OS</span></p>
		</div>

		<GlassPanel blur={24} opacity={0.7} borderOpacity={0.08} rounded="rounded-2xl" class="p-5 shadow-2xl sm:p-7 md:p-8">
			<div class="mb-7 md:mb-9">
				<div class="mb-3 flex items-center justify-between">
					<p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#6961ff]">Step {step} of 4</p>
					<p class="text-xs font-medium text-slate-400">Organization Setup</p>
				</div>
				<div class="flex h-1.5 w-full gap-2">
					<div class="h-full flex-1 rounded-full bg-[#6961ff] shadow-[0_0_14px_rgba(105,97,255,0.6)]"></div>
					<div class="h-full flex-1 rounded-full bg-slate-700/60"></div>
					<div class="h-full flex-1 rounded-full bg-slate-700/60"></div>
					<div class="h-full flex-1 rounded-full bg-slate-700/60"></div>
				</div>
			</div>

			<div class="mb-7 md:mb-8">
				<h1 class="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">Build your workspace</h1>
				<p class="mt-2 leading-relaxed text-slate-400">Let's start by setting up your organization's profile. This will be the home for your team and projects.</p>
			</div>

			<form class="space-y-5" on:submit|preventDefault={continueStep}>
				<div class="space-y-2">
					<label class="ml-1 text-sm font-semibold text-slate-300" for="org-name">Organization Name</label>
					<input
						id="org-name"
						type="text"
						bind:value={orgName}
						placeholder="e.g. Acme Studio"
						class="h-12 w-full rounded-lg border border-slate-700/60 bg-slate-800/40 px-4 text-white placeholder:text-slate-500 focus:border-[#6961ff] focus:outline-none focus:ring-2 focus:ring-[#6961ff]/50"
					/>
				</div>

				<div class="space-y-2">
					<label class="ml-1 text-sm font-semibold text-slate-300" for="industry">Industry</label>
					<div class="relative">
						<select
							id="industry"
							bind:value={industry}
							class="h-12 w-full appearance-none rounded-lg border border-slate-700/60 bg-slate-800/40 px-4 pr-10 text-white focus:border-[#6961ff] focus:outline-none focus:ring-2 focus:ring-[#6961ff]/50"
						>
							<option value="" disabled>Select your industry</option>
							{#each industryOptions as option}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
						<MaterialIcon icon="expand_more" size={20} class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
					</div>
				</div>

				<div class="space-y-2">
					<label class="ml-1 text-sm font-semibold text-slate-300" for="logo-upload">Workspace Logo</label>
					<div class="group relative cursor-pointer rounded-xl border-2 border-dashed border-slate-700/60 bg-white/[0.02] p-5 transition-all hover:border-[#6961ff]/60 hover:bg-[#6961ff]/5 sm:p-7">
						<div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800/70 transition-transform group-hover:scale-105">
							<MaterialIcon icon="cloud_upload" size={24} class="text-slate-300 group-hover:text-[#6961ff]" />
						</div>
						<p class="text-center text-sm font-medium text-white">Click to upload or drag and drop</p>
						<p class="mt-1 text-center text-xs text-slate-500">PNG, JPG or SVG (max. 800x400px)</p>
						{#if logoName}
							<p class="mt-3 text-center text-xs font-medium text-[#20B2AA]">Selected: {logoName}</p>
						{/if}
						<input id="logo-upload" type="file" class="absolute inset-0 cursor-pointer opacity-0" on:change={onLogoSelected} />
					</div>
				</div>

				<div class="pt-3">
					<button type="submit" class="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#6961ff] font-bold text-white shadow-lg shadow-[#6961ff]/30 transition hover:bg-[#6961ff]/90">
						Continue
						<MaterialIcon icon="arrow_forward" size={18} class="text-white" />
					</button>
				</div>
			</form>
		</GlassPanel>

		<p class="mt-6 text-center text-xs text-slate-500">By continuing, you agree to our Terms of Service and Privacy Policy.</p>
	</div>
</section>
