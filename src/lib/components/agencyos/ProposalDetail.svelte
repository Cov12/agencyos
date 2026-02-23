<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Proposal } from '$lib/stores/agencyos';
	import StatusBadge from '$lib/components/agencyos/shared/StatusBadge.svelte';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';

	const dispatch = createEventDispatcher();

	export let proposal: Proposal;

	let reviewNote = '';
	let submitting = false;

	const PRIORITY_COLORS: Record<string, string> = {
		low: 'green', medium: 'yellow', high: 'orange', critical: 'red',
	};

	function handleApprove() {
		submitting = true;
		dispatch('approve', { id: proposal.id, note: reviewNote });
	}

	function handleReject() {
		submitting = true;
		dispatch('reject', { id: proposal.id, note: reviewNote });
	}

	$: isPending = proposal.status === 'pending';
</script>

<div class="overflow-hidden rounded-xl border border-white/10 shadow-xl"
	style="background: rgba(20, 20, 30, 0.95); backdrop-filter: blur(20px);"
>
	<!-- Header -->
	<div class="flex items-start justify-between border-b border-white/10 px-6 py-4">
		<div class="flex-1">
			<h2 class="text-lg font-semibold text-white">{proposal.title}</h2>
			<div class="mt-1 flex items-center gap-2 text-sm text-slate-400">
				<span>{proposal.dept}</span>
				<span>·</span>
				<span>{proposal.createdAt}</span>
			</div>
		</div>
		<button
			class="rounded-lg p-1 transition-colors hover:bg-white/10 text-slate-400"
			on:click={() => dispatch('close')}
		>
			<MaterialIcon icon="close" size={20} />
		</button>
	</div>

	<div class="max-h-[60vh] overflow-y-auto px-6 py-4">
		<!-- Priority -->
		<div class="mb-4 rounded-lg border border-white/10 p-4 bg-white/5">
			<StatusBadge
				label="{proposal.priority.charAt(0).toUpperCase() + proposal.priority.slice(1)} Priority"
				color={PRIORITY_COLORS[proposal.priority]}
				size="md"
			/>
		</div>

		<!-- Description -->
		<div class="mb-4">
			<h3 class="mb-1 text-sm font-medium text-slate-400">Description</h3>
			<p class="text-sm leading-relaxed text-slate-200">{proposal.description}</p>
		</div>

		<!-- Review Note -->
		{#if isPending}
			<div class="mt-4">
				<label for="review-note" class="mb-1 block text-sm font-medium text-slate-400">
					Review Note (optional)
				</label>
				<textarea
					id="review-note"
					bind:value={reviewNote}
					placeholder="Add a note about your decision..."
					rows="2"
					class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white
						focus:border-[#6961ff] focus:outline-none focus:ring-0 placeholder-slate-500"
				/>
			</div>
		{/if}
	</div>

	<!-- Actions -->
	{#if isPending}
		<div class="flex items-center justify-end gap-2 border-t border-white/10 px-6 py-4">
			<button
				class="rounded-lg px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10"
				disabled={submitting}
				on:click={handleReject}
			>
				Reject
			</button>
			<button
				class="rounded-lg bg-[#6961ff] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#5851d8] disabled:opacity-50 shadow-lg shadow-[#6961ff]/20"
				disabled={submitting}
				on:click={handleApprove}
			>
				{#if submitting}
					<span class="inline-flex items-center gap-2">
						<div class="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
						Processing...
					</span>
				{:else}
					Approve
				{/if}
			</button>
		</div>
	{/if}
</div>
