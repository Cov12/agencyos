<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Proposal } from '$lib/apis/agencyos';

	const dispatch = createEventDispatcher();

	export let proposal: Proposal;
	export let orgId: string = '';

	let reviewNote = '';
	let submitting = false;

	const RISK_COLORS: Record<string, { bg: string; text: string; border: string }> = {
		low: { bg: 'bg-green-500/10', text: 'text-green-600 dark:text-green-400', border: 'border-green-500/30' },
		medium: { bg: 'bg-yellow-500/10', text: 'text-yellow-600 dark:text-yellow-400', border: 'border-yellow-500/30' },
		high: { bg: 'bg-orange-500/10', text: 'text-orange-600 dark:text-orange-400', border: 'border-orange-500/30' },
		critical: { bg: 'bg-red-500/10', text: 'text-red-600 dark:text-red-400', border: 'border-red-500/30' }
	};

	const DEPT_NAMES: Record<string, string> = {
		sales_admin: 'Sales & Admin',
		customer: 'Customer Success',
		back_office: 'Back Office',
		chief: 'Chief AI'
	};

	function formatTimestamp(ts: number): string {
		return new Date(ts).toLocaleString();
	}

	async function handleApprove() {
		submitting = true;
		dispatch('approve', { id: proposal.id, note: reviewNote });
	}

	async function handleReject() {
		submitting = true;
		dispatch('reject', { id: proposal.id, note: reviewNote });
	}

	$: riskStyle = RISK_COLORS[proposal.risk_level] ?? RISK_COLORS.low;
	$: isPending = proposal.status === 'pending';
</script>

<div class="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-900">
	<!-- Header -->
	<div class="flex items-start justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
		<div class="flex-1">
			<h2 class="text-lg font-semibold">{proposal.title}</h2>
			<div class="mt-1 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
				<span>{DEPT_NAMES[proposal.department_id] ?? proposal.department_id}</span>
				<span>·</span>
				<span>{proposal.action_type.replace(/_/g, ' ')}</span>
				<span>·</span>
				<span>{formatTimestamp(proposal.created_at)}</span>
			</div>
		</div>
		<button
			class="rounded-lg p-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
			on:click={() => dispatch('close')}
		>
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<div class="max-h-[60vh] overflow-y-auto px-6 py-4">
		<!-- Risk Assessment -->
		<div class="mb-4 rounded-lg border p-4 {riskStyle.bg} {riskStyle.border}">
			<div class="flex items-center gap-2">
				<span class="text-sm font-medium {riskStyle.text}">
					{proposal.risk_level.charAt(0).toUpperCase() + proposal.risk_level.slice(1)} Risk
				</span>
				{#if proposal.risk_level === 'critical'}
					<svg class="h-4 w-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd"
							d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
							clip-rule="evenodd" />
					</svg>
				{/if}
			</div>
			{#if proposal.risk_reasoning}
				<p class="mt-1 text-sm {riskStyle.text} opacity-80">{proposal.risk_reasoning}</p>
			{/if}
		</div>

		<!-- Description -->
		<div class="mb-4">
			<h3 class="mb-1 text-sm font-medium text-gray-500 dark:text-gray-400">Description</h3>
			<p class="text-sm leading-relaxed">{proposal.description}</p>
		</div>

		<!-- Action Payload -->
		{#if proposal.action_payload && Object.keys(proposal.action_payload).length > 0}
			<div class="mb-4">
				<h3 class="mb-1 text-sm font-medium text-gray-500 dark:text-gray-400">Action Details</h3>
				<div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
					<pre class="overflow-x-auto text-xs leading-relaxed">{JSON.stringify(proposal.action_payload, null, 2)}</pre>
				</div>
			</div>
		{/if}

		<!-- Metadata -->
		<div class="mb-4 grid grid-cols-2 gap-3 text-sm">
			<div>
				<span class="text-gray-500 dark:text-gray-400">Created by</span>
				<p class="font-medium">{proposal.created_by_ai ?? 'Unknown'}</p>
			</div>
			{#if proposal.reviewed_by}
				<div>
					<span class="text-gray-500 dark:text-gray-400">Reviewed by</span>
					<p class="font-medium">{proposal.reviewed_by}</p>
				</div>
			{/if}
			{#if proposal.review_note}
				<div class="col-span-2">
					<span class="text-gray-500 dark:text-gray-400">Review note</span>
					<p class="font-medium">{proposal.review_note}</p>
				</div>
			{/if}
		</div>

		<!-- Execution Result -->
		{#if proposal.execution_result && Object.keys(proposal.execution_result).length > 0}
			<div class="mb-4">
				<h3 class="mb-1 text-sm font-medium text-gray-500 dark:text-gray-400">Execution Result</h3>
				<div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
					<pre class="overflow-x-auto text-xs">{JSON.stringify(proposal.execution_result, null, 2)}</pre>
				</div>
			</div>
		{/if}

		<!-- Review Note Input -->
		{#if isPending}
			<div class="mt-4">
				<label for="review-note" class="mb-1 block text-sm font-medium text-gray-500 dark:text-gray-400">
					Review Note (optional)
				</label>
				<textarea
					id="review-note"
					bind:value={reviewNote}
					placeholder="Add a note about your decision..."
					rows="2"
					class="w-full rounded-lg border border-gray-200 bg-transparent px-3 py-2 text-sm
						focus:border-blue-500 focus:outline-none dark:border-gray-700"
				/>
			</div>
		{/if}
	</div>

	<!-- Action Buttons -->
	{#if isPending}
		<div class="flex items-center justify-end gap-2 border-t border-gray-200 px-6 py-4 dark:border-gray-700">
			<button
				class="rounded-lg px-4 py-2 text-sm font-medium text-red-600 transition-colors
					hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
				disabled={submitting}
				on:click={handleReject}
			>
				Reject
			</button>
			<button
				class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors
					hover:bg-green-700 disabled:opacity-50"
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
