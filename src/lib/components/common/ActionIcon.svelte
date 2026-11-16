<script lang="ts">
	export let name: 'edit' | 'copy' | 'check' | 'plus' | 'close' | 'menu';
</script>

<svg
	width="20"
	height="20"
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.7"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	focusable="false"
>
	{#if name === 'edit'}<path d="m15 5 4 4M4 20l4.5-1 11-11a2.8 2.8 0 0 0-4-4l-11 11L4 20Z" />
	{:else if name === 'copy'}<rect x="4" y="8" width="12" height="12" rx="3" /><path
			d="M9 5V4a1 1 0 0 1 1-1h8a3 3 0 0 1 3 3v8a1 1 0 0 1-1 1h-1"
		/>
	{:else if name === 'check'}<path d="m5 12 4 4L19 6" />
	{:else if name === 'plus'}<path d="M12 5v14M5 12h14" />
	{:else if name === 'close'}<path d="m6 6 12 12M18 6 6 18" />
	{:else}<path d="M4 6h16M4 12h16M4 18h16" />{/if}
</svg>
