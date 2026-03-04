<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import MaterialIcon from '$lib/components/agencyos/shared/MaterialIcon.svelte';

  const PORTAL_URL = 'https://portal.wbit.app';

  let loading = true;
  let error = '';

  onMount(async () => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const redirectTo = params.get('redirect_to');

    if (!token) {
      error = 'No authentication token was provided. Please sign in again from the portal.';
      loading = false;
      return;
    }

    try {
      localStorage.setItem('token', token);
      document.cookie = `agencyos_token=${encodeURIComponent(token)}; path=/; max-age=86400`;

      const destination = redirectTo && redirectTo.startsWith('/') ? redirectTo : '/agencyos';
      await goto(destination);
    } catch (e) {
      error = 'We could not complete sign-in. Please try again.';
      loading = false;
    }
  });
</script>

<div class="min-h-screen bg-[#0f0f13] flex items-center justify-center px-4">
  {#if loading}
    <div class="flex flex-col items-center gap-4 text-center">
      <div class="w-12 h-12 border-2 border-[#6961ff]/30 border-t-[#6961ff] rounded-full animate-spin"></div>
      <p class="text-white/50 text-sm">Completing sign-in...</p>
    </div>
  {:else if error}
    <div class="w-full max-w-md rounded-xl border border-white/10 bg-white/[0.03] p-6 text-center">
      <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#6961ff]/20 text-[#6961ff]">
        <MaterialIcon icon="error" class="text-2xl" />
      </div>
      <h1 class="text-white text-lg font-semibold">Authentication Error</h1>
      <p class="mt-2 text-white/50 text-sm">{error}</p>

      <a
        href="{PORTAL_URL}/auth/sign-in"
        class="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#6961ff] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#7b74ff]"
      >
        <MaterialIcon icon="refresh" class="text-base" />
        Return to Portal
      </a>
    </div>
  {/if}
</div>
