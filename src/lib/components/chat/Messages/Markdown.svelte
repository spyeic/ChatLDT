<script lang="ts" context="module">
	import { marked, Renderer } from 'marked';
	import DOMPurify from 'dompurify';
	import hljs from 'highlight.js';
	import katex from 'katex';
	import mathExtension from '$lib/utils/marked/katex-extension';
	const escape = (value: string) =>
		value.replace(
			/[&<>"']/g,
			(c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] || c
		);
	const renderer = new Renderer();
	renderer.html = (html) => escape(html);
	renderer.image = (_href, _title, text) => escape(text || '');
	renderer.code = (code, language) => {
		const lang = (language || '').split(/\s/)[0];
		const html =
			lang && hljs.getLanguage(lang)
				? hljs.highlight(code, { language: lang }).value
				: escape(code);
		return `<pre><code class="hljs">${html}</code></pre>`;
	};
	marked.use({ renderer, breaks: true }, mathExtension({}));
	marked.use({
		extensions: ['inlineKatex', 'blockKatex'].map((name) => ({
			name,
			renderer: (token: any) =>
				katex.renderToString(token.text || '', {
					displayMode: token.displayMode,
					throwOnError: false,
					trust: false,
					maxExpand: 1000
				})
		}))
	});
</script>

<script lang="ts">
	import { mount, unmount } from 'svelte';
	import CopyButton from '$lib/components/common/CopyButton.svelte';
	export let content = '';
	$: html = DOMPurify.sanitize(marked.parse(content) as string, {
		USE_PROFILES: { html: true, mathMl: true },
		FORBID_TAGS: ['img', 'iframe', 'video', 'audio', 'form', 'input', 'svg']
	});
	function enhanceCodeBlocks(node: HTMLElement, _html: string) {
		let mounted: ReturnType<typeof mount>[] = [];
		function cleanup() {
			for (const component of mounted) void unmount(component);
			mounted = [];
		}
		function decorate() {
			for (const pre of node.querySelectorAll('pre')) {
				const code = pre.querySelector('code');
				if (!code) continue;
				const wrapper = document.createElement('div');
				wrapper.className = 'code-block';
				pre.before(wrapper);
				wrapper.append(pre);
				const actions = document.createElement('div');
				actions.className = 'code-actions';
				wrapper.append(actions);
				mounted.push(
					mount(CopyButton, {
						target: actions,
						props: { text: code.textContent || '', code: true, align: 'end' }
					})
				);
			}
		}
		decorate();
		return {
			update(_value: string) {
				cleanup();
				decorate();
			},
			destroy: cleanup
		};
	}
</script>

<div use:enhanceCodeBlocks={html} class="markdown prose dark:prose-invert max-w-none break-words">
	{@html html}
</div>

<style>
	.markdown {
		font-size: 16px;
		line-height: 1.7;
		overflow-wrap: anywhere;
	}
	.markdown :global(p),
	.markdown :global(ul),
	.markdown :global(ol),
	.markdown :global(blockquote) {
		margin-block: 0.85em;
	}
	.markdown :global(h1),
	.markdown :global(h2),
	.markdown :global(h3),
	.markdown :global(h4) {
		margin-block: 1.4em 0.65em;
		line-height: 1.35;
		font-weight: 600;
	}
	.markdown :global(li) {
		margin-block: 0.25em;
	}
	.markdown :global(pre) {
		max-width: 100%;
		font-size: 14px;
		line-height: 1.6;
	}
	.markdown :global(table) {
		max-width: 100%;
		white-space: nowrap;
	}

	.markdown :global(.code-block) {
		position: relative;
		max-width: 100%;
	}
	.markdown :global(.code-actions) {
		position: absolute;
		inset-block-start: 5px;
		inset-inline-end: 6px;
		color: #d4d4d4;
	}
	.markdown :global(pre) {
		overflow-x: auto;
		padding: 2.6rem 1rem 1rem;
		border-radius: 0.75rem;
		background: #171717;
		color: #eee;
	}
	.markdown :global(pre code.hljs) {
		display: block;
		padding: 0;
		background: transparent;
	}
	.markdown :global(a) {
		text-decoration: underline;
	}
	.markdown :global(table) {
		display: block;
		overflow-x: auto;
	}
	@media (max-width: 767px), (max-height: 500px) and (pointer: coarse) {
		.markdown :global(pre) {
			padding-block-start: 3.5rem;
		}
	}
</style>
