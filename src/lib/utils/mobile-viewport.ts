/** VisualViewport may shrink for a keyboard while the layout viewport does not. */
export function viewportGeometry(layoutHeight: number, height: number, top: number, scale: number) {
	if (Math.abs(scale - 1) > 0.02 || height <= 0) return null; // Preserve pinch zoom.
	return { height: Math.min(layoutHeight, height), top: Math.max(0, top) };
}

export function watchMobileViewport() {
	const root = document.documentElement;
	const mobile = matchMedia('(max-width: 767px), (max-height: 500px) and (pointer: coarse)');
	const viewport = window.visualViewport;
	let frame = 0;
	function update() {
		cancelAnimationFrame(frame);
		frame = requestAnimationFrame(() => {
			const geometry =
				mobile.matches && viewport
					? viewportGeometry(root.clientHeight, viewport.height, viewport.offsetTop, viewport.scale)
					: null;
			if (geometry) {
				root.style.setProperty('--app-viewport-height', `${geometry.height}px`);
				root.style.setProperty('--app-viewport-top', `${geometry.top}px`);
			} else {
				root.style.removeProperty('--app-viewport-height');
				root.style.removeProperty('--app-viewport-top');
			}
			const focused = document.activeElement?.matches('textarea, input, [contenteditable="true"]');
			const keyboard = focused && geometry && root.clientHeight - geometry.height > 150;
			root.style.setProperty(
				'--app-safe-bottom',
				keyboard ? '0px' : 'env(safe-area-inset-bottom, 0px)'
			);
		});
	}
	viewport?.addEventListener('resize', update);
	viewport?.addEventListener('scroll', update);
	window.addEventListener('resize', update);
	document.addEventListener('focusin', update);
	document.addEventListener('focusout', update);
	mobile.addEventListener('change', update);
	update();
	return () => {
		cancelAnimationFrame(frame);
		viewport?.removeEventListener('resize', update);
		viewport?.removeEventListener('scroll', update);
		window.removeEventListener('resize', update);
		document.removeEventListener('focusin', update);
		document.removeEventListener('focusout', update);
		mobile.removeEventListener('change', update);
		for (const name of ['--app-viewport-height', '--app-viewport-top', '--app-safe-bottom'])
			root.style.removeProperty(name);
	};
}
