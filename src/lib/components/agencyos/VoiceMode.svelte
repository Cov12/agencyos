<script lang="ts">
	import { goto } from '$app/navigation';

	let isListening = true;
	let statusText = 'Listening to your request...';
	let subtitle = "Go ahead, I'm ready for your command.";

	function dismiss() {
		goto('/agencyos');
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') dismiss();
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-black/40 backdrop-blur-xl">
	<div class="flex flex-col items-center justify-center w-full max-w-2xl relative">
		<!-- Orb -->
		<div class="relative flex items-center justify-center size-[300px] mb-12">
			<div class="absolute inset-0 rounded-full bg-[#20B2AA]/20 blur-[80px] animate-pulse"></div>
			<div class="absolute size-full rounded-full border border-[#20B2AA]/30 animate-[wave_2s_linear_infinite] opacity-0"></div>
			<div class="absolute size-full rounded-full border border-[#20B2AA]/20 animate-[wave_2s_linear_infinite] opacity-0" style="animation-delay: 0.8s"></div>
			<div class="relative size-48 rounded-full orb-core animate-[orb-breathe_4s_ease-in-out_infinite] backdrop-blur-md flex items-center justify-center border border-white/10">
				<div class="absolute top-4 left-6 size-16 bg-gradient-to-br from-white/30 to-transparent rounded-full blur-xl transform -rotate-45"></div>
				<span class="material-symbols-outlined text-white/50 text-6xl drop-shadow-[0_0_15px_rgba(255,255,255,0.5)]">graphic_eq</span>
			</div>
		</div>

		<!-- Status -->
		<div class="flex flex-col items-center gap-3 text-center z-10">
			<h1 class="text-white text-3xl md:text-4xl font-semibold tracking-tight drop-shadow-xl">{statusText}</h1>
			<p class="text-slate-300 text-lg font-light tracking-wide max-w-md">{subtitle}</p>
		</div>

		<!-- Waveform -->
		<div class="h-12 flex items-center gap-1 mt-8 opacity-60">
			{#each [3, 6, 4, 8, 4, 6, 3] as h, i}
				<div class="w-1 bg-[#20B2AA] rounded-full animate-pulse" style="height: {h * 4}px; animation-duration: {0.8 + i * 0.2}s"></div>
			{/each}
		</div>
	</div>

	<!-- Controls -->
	<div class="absolute bottom-12 flex items-center gap-4">
		<button class="group flex items-center justify-center size-12 rounded-full glass-panel hover:bg-white/10 transition-all text-slate-300 hover:text-white">
			<span class="material-symbols-outlined transition-transform group-hover:rotate-45">settings</span>
		</button>
		<button class="group flex items-center gap-2 pl-4 pr-5 h-12 rounded-full glass-panel hover:bg-white/10 transition-all border border-white/10 hover:border-white/20" on:click={dismiss}>
			<div class="size-6 bg-slate-800 rounded-full flex items-center justify-center group-hover:bg-slate-700 transition-colors">
				<span class="material-symbols-outlined text-[16px] text-white">close</span>
			</div>
			<span class="text-white text-sm font-semibold tracking-wide">Dismiss</span>
		</button>
		<div class="absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
			<span class="text-white/30 text-xs font-mono">Press ESC to close</span>
		</div>
	</div>
</div>

<style>
	.glass-panel {
		background: rgba(17, 33, 32, 0.4);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border: 1px solid rgba(255, 255, 255, 0.1);
	}
	.orb-core {
		background: radial-gradient(circle at 30% 30%, rgba(32, 178, 170, 0.8), rgba(32, 178, 170, 0.2));
		box-shadow: 0 0 60px rgba(32, 178, 170, 0.4), inset 0 0 40px rgba(255, 255, 255, 0.2);
	}
	@keyframes orb-breathe {
		0%, 100% { transform: scale(1); opacity: 0.8; }
		50% { transform: scale(1.05); opacity: 1; }
	}
	@keyframes wave {
		0% { transform: scale(1); opacity: 0.5; }
		100% { transform: scale(2); opacity: 0; }
	}
</style>
