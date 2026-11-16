import { chromium } from 'playwright';
import { readFileSync, mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const base = process.env.CHATLDT_BROWSER_URL;
if (!base || !process.env.CHATLDT_BROWSER_CREDENTIALS_FILE)
	throw new Error(
		'Set CHATLDT_BROWSER_URL to an isolated test server and CHATLDT_BROWSER_CREDENTIALS_FILE to its private test-admin JSON.'
	);
const artifacts = process.env.CHATLDT_TEST_ARTIFACTS || join(tmpdir(), 'chatldt-browser-results');
mkdirSync(artifacts, { recursive: true });
import assert from 'node:assert/strict';
const browser = await chromium.launch({
	executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
	headless: true
});
const errors = [];
const guestName = 'Browser Friend ' + Date.now();
const guestContext = await browser.newContext({
	locale: 'en-US',
	viewport: { width: 1280, height: 820 }
});
const adminContext = await browser.newContext({
	locale: 'en-US',
	viewport: { width: 1280, height: 820 }
});
const user = await guestContext.newPage(),
	admin = await adminContext.newPage();
for (const p of [user, admin]) p.on('pageerror', (e) => errors.push(e.message));
try {
	await user.goto(base);
	await user.locator('#chat-input').fill('Browser first question');
	await user.getByRole('button', { name: 'Send ↑', exact: true }).click();
	await user.getByRole('heading', { name: 'Choose a nickname' }).waitFor();
	await user.getByRole('button', { name: 'Cancel', exact: true }).click();
	assert.equal(await user.locator('#chat-input').inputValue(), 'Browser first question');
	await user.getByRole('button', { name: 'Send ↑', exact: true }).click();
	await user.locator('#modal-field').fill(guestName);
	await user.getByRole('button', { name: 'Confirm', exact: true }).click();
	await user.locator('dialog').waitFor({ state: 'hidden' });
	await user.locator('main article').first().waitFor();
	console.log('PASS guest nickname, cancellation and first atomic send');
	const chatUrl = user.url();
	await user.locator('#chat-input').fill('draft while waiting');
	assert.equal(await user.getByRole('button', { name: 'Send ↑', exact: true }).isDisabled(), true);
	await user.reload();
	await user.locator('main article').first().waitFor();
	assert.equal(await user.locator('#chat-input').inputValue(), 'draft while waiting');
	const otherTab = await guestContext.newPage();
	await otherTab.goto(chatUrl);
	await otherTab.locator('main article').first().waitFor();
	console.log('PASS persisted guest identity, shared tabs and text draft');
	await admin.goto(base);
	await admin.getByRole('button', { name: 'Sign in', exact: true }).click();
	const creds = JSON.parse(readFileSync(process.env.CHATLDT_BROWSER_CREDENTIALS_FILE));
	await admin.locator('#auth-email').fill(creds.email);
	await admin.locator('#auth-password').fill(creds.password);
	await admin.getByRole('button', { name: 'Confirm', exact: true }).click();
	await admin.locator('dialog').waitFor({ state: 'hidden' });
	await admin.getByRole('button', { name: 'admin', exact: true }).waitFor();
	assert.equal(await admin.locator('main article').count(), 0);
	await admin
		.getByRole('button', { name: new RegExp(guestName + '.*Guest') })
		.first()
		.click();
	await admin.getByRole('button', { name: 'Browser first question', exact: true }).first().click();
	await admin.locator('main article').first().waitFor();
	await admin.locator('#chat-input').fill('Prepared answer');
	await user.locator('main article').last().hover();
	await user.getByRole('button', { name: 'Edit', exact: true }).click();
	await user.locator('#modal-field').fill('Browser edited question');
	await user.getByRole('button', { name: 'Confirm', exact: true }).click();
	await user.locator('dialog').waitFor({ state: 'hidden' });
	await admin.getByText('Browser edited question', { exact: true }).waitFor();
	assert.equal(await admin.locator('#chat-input').inputValue(), 'Prepared answer');
	await admin.getByRole('button', { name: 'Send ↑', exact: true }).click();
	await user
		.getByRole('button', { name: 'Stop generating ■', exact: true })
		.waitFor({ state: 'detached' });
	await user.waitForFunction(
		() => document.querySelector('form button[type=submit]')?.disabled === false
	);
	assert.equal(await user.getByRole('button', { name: 'Send ↑', exact: true }).isDisabled(), false);
	await user.getByText('Prepared answer', { exact: true }).waitFor();
	assert.equal(await user.locator('#chat-input').inputValue(), 'draft while waiting');
	await user.waitForFunction(
		() => document.querySelector('form button[type=submit]')?.disabled === false
	);
	assert.equal(await user.getByRole('button', { name: 'Send ↑', exact: true }).isDisabled(), false);
	assert.equal(
		await user
			.locator('main article')
			.nth(0)
			.evaluate((e) => e.classList.contains('justify-end')),
		true
	);
	assert.equal(
		await admin
			.locator('main article')
			.nth(0)
			.evaluate((e) => e.classList.contains('justify-end')),
		false
	);
	console.log('PASS administrator welcome/grouping, mirrored messages, live edit and reply');
	await user.getByRole('button', { name: 'Send ↑', exact: true }).click();
	await user.getByRole('button', { name: 'Stop generating ■', exact: true }).waitFor();
	await admin.locator('#chat-input').fill('Retained administrator draft');
	await user.getByRole('button', { name: 'Stop generating ■', exact: true }).click();
	await admin.getByText('Cancelled', { exact: true }).waitFor();
	assert.equal(await admin.locator('#chat-input').inputValue(), 'Retained administrator draft');
	assert.equal(await admin.getByRole('button', { name: 'Send ↑', exact: true }).isDisabled(), true);
	console.log('PASS cancellation locks the round and retains administrator draft');
	await user.getByRole('button', { name: guestName, exact: true }).click();
	await user.locator('#language').selectOption('zh-CN');
	await user.locator('#theme').selectOption('dark');
	await user.getByRole('button', { name: 'Confirm', exact: true }).click();
	await user.locator('dialog').waitFor({ state: 'hidden' });
	await user.getByRole('button', { name: '发送 ↑', exact: true }).waitFor();
	assert.equal(await user.locator('html').getAttribute('lang'), 'zh-CN');
	assert.equal(await user.locator('html').evaluate((e) => e.classList.contains('dark')), true);
	await user.setViewportSize({ width: 390, height: 844 });
	assert.equal(await user.locator('aside').isVisible(), false);
	await user.screenshot({ path: join(artifacts, 'mobile-dark.png'), fullPage: true });
	console.log('PASS Chinese, dark theme and mobile layout');
	// Register directly from the live guest settings; old tabs share cookies
	// and can observe revocation before the HTTP login response sets its cookie.
	await user.locator('#chat-input').fill('unsent migration draft');
	await user.getByRole('button', { name: '切换侧边栏', exact: true }).click();
	await user.getByRole('button', { name: guestName, exact: true }).click();
	await user.getByRole('button', { name: '注册', exact: true }).click();
	await user.locator('#auth-email').fill(`browser-${Date.now()}@example.test`);
	await user.locator('#auth-password').fill('browser-test-' + Date.now());
	await user.getByRole('button', { name: '确认', exact: true }).click();
	await user.locator('dialog').waitFor({ state: 'hidden' });
	await user.locator('dialog').waitFor({ state: 'hidden' });
	await user.goto(chatUrl);
	await user.locator('main article').first().waitFor();
	assert.equal(await user.locator('#chat-input').inputValue(), 'unsent migration draft');
	const me = await user.evaluate(
		async () => (await (await fetch('/api/v1/ldt/session')).json()).identity
	);
	assert.equal(me.kind, 'user');
	console.log('PASS guest signup/migration from UI with another live tab and draft preservation');
	const png = Buffer.from(
		'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAANUlEQVR4nO3QsQ0AMAzDsLT//9yeoCkbeYAN6LzZdZf3x0GSKEmUJEoSJYmSREmiJFGSaMoHo8QBPwYSAhsAAAAASUVORK5CYII=',
		'base64'
	);
	await user
		.locator('input[type=file]')
		.first()
		.setInputFiles([{ name: 'one.png', mimeType: 'image/png', buffer: png }]);
	await user.locator('#chat-input').evaluate((element, bytes) => {
		const data = new DataTransfer();
		data.items.add(new File([new Uint8Array(bytes)], 'pasted.png', { type: 'image/png' }));
		element.dispatchEvent(
			new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true })
		);
	}, Array.from(png));
	await user.getByRole('button', { name: '发送 ↑', exact: true }).click();
	await user.locator('main article').last().locator('img').nth(1).waitFor();
	assert.equal(await user.locator('main article').last().locator('img').count(), 2);
	await user.waitForFunction(() =>
		[...document.querySelectorAll('main article:last-child img')].every(
			(i) => i.complete && i.naturalWidth === 32
		)
	);
	assert.equal(await user.getByRole('button', { name: '重试上一次发送', exact: true }).count(), 0);
	await admin.getByText('unsent migration draft', { exact: true }).waitFor();
	assert.equal(await admin.locator('#chat-input').inputValue(), 'Retained administrator draft');
	console.log('PASS combined multi-image send and protected preview with live ownership sync');
	const adminUrl = admin.url();
	assert.equal(
		await admin
			.getByRole('button', { name: new RegExp(guestName + '.*User') })
			.first()
			.getAttribute('aria-expanded'),
		'false'
	);
	await guestContext.setOffline(true);
	await admin.locator('#chat-input').fill('Reconnect recovery answer');
	await admin.getByRole('button', { name: 'Send ↑', exact: true }).click();
	await admin.getByText('Reconnect recovery answer', { exact: true }).waitFor();
	await guestContext.setOffline(false);
	await user.getByText('Reconnect recovery answer', { exact: true }).waitFor();
	assert.equal(admin.url(), adminUrl);
	console.log('PASS disconnected client restores committed reply on reconnect without navigation');

	const profile = mkdtempSync(join(tmpdir(), 'chatldt-persistent-profile-'));
	const options = {
		executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
		headless: true,
		locale: 'en-US'
	};
	let persistent;
	try {
		persistent = await chromium.launchPersistentContext(profile, options);
		let page = persistent.pages()[0] || (await persistent.newPage());
		await page.goto(base);
		await page.locator('#chat-input').fill('browser restart persistence');
		await page.getByRole('button', { name: 'Send ↑', exact: true }).click();
		await page.locator('#modal-field').fill('Persistent Guest');
		await page.getByRole('button', { name: 'Confirm', exact: true }).click();
		await page.locator('main article').first().waitFor();
		const url = page.url();
		const old = await page.evaluate(
			async () => (await (await fetch('/api/v1/ldt/session')).json()).identity.id
		);
		await persistent.close();
		persistent = await chromium.launchPersistentContext(profile, options);
		page = persistent.pages()[0] || (await persistent.newPage());
		await page.goto(url);
		await page.locator('main article').first().waitFor();
		const restored = await page.evaluate(
			async () => (await (await fetch('/api/v1/ldt/session')).json()).identity.id
		);
		assert.equal(restored, old);
		console.log(
			'PASS guest restored after the entire persistent-profile browser process closes and reopens'
		);
	} finally {
		await persistent?.close();
	}
	assert.deepEqual(errors, []);
	console.log('ALL BROWSER CHECKS PASSED');
} catch (error) {
	await user.screenshot({ path: join(artifacts, 'failure.png'), fullPage: true });
	console.error('BROWSER FAILURE', error);
	console.error('PAGE ERRORS', errors);
	process.exitCode = 1;
} finally {
	await browser.close();
}
