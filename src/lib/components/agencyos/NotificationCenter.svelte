<script lang="ts">
	import { notifications, unreadCount, type Notification } from '$lib/stores/agencyos';
	import GlassPanel from '$lib/components/agencyos/shared/GlassPanel.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';

	// Seed with demo data if store is empty
	import { onMount } from 'svelte';

	const demoNotifications: Notification[] = [
		{
			id: '1', title: 'Sales AI', dept: 'sales',
			body: 'Drafted cold outreach sequence for 50 high-value leads in Fintech sector.',
			icon: 'smart_toy', time: '2m ago', read: false, type: 'action',
		},
		{
			id: '2', title: 'Finance Bot', dept: 'backoffice',
			body: 'Invoice #4022 for $4,250.00 exceeds weekly spending limit.',
			icon: 'attach_money', time: '14m ago', read: false, type: 'alert',
		},
		{
			id: '3', title: 'System Backup', dept: 'backoffice',
			body: 'Daily database snapshot completed successfully. Size: 2.4GB.',
			icon: 'database', time: '2h ago', read: true, type: 'info',
		},
		{
			id: '4', title: 'Calendar Sync', dept: 'customer',
			body: 'Meeting with Design Team starts in 15 minutes.',
			icon: 'calendar_month', time: '4h ago', read: true, type: 'info',
		},
		{
			id: '5', title: 'Marketing Assets', dept: 'sales',
			body: 'New campaign visuals ready for approval.',
			icon: 'image', time: '5h ago', read: true, type: 'info',
		},
	];

	onMount(() => {
		if ($notifications.length === 0) {
			notifications.set(demoNotifications);
		}
	});

	const ICON_STYLES: Record<string, { bg: string; color: string }> = {
		smart_toy: { bg: 'bg-indigo-500/20', color: 'text-indigo-400' },
		attach_money: { bg: 'bg-emerald-500/20', color: 'text-emerald-400' },
		database: { bg: 'bg-blue-500/20', color: 'text-blue-400' },
		calendar_month: { bg: 'bg-purple-500/20', color: 'text-purple-400' },
		image: { bg: 'bg-pink-500/20', color: 'text-pink-400' },
	};

	function getIconStyle(icon: string) {
		return ICON_STYLES[icon] ?? { bg: 'bg-white/10', color: 'text-white/60' };
	}

	function markAllRead() {
		notifications.update((n) => n.map((x) => ({ ...x, read: true })));
	}

	function markRead(id: string) {
		notifications.update((n) => n.map((x) => x.id === id ? { ...x, read: true } : x));
	}

	$: actionRequired = $notifications.filter((n) => n.type !== 'info' && !n.read);
	$: earlier = $notifications.filter((n) => n.type === 'info' || n.read);
</script>

<div class="w-full h-full flex justify-end">
	<div class="w-full max-w-[420px] flex flex-col border-l border-white/[0.08] h-full"
		style="background: rgba(16, 15, 35, 0.7); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); box-shadow: -10px 0 40px rgba(0,0,0,0.5);"
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-white/[0.08] px-4 sm:px-6 py-4 sm:py-5 shrink-0">
			<div class="flex items-center gap-2 sm:gap-3">
				<MaterialIcon icon="notifications_active" size={24} class="text-[#6961ff]" />
				<h2 class="text-lg sm:text-xl font-bold tracking-tight text-white">Notifications</h2>
				{#if $unreadCount > 0}
					<span class="flex h-5 w-5 items-center justify-center rounded-full bg-[#6961ff] text-[10px] font-bold text-white">
						{$unreadCount}
					</span>
				{/if}
			</div>
			<button
				class="group flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-white"
				on:click={markAllRead}
			>
				<MaterialIcon icon="check_circle" size={14} />
				<span>Clear All</span>
			</button>
		</div>

		<!-- Scrollable Content -->
		<div class="flex-1 overflow-y-auto p-3 sm:p-4 space-y-4 sm:space-y-6">
			<!-- Action Required -->
			{#if actionRequired.length > 0}
				<div class="space-y-2 sm:space-y-3">
					<h3 class="px-1 sm:px-2 text-[10px] sm:text-xs font-bold uppercase tracking-wider text-slate-400">Action Required</h3>
					{#each actionRequired as notif}
						<div
							class="group relative overflow-hidden rounded-lg sm:rounded-xl border border-white/[0.08] bg-[#1b1b28]/80 hover:bg-[#232334] transition-colors p-3 sm:p-4 shadow-lg cursor-pointer"
							on:click={() => markRead(notif.id)}
							on:keydown={(e) => e.key === 'Enter' && markRead(notif.id)}
							role="button"
							tabindex="0"
						>
							<div class="absolute left-0 top-0 bottom-0 w-1 {notif.type === 'alert' ? 'bg-red-500' : 'bg-yellow-500'}"></div>
							<div class="flex items-start gap-2.5 sm:gap-3">
								<div class="flex h-9 w-9 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-lg {getIconStyle(notif.icon).bg}">
									<MaterialIcon icon={notif.icon} size={22} class={getIconStyle(notif.icon).color} />
								</div>
								<div class="flex-1 min-w-0">
									<div class="flex items-center justify-between mb-1">
										<p class="text-xs sm:text-sm font-bold text-white">{notif.title}</p>
										<span class="text-[10px] text-slate-400">{notif.time}</span>
									</div>
									<p class="text-xs sm:text-sm text-slate-300 leading-relaxed mb-2 sm:mb-3">{notif.body}</p>
									<StatusBadge
										label={notif.type === 'alert' ? 'High Risk' : 'Medium Risk'}
										color={notif.type === 'alert' ? 'red' : 'yellow'}
									/>
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Earlier -->
			{#if earlier.length > 0}
				<div class="space-y-2 sm:space-y-3">
					<h3 class="px-1 sm:px-2 text-[10px] sm:text-xs font-bold uppercase tracking-wider text-slate-400">Earlier Today</h3>
					{#each earlier as notif}
						<div class="group relative overflow-hidden rounded-lg sm:rounded-xl border border-white/[0.08] bg-[#1b1b28]/60 hover:bg-[#232334] transition-colors p-2.5 sm:p-3 shadow-sm">
							<div class="flex items-start gap-2.5 sm:gap-3">
								<div class="flex h-7 w-7 sm:h-8 sm:w-8 shrink-0 items-center justify-center rounded-lg {getIconStyle(notif.icon).bg}">
									<MaterialIcon icon={notif.icon} size={18} class={getIconStyle(notif.icon).color} />
								</div>
								<div class="flex-1 min-w-0">
									<div class="flex items-center justify-between mb-0.5">
										<p class="text-xs sm:text-sm font-semibold text-slate-200">{notif.title}</p>
										<span class="text-[10px] text-slate-500">{notif.time}</span>
									</div>
									<p class="text-[11px] sm:text-xs text-slate-400 mb-2">{notif.body}</p>
									{#if notif.type === 'info' && notif.read}
										<StatusBadge label="Complete" color="green" />
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}

			<div class="mt-4 pb-8 text-center">
				<p class="text-[10px] text-slate-600">AgencyOS • All systems operational</p>
			</div>
		</div>
	</div>
</div>
