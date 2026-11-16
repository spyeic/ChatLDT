import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { readFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
const base = process.env.CHATLDT_BROWSER_URL,
	file = process.env.CHATLDT_BROWSER_CREDENTIALS_FILE;
if (!base || !file) throw Error('Use an isolated fixture and private credentials.');
const creds = JSON.parse(readFileSync(file, 'utf8'));
const out = process.env.CHATLDT_TEST_ARTIFACTS || '/private/tmp/chatldt-chat-style/interaction';
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
	executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
});
const errors = [];
async function api(c, path, method = 'GET', data) {
	const session = await (await c.request.get(base + '/api/v1/ldt/session')).json();
	const r = await c.request.fetch(base + '/api/v1/ldt' + path, {
		method,
		headers: { Origin: base, 'x-ldt-csrf': session.csrf },
		data
	});
	assert.ok(r.ok(), `${path}: ${r.status()} ${await r.text()}`);
	return r.json();
}
async function until(fn, label) {
	for (let i = 0; i < 150; i++) {
		if (await fn()) return;
		await new Promise((r) => setTimeout(r, 30));
	}
	throw Error(label);
}
const png = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAANUlEQVR4nO3QsQ0AMAzDsLT//9yeoCkbeYAN6LzZdZf3x0GSKEmUJEoSJYmSREmiJFGSaMoHo8QBPwYSAhsAAAAASUVORK5CYII=',
	'base64'
);
try {
	const ac = await browser.newContext({
		viewport: { width: 1440, height: 900 },
		locale: 'en-US',
		colorScheme: 'dark'
	});
	await api(ac, '/signin', 'POST', { email: creds.email, password: creds.password });
	await api(ac, '/profile', 'PATCH', { name: 'admin', language: 'en-US', theme: 'dark' });
	const a = await ac.newPage();
	a.on('pageerror', (e) => errors.push(e.message));
	await a.goto(base);
	await a.locator('h1').waitFor();
	assert.equal(await a.locator('#chat-input').isVisible(), false);
	await a.getByRole('button', { name: 'Choose a registered user', exact: true }).click();
	await a.locator('#target-user').selectOption({ label: 'E' });
	await a.getByRole('button', { name: 'Confirm', exact: true }).click();
	await a.locator('dialog').waitFor({ state: 'hidden' });
	await a.locator('#chat-input').fill('Admin initiated test');
	await a.getByRole('button', { name: 'Send', exact: true }).click();
	await a.locator('main article').waitFor();
	assert.equal(await a.getByRole('button', { name: 'Send', exact: true }).isDisabled(), true);
	assert.equal(await a.getByRole('button', { name: 'Stop generating', exact: true }).count(), 0);
	console.log(
		'PASS admin recipient gate, registered-user creation, own-side alignment, no admin cancellation'
	);
	const gc = await browser.newContext({
		viewport: { width: 1440, height: 900 },
		locale: 'en-US',
		colorScheme: 'dark'
	});
	const g = await gc.newPage();
	g.on('pageerror', (e) => errors.push(e.message));
	await g.goto(base);
	await g.locator('h1').waitFor();
	assert.equal(
		await g.getByRole('button', { name: 'Start a conversation', exact: true }).count(),
		0
	);
	const input = g.locator('#chat-input');
	await input.fill('中文草稿');
	await input.focus();
	await g.evaluate(() => {
		window.__editor = document.querySelector('#chat-input');
	});
	await input.dispatchEvent('compositionstart');
	await input.dispatchEvent('keydown', {
		key: 'Enter',
		code: 'Enter',
		keyCode: 229,
		isComposing: true
	});
	assert.equal(await g.locator('dialog[open]').count(), 0);
	await input.dispatchEvent('compositionend');
	await g.keyboard.press('Shift+Enter');
	assert.match(await input.inputValue(), /\n/);
	await g
		.locator('input[type=file]')
		.first()
		.setInputFiles([
			{ name: 'one.png', mimeType: 'image/png', buffer: png },
			{ name: 'two.png', mimeType: 'image/png', buffer: png }
		]);
	const oldUrls = await g.locator('.image-drafts img').evaluateAll((es) => es.map((e) => e.src));
	await g.getByRole('button', { name: 'Send', exact: true }).click();
	await g.getByRole('button', { name: 'Cancel', exact: true }).click();
	await g.locator('dialog').waitFor({ state: 'hidden' });
	assert.deepEqual(
		await g.locator('.image-drafts img').evaluateAll((es) => es.map((e) => e.src)),
		oldUrls
	);
	assert.equal(await input.inputValue(), '中文草稿\n');
	await g.getByRole('button', { name: 'Send', exact: true }).click();
	await g.locator('#modal-field').fill('Style test guest');
	await g.getByRole('button', { name: 'Confirm', exact: true }).click();
	await g.locator('dialog').waitFor({ state: 'hidden' });
	await g.locator('main article img').first().waitFor();
	assert.ok(await g.evaluate(() => window.__editor === document.querySelector('#chat-input')));
	assert.equal(await g.locator('main article').count(), 1);
	assert.equal(await g.locator('main article img').count(), 2);
	assert.equal(await input.inputValue(), '');
	assert.equal(await g.locator('.image-drafts img').count(), 0);
	await input.focus();
	assert.equal(await input.evaluate((e) => e === document.activeElement), true);
	await input.fill('Draft while waiting');
	assert.equal(await g.getByRole('button', { name: 'Send', exact: true }).isDisabled(), true);
	await g.getByRole('button', { name: 'Stop generating', exact: true }).click();
	await g.getByText('Cancelled', { exact: true }).waitFor();
	assert.equal(await input.inputValue(), 'Draft while waiting');
	assert.equal(await g.locator('main article .edit-message').count(), 0);
	console.log(
		'PASS IME/Shift+Enter, nickname cancellation preserves draft and images, first send keeps editor node, waiting draft, cancellation locks edits'
	);
	// Hold the first send in flight and verify rapid activation uses one intent.
	let release;
	const gate = new Promise((r) => (release = r));
	await g.route('**/api/v1/ldt/send', async (route) => {
		await gate;
		await route.continue();
	});
	await g.getByRole('button', { name: 'Send', exact: true }).click();
	await g.locator('.composer').evaluate((e) => e.requestSubmit());
	release();
	await until(async () => (await g.locator('main article').count()) === 2, 'second message');
	await g.unroute('**/api/v1/ldt/send');
	await until(
		async () => await g.getByRole('button', { name: 'Stop generating', exact: true }).isEnabled(),
		'send finishes'
	);
	const chatId = new URL(g.url()).pathname.split('/').at(-1);
	let state = await api(ac, '/chats/' + chatId);
	const long =
		'## 阅读与排版\n\n' +
		'A paragraph with **Markdown**, lists and a formula $a^2+b^2=c^2$. 中文段落。\n\n'.repeat(35) +
		'```text\n' +
		'long_code_'.repeat(100) +
		'\n```\n\n|' +
		'Wide heading|'.repeat(18) +
		'\n|' +
		'---|'.repeat(18) +
		'\n|' +
		'Cell|'.repeat(18) +
		'\n';
	await api(ac, '/send', 'POST', {
		key: crypto.randomUUID(),
		chat_id: chatId,
		round_id: state.current_round_id,
		turn_version: state.turn_version,
		content: long,
		attachments: []
	});
	await g.locator('main article').nth(2).waitFor();
	await g.waitForTimeout(3300);
	await until(
		async () =>
			await g.locator('main').evaluate((e) => e.scrollHeight - e.scrollTop - e.clientHeight < 5),
		'follow at bottom'
	);
	assert.ok(await g.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
	await g.locator('main').evaluate((e) => (e.scrollTop = 120));
	await g.getByRole('button', { name: 'Back to bottom', exact: true }).waitFor();
	const oldScroll = await g.locator('main').evaluate((e) => e.scrollTop);
	// Editing an incoming message resizes history while the reader stays in place.
	state = await api(ac, '/chats/' + chatId);
	const last = state.messages.at(-1);
	await api(ac, `/chats/${chatId}/messages/${last.id}`, 'PATCH', {
		key: crypto.randomUUID(),
		content: long + '\n\n' + 'Added content. '.repeat(200),
		text_version: last.text_version
	});
	await g.waitForTimeout(600);
	assert.ok(Math.abs((await g.locator('main').evaluate((e) => e.scrollTop)) - oldScroll) < 3);
	state = await api(gc, '/chats/' + chatId);
	state = await api(gc, '/send', 'POST', {
		key: crypto.randomUUID(),
		chat_id: chatId,
		round_id: state.current_round_id,
		turn_version: state.turn_version,
		content: 'Question from another tab',
		attachments: []
	});
	await api(ac, '/send', 'POST', {
		key: crypto.randomUUID(),
		chat_id: chatId,
		round_id: state.current_round_id,
		turn_version: state.turn_version,
		content: 'A new incoming reply. '.repeat(80),
		attachments: []
	});
	await until(
		async () => (await g.locator('main article').count()) === 5,
		'new messages arrive while reading'
	);
	await g.waitForTimeout(3300);
	assert.ok(Math.abs((await g.locator('main').evaluate((e) => e.scrollTop)) - oldScroll) < 3);
	await g.getByRole('button', { name: 'Back to bottom', exact: true }).click();
	await until(
		async () =>
			await g.locator('main').evaluate((e) => e.scrollHeight - e.scrollTop - e.clientHeight < 5),
		'jump bottom'
	);
	console.log(
		'PASS one in-flight send, long Markdown/code/table/formula bounds, follow at bottom and preserve history position'
	);
	await input.fill('Persistent collapse draft');
	await g.locator('.desktop-collapse').click();
	await until(
		async () =>
			await g.locator('#chat-sidebar').evaluate((e) => e.getBoundingClientRect().width < 1),
		'collapse finishes'
	);
	assert.equal(await g.locator('#chat-sidebar').evaluate((e) => e.inert), true);
	const pane = await g.locator('.chat-pane').boundingBox(),
		box = await g.locator('.composer-box').boundingBox();
	assert.ok(Math.abs(box.x + box.width / 2 - pane.x - pane.width / 2) < 1);
	assert.ok(box.width <= 800);
	await g.screenshot({ path: join(out, 'desktop-collapsed.png') });
	await g.reload();
	await g.getByRole('button', { name: 'Open sidebar', exact: true }).waitFor();
	assert.equal(await input.inputValue(), 'Persistent collapse draft');
	await g.getByRole('button', { name: 'Open sidebar', exact: true }).click();
	await until(
		async () =>
			await g.locator('#chat-sidebar').evaluate((e) => e.getBoundingClientRect().width === 260),
		'expand finishes'
	);
	await g.getByRole('button', { name: 'Search', exact: true }).click();
	await g.locator('#chat-search').fill('no matching test title');
	await until(
		async () => (await g.locator('nav .chat-item').count()) === 0,
		'search filters own chats'
	);
	await g.locator('#chat-search').press('Escape');
	assert.equal(await g.locator('#chat-search').count(), 0);
	await until(async () => (await g.locator('nav .chat-item').count()) > 0, 'search reset');
	console.log(
		'PASS desktop collapse animation, inert, restore, persistence, column centering and search entry'
	);
	assert.deepEqual(errors, []);
	console.log('ALL CHAT STYLE CHECKS PASSED');
} finally {
	await browser.close();
}
