<script lang="ts">
	import { onMount, getContext, createEventDispatcher } from 'svelte';
	import { getDepartments, type Department } from '$lib/apis/agencyos';
	import { user } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let orgId: string = '';
	export let selectedDepartment: string | null = null;

	let departments: Department[] = [];
	let loading = true;
	let open = false;

	const CHIEF_AI = {
		id: 'chief',
		slug: 'chief',
		name: 'Chief AI',
		description: 'Cross-department coordination and strategic reasoning',
		model_tier: 'premium',
		capabilities: ['cross_department', 'strategic_analysis']
	} satisfies Department;

	const DEPARTMENT_ICONS: Record<string, string> = {
		sales_admin: '💼',
		customer: '🤝',
		back_office: '📋',
		chief: '🧠'
	};

	const TIER_BADGES: Record<string, { label: string; class: string }> = {
		local: { label: 'Fast', class: 'bg-green-500/20 text-green-400' },
		mid: { label: 'Smart', class: 'bg-blue-500/20 text-blue-400' },
		premium: { label: 'Premium', class: 'bg-purple-500/20 text-purple-400' }
	};

	onMount(async () => {
		if (!orgId) return;
		try {
			const token = localStorage.getItem('token') ?? '';
			const res = await getDepartments(token, orgId);
			departments = res.departments;
		} catch (err) {
			console.error('Failed to load departments:', err);
		} finally {
			loading = false;
		}
	});

	function selectDepartment(dept: Department | null) {
		selectedDepartment = dept?.slug ?? null;
		open = false;
		dispatch('select', { department: dept });
	}

	function getIcon(slug: string): string {
		return DEPARTMENT_ICONS[slug] ?? '🏢';
	}

	$: activeDept =
		selectedDepartment === 'chief'
			? CHIEF_AI
			: departments.find((d) => d.slug === selectedDepartment) ?? null;
</script>

<div class="relative">
	<Tooltip content={activeDept ? activeDept.name : 'Select Department'}>
		<button
			class="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors
				hover:bg-gray-100 dark:hover:bg-gray-800
				{open ? 'bg-gray-100 dark:bg-gray-800' : ''}"
			on:click={() => (open = !open)}
		>
			<span class="text-lg">{activeDept ? getIcon(activeDept.slug) : '🏢'}</span>
			<span class="max-w-[120px] truncate">
				{activeDept ? activeDept.name : 'All Departments'}
			</span>
			<svg
				class="h-4 w-4 transition-transform {open ? 'rotate-180' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
		</button>
	</Tooltip>

	{#if open}
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div class="fixed inset-0 z-40" on:click={() => (open = false)} />

		<div
			class="absolute left-0 top-full z-50 mt-1 w-72 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900"
		>
			<!-- Chief AI option -->
			<button
				class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors
					hover:bg-gray-50 dark:hover:bg-gray-800
					{selectedDepartment === 'chief' ? 'bg-gray-50 dark:bg-gray-800' : ''}"
				on:click={() => selectDepartment(CHIEF_AI)}
			>
				<span class="text-2xl">🧠</span>
				<div class="flex-1">
					<div class="flex items-center gap-2">
						<span class="font-medium">Chief AI</span>
						<span class="rounded-full px-2 py-0.5 text-xs {TIER_BADGES.premium.class}">
							{TIER_BADGES.premium.label}
						</span>
					</div>
					<p class="text-xs text-gray-500 dark:text-gray-400">Auto-routes across departments</p>
				</div>
			</button>

			<div class="border-t border-gray-200 dark:border-gray-700" />

			{#if loading}
				<div class="flex items-center justify-center py-6">
					<div class="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
				</div>
			{:else}
				{#each departments as dept}
					<button
						class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors
							hover:bg-gray-50 dark:hover:bg-gray-800
							{selectedDepartment === dept.slug ? 'bg-gray-50 dark:bg-gray-800' : ''}"
						on:click={() => selectDepartment(dept)}
					>
						<span class="text-2xl">{getIcon(dept.slug)}</span>
						<div class="flex-1">
							<div class="flex items-center gap-2">
								<span class="font-medium">{dept.name}</span>
								{#if TIER_BADGES[dept.model_tier]}
									<span
										class="rounded-full px-2 py-0.5 text-xs {TIER_BADGES[dept.model_tier].class}"
									>
										{TIER_BADGES[dept.model_tier].label}
									</span>
								{/if}
							</div>
							<p class="text-xs text-gray-500 dark:text-gray-400">{dept.description}</p>
						</div>
					</button>
				{/each}

				{#if departments.length === 0}
					<p class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
						No departments configured
					</p>
				{/if}
			{/if}
		</div>
	{/if}
</div>
