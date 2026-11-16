<script lang="ts">
	import { onMount, tick } from 'svelte';
	export let open = false;
	export let collapsed = false;
	export let label = '';
	export let closeLabel = '';
	export let onClose = () => {};
	let element: HTMLDivElement;
	let mobile = false,
		supportsPopover = false,
		ready = false,
		mounted = false,
		active = false;
	let sequence = 0,
		closing: Promise<void> | null = null;
	let background: HTMLElement | null = null,
		backgroundWasInert = false;
	let returnFocus: HTMLElement | null = null;
	$: if (ready) void sync(open, mobile);
	function unlock() {
		if (background) background.inert = backgroundWasInert;
		background = null;
	}
	function hide(restoreFocus = true) {
		if (typeof element.hidePopover === 'function' && element.matches(':popover-open'))
			element.hidePopover();
		mounted = active = false;
		unlock();
		if (restoreFocus && returnFocus?.isConnected && !document.querySelector('dialog[open]'))
			returnFocus.focus({ preventScroll: true });
	}
	export function close(): Promise<void> {
		if (!mounted) return Promise.resolve();
		if (closing) return closing;
		const ticket = ++sequence;
		active = false;
		closing = (async () => {
			await tick();
			void getComputedStyle(element).opacity;
			const animations = element.getAnimations({ subtree: true });
			let timer: ReturnType<typeof setTimeout>;
			await Promise.race([
				Promise.allSettled(animations.map((a) => a.finished)),
				new Promise((r) => (timer = setTimeout(r, 300)))
			]);
			clearTimeout(timer!);
			if (ticket === sequence) {
				hide();
				closing = null;
			}
		})();
		return closing;
	}
	async function sync(wanted: boolean, isMobile: boolean) {
		if (!isMobile) {
			++sequence;
			hide(false);
			return;
		}
		if (!wanted) {
			await close();
			return;
		}
		if (mounted && active) return;
		const ticket = ++sequence;
		closing = null;
		if (!mounted) returnFocus = document.activeElement as HTMLElement;
		mounted = true;
		await tick();
		if (ticket !== sequence) return;
		if (typeof element.showPopover === 'function' && !element.matches(':popover-open'))
			element.showPopover();
		if (!background) {
			background = document.querySelector('.chat-pane');
			if (background) {
				backgroundWasInert = background.inert;
				background.inert = true;
			}
		}
		void getComputedStyle(element.querySelector('.sidebar')!).transform;
		requestAnimationFrame(() =>
			requestAnimationFrame(() => {
				if (ticket !== sequence) return;
				active = true;
				element.querySelector<HTMLButtonElement>('.drawer-close')?.focus({ preventScroll: true });
			})
		);
	}
	onMount(() => {
		supportsPopover = typeof element.showPopover === 'function';
		const media = matchMedia('(max-width: 767px), (max-height: 500px) and (pointer: coarse)');
		const change = () => {
			mobile = media.matches;
			if (!mobile) onClose();
		};
		change();
		ready = true;
		const keys = (event: KeyboardEvent) => {
			if (!mobile || !mounted || document.querySelector('dialog[open]')) return;
			if (event.key === 'Escape') {
				event.preventDefault();
				onClose();
			}
			if (event.key !== 'Tab') return;
			const buttons = Array.from(
				element.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, a[href]')
			).filter((e) => e.tabIndex >= 0 && e.getClientRects().length);
			const first = buttons[0],
				last = buttons.at(-1);
			if (event.shiftKey && document.activeElement === first) {
				event.preventDefault();
				last?.focus();
			} else if (!event.shiftKey && document.activeElement === last) {
				event.preventDefault();
				first?.focus();
			}
		};
		media.addEventListener('change', change);
		document.addEventListener('keydown', keys);
		return () => {
			++sequence;
			unlock();
			media.removeEventListener('change', change);
			document.removeEventListener('keydown', keys);
		};
	});
</script>

<div
	bind:this={element}
	id="chat-sidebar"
	class="drawer"
	class:mobile
	class:collapsed
	inert={!mobile && collapsed}
	class:mounted
	class:active
	popover={mobile && supportsPopover ? 'manual' : undefined}
	role={mobile ? 'dialog' : undefined}
	aria-modal={mobile && mounted ? 'true' : undefined}
	aria-label={mobile ? label : undefined}
>
	<button
		class="drawer-shade"
		type="button"
		tabindex="-1"
		aria-label={closeLabel}
		on:click={onClose}
	></button>
	<slot />
</div>

<style>
	.drawer {
		display: block;
		inline-size: var(--sidebar-width);
		flex-shrink: 0;
		overflow: hidden;
		transition: inline-size 230ms cubic-bezier(0.2, 0.7, 0.2, 1);
	}
	.drawer.collapsed:not(.mobile) {
		inline-size: 0;
	}
	.drawer-shade {
		display: none;
	}
	@media (max-width: 767px), (max-height: 500px) and (pointer: coarse) {
		.drawer:not(.mounted) {
			display: none;
		}
		.drawer.mobile {
			position: fixed;
			display: block;
			inset: var(--app-viewport-top, 0px) 0 auto;
			inline-size: 100%;
			block-size: 100vh;
			block-size: var(--app-viewport-height, var(--app-height));
			max-inline-size: none;
			max-block-size: none;
			margin: 0;
			padding: 0;
			border: 0;
			background: transparent;
			color: inherit;
			overflow: hidden;
			z-index: 50;
		}
		.drawer.mobile:not(.mounted) {
			display: none;
		}
		.drawer-shade {
			display: block;
			position: absolute;
			inset: 0;
			width: 100%;
			height: 100%;
			border: 0;
			border-radius: 0;
			background: #0007 !important;
			opacity: 0;
			transition: opacity 230ms ease-out;
		}
		.drawer.mobile :global(.sidebar) {
			position: relative;
			inline-size: min(84vw, 20rem);
			block-size: 100%;
			padding-block: max(12px, env(safe-area-inset-top, 0px))
				max(12px, var(--app-safe-bottom, env(safe-area-inset-bottom, 0px)));
			padding-inline-start: max(12px, env(safe-area-inset-left, 0px));
			transform: translateX(-100%);
			transition: transform 230ms cubic-bezier(0.2, 0.7, 0.2, 1);
			box-shadow: 4px 0 24px #0003;
		}
		.drawer.active :global(.sidebar) {
			transform: translateX(0);
		}
		.drawer.active .drawer-shade {
			opacity: 1;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.drawer,
		.drawer-shade,
		.drawer.mobile :global(.sidebar) {
			transition-duration: 0s;
		}
	}
</style>
