import { describe, it, expect } from 'vitest';
import { marked } from 'marked';
import mathExtension from './katex-extension';
describe('retained Markdown math tokenization', () => {
	it('keeps inline math and fenced source separate', () => {
		marked.use(mathExtension({}));
		const tokens = marked.lexer('Before $x^2$ after.\n\n```js\nconst x = 1;\n```');
		const inline = (tokens[0] as any).tokens;
		expect(inline.some((t: any) => t.type === 'inlineKatex' && t.text === 'x^2')).toBe(true);
		expect(tokens.some((t) => t.type === 'code')).toBe(true);
	});
	it('parses multiline display formulas without swallowing adjacent text', () => {
		const tokens = marked.lexer('$$\nx + y\n$$\n\nAfter');
		expect(tokens[0].type).toBe('blockKatex');
		expect(tokens[tokens.length - 1].type).toBe('paragraph');
	});
});
