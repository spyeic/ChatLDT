<script lang="ts">
	import { locale, t } from '$lib/i18n';
	import ActionIcon from '$lib/components/common/ActionIcon.svelte';
	import CopyButton from '$lib/components/common/CopyButton.svelte';
	export let content = '';
	export let editable = false;
	export let own = false;
	export let onEdit = () => {};
	let feedback = false;
</script>

<div
	class="message-actions"
	class:own
	class:feedback
	aria-label={$locale ? t('Message actions') : 'Message actions'}
>
	{#if editable}<button
			type="button"
			class="icon-button edit-message"
			aria-label={$locale ? t('Edit') : 'Edit'}
			title={$locale ? t('Edit') : 'Edit'}
			on:click={onEdit}><ActionIcon name="edit" /></button
		>{/if}
	{#if content.trim()}<CopyButton
			text={content}
			align={own ? 'end' : 'start'}
			onFeedback={(active) => (feedback = active)}
		/>{/if}
</div>

<style>
	.message-actions {
		display: flex;
		align-items: center;
		gap: 2px;
		min-block-size: 34px;
		padding-block-start: 3px;
		color: var(--muted-text);
	}
	.message-actions.own {
		justify-content: flex-end;
	}
	@media (hover: hover) and (pointer: fine) {
		.message-actions {
			opacity: 0;
			pointer-events: none;
			transition: opacity 150ms ease-out;
		}
		:global(.message-row:hover) .message-actions,
		:global(.message-row:focus-within) .message-actions,
		.message-actions:focus-within,
		.message-actions.feedback {
			opacity: 1;
			pointer-events: auto;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.message-actions {
			transition-duration: 0s;
		}
	}
</style>
