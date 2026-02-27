<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		WEBUI_NAME,
		showSidebar,
		user,
		mobile
	} from '$lib/stores';
	import { getOrganization, createOrganization } from '$lib/apis/agencyos';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import AgencyNav from '$lib/components/agencyos/shared/AgencyNav.svelte';
	import { agencyNavCollapsed, agencyNavMobile, activeOrg, unreadCount } from '$lib/stores/agencyos';
	import NotificationCenter from '$lib/components/agencyos/NotificationCenter.svelte';

	let notificationPanelOpen = false;

	const i18n = getContext('i18n');

	let loaded = false;
	let orgLoading = true;

	// Sync mobile state from parent app
	$: agencyNavMobile.set($mobile);

	// On mobile, collapse nav by default
	$: if ($mobile) agencyNavCollapsed.set(true);

	function toggleNav() {
		agencyNavCollapsed.update((v) => !v);
	}

	onMount(async () => {
		// Hide OpenWebUI's default sidebar on AgencyOS routes
		showSidebar.set(false);
		loaded = true;

		const token = (($user as { token?: string } | undefined)?.token ?? localStorage.token) as
			| string
			| undefined;

		if (!token) {
			orgLoading = false;
			return;
		}

		try {
			// TODO: Support multi-org — load user's org from membership lookup
			const organization = await getOrganization(token, 'default');
			activeOrg.set(organization);
		} catch (error) {
			try {
				const created = await createOrganization(token, {
					name: 'My Organization',
					slug: 'default'
				});
				activeOrg.set(created.organization);
			} catch (createError) {
				console.error('Failed to resolve organization context', createError ?? error);
			}
		} finally {
			orgLoading = false;
		}
	});

	// Pages that use full-screen overlays (no nav chrome)
	$: isOverlay = $page.url.pathname.includes('/voice') || $page.url.pathname.includes('/onboarding');
</script>

<svelte:head>
	<title>
		{$i18n.t('AgencyOS')} • {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div
		class="relative flex w-full h-screen max-h-[100dvh] transition-all duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: ''} max-w-full bg-[#0f0f13]"
	>
		<!-- Mobile Nav Overlay (must be BEFORE nav so nav renders on top) -->
		{#if $mobile && !$agencyNavCollapsed && !isOverlay}
			<button
				class="fixed inset-0 bg-black/50 z-40"
				on:click={() => agencyNavCollapsed.set(true)}
				aria-label="Close navigation"
			/>
		{/if}

		<!-- AgencyOS Sidebar Nav (hidden on overlay pages) -->
		{#if !isOverlay}
			<div class="{$mobile ? 'fixed inset-y-0 left-0 z-50' : ''}">
				<AgencyNav collapsed={$agencyNavCollapsed} onToggle={toggleNav} onNavigate={() => { if ($mobile) agencyNavCollapsed.set(true); }} />
			</div>
		{/if}

		<!-- Main Content Area -->
		<div class="flex-1 flex flex-col min-w-0 h-full">
			<!-- Top Bar -->
			{#if !isOverlay}
				<nav class="px-4 pt-2 pb-1 flex items-center gap-2 shrink-0 border-b border-white/5">
					<!-- AgencyOS nav toggle (when collapsed or mobile) -->
					{#if $agencyNavCollapsed}
						<button
							class="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition"
							on:click={toggleNav}
						>
							<span class="material-symbols-outlined text-[20px]">menu</span>
						</button>
					{/if}

					<!-- Breadcrumb / Page title -->
					<div class="flex items-center gap-2 text-sm">
						<a href="/agencyos" class="text-slate-500 hover:text-white transition">AgencyOS</a>
						{#if $page.url.pathname !== '/agencyos'}
							<span class="text-slate-600">/</span>
							<span class="text-slate-300 capitalize">
								{$page.url.pathname.split('/').pop()}
							</span>
						{/if}
					</div>

					<div class="ml-auto flex items-center gap-2">
						<button
							class="relative p-2 rounded-lg transition-all {notificationPanelOpen ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/10 hover:text-white'}"
							on:click={() => (notificationPanelOpen = !notificationPanelOpen)}
						>
							<span class="material-symbols-outlined text-[20px]">notifications</span>
							{#if $unreadCount > 0}
								<span class="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[9px] font-bold min-w-[16px] h-4 flex items-center justify-center rounded-full px-1">
									{$unreadCount}
								</span>
							{/if}
						</button>
					</div>
				</nav>
			{/if}

			<!-- Notification Slide-out Panel -->
			{#if notificationPanelOpen}
				<button
					class="fixed inset-0 z-30 bg-black/30"
					on:click={() => (notificationPanelOpen = false)}
					aria-label="Close notifications"
				/>
				<div class="fixed top-0 right-0 z-40 h-full w-full max-w-md shadow-2xl shadow-black/50 border-l border-white/5 bg-[#0f0f13] overflow-y-auto">
					<NotificationCenter />
				</div>
			{/if}

			<!-- Page Content -->
			<div
				class="flex-1 overflow-y-auto {isOverlay ? '' : 'p-4 md:p-6'}"
				id="agencyos-container"
			>
				{#if orgLoading}
					<div class="h-full min-h-[240px] flex items-center justify-center text-slate-400">
						<div class="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white mr-3"></div>
						Resolving organization context...
					</div>
				{:else}
					<slot />
				{/if}
			</div>
		</div>


	</div>
{/if}
