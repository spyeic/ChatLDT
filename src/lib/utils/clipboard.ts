/** Copy raw source. Never claim success unless the browser confirms the write. */
export async function copyText(
	text: string,
	container: HTMLElement = document.body
): Promise<void> {
	if (window.isSecureContext && navigator.clipboard?.writeText) {
		try {
			await navigator.clipboard.writeText(text);
			return;
		} catch {
			/* Try the legacy user-gesture path below. */
		}
	}
	const selection = window.getSelection();
	const ranges = selection
		? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i).cloneRange())
		: [];
	const active = document.activeElement as HTMLElement | null;
	const field = document.createElement('textarea');
	field.value = text;
	field.readOnly = true;
	field.tabIndex = -1;
	field.style.cssText =
		'position:fixed;inset:0 auto auto 0;width:1px;height:1px;opacity:0;pointer-events:none';
	container.append(field);
	try {
		field.focus({ preventScroll: true });
		field.select();
		if (!document.execCommand || !document.execCommand('copy'))
			throw new Error('Clipboard write was denied');
	} finally {
		field.remove();
		if (active?.isConnected) active.focus({ preventScroll: true });
		if (selection) {
			selection.removeAllRanges();
			for (const range of ranges)
				if (range.commonAncestorContainer.isConnected) selection.addRange(range);
		}
	}
}
