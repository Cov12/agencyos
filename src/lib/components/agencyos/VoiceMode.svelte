<script lang="ts">
	import { goto } from '$app/navigation';
	import { onDestroy } from 'svelte';

	export let onDismiss: (() => void) | undefined = undefined;
	import { user } from '$lib/stores';
	import { activeDeptId, activeDept, activeOrgId } from '$lib/stores/agencyos';
	import { sendDepartmentChat, sendChiefChat } from '$lib/apis/agencyos';
	import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';

	type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking';

	interface VoiceTurn {
		role: 'user' | 'ai';
		text: string;
		timestamp: number;
	}

	let voiceState: VoiceState = 'idle';
	let mediaRecorder: MediaRecorder | null = null;
	let audioChunks: Blob[] = [];
	let currentAudio: HTMLAudioElement | null = null;
	let conversationHistory: VoiceTurn[] = [];
	let chatId: string | undefined;

	let lastTranscription = '';
	let lastResponse = '';
	let errorMessage = '';
	let abortProcessing = false;


	const stateTitles: Record<VoiceState, string> = {
		idle: 'Tap to speak',
		listening: 'Listening...',
		processing: 'Thinking...',
		speaking: 'Speaking...'
	};

	$: deptName = $activeDept?.name ?? 'Chief AI';
	$: statusText = stateTitles[voiceState];
	$: subtitle = `Connected to ${deptName}`;
	$: recentTurns = conversationHistory.slice(-4).reverse();

	function getAuthToken() {
		return (($user as { token?: string } | undefined)?.token ?? localStorage.token) as string | undefined;
	}

	function getRecorderMimeType() {
		if (typeof MediaRecorder === 'undefined') return '';
		if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
		if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
		if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
		return '';
	}

	async function startListening() {
		if (voiceState === 'processing') return;

		stopSpeaking();
		errorMessage = '';
		lastTranscription = '';
		abortProcessing = false;

		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			const mimeType = getRecorderMimeType();
			mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
			audioChunks = [];

			mediaRecorder.ondataavailable = (event: BlobEvent) => {
				if (event.data.size > 0) audioChunks = [...audioChunks, event.data];
			};

			mediaRecorder.onstop = () => {
				mediaRecorder?.stream.getTracks().forEach((track) => track.stop());
				mediaRecorder = null;
				if (!abortProcessing) {
					processAudio();
				} else {
					voiceState = 'idle';
					abortProcessing = false;
				}
			};

			mediaRecorder.start();
			voiceState = 'listening';
		} catch (error) {
			errorMessage =
				error instanceof Error
					? error.message
					: 'Microphone access failed. Please allow microphone permissions.';
			voiceState = 'idle';
		}
	}

	function stopListening() {
		if (voiceState !== 'listening') return;
		mediaRecorder?.stop();
	}

	function interruptListening() {
		if (voiceState !== 'listening') return;
		abortProcessing = true;
		mediaRecorder?.stop();
	}

	function stopSpeaking() {
		if (currentAudio) {
			currentAudio.pause();
			currentAudio.currentTime = 0;
			if (currentAudio.src.startsWith('blob:')) URL.revokeObjectURL(currentAudio.src);
			currentAudio = null;
		}
		if (voiceState === 'speaking') voiceState = 'idle';
	}

	function interruptVoiceMode() {
		if (voiceState === 'listening') {
			interruptListening();
			return;
		}

		if (voiceState === 'speaking') {
			stopSpeaking();
			return;
		}
	}

	async function processAudio() {
		if (!audioChunks.length) {
			voiceState = 'idle';
			return;
		}

		voiceState = 'processing';
		errorMessage = '';

		try {
			const token = getAuthToken();
			if (!token) throw new Error('Missing auth token. Please sign in again.');

			const mimeType = mediaRecorder?.mimeType || 'audio/webm';
			const audioBlob = new Blob(audioChunks, { type: mimeType });
			audioChunks = [];

			const formData = new FormData();
			formData.append('file', audioBlob, 'recording.webm');

			const transcriptionRes = await fetch('/api/v1/audio/transcriptions', {
				method: 'POST',
				headers: { Authorization: `Bearer ${token}` },
				body: formData
			});

			if (!transcriptionRes.ok) {
				throw new Error('Transcription failed. Please try speaking again.');
			}

			const transcriptionData = await transcriptionRes.json();
			const transcribedText = String(transcriptionData?.text ?? '').trim();

			if (!transcribedText) {
				voiceState = 'idle';
				errorMessage = 'I could not hear anything clearly. Please try again.';
				return;
			}

			lastTranscription = transcribedText;
			conversationHistory = [
				...conversationHistory,
				{ role: 'user', text: transcribedText, timestamp: Date.now() }
			];

			const responseText = await sendVoiceMessage(transcribedText);
			lastResponse = responseText;
			conversationHistory = [
				...conversationHistory,
				{ role: 'ai', text: responseText, timestamp: Date.now() }
			];

			await speakResponse(responseText);
		} catch (error) {
			console.error(error);
			errorMessage = error instanceof Error ? error.message : 'Voice processing failed.';
			voiceState = 'idle';
		}
	}

	async function sendVoiceMessage(text: string) {
		const token = getAuthToken();
		const currentUserId = $user?.id ?? 'voice-user';
		if (!token) throw new Error('Missing auth token.');

		const conversation_history = conversationHistory
			.slice(-10)
			.map((turn) => ({ role: turn.role === 'user' ? 'user' : 'assistant', content: turn.text }));

		const payload = {
			message: text,
			user_id: currentUserId,
			chat_id: chatId,
			conversation_history
		};

		const response =
			$activeDeptId && $activeDeptId !== 'chief'
				? await sendDepartmentChat(token, $activeOrgId, $activeDeptId, payload)
				: await sendChiefChat(token, $activeOrgId, payload);

		chatId = response.proposals?.[0]?.chat_id ?? chatId;
		return response.content;
	}

	async function speakResponse(text: string) {
		const token = getAuthToken();
		if (!token) throw new Error('Missing auth token.');

		voiceState = 'speaking';

		const speechRes = await fetch('/api/v1/audio/speech', {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ input: text })
		});

		if (!speechRes.ok) {
			throw new Error('Speech playback failed.');
		}

		const audioBlob = await speechRes.blob();
		const audioUrl = URL.createObjectURL(audioBlob);
		const audio = new Audio(audioUrl);

		audio.onended = () => {
			URL.revokeObjectURL(audioUrl);
			if (currentAudio === audio) currentAudio = null;
			voiceState = 'idle';
		};

		audio.onerror = () => {
			URL.revokeObjectURL(audioUrl);
			if (currentAudio === audio) currentAudio = null;
			errorMessage = 'Audio playback failed.';
			voiceState = 'idle';
		};

		currentAudio = audio;
		await audio.play();
	}

	function dismiss() {
		interruptVoiceMode();
		if (onDismiss) {
			onDismiss();
		} else {
			goto('/agencyos');
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') dismiss();
	}

	onDestroy(() => {
		if (voiceState === 'listening') {
			abortProcessing = true;
			mediaRecorder?.stop();
		}
		stopSpeaking();
	});
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-black/40 backdrop-blur-xl px-4">
	<div class="flex flex-col items-center justify-center w-full max-w-2xl relative">
		<div class="text-xs sm:text-sm text-[#20B2AA]/90 tracking-wide uppercase mb-4 sm:mb-6 px-3 py-1.5 rounded-full border border-[#20B2AA]/25 bg-[#1c1c21]/70 backdrop-blur-md">
			Voice Channel: {deptName}
		</div>

		<!-- Orb -->
		<div class="relative flex items-center justify-center w-[200px] h-[200px] sm:w-[260px] sm:h-[260px] md:w-[300px] md:h-[300px] mb-8 sm:mb-10">
			<div class="absolute inset-0 rounded-full bg-[#20B2AA]/20 blur-[80px] animate-pulse"></div>
			{#if voiceState === 'listening' || voiceState === 'speaking'}
				<div class="absolute w-full h-full rounded-full border border-[#20B2AA]/30 animate-[wave_2s_linear_infinite] opacity-0"></div>
				<div class="absolute w-full h-full rounded-full border border-[#20B2AA]/20 animate-[wave_2s_linear_infinite] opacity-0" style="animation-delay: 0.8s"></div>
			{/if}
			<div class="relative w-32 h-32 sm:w-40 sm:h-40 md:w-48 md:h-48 rounded-full orb-core backdrop-blur-md flex items-center justify-center border border-white/10 {voiceState === 'listening' ? 'animate-[orb-breathe_4s_ease-in-out_infinite]' : ''}">
				<div class="absolute top-4 left-6 w-16 h-16 bg-gradient-to-br from-white/30 to-transparent rounded-full blur-xl transform -rotate-45"></div>
				{#if voiceState === 'processing'}
					<MaterialIcon icon="hourglass_top" size={48} class="text-white/70 animate-spin sm:text-[64px]" />
				{:else if voiceState === 'speaking'}
					<MaterialIcon icon="volume_up" size={48} class="text-white/70 drop-shadow-[0_0_15px_rgba(255,255,255,0.5)] sm:text-[64px]" />
				{:else}
					<MaterialIcon icon="graphic_eq" size={48} class="text-white/60 drop-shadow-[0_0_15px_rgba(255,255,255,0.5)] sm:text-[64px]" />
				{/if}
			</div>
		</div>

		<!-- Status -->
		<div class="flex flex-col items-center gap-2 sm:gap-3 text-center z-10 px-2">
			<h1 class="text-white text-xl sm:text-2xl md:text-4xl font-semibold tracking-tight drop-shadow-xl break-words">{statusText}</h1>
			<p class="text-slate-300 text-sm sm:text-base md:text-lg font-light tracking-wide max-w-md break-words">{subtitle}</p>
		</div>

		{#if voiceState === 'speaking'}
			<!-- Waveform -->
			<div class="h-12 flex items-center gap-1 mt-6 sm:mt-8 opacity-60">
				{#each [3, 6, 4, 8, 4, 6, 3] as h, i}
					<div class="w-1 bg-[#20B2AA] rounded-full animate-pulse" style="height: {h * 4}px; animation-duration: {0.8 + i * 0.2}s"></div>
				{/each}
			</div>
		{/if}

		<div class="mt-6 w-full max-w-xl rounded-2xl border border-white/10 bg-[#1c1c21]/70 backdrop-blur-md p-4 sm:p-5 space-y-2">
			{#if lastTranscription}
				<p class="text-xs uppercase tracking-wider text-white/40">Heard</p>
				<p class="text-sm sm:text-base text-white/90">“{lastTranscription}”</p>
			{/if}
			{#if lastResponse}
				<p class="text-xs uppercase tracking-wider text-white/40 pt-1">Response</p>
				<p class="text-sm sm:text-base text-[#20B2AA]/95">{lastResponse}</p>
			{/if}
			{#if !lastTranscription && !lastResponse}
				<p class="text-sm text-white/50">Your voice conversation will appear here.</p>
			{/if}
		</div>

		{#if errorMessage}
			<p class="mt-4 text-sm text-rose-300 bg-rose-500/10 border border-rose-300/20 rounded-xl px-3 py-2 max-w-xl text-center">
				{errorMessage}
			</p>
		{/if}

		{#if recentTurns.length}
			<div class="mt-4 w-full max-w-xl space-y-2">
				{#each recentTurns as turn}
					<div class="text-xs sm:text-sm rounded-xl px-3 py-2 border border-white/10 bg-white/[0.03] text-white/70">
						<span class="uppercase tracking-wide text-[10px] text-white/40 mr-2">{turn.role === 'user' ? 'You' : deptName}</span>
						{turn.text}
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Controls -->
	<div class="absolute bottom-8 sm:bottom-12 flex items-center gap-3 sm:gap-4 flex-wrap justify-center px-4">
		{#if voiceState === 'idle'}
			<button
				class="group flex items-center gap-2 sm:gap-3 pl-5 pr-6 h-14 min-h-[56px] rounded-full border border-[#20B2AA]/40 bg-[#20B2AA]/15 hover:bg-[#20B2AA]/25 transition-all shadow-[0_0_30px_rgba(32,178,170,0.2)]"
				on:click={startListening}
			>
				<div class="w-8 h-8 rounded-full bg-[#20B2AA]/30 flex items-center justify-center">
					<MaterialIcon icon="mic" class="text-white" />
				</div>
				<span class="text-white text-sm sm:text-base font-semibold tracking-wide">Tap to talk</span>
			</button>
		{:else if voiceState === 'listening' || voiceState === 'speaking'}
			<button
				class="group flex items-center gap-2 pl-4 pr-5 h-12 min-h-[48px] rounded-full hover:bg-rose-500/15 transition-all border border-rose-300/30 hover:border-rose-200/50 bg-rose-500/10 backdrop-blur-md"
				on:click={interruptVoiceMode}
			>
				<div class="w-6 h-6 bg-rose-900/70 rounded-full flex items-center justify-center group-hover:bg-rose-800/80 transition-colors">
					<MaterialIcon icon="stop" size={16} class="text-white" />
				</div>
				<span class="text-white text-sm font-semibold tracking-wide">
					{voiceState === 'listening' ? 'Stop listening' : 'Stop speaking'}
				</span>
			</button>
		{/if}

		{#if voiceState === 'listening'}
			<button class="group flex items-center gap-2 pl-4 pr-5 h-12 min-h-[48px] rounded-full hover:bg-white/10 transition-all border border-white/10 hover:border-white/20 bg-white/5 backdrop-blur-md" on:click={stopListening}>
				<div class="w-6 h-6 bg-slate-700 rounded-full flex items-center justify-center group-hover:bg-slate-600 transition-colors">
					<MaterialIcon icon="check" size={16} class="text-white" />
				</div>
				<span class="text-white text-sm font-semibold tracking-wide">Done</span>
			</button>
		{/if}

		<button class="group flex items-center gap-2 pl-4 pr-5 h-12 min-h-[48px] rounded-full hover:bg-white/10 transition-all border border-white/10 hover:border-white/20 bg-white/5 backdrop-blur-md" on:click={dismiss}>
			<div class="w-6 h-6 bg-slate-800 rounded-full flex items-center justify-center group-hover:bg-slate-700 transition-colors">
				<MaterialIcon icon="close" size={16} class="text-white" />
			</div>
			<span class="text-white text-sm font-semibold tracking-wide">Dismiss</span>
		</button>

		<div class="absolute -bottom-7 sm:-bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
			<span class="text-white/30 text-xs font-mono hidden sm:inline">Press ESC to close</span>
		</div>
	</div>
</div>

<style>
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
