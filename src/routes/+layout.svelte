<script>
	import { onMount } from 'svelte';
	import { watchMobileViewport } from '$lib/utils/mobile-viewport';
	onMount(watchMobileViewport);
	import '../tailwind.css';
	import '../app.css';
	import 'katex/dist/katex.min.css';
	import 'highlight.js/styles/github-dark.css';
</script>

<slot />
