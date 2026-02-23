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
		class="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors
			hover:bg-white/10 {open ? 'bg-white/10' : ''}"
		on:click={() => (open = !open)}
	>
		<span class="text-lg">{activeDept ? getIcon(activeDept.id) : '🏢'}</span>
		<span class="max-w-[120px] truncate text-white">
			{activeDept ? activeDept.name : 'All Departments'}
		</span>
		<svg
			class="h-4 w-4 text-white/50 transition-transform {open ? 'rotate-180' : ''}"
			fill="none" stroke="currentColor" viewBox="0 0 24 24"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
		</svg>
	</button>

	{#if open}
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div class="fixed inset-0 z-40" on:click={() => (open = false)} />

		<div class="absolute left-0 top-full z-50 mt-1 w-72 overflow-hidden rounded-xl border border-white/10 shadow-lg"
			style="background: rgba(20, 20, 35, 0.95); backdrop-filter: blur(20px);"
		>
			<!-- Chief AI -->
			<button
				class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors
					hover:bg-white/10 {$activeDeptId === 'chief' ? 'bg-white/10' : ''}"
				on:click={() => selectDepartment(CHIEF_AI)}
			>
				<span class="text-2xl">🧠</span>
				<div class="flex-1">
					<div class="flex items-center gap-2">
						<span class="font-medium text-white">Chief AI</span>
						<StatusBadge label="Premium" color="purple" />
					</div>
					<p class="text-xs text-slate-400">Auto-routes across departments</p>
				</div>
			</button>

			<div class="border-t border-white/10" />

			{#each $departments as dept}
				<button
					class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors
						hover:bg-white/10 {$activeDeptId === dept.id ? 'bg-white/10' : ''}"
					on:click={() => selectDepartment(dept)}
				>
					<span class="text-2xl">{getIcon(dept.id)}</span>
					<div class="flex-1">
						<div class="flex items-center gap-2">
							<span class="font-medium text-white">{dept.name}</span>
							{#if dept.model && MODEL_TIERS[dept.model]}
								<StatusBadge label={MODEL_TIERS[dept.model].label} color={MODEL_TIERS[dept.model].color} />
							{/if}
							{#if dept.status === 'setup'}
								<StatusBadge label="Setup" color="yellow" />
							{/if}
						</div>
						<p class="text-xs text-slate-400">{dept.description}</p>
					</div>
				</button>
			{/each}

			{#if $departments.length === 0}
				<p class="px-4 py-3 text-sm text-slate-400">No departments configured</p>
			{/if}
		</div>
	{/if}
</div>
