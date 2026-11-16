<script context="module" lang="ts">
	let nextId = 0;
	let lastAnnouncement = '';
</script>

<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { locale, t } from '$lib/i18n';
	import { copyText } from '$lib/utils/clipboard';
	import ActionIcon from './ActionIcon.svelte';
	export let text = '';
	export let align: 'start' | 'end' = 'start';
	export let code = false;
	export let onFeedback = (_active: boolean) => {};
	const sourceId = 'copy-source-' + ++nextId;
	let source: HTMLTextAreaElement, button: HTMLButtonElement;
	let state: 'idle' | 'success' | 'failure' = 'idle',
		announcement = '';
	let timer: ReturnType<typeof setTimeout>,
		nativeCommands = false,
		disposed = false;
	$: label = getLabel($locale, state, code);
	function getLabel(_locale: string, value: typeof state, isCode: boolean) {
		return value === 'success'
			? t('Copied')
			: value === 'failure'
				? t('Copy failed. Select the text and copy manually.')
				: isCode
					? t('Copy code')
					: t('Copy');
	}
	async function copy() {
		if (!text.length) return;
		clearTimeout(timer);
		try {
			await copyText(text, button.closest('dialog') || document.body);
			if (disposed) return;
			state = 'success';
		} catch {
			if (disposed) return;
			state = 'failure';
		}
		let message =
			state === 'success' ? t('Copied') : t('Copy failed. Select the text and copy manually.');
		if (message === lastAnnouncement) message += '\u00a0';
		lastAnnouncement = message;
		announcement = message;
		onFeedback(true);
		timer = setTimeout(
			() => {
				state = 'idle';
				announcement = '';
				onFeedback(false);
			},
			state === 'success' ? 1500 : 3500
		);
	}
	onMount(() => {
		nativeCommands = 'CommandEvent' in window && 'commandForElement' in HTMLButtonElement.prototype;
		const command = (event: Event) => {
			if ((event as Event & { command: string }).command === '--copy') void copy();
		};
		source.addEventListener('command', command);
		return () => source.removeEventListener('command', command);
	});
	onDestroy(() => {
		disposed = true;
		clearTimeout(timer);
		onFeedback(false);
	});
</script>

<span class="copy-control" class:align-end={align === 'end'} data-state={state}>
	<textarea hidden readonly tabindex="-1" id={sourceId} bind:this={source} value={text}></textarea>
	<button
		bind:this={button}
		type="button"
		class="icon-button copy-button"
		aria-label={label}
		title={label}
		{...{ command: '--copy', commandfor: sourceId }}
		on:click={() => {
			if (!nativeCommands) void copy();
		}}
	>
		<ActionIcon name={state === 'success' ? 'check' : 'copy'} />
	</button>
	<span class="copy-status" class:visible={state !== 'idle'} role="status" aria-live="polite"
		>{announcement}</span
	>
</span>

<style>
	.copy-control {
		position: relative;
		display: inline-flex;
		flex: none;
	}
	.copy-status {
		position: absolute;
		inset-block-start: calc(100% + 2px);
		inset-inline-start: 0;
		z-index: 5;
		inline-size: max-content;
		max-inline-size: min(19rem, 75vw);
		border-radius: 8px;
		padding: 5px 8px;
		font-size: 12px;
		line-height: 1.4;
		background: var(--feedback-bg);
		color: var(--feedback-text);
		box-shadow: 0 2px 10px #0002;
		opacity: 0;
		pointer-events: none;
		transition: opacity 120ms ease-out;
	}
	.align-end .copy-status {
		inset-inline-start: auto;
		inset-inline-end: 0;
	}
	.copy-status.visible {
		opacity: 1;
	}
</style>
