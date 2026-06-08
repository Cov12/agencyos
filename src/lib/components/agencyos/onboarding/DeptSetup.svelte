<script lang="ts">
	import { goto } from '$app/navigation';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import { departments } from '$lib/stores/agencyos';

	export let step: number;

	const departmentDescriptions: Record<string, string> = {
		sales: 'Manage leads, contracts, and internal scheduling.',
		customer: 'Handle tickets, live chat, and client satisfaction.',
		backoffice: 'Invoicing, payroll, and internal resource planning.'
	};

	const iconMap: Record<string, string> = {
		sales: 'payments',
		customer: 'support_agent',
		backoffice: 'account_balance'
	};

	const gradientMap: Record<string, string> = {
		sales: 'bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/20',
		customer: 'bg-gradient-to-br from-emerald-400 to-teal-600 shadow-lg shadow-emerald-500/20',
		backoffice: 'bg-gradient-to-br from-orange-400 to-rose-500 shadow-lg shadow-orange-500/20'
	};

	function isChecked(status: string) {
		return status === 'active';
	}

	function toggleDepartment(id: string, checked: boolean) {
		departments.update((items) =>
			items.map((dept) => {
				if (dept.id !== id) return dept;
				return {
					...dept,
					status: checked ? 'active' : 'inactive'
				};
			})
		);
	}

	function goBack() {
		goto('/agencyos/onboarding/step1');
	}

	function goNext() {
		goto('/agencyos/onboarding/step3');
	}
</script>

<section class="relative min-h-screen overflow-hidden bg-[#0f0f13] px-4 py-8 text-slate-100 sm:px-6 md:py-10">
	<div class="pointer-events-none absolute -left-20 -top-24 h-80 w-80 rounded-full bg-[#6961ff]/20 blur-3xl"></div>
	<div class="pointer-events-none absolute -bottom-20 -right-16 h-80 w-80 rounded-full bg-[#20B2AA]/10 blur-3xl"></div>

	<div class="relative mx-auto w-full max-w-3xl">
		<div class="mb-8 flex items-center justify-center gap-3">
			<div class="h-2 w-2 rounded-full bg-[#6961ff]/40"></div>
			<div class="h-2 w-2 rounded-full bg-[#6961ff] ring-4 ring-[#6961ff]/20"></div>
			<div class="h-2 w-2 rounded-full bg-slate-700"></div>
			<div class="h-2 w-2 rounded-full bg-slate-700"></div>
			<span class="ml-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#6961ff]">Step {step} of 4</span>
		</div>

		<GlassPanel blur={24} opacity={0.7} borderOpacity={0.08} rounded="rounded-2xl" class="overflow-hidden shadow-2xl">
			<div class="border-b border-white/5 px-5 pb-5 pt-7 text-center sm:px-7 md:px-9 md:pb-6 md:pt-10">
				<div class="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-[#6961ff]/10 text-[#6961ff]">
					<MaterialIcon icon="category" size={30} />
				</div>
				<h1 class="text-2xl font-bold tracking-tight text-white sm:text-3xl">Activate Your Departments</h1>
				<p class="mx-auto mt-2 max-w-lg text-slate-400">Choose the core areas of your agency you want to manage. You can always change this later in settings.</p>
			</div>

			<div class="space-y-3 p-4 sm:p-5 md:p-6">
				{#each $departments as dept}
					<div class="group flex items-center justify-between rounded-lg border border-white/5 bg-white/5 p-4 transition-all hover:border-[#6961ff]/50">
						<div class="flex min-w-0 items-center gap-3 sm:gap-4">
							<div class={`flex h-12 w-12 items-center justify-center rounded-xl ${gradientMap[dept.id] ?? 'bg-slate-700'}`}>
								<MaterialIcon icon={iconMap[dept.id] ?? dept.icon} size={22} class="text-white" />
							</div>
							<div class="min-w-0">
								<h3 class="font-semibold text-white">{dept.name}</h3>
								<p class="hidden truncate text-sm text-slate-400 sm:block">{departmentDescriptions[dept.id] ?? dept.description}</p>
							</div>
						</div>

						<label class="relative flex h-[31px] w-[51px] cursor-pointer items-center rounded-full bg-slate-700 p-0.5 transition-colors has-[:checked]:bg-[#6961ff]">
							<input
								type="checkbox"
								checked={isChecked(dept.status)}
								on:change={(event) => toggleDepartment(dept.id, (event.currentTarget as HTMLInputElement).checked)}
								class="peer invisible absolute"
							/>
							<div class="h-full w-[27px] rounded-full bg-white shadow-sm transition-all peer-checked:translate-x-5"></div>
						</label>
					</div>
				{/each}
			</div>

			<div class="flex flex-col items-center justify-between gap-3 border-t border-white/5 bg-white/[0.02] px-4 py-4 sm:flex-row sm:px-6 md:px-8 md:py-6">
				<button on:click={goBack} class="flex w-full items-center justify-center gap-2 rounded-lg px-6 py-2.5 font-semibold text-slate-400 transition-all hover:bg-white/5 hover:text-white sm:w-auto">
					<MaterialIcon icon="arrow_back" size={18} />
					Back
				</button>
				<div class="flex w-full items-center gap-3 sm:w-auto sm:gap-4">
					<span class="hidden text-xs text-slate-500 sm:inline">Auto-saving selection...</span>
					<button on:click={goNext} class="flex w-full items-center justify-center gap-2 rounded-lg bg-[#6961ff] px-8 py-2.5 font-bold text-white shadow-lg shadow-[#6961ff]/20 transition-all hover:bg-[#6961ff]/90 sm:w-auto">
						Continue
						<MaterialIcon icon="arrow_forward" size={18} />
					</button>
				</div>
			</div>
		</GlassPanel>
	</div>
</section>
