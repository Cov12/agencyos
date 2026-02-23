<script lang="ts">
	import { goto } from '$app/navigation';

	let currentTime = '14:02';
	let currentDate = 'Wednesday, October 24';

	function updateTime() {
		const now = new Date();
		currentTime = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
		currentDate = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
	}

	function unlock() {
		goto('/agencyos');
	}

	// Update time every second
	const interval = setInterval(updateTime, 1000);
	updateTime();
</script>

<div class="relative z-10 flex h-full w-full flex-col justify-between p-6 md:p-10">
	<!-- Aurora Background -->
	<div class="aurora-bg"></div>

	<!-- Header -->
	<header class="flex w-full items-center justify-between relative z-10">
		<div class="flex items-center gap-2 text-white/60 text-sm font-medium tracking-wide">
			<span class="material-symbols-outlined text-[18px]">signal_cellular_alt</span>
			<span>AgencyOS Network</span>
		</div>
		<div class="flex items-center gap-4">
			<div class="hidden md:flex gap-3">
				<div class="glass-button flex h-8 items-center justify-center rounded-full px-3 text-white/80 gap-2">
					<span class="material-symbols-outlined text-[16px]">wifi</span>
					<span class="text-xs font-semibold">Wi-Fi 6E</span>
				</div>
				<div class="glass-button flex h-8 items-center justify-center rounded-full px-3 text-white/80 gap-2">
					<span class="material-symbols-outlined text-[16px]">memory</span>
					<span class="text-xs font-semibold">AI Core Online</span>
				</div>
			</div>
		</div>
	</header>

	<!-- Center Clock -->
	<main class="flex flex-1 flex-col items-center justify-center text-center relative z-10">
		<h2 class="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-[#6961ff]/80">{currentDate}</h2>
		<h1 class="text-[8rem] leading-none font-thin tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-white/60 md:text-[10rem] lg:text-[12rem] drop-shadow-2xl">
			{currentTime}
		</h1>
		<div class="mt-8 flex flex-col items-center gap-3">
			<div class="flex items-center gap-3 rounded-2xl glass-panel px-6 py-3 shadow-lg">
				<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#6961ff] to-purple-600 shadow-inner">
					<span class="material-symbols-outlined text-white text-[20px]">dataset</span>
				</div>
				<div class="flex flex-col text-left">
					<span class="text-lg font-bold leading-tight tracking-tight text-white">AgencyOS</span>
					<span class="text-[10px] font-medium uppercase tracking-wider text-white/50">Neural Workspace</span>
				</div>
			</div>
		</div>
	</main>

	<!-- Unlock -->
	<footer class="mb-8 flex flex-col items-center gap-6 relative z-10">
		<button class="relative group cursor-pointer" on:click={unlock}>
			<div class="absolute -inset-1 rounded-full bg-[#6961ff]/20 blur-lg opacity-50 group-hover:opacity-100 transition duration-500 animate-pulse"></div>
			<div class="relative flex h-16 w-16 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur-md transition-all duration-300 hover:bg-white/20 hover:scale-105 active:scale-95 border border-white/10 ring-1 ring-white/20">
				<span class="material-symbols-outlined text-[32px]">fingerprint</span>
			</div>
		</button>
		<button class="group flex items-center gap-2 rounded-full glass-panel px-6 py-2.5 text-sm font-medium text-white transition-all hover:bg-white/10" on:click={unlock}>
			<span class="group-hover:text-[#6961ff] transition-colors">Click or Swipe to Enter</span>
			<span class="material-symbols-outlined text-[16px] text-white/50 group-hover:translate-x-1 group-hover:text-white transition-all">arrow_forward</span>
		</button>
	</footer>
</div>

<style>
	.aurora-bg {
		background:
			radial-gradient(circle at 15% 50%, rgba(105, 97, 255, 0.25) 0%, transparent 25%),
			radial-gradient(circle at 85% 30%, rgba(56, 189, 248, 0.15) 0%, transparent 25%),
			radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.1) 0%, transparent 50%);
		background-color: #0f0e17;
		position: absolute;
		inset: 0;
		z-index: 0;
	}
	.glass-panel {
		background: rgba(255, 255, 255, 0.03);
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
		border: 1px solid rgba(255, 255, 255, 0.05);
	}
	.glass-button {
		background: rgba(40, 39, 58, 0.4);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
	}
</style>
