<script lang="ts">
	import { goto } from '$app/navigation';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';
	import { user } from '$lib/stores';
	import {
		activeOrgId,
		departmentRoles,
		onboardingAnswers,
		onboardingComplete,
		resetOnboardingAnswers,
		selectedDepartments
	} from '$lib/stores/agencyos';
	import { completeOnboarding, provisionOnboardingAgents } from '$lib/apis/agencyos';

	export let step: number;

	/** Which request the finish path is waiting on — drives the button label. */
	let phase: 'idle' | 'provisioning' | 'completing' = 'idle';
	$: launching = phase !== 'idle';
	/** Soft notices, never blockers: the user still lands in the app. */
	let notices: string[] = [];
	/** Outcome of the provisioning call, per role: set once the call returns. */
	let provisioned: Set<string> | null = null;
	let provisionFailed = false;

	/** The real team: every department switched on in DeptSetup. Empty is valid — the Chief
	 * AI always exists and lazy provisioning covers the rest later. */
	$: specialists = $selectedDepartments;

	/** State is passed in (not read from the closure) so the template re-evaluates the badge
	 * whenever any of it changes. */
	function specialistBadge(
		role: string,
		currentPhase: typeof phase,
		provisionedRoles: Set<string> | null,
		failed: boolean
	): { label: string; color: string } {
		if (currentPhase === 'provisioning') return { label: 'SETTING UP', color: 'blue' };
		if (failed) return { label: 'ADD LATER', color: 'yellow' };
		if (provisionedRoles) {
			return provisionedRoles.has(role)
				? { label: 'ACTIVATED', color: 'green' }
				: { label: 'ADD LATER', color: 'yellow' };
		}
		return { label: 'READY', color: 'purple' };
	}

	function authToken(): string | undefined {
		return (($user as { token?: string } | undefined)?.token ??
			(typeof localStorage !== 'undefined' ? localStorage.token : undefined)) as
			| string
			| undefined;
	}

	function goBack() {
		goto('/agencyos/onboarding/step3');
	}

	/**
	 * Finish the wizard: provision the selected departments' agents, then persist the
	 * captured answers, seed them into the assistant's memory and mark onboarding complete
	 * server-side — then enter the app.
	 *
	 * Failure NEVER traps the user in the wizard: both calls are best-effort (the backend
	 * commits completion even when the seed fails, and unprovisioned roles are created
	 * lazily later), so anything that goes wrong here just shows a soft notice and still
	 * routes to /agencyos.
	 */
	async function launch() {
		if (phase !== 'idle') return;
		notices = [];
		provisioned = null;
		provisionFailed = false;

		const token = authToken();
		const orgId = $activeOrgId;
		const roles = departmentRoles($selectedDepartments);

		if (token && orgId) {
			if (roles.length > 0) {
				phase = 'provisioning';
				try {
					const result = await provisionOnboardingAgents(token, orgId, roles);
					provisioned = new Set((result?.agents ?? []).map((agent) => agent.role));
					if (roles.some((role) => !provisioned?.has(role))) {
						notices = [...notices, 'Some of your specialists are still being set up — you can add them later in settings.'];
					}
				} catch (error) {
					// 400 (unknown role), 502 (bridge down) or network — all non-fatal.
					console.error('Failed to provision onboarding agents', error);
					provisionFailed = true;
					notices = [...notices, "We couldn't set up your team just now — you can add agents later in settings."];
				}
			}

			phase = 'completing';
			try {
				// subAccountId intentionally omitted: P1 seeds at company/business scope.
				const result = await completeOnboarding(token, orgId, $onboardingAnswers);
				onboardingComplete.set(true);
				resetOnboardingAnswers();
				if (result && result.seeded === false) {
					notices = [...notices, "Saved. Your assistant's memory is still syncing — it'll catch up shortly."];
				}
			} catch (error) {
				console.error('Failed to complete onboarding', error);
				notices = [...notices, "We couldn't save your answers just now. You can add them later in settings."];
			}
		} else {
			phase = 'completing';
			notices = ["We couldn't save your answers just now. You can add them later in settings."];
		}

		// A notice deserves a beat on screen before the route change swaps the page out.
		if (notices.length > 0) {
			await new Promise((resolve) => setTimeout(resolve, 1600));
		}
		await goto('/agencyos');
		phase = 'idle';
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
					<p class="mx-auto mt-4 max-w-2xl text-base text-slate-400 sm:text-lg">
						{specialists.length > 0
							? 'Meet your Chief AI and the specialists for the departments you chose.'
							: 'Meet your Chief AI. Add specialists anytime from settings — your assistant can bring them on as you need them.'}
					</p>
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

				{#if specialists.length > 0}
					<div class="mb-8 w-full md:mb-12">
						<p class="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
							Chief AI + your {specialists.length} specialist{specialists.length !== 1 ? 's' : ''}
						</p>
						<div class="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 md:gap-6">
							{#each specialists as dept (dept.id)}
								{@const badge = specialistBadge(dept.role, phase, provisioned, provisionFailed)}
								<div class="flex flex-col items-center rounded-lg border border-white/10 bg-white/5 p-5 transition-colors hover:bg-white/10">
									<div class={`mb-4 flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br shadow-lg shadow-black/20 ${dept.gradient}`}>
										<MaterialIcon icon={dept.icon} size={30} class="text-white" />
									</div>
									<h4 class="text-sm font-semibold">{dept.name}</h4>
									<p class="mt-1 text-[11px] text-slate-400">{dept.description}</p>
									<StatusBadge label={badge.label} color={badge.color} class="mt-3" />
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<div class="flex w-full flex-col items-center justify-center gap-4 sm:flex-row">
					<button on:click={goBack} class="flex items-center gap-2 rounded-lg px-8 py-3 font-medium text-slate-400 transition-all hover:bg-white/5 hover:text-white">
						<MaterialIcon icon="arrow_back" size={16} />
						Back
					</button>
					<button
						on:click={launch}
						disabled={launching}
						class="flex w-full items-center justify-center gap-3 rounded-lg bg-[#6961ff] px-8 py-3 font-bold text-white shadow-lg shadow-[#6961ff]/30 transition-all hover:scale-[1.01] hover:bg-[#6961ff]/90 disabled:cursor-wait disabled:opacity-80 disabled:hover:scale-100 sm:w-auto md:px-12 md:py-4"
					>
						{phase === 'provisioning'
							? 'Setting up your team…'
							: phase === 'completing'
								? 'Briefing your assistant…'
								: 'Launch Your Organization'}
						<MaterialIcon icon={launching ? 'autorenew' : 'rocket_launch'} size={18} class={launching ? 'animate-spin' : ''} />
					</button>
				</div>

				{#each notices as notice}
					<p class="mt-5 flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-300">
						<MaterialIcon icon="info" size={16} />
						{notice}
					</p>
				{/each}

				<p class="mt-8 flex items-center gap-2 text-xs text-slate-500">
					<MaterialIcon icon="shield" size={14} />
					All agents are running on secure, private AgencyOS instances.
				</p>
			</div>
		</GlassPanel>
	</div>
</section>
