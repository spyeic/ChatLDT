<script lang="ts">
	import { createEventDispatcher, onDestroy, tick } from 'svelte';
	const dispatch = createEventDispatcher<{ close: void }>();
	export let labelledby = 'dialog-title';
	let element: HTMLDialogElement,
		sequence = 0,
		closing: Promise<boolean> | null = null;
	export async function showModal() {
		const ticket = ++sequence;
		closing = null;
		await tick();
		element.removeAttribute('data-closing');
		if (!element.open) {
			element.setAttribute('data-entering', '');
			element.showModal();
			void getComputedStyle(element).opacity;
			requestAnimationFrame(() =>
				requestAnimationFrame(() => {
					if (ticket === sequence) element.removeAttribute('data-entering');
				})
			);
		}
	}
	export function close(): Promise<boolean> {
		if (!element?.open) return Promise.resolve(true);
		if (closing) return closing;
		const ticket = ++sequence;
		element.setAttribute('data-closing', '');
		// Keep native modality/inert and focus until the fade has finished, also
		// in browsers which parse allow-discrete but cannot animate display.
		void getComputedStyle(element).opacity;
		const animations = element
			.getAnimations({ subtree: true })
			.filter((a) => a.effect instanceof KeyframeEffect && a.effect.target === element);
		closing = (async () => {
			let timeout: ReturnType<typeof setTimeout>;
			await Promise.race([
				Promise.allSettled(animations.map((a) => a.finished)),
				new Promise((resolve) => (timeout = setTimeout(resolve, 250)))
			]);
			clearTimeout(timeout!);
			if (ticket !== sequence) return false;
			element.close();
			element.removeAttribute('data-closing');
			closing = null;
			return true;
		})();
		return closing;
	}
	function closed() {
		if (element?.open) return; // Ignore a queued close event after a rapid reopen.
		++sequence;
		closing = null;
		dispatch('close');
	}
	onDestroy(() => {
		++sequence;
		if (element?.open) element.close();
	});
</script>

<dialog
	bind:this={element}
	aria-labelledby={labelledby}
	class="modal-panel"
	on:cancel={(event) => {
		event.preventDefault();
		void close();
	}}
	on:close={closed}
>
	<slot />
</dialog>

<style>
	.modal-panel {
		margin: auto;
		inline-size: min(92vw, 32rem);
		max-block-size: 85dvh;
		overflow-y: auto;
		overscroll-behavior: contain;
		border: 0;
		border-radius: 16px;
		padding: 24px;
		background: var(--panel-bg);
		color: var(--panel-text);
		box-shadow: 0 16px 70px #0003;
		opacity: 0;
		transition-property: opacity, transform, display, overlay;
		transition-duration: 150ms;
		transition-timing-function: ease-out;
		transition-behavior: allow-discrete;
	}
	.modal-panel[open]:not([data-closing]):not([data-entering]) {
		opacity: 1;
		transition-duration: 190ms;
	}
	.modal-panel:not([open]) {
		transition-duration: 0s;
	}
	.modal-panel::backdrop {
		background: #0000;
		overscroll-behavior: contain;
		overflow: hidden;
		transition-property: background-color, display, overlay;
		transition-duration: 150ms;
		transition-timing-function: ease-out;
		transition-behavior: allow-discrete;
	}
	.modal-panel[open]:not([data-closing]):not([data-entering])::backdrop {
		background: #0006;
		transition-duration: 190ms;
	}
	.modal-panel:not([open])::backdrop {
		transition-duration: 0s;
	}
	@starting-style {
		.modal-panel[open]:not([data-closing]):not([data-entering]) {
			opacity: 0;
		}
		.modal-panel[open]:not([data-closing]):not([data-entering])::backdrop {
			background: #0000;
		}
	}
	@media (prefers-reduced-motion: no-preference) {
		.modal-panel {
			transform: translateY(6px) scale(0.98);
		}
		.modal-panel[open]:not([data-closing]):not([data-entering]) {
			transform: translateY(0) scale(1);
		}
		@starting-style {
			.modal-panel[open]:not([data-closing]):not([data-entering]) {
				transform: translateY(6px) scale(0.98);
			}
		}
	}
	@media (max-width: 767px), (max-height: 500px) and (pointer: coarse) {
		.modal-panel {
			inset-inline: env(safe-area-inset-left, 0px) env(safe-area-inset-right, 0px);
			inline-size: min(
				92vw,
				32rem,
				calc(100vw - env(safe-area-inset-left, 0px) - env(safe-area-inset-right, 0px) - 24px)
			);
			inset-block-start: var(--app-viewport-top, 0px);
			inset-block-end: calc(
				100% - var(--app-viewport-height, var(--app-height)) - var(--app-viewport-top, 0px)
			);
			max-block-size: calc(
				var(--app-viewport-height, var(--app-height)) - env(safe-area-inset-top, 0px) -
					var(--app-safe-bottom, env(safe-area-inset-bottom, 0px)) - 24px
			);
			padding: 20px;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.modal-panel,
		.modal-panel::backdrop {
			transition-duration: 0s !important;
			transform: none;
		}
	}
</style>
