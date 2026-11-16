<script lang="ts">
	import ActionIcon from '$lib/components/common/ActionIcon.svelte';
	import { locale, t } from '$lib/i18n';
	export let text = '';
	export let disabled = false;
	export let busy = false;
	export let canCancel = false;
	export let label = 'Message';
	export let sendLabel = 'Send';
	export let cancelLabel = 'Stop generating';
	export let images: { url: string; name: string }[] = [];
	export let onSend = () => {};
	export let onCancel = () => {};
	export let onFiles = (files: File[]) => {};
	export let onRemove = (index: number) => {};
	let picker: HTMLInputElement;
	function paste(event: ClipboardEvent) {
		const files = Array.from(event.clipboardData?.files || []);
		if (files.length) {
			event.preventDefault();
			onFiles(files);
		}
	}
</script>

<form class="composer conversation-width" on:submit|preventDefault={onSend}>
	<div class="composer-box">
		{#if images.length}
			<div class="image-drafts flex gap-2 flex-wrap mb-2">
				{#each images as image, i}
					<div class="relative">
						<img class="size-20 rounded-xl object-cover" src={image.url} alt={image.name} /><button
							type="button"
							class="icon-button image-remove absolute top-0 right-0 rounded-full"
							aria-label={($locale ? t('Remove image') : 'Remove image') + ' ' + image.name}
							on:click={() => onRemove(i)}><ActionIcon name="close" /></button
						>
					</div>
				{/each}
			</div>
		{/if}
		<label class="sr-only" for="chat-input">{label}</label>
		<div class="growable-textarea" data-replicated-value={text}>
			<textarea
				id="chat-input"
				bind:value={text}
				maxlength="32000"
				rows="1"
				class="w-full bg-transparent resize-none border-0 rounded-xl px-2 py-1"
				placeholder={label}
				on:paste={paste}
				on:keydown={(event) => {
					if (
						event.key === 'Enter' &&
						!event.shiftKey &&
						!event.isComposing &&
						event.keyCode !== 229
					) {
						event.preventDefault();
						if (!disabled && !busy) onSend();
					}
				}}
			></textarea>
		</div>
		<div class="composer-actions flex items-center justify-between gap-2">
			<input
				bind:this={picker}
				class="sr-only"
				type="file"
				accept="image/jpeg,image/png,image/webp"
				multiple
				on:change={() => {
					onFiles(Array.from(picker.files || []));
					picker.value = '';
				}}
			/>
			<button
				type="button"
				class="upload-button icon-button rounded-full size-10 hover:bg-gray-200 dark:hover:bg-gray-700"
				aria-label={$locale ? t('Attach images') : 'Attach images'}
				title={$locale ? t('Attach images') : 'Attach images'}
				on:click={() => picker.click()}><ActionIcon name="plus" /></button
			>
			<div class="flex gap-2">
				{#if canCancel}<button
						type="button"
						class="primary-button round-action cancel-button"
						aria-label={cancelLabel}
						title={cancelLabel}
						disabled={busy}
						on:click={onCancel}><ActionIcon name="stop" /></button
					>{/if}
				<button
					type="submit"
					class="primary-button round-action"
					aria-label={sendLabel}
					title={sendLabel}
					disabled={disabled || busy || (!text.trim() && !images.length)}
					><ActionIcon name="up" /></button
				>
			</div>
		</div>
	</div>
</form>

<style>
	.composer {
		flex-shrink: 0;
		padding-bottom: 20px;
	}
	.composer-box {
		padding: 12px;
		border-radius: 26px;
		background: var(--composer-bg);
		box-shadow: var(--composer-shadow);
	}
	.composer-actions {
		margin-top: 4px;
	}
	.round-action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border: 0;
		border-radius: 50%;
		padding: 0;
		background: var(--send-bg);
		color: var(--send-text);
	}
	.round-action:disabled {
		opacity: 1;
		background: var(--disabled-bg);
		color: var(--disabled-text);
	}
	.cancel-button {
		background: var(--send-bg);
		color: var(--send-text);
	}
	.image-drafts {
		max-height: min(176px, calc(var(--app-viewport-height, var(--app-height)) * 0.2));
		overflow-y: auto;
		overscroll-behavior: contain;
	}
	.growable-textarea > textarea {
		display: block;
		width: 100%;
		height: auto;
		min-height: 36px;
		max-height: min(16rem, 30dvh);
		overflow-y: auto;
		field-sizing: content;
		line-height: 24px;
	}
	@supports not (field-sizing: content) {
		.growable-textarea {
			display: grid;
		}
		.growable-textarea::after,
		.growable-textarea > textarea {
			grid-area: 1/1;
			min-height: 36px;
			max-height: min(16rem, 30dvh);
			font: inherit;
			line-height: 24px;
			padding: 4px 8px;
			white-space: pre-wrap;
			overflow-wrap: anywhere;
		}
		.growable-textarea::after {
			content: attr(data-replicated-value) ' ';
			visibility: hidden;
			overflow: hidden;
		}
	}
	@media (max-width: 767px), (max-height: 500px) and (pointer: coarse) {
		.composer {
			padding-bottom: max(8px, var(--app-safe-bottom, env(safe-area-inset-bottom, 0px)));
		}
		.composer-box {
			padding: 8px;
		}
		.growable-textarea > textarea {
			font-size: 16px;
			min-height: 32px;
			max-height: min(216px, calc(var(--app-viewport-height, var(--app-height)) * 0.28));
		}
		.composer-actions {
			min-height: 44px;
			margin-top: 4px;
			gap: 4px;
		}
		.composer-actions > div {
			gap: 4px;
		}
		.composer-actions button {
			min-height: 44px;
			padding-inline: 12px;
			white-space: nowrap;
		}
		.composer-actions .round-action,
		.composer-actions .upload-button {
			min-width: 44px;
			padding: 0;
		}
		.image-drafts {
			max-height: min(120px, calc(var(--app-viewport-height, var(--app-height)) * 0.2));
			overflow-y: auto;
			overscroll-behavior: contain;
		}
		@supports not (field-sizing: content) {
			.growable-textarea::after,
			.growable-textarea > textarea {
				min-height: 32px;
				max-height: min(216px, calc(var(--app-viewport-height, var(--app-height)) * 0.28));
				font-size: 16px;
			}
		}
	}

	.image-remove {
		background: #262626;
		color: white;
	}
	@media (hover: hover) {
		.image-remove:hover {
			background: #404040;
		}
	}
	.image-remove:active {
		background: #525252;
	}
</style>
