<script lang="ts">
	// P1: step 2 captures business context (the facts seeded into Contexta). Department
	// provisioning is P2 — DeptSetup.svelte is left untouched for that drop, and this step
	// deliberately does not activate or create anything.
	import ContextSetup from '$lib/components/agencyos/onboarding/ContextSetup.svelte';
</script>

<ContextSetup step={2} />
