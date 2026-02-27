<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { departments, activeDeptId, type Department } from '$lib/stores/agencyos';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	const dispatch = createEventDispatcher();

	let open = false;

	const CHIEF_AI: Department = {
		id: 'chief',
		name: 'Chief AI',
		icon: 'psychology',
		gradient: 'from-purple-500 to-indigo-600',
		description: 'Cross-department coordination and strategic reasoning',
		status: 'active',
		agentCount: 1,
		model: 'premium',
	};

	const MODEL_TIERS: Record<string, { label: string; color: string }> = {
		premium: { label: 'Premium', color: 'purple' },
		cloud: { label: 'Smart', color: 'blue' },
		local: { label: 'Fast', color: 'green' },
	};

	const DEPT_ICONS: Record<string, string> = {
		sales: '💼',
		customer: '🤝',
		backoffice: '📋',
		chief: '🧠',
	};

	function selectDepartment(dept: Department | null) {
		$activeDeptId = dept?.id ?? null;
		open = false;
		dispatch('select', { department: dept });
	}

	function getIcon(id: string): string {
		return DEPT_ICONS[id] ?? '🏢';
	}

	$: activeDept = $activeDeptId === 'chief'
		? CHIEF_AI
		: $departments.find((d) => d.id === $activeDeptId) ?? null;
</script>

<div class="relative">
	<button
		class="flex items-center gap-2 sm:gap-2.5 rounded-xl px-3 sm:px-3.5 md:px-4 py-2.5 md:py-3 text-sm md:text-base font-medium transition-colors min-h-[44px] {open ? 'bg-white/10' : 'hover:bg-white/10'}"
		on:click={() => (open = !open)}
	>
		<span class="text-lg md:text-xl">{activeDept ? getIcon(activeDept.id) : '🏢'}</span>
		<span class="max-w-[100px] sm:max-w-[120px] md:max-w-[160px] lg:max-w-[200px] truncate text-white">
			{activeDept ? activeDept.name : 'All Departments'}
		</span>
		<svg
			class="h-4 w-4 md:h-5 md:w-5 text-white/50 transition-transform shrink-0"
			class:rotate-180={open}
			fill="none" stroke="currentColor" viewBox="0 0 24 24"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
		</svg>
	</button>

	{#if open}
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div class="fixed inset-0 z-40" on:click={() => (open = false)} />

		<div class="absolute left-0 sm:left-0 right-0 sm:right-auto top-full z-50 mt-1.5 md:mt-2 w-auto sm:w-72 md:w-80 lg:w-96 overflow-hidden rounded-xl border border-white/10 shadow-lg max-h-[70vh] md:max-h-[75vh] overflow-y-auto"
			style="background: rgba(20, 20, 35, 0.95); backdrop-filter: blur(20px); min-width: 260px;"
		>
			<!-- Chief AI -->
			<button
				class="flex w-full items-center gap-3 md:gap-3.5 px-4 md:px-5 py-3.5 md:py-4 text-left transition-colors min-h-[52px] md:min-h-[56px] {$activeDeptId === 'chief' ? 'bg-white/10' : 'hover:bg-white/10'}"
				on:click={() => selectDepartment(CHIEF_AI)}
			>
				<span class="text-2xl md:text-[1.65rem] shrink-0">🧠</span>
				<div class="flex-1 min-w-0">
					<div class="flex items-center gap-2 flex-wrap">
						<span class="font-medium text-white text-sm md:text-base">Chief AI</span>
						<StatusBadge label="Premium" color="purple" />
					</div>
					<p class="text-xs md:text-sm text-slate-400 truncate">Auto-routes across departments</p>
				</div>
			</button>

			<div class="border-t border-white/10" />

			{#each $departments as dept}
				<button
					class="flex w-full items-center gap-3 md:gap-3.5 px-4 md:px-5 py-3.5 md:py-4 text-left transition-colors min-h-[52px] md:min-h-[56px] {$activeDeptId === dept.id ? 'bg-white/10' : 'hover:bg-white/10'}"
					on:click={() => selectDepartment(dept)}
				>
					<span class="text-2xl md:text-[1.65rem] shrink-0">{getIcon(dept.id)}</span>
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2 flex-wrap">
							<span class="font-medium text-white text-sm md:text-base truncate">{dept.name}</span>
							{#if dept.model && MODEL_TIERS[dept.model]}
								<StatusBadge label={MODEL_TIERS[dept.model].label} color={MODEL_TIERS[dept.model].color} />
							{/if}
							{#if dept.status === 'setup'}
								<StatusBadge label="Setup" color="yellow" />
							{/if}
						</div>
						<p class="text-xs md:text-sm text-slate-400 truncate">{dept.description}</p>
					</div>
				</button>
			{/each}

			{#if $departments.length === 0}
				<p class="px-4 md:px-5 py-3 md:py-4 text-sm md:text-base text-slate-400">No departments configured</p>
			{/if}
		</div>
	{/if}
</div>
