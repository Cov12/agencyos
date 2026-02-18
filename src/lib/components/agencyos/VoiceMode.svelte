<script lang="ts">
	import { onDestroy, createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	export let disabled = false;

	type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';
	let state: VoiceState = 'idle';

	let mediaRecorder: MediaRecorder | null = null;
	let audioChunks: Blob[] = [];
	let analyserNode: AnalyserNode | null = null;
	let animationFrame: number | null = null;
	let canvas: HTMLCanvasElement;
	let audioLevel = 0;

	const STATE_LABELS: Record<VoiceState, string> = {
		idle: 'Tap to speak',
		listening: 'Listening...',
		thinking: 'Thinking...',
		speaking: 'Speaking...'
	};

	async function startListening() {
		if (disabled || state !== 'idle') return;

		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

			// Set up audio analyser for visual feedback
			const audioCtx = new AudioContext();
			const source = audioCtx.createMediaStreamSource(stream);
			analyserNode = audioCtx.createAnalyser();
			analyserNode.fftSize = 256;
			source.connect(analyserNode);

			// Set up recorder
			mediaRecorder = new MediaRecorder(stream);
			audioChunks = [];

			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) audioChunks.push(e.data);
			};

			mediaRecorder.onstop = () => {
				const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
				stream.getTracks().forEach((t) => t.stop());
				cancelAnimationFrame(animationFrame!);
				analyserNode = null;

				state = 'thinking';
				dispatch('audio', { blob: audioBlob });
			};

			mediaRecorder.start();
			state = 'listening';
			drawWaveform();
		} catch (err) {
			console.error('Microphone access denied:', err);
			state = 'idle';
		}
	}

	function stopListening() {
		if (state === 'listening' && mediaRecorder?.state === 'recording') {
			mediaRecorder.stop();
		}
	}

	function drawWaveform() {
		if (!analyserNode || !canvas) return;

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const bufferLength = analyserNode.frequencyBinCount;
		const dataArray = new Uint8Array(bufferLength);

		function draw() {
			if (!analyserNode) return;
			animationFrame = requestAnimationFrame(draw);

			analyserNode.getByteTimeDomainData(dataArray);

			// Calculate audio level (0-1)
			let sum = 0;
			for (let i = 0; i < bufferLength; i++) {
				const v = (dataArray[i] - 128) / 128;
				sum += v * v;
			}
			audioLevel = Math.sqrt(sum / bufferLength);
		}

		draw();
	}

	/** Called by parent when TTS audio starts playing */
	export function setSpeaking() {
		state = 'speaking';
	}

	/** Called by parent when TTS audio finishes */
	export function setIdle() {
		state = 'idle';
	}

	/** Called by parent when processing starts */
	export function setThinking() {
		state = 'thinking';
	}

	function handleClick() {
		if (state === 'idle') {
			startListening();
		} else if (state === 'listening') {
			stopListening();
		}
	}

	onDestroy(() => {
		if (mediaRecorder?.state === 'recording') {
			mediaRecorder.stop();
		}
		if (animationFrame) {
			cancelAnimationFrame(animationFrame);
		}
	});

	$: pulseScale = state === 'listening' ? 1 + audioLevel * 0.4 : 1;
</script>

<div class="flex flex-col items-center gap-2">
	<!-- Main Button -->
	<button
		class="relative flex h-14 w-14 items-center justify-center rounded-full transition-all duration-200
			{state === 'idle' ? 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700' : ''}
			{state === 'listening' ? 'bg-red-500 text-white shadow-lg shadow-red-500/30' : ''}
			{state === 'thinking' ? 'bg-blue-500 text-white' : ''}
			{state === 'speaking' ? 'bg-green-500 text-white' : ''}"
		{disabled}
		on:click={handleClick}
	>
		<!-- Pulse ring for listening state -->
		{#if state === 'listening'}
			<div
				class="absolute inset-0 rounded-full bg-red-500/30"
				style="transform: scale({pulseScale}); transition: transform 100ms ease-out;"
			/>
		{/if}

		<!-- Icon -->
		{#if state === 'idle'}
			<!-- Mic icon -->
			<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
					d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4M12 15a3 3 0 003-3V5a3 3 0 00-6 0v7a3 3 0 003 3z" />
			</svg>
		{:else if state === 'listening'}
			<!-- Stop icon -->
			<svg class="relative z-10 h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
				<rect x="6" y="6" width="12" height="12" rx="2" />
			</svg>
		{:else if state === 'thinking'}
			<!-- Spinner -->
			<div class="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-white" />
		{:else if state === 'speaking'}
			<!-- Waveform bars -->
			<div class="flex items-center gap-0.5">
				{#each [1, 2, 3, 4, 5] as bar}
					<div
						class="w-1 rounded-full bg-white"
						style="height: {8 + Math.random() * 12}px; animation: waveform 0.5s ease-in-out infinite alternate;
							animation-delay: {bar * 0.1}s;"
					/>
				{/each}
			</div>
		{/if}
	</button>

	<!-- State label -->
	<span class="text-xs text-gray-500 dark:text-gray-400">
		{STATE_LABELS[state]}
	</span>

	<!-- Hidden canvas for audio analysis -->
	<canvas bind:this={canvas} class="hidden" width="0" height="0" />
</div>

<style>
	@keyframes waveform {
		from {
			height: 6px;
		}
		to {
			height: 18px;
		}
	}
</style>
