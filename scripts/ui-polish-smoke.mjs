import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { readFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
const base = process.env.CHATLDT_BROWSER_URL;
const credentials = process.env.CHATLDT_BROWSER_CREDENTIALS_FILE;
if (!base || !credentials)
	throw new Error('Use an isolated UI fixture and private credentials JSON.');
const creds = JSON.parse(readFileSync(credentials, 'utf8'));
const artifacts = process.env.CHATLDT_TEST_ARTIFACTS || '/private/tmp/chatldt-ui-polish/results';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({
	headless: true,
	executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
});
const errors = [];
const adminContext = await browser.newContext({
	viewport: { width: 1280, height: 820 },
	locale: 'en-US',
	colorScheme: 'dark'
});
await adminContext.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base });
const admin = await adminContext.newPage();
admin.on('pageerror', (e) => errors.push(e.message));
async function wait(check, message, timeout = 5000) {
	const end = Date.now() + timeout;
	while (Date.now() < end) {
		if (await check()) return;
		await new Promise((r) => setTimeout(r, 30));
	}
	throw new Error(message);
}
async function login(page, email, password) {
	await page.goto(base);
	await page.getByRole('button', { name: 'Sign in', exact: true }).click();
	await page.locator('#auth-email').fill(email);
	await page.locator('#auth-password').fill(password);
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await page.locator('dialog').waitFor({ state: 'hidden' });
}
async function api(context, path, method = 'GET', body) {
	const csrf = (await (await context.request.get(base + '/api/v1/ldt/session')).json()).csrf;
	const response = await context.request.fetch(base + '/api/v1/ldt' + path, {
		method,
		headers: { Origin: base, 'x-ldt-csrf': csrf },
		data: body
	});
	assert.ok(response.ok(), `${method} ${path}: ${response.status()}`);
	return response.json();
}
try {
	await login(admin, creds.email, creds.password);
	await api(adminContext, '/profile', 'PATCH', {
		name: 'admin',
		language: 'en-US',
		theme: 'system'
	});
	await admin.reload();
	await admin.getByRole('button', { name: 'admin', exact: true }).waitFor();
	await admin.reload();
	await admin.getByRole('button', { name: 'admin', exact: true }).waitFor();
	// Seed a new conversation through the public API, so this test is repeatable.
	const fixtureUser = await browser.newContext();
	await api(fixtureUser, '/signin', 'POST', {
		email: creds.user_email,
		password: creds.user_password
	});
	const fixture = await api(fixtureUser, '/send', 'POST', {
		key: crypto.randomUUID(),
		chat_id: crypto.randomUUID(),
		round_id: null,
		turn_version: 0,
		content:
			'你好，这是一条用于界面回归的消息。\n\n```python\nprint("ChatLDT")\n```\n\n保留原始 Markdown 和换行。',
		attachments: [],
		initial_title: '界面交互检查'
	});
	creds.chat_id = fixture.id;
	await api(adminContext, '/send', 'POST', {
		key: crypto.randomUUID(),
		chat_id: fixture.id,
		round_id: fixture.current_round_id,
		turn_version: fixture.turn_version,
		content: 'hello\n\n我们继续使用当前的消息方向和主题。',
		attachments: []
	});
	await fixtureUser.close();
	await admin.goto(base + '/c/' + creds.chat_id);
	await admin.waitForLoadState('networkidle');
	await admin.locator('main article').first().waitFor();
	assert.equal(await admin.title(), '界面交互检查 · ChatLDT');
	assert.equal(await admin.locator('body').getByText('Open WebUI', { exact: true }).count(), 0);
	assert.equal(await admin.locator('main article .text-xs').count(), 0);
	assert.equal(
		await admin.locator('main article').first().getAttribute('aria-label'),
		'Their message'
	);
	assert.equal(
		await admin.locator('main article').last().getAttribute('aria-label'),
		'Your message'
	);
	console.log(
		'PASS existing administrator displays admin after refresh; no sender name rows; original orientation retained'
	);
	const first = admin.locator('main article').first(),
		last = admin.locator('main article').last();
	await admin.mouse.move(1230, 20);
	const before = await last.boundingBox();
	await wait(
		async () =>
			+(await last.locator('.message-actions').evaluate((e) => getComputedStyle(e).opacity)) === 0,
		'desktop toolbar should hide'
	);
	await last.hover();
	await wait(
		async () =>
			+(await last.locator('.message-actions').evaluate((e) => getComputedStyle(e).opacity)) === 1,
		'hover should reveal toolbar'
	);
	const actions = last.locator('.message-actions');
	const button = actions.locator('.copy-button');
	assert.equal(await button.getAttribute('aria-label'), 'Copy');
	await button.hover();
	await wait(
		async () => (await actions.evaluate((e) => getComputedStyle(e).opacity)) === '1',
		'toolbar fade completes'
	);
	const after = await last.boundingBox();
	assert.deepEqual(after, before);
	const bubble = await last.locator('.message-bubble').boundingBox(),
		toolbar = await actions.boundingBox();
	assert.ok(Math.abs(bubble.x + bubble.width - toolbar.x - toolbar.width) < 2);
	assert.equal(await first.locator('.edit-message').count(), 0);
	assert.equal(await last.locator('.edit-message').count(), 1);
	console.log('PASS hover travel, stable layout, alignment and edit permissions');
	const chat = await api(adminContext, '/chats/' + creds.chat_id);
	await button.click();
	await wait(
		async () => (await button.getAttribute('aria-label')) === 'Copied',
		'copy success feedback'
	);
	assert.equal(
		await admin.evaluate(() => navigator.clipboard.readText()),
		chat.messages.at(-1).content
	);
	assert.equal(await button.isEnabled(), true);
	await wait(
		async () => (await button.getAttribute('aria-label')) === 'Copy',
		'copy feedback should reset',
		3000
	);
	await first.hover();
	await first.locator('.message-actions .copy-button').click();
	assert.equal(
		await admin.evaluate(() => navigator.clipboard.readText()),
		chat.messages[0].content
	);
	await first.locator('.code-actions .copy-button').click();
	assert.equal(await admin.evaluate(() => navigator.clipboard.readText()), 'print("ChatLDT")');
	console.log('PASS exact raw Markdown/newline copy and separate code-block copy');
	await admin.evaluate(() => {
		window.__clipboard = navigator.clipboard;
		window.__exec = document.execCommand;
		Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
	});
	await last.hover();
	await last.locator('.copy-button').click();
	assert.equal(
		await admin.evaluate(() => window.__clipboard.readText()),
		chat.messages.at(-1).content
	);
	await admin.evaluate(() => {
		Object.defineProperty(navigator, 'clipboard', {
			configurable: true,
			value: { writeText: () => Promise.reject(new DOMException('denied', 'NotAllowedError')) }
		});
		document.execCommand = () => false;
	});
	await last.locator('.copy-button').click();
	await wait(
		async () => (await last.locator('.copy-control').getAttribute('data-state')) === 'failure',
		'failed copy must not show success'
	);
	assert.match(await last.locator('.copy-status').innerText(), /copy manually/);
	await admin.evaluate(() => {
		Object.defineProperty(navigator, 'clipboard', {
			configurable: true,
			value: window.__clipboard
		});
		document.execCommand = window.__exec;
	});
	console.log('PASS Clipboard API missing fallback and permission-denied failure feedback');
	await last.locator('.edit-message').focus();
	await admin.keyboard.press('Tab');
	await last.locator('.copy-button').focus();
	await admin.mouse.move(1230, 20);
	await wait(
		async () => (await actions.evaluate((e) => getComputedStyle(e).opacity)) === '1',
		'toolbar fade completes'
	);
	assert.notEqual(
		await last.locator('.copy-button').evaluate((e) => getComputedStyle(e).outlineStyle),
		'none'
	);
	await admin.keyboard.press('Enter');
	await wait(
		async () => (await last.locator('.copy-control').getAttribute('data-state')) === 'success',
		'keyboard activates copy'
	);
	assert.equal(
		await admin.evaluate(() => navigator.clipboard.readText()),
		chat.messages.at(-1).content
	);
	const text = first.locator('.markdown p').first();
	const rect = await text.boundingBox();
	await admin.mouse.move(rect.x + 3, rect.y + 10);
	await admin.mouse.down();
	await admin.mouse.move(rect.x + 130, rect.y + 10, { steps: 12 });
	await admin.mouse.up();
	assert.ok((await admin.evaluate(() => getSelection().toString())).length > 0);
	for (const node of [
		first,
		last,
		first.locator('.message-bubble'),
		last.locator('.message-bubble')
	])
		assert.equal(await node.evaluate((e) => getComputedStyle(e).outlineStyle), 'none');
	console.log(
		'PASS keyboard focus remains visible and normal text selection has no message container frame'
	);
	await admin.getByRole('button', { name: 'admin', exact: true }).click();
	const dialog = admin.locator('dialog');
	await dialog.waitFor();
	await wait(
		async () => (await dialog.evaluate((e) => getComputedStyle(e).opacity)) === '1',
		'modal entry finishes before normal exit check'
	);
	assert.equal(await admin.locator('#modal-field').inputValue(), 'admin');
	assert.equal(await admin.locator('#modal-field').getAttribute('readonly'), '');
	assert.ok(await dialog.evaluate((e) => e.matches(':modal')));
	await admin.getByRole('button', { name: 'Cancel', exact: true }).click();
	assert.ok(await dialog.evaluate((e) => e.open));
	assert.equal(await dialog.getAttribute('data-closing'), '');
	await dialog.waitFor({ state: 'hidden' });
	assert.equal(await admin.evaluate(() => document.activeElement.textContent.trim()), 'admin');
	await admin.emulateMedia({ reducedMotion: 'reduce' });
	await admin.getByRole('button', { name: 'admin', exact: true }).click();
	assert.equal(await dialog.evaluate((e) => getComputedStyle(e).transform), 'none');
	await admin.keyboard.press('Escape');
	await dialog.waitFor({ state: 'hidden' });
	await admin.emulateMedia({ reducedMotion: 'no-preference' });
	for (let i = 0; i < 3; i++) {
		await admin.getByRole('button', { name: 'admin', exact: true }).click();
		await admin.keyboard.press('Escape');
		await dialog.waitFor({ state: 'hidden' });
	}
	console.log('PASS native modal exit wait, focus return, fast open/close and reduced motion');
	await wait(
		async () => (await last.locator('.copy-control').getAttribute('data-state')) === 'idle',
		'feedback clears before screenshot'
	);
	await admin.locator('#chat-input').evaluate((e) => e.blur());
	await last.hover();
	await admin.screenshot({ path: join(artifacts, 'after-admin-dark.png'), fullPage: true });
	const userContext = await browser.newContext({
		viewport: { width: 1280, height: 820 },
		locale: 'en-US',
		colorScheme: 'light',
		reducedMotion: 'no-preference'
	});
	await userContext.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base });
	const user = await userContext.newPage();
	user.on('pageerror', (e) => errors.push(e.message));
	await login(user, creds.user_email, creds.user_password);
	await api(userContext, '/profile', 'PATCH', { name: 'E', language: 'en-US', theme: 'system' });
	await user.goto(base + '/c/' + creds.chat_id);
	await user.locator('main article').first().waitFor();
	const registered = (await api(userContext, '/session')).identity;
	assert.equal(await user.getByRole('button', { name: registered.name, exact: true }).count(), 1);
	assert.equal(
		await user.locator('main article').first().getAttribute('aria-label'),
		'Your message'
	);
	assert.equal(await user.locator('main article .edit-message').count(), 0);
	await user.locator('#chat-input').fill('工具栏回归：下一轮问题');
	await user.getByRole('button', { name: 'Send', exact: true }).click();
	await user.getByRole('button', { name: 'Stop generating', exact: true }).waitFor();
	await user.getByRole('button', { name: 'Stop generating', exact: true }).click();
	await user.getByText('Cancelled', { exact: true }).waitFor();
	const cancelled = user.locator('main article').last();
	assert.equal(await cancelled.locator('.edit-message').count(), 0);
	await cancelled.hover();
	await cancelled.locator('.copy-button').click();
	assert.equal(await user.evaluate(() => navigator.clipboard.readText()), '工具栏回归：下一轮问题');
	await user.locator('#chat-input').fill('渐进回复复制');
	await user.getByRole('button', { name: 'Send', exact: true }).click();
	await user.getByRole('button', { name: 'Stop generating', exact: true }).waitFor();
	await user.bringToFront();
	await user.waitForFunction(() => document.visibilityState === 'visible');
	await user.waitForLoadState('networkidle');
	const state = await api(adminContext, '/chats/' + creds.chat_id);
	const complete = '完整回复内容，复制时不能截断。\n\n' + '这段文字用于渐进显示检查。'.repeat(75);
	await api(adminContext, '/send', 'POST', {
		key: crypto.randomUUID(),
		chat_id: creds.chat_id,
		round_id: state.current_round_id,
		turn_version: state.turn_version,
		content: complete,
		attachments: [],
		target_user_id: null,
		initial_title: null
	});
	await user.locator('main article').nth(state.messages.length).waitFor();
	const animated = user.locator('main article').last();
	assert.ok((await animated.locator('.markdown').innerText()).length < complete.length);
	await animated.hover();
	await animated.locator('.message-actions .copy-button').click();
	assert.equal(await user.evaluate(() => navigator.clipboard.readText()), complete);
	await user.screenshot({ path: join(artifacts, 'after-user-light.png'), fullPage: true });
	console.log(
		'PASS registered user orientation, cancelled-history copy and complete source during progressive reply'
	);
	const touchContext = await browser.newContext({
		viewport: { width: 390, height: 844 },
		hasTouch: true,
		isMobile: true,
		locale: 'zh-CN',
		colorScheme: 'dark'
	});
	const touch = await touchContext.newPage();
	touch.on('pageerror', (e) => errors.push(e.message));
	await touch.goto(base);
	await touch.locator('#chat-input').fill('游客工具栏检查');
	await touch.getByRole('button', { name: '发送', exact: true }).click();
	await touch.locator('#modal-field').fill('触屏游客');
	await touch.getByRole('button', { name: '确认', exact: true }).click();
	await touch.locator('main article').first().waitFor();
	assert.equal(
		await touch.locator('.message-actions').evaluate((e) => getComputedStyle(e).opacity),
		'1'
	);
	assert.equal(await touch.locator('.edit-message').getAttribute('aria-label'), '编辑');
	assert.equal(await touch.locator('.copy-button').getAttribute('aria-label'), '复制');
	assert.ok(await touch.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
	await touch.screenshot({ path: join(artifacts, 'after-guest-mobile-dark.png'), fullPage: true });
	assert.ok(
		(await touch.locator('link[rel=icon]').first().getAttribute('href')).includes('chatldt-icon-v1')
	);
	const manifest = await (await touch.request.get(base + '/chatldt-v1.webmanifest')).json();
	assert.equal(manifest.name, 'ChatLDT');
	for (const icon of manifest.icons)
		assert.equal((await touch.request.get(base + icon.src)).status(), 200);
	console.log(
		'PASS touch toolbar, Chinese labels, mobile bounds and refreshed favicon/PWA branding'
	);
	// A pure-image message retains text editing but offers no text copy action.
	await touch.getByRole('button', { name: '停止生成', exact: true }).click();
	await touch.getByRole('button', { name: '停止生成', exact: true }).waitFor({ state: 'detached' });
	const png = Buffer.from(
		'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAANUlEQVR4nO3QsQ0AMAzDsLT//9yeoCkbeYAN6LzZdZf3x0GSKEmUJEoSJYmSREmiJFGSaMoHo8QBPwYSAhsAAAAASUVORK5CYII=',
		'base64'
	);
	await touch
		.locator('input[type=file]')
		.first()
		.setInputFiles({ name: 'only-image.png', mimeType: 'image/png', buffer: png });
	await touch.getByRole('button', { name: '发送', exact: true }).click();
	await touch.locator('main article').last().locator('img').waitFor();
	assert.equal(await touch.locator('main article').last().locator('.copy-button').count(), 0);
	await touch.locator('main article').last().locator('.edit-message').click();
	await touch.locator('#modal-field').fill('纯图片消息补充文字');
	await touch.getByRole('button', { name: '确认', exact: true }).click();
	await touch.locator('dialog').waitFor({ state: 'hidden' });
	assert.equal(await touch.locator('main article').last().locator('img').count(), 1);
	assert.equal(await touch.locator('main article').last().locator('.copy-button').count(), 1);
	console.log('PASS pure-image message has no text copy; text editing preserves its attachment');
	// All identities can use both supported languages/themes through the same modal.
	for (const [page, account, initialConfirm] of [
		[admin, 'admin', 'Confirm'],
		[user, registered.name, 'Confirm'],
		[touch, '触屏游客', '确认']
	]) {
		if (page === touch) await page.getByRole('button', { name: '切换侧边栏', exact: true }).click();
		await page.getByRole('button', { name: account, exact: true }).click();
		await page.locator('#theme').selectOption(page === touch ? 'light' : 'dark');
		await page.locator('#language').selectOption(page === touch ? 'en-US' : 'zh-CN');
		await page.getByRole('button', { name: initialConfirm, exact: true }).click();
		await page.locator('dialog').waitFor({ state: 'hidden' });
		assert.equal(
			await page.locator('html').getAttribute('lang'),
			page === touch ? 'en-US' : 'zh-CN'
		);
		assert.equal(
			await page.locator('html').evaluate((e) => e.classList.contains('dark')),
			page !== touch
		);
		if (page === touch)
			await page.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
		await page.getByRole('button', { name: account, exact: true }).click();
		await page.locator('#theme').selectOption(page === admin ? 'light' : 'system');
		await page.locator('#language').selectOption('en-US');
		await page
			.getByRole('button', { name: page === touch ? 'Confirm' : '确认', exact: true })
			.click();
		await page.locator('dialog').waitFor({ state: 'hidden' });
	}
	console.log('PASS admin/user/guest settings, both languages and light/dark/system themes');
	assert.deepEqual(errors, []);
	console.log('ALL UI POLISH CHECKS PASSED');
} catch (error) {
	await admin.screenshot({ path: join(artifacts, 'failure-admin.png'), fullPage: true });
	console.error(error);
	console.error('PAGE ERRORS', errors);
	process.exitCode = 1;
} finally {
	await browser.close();
}
