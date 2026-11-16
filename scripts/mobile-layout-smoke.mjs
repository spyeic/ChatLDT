import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { readFileSync, mkdirSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
const base = process.env.CHATLDT_BROWSER_URL,
	file = process.env.CHATLDT_BROWSER_CREDENTIALS_FILE;
if (!base || !file) throw new Error('Use an isolated server and private UI fixture credentials.');
const credentials = JSON.parse(readFileSync(file, 'utf8'));
const artifacts = process.env.CHATLDT_TEST_ARTIFACTS || '/private/tmp/chatldt-mobile-results';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({
	headless: true,
	executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
});
const errors = [],
	measurements = [];
async function until(fn, message) {
	for (let i = 0; i < 150; i++) {
		if (await fn()) return;
		await new Promise((r) => setTimeout(r, 30));
	}
	throw Error(message);
}
async function api(context, path, method = 'GET', data) {
	const session = await (await context.request.get(base + '/api/v1/ldt/session')).json();
	const result = await context.request.fetch(base + '/api/v1/ldt' + path, {
		method,
		headers: { Origin: base, 'x-ldt-csrf': session.csrf },
		data
	});
	assert.ok(result.ok(), `${method} ${path}: ${result.status()}`);
	return result.json();
}
function listen(page) {
	page.on('pageerror', (e) => errors.push(e.message));
}
const seed = await browser.newContext();
await api(seed, '/signin', 'POST', {
	email: credentials.user_email,
	password: credentials.user_password
});
const png = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAANUlEQVR4nO3QsQ0AMAzDsLT//9yeoCkbeYAN6LzZdZf3x0GSKEmUJEoSJYmSREmiJFGSaMoHo8QBPwYSAhsAAAAASUVORK5CYII=',
	'base64'
);
const attachments = [];
for (let i = 0; i < 2; i++) {
	const csrf = (await api(seed, '/session')).csrf;
	const result = await seed.request.post(base + '/api/v1/ldt/files', {
		headers: { Origin: base, 'x-ldt-csrf': csrf },
		multipart: { file: { name: `mobile-${i}.png`, mimeType: 'image/png', buffer: png } }
	});
	assert.ok(result.ok(), await result.text());
	attachments.push((await result.json()).id);
}
const question = await api(seed, '/send', 'POST', {
	key: crypto.randomUUID(),
	chat_id: crypto.randomUUID(),
	round_id: null,
	turn_version: 0,
	content: 'Mobile image question',
	attachments,
	initial_title: 'Mobile layout checks'
});
const admin = await browser.newContext();
await api(admin, '/signin', 'POST', { email: credentials.email, password: credentials.password });
await api(admin, '/send', 'POST', {
	key: crypto.randomUUID(),
	chat_id: question.id,
	round_id: question.current_round_id,
	turn_version: question.turn_version,
	content:
		'```python\nprint("ChatLDT")\n```\n\n' +
		'Long message for scrolling. 长消息保留正常换行与滚动。\n\n'.repeat(35),
	attachments: []
});
try {
	for (const width of [360, 390, 430])
		for (const locale of ['en-US', 'zh-CN'])
			for (const scheme of ['light', 'dark']) {
				const context = await browser.newContext({
					viewport: { width, height: 844 },
					isMobile: true,
					hasTouch: true,
					locale,
					colorScheme: scheme,
					...(width === 390 && locale === 'en-US' && scheme === 'dark'
						? { recordVideo: { dir: join(artifacts, 'video'), size: { width: 390, height: 844 } } }
						: {})
				});
				await context.addInitScript(() => {
					const actual = window.visualViewport;
					window.__viewport = Object.assign(new EventTarget(), {
						height: innerHeight,
						offsetTop: 0,
						scale: 1,
						width: innerWidth
					});
					Object.defineProperty(window, 'visualViewport', {
						configurable: true,
						get: () => window.__viewport
					});
					window.addEventListener('resize', () => {
						window.__viewport.height = innerHeight;
						window.__viewport.width = innerWidth;
						window.__viewport.dispatchEvent(new Event('resize'));
					});
					window.__actualViewport = actual;
				});
				const page = await context.newPage();
				listen(page);
				await page.goto(base);
				await page.locator('h1').waitFor();
				await until(
					async () =>
						(await page.locator('.welcome-group').evaluate((e) => getComputedStyle(e).opacity)) ===
						'1',
					'welcome entry animation completes'
				);
				await until(
					async () => (await page.locator('html').getAttribute('lang')) === locale,
					'language initialized'
				);
				const info = await page.evaluate(() => {
					const root = document.documentElement,
						input = document.querySelector('#chat-input'),
						title = document.querySelector('h1'),
						composer = document.querySelector('.composer-box'),
						shell = document.querySelector('.app-shell');
					const c = title.getBoundingClientRect(),
						icon = document.querySelector('.welcome-group img').getBoundingClientRect();
					return {
						root: getComputedStyle(root).backgroundColor,
						body: getComputedStyle(document.body).backgroundColor,
						shell: getComputedStyle(shell).backgroundColor,
						theme: document.querySelector('meta[name="theme-color"]').content,
						composer: composer.getBoundingClientRect().height,
						font: parseFloat(getComputedStyle(title).fontSize),
						align: getComputedStyle(title).textAlign,
						inputFont: parseFloat(getComputedStyle(input).fontSize),
						centerDelta: Math.abs(c.x + c.width / 2 - icon.x - icon.width / 2),
						bodyScroll: root.scrollHeight - root.clientHeight,
						buttons: [...document.querySelectorAll('.composer-actions button')].map((b) => ({
							w: b.getBoundingClientRect().width,
							h: b.getBoundingClientRect().height
						})),
						overflow: root.scrollWidth > innerWidth
					};
				});
				assert.equal(info.root, info.body);
				assert.equal(info.root, info.shell);
				assert.equal(info.theme, scheme === 'dark' ? '#171717' : '#ffffff');
				assert.ok(info.composer >= 80 && info.composer <= 110, JSON.stringify(info));
				assert.ok(info.font >= 26 && info.font <= 32);
				assert.equal(info.align, 'center');
				if (locale === 'en-US')
					assert.ok(
						await page
							.locator('h1')
							.evaluate(
								(e) =>
									e.getBoundingClientRect().height > parseFloat(getComputedStyle(e).fontSize) * 2.4
							),
						'English welcome forms two balanced lines'
					);
				assert.ok(info.centerDelta < 1);
				assert.ok(info.inputFont >= 16);
				assert.ok(info.buttons.every((b) => b.w >= 44 && b.h >= 44));
				assert.equal(info.overflow, false);
				assert.equal(info.bodyScroll, 0);
				measurements.push({ width, locale, scheme, ...info });
				await page.screenshot({
					path: join(artifacts, `welcome-${width}-${locale}-${scheme}.png`)
				});
				const toggle = page.getByRole('button', {
					name: locale === 'en-US' ? 'Toggle sidebar' : '切换侧边栏',
					exact: true
				});
				const pane = page.locator('.chat-pane'),
					initial = await pane.boundingBox();
				await toggle.click();
				const drawer = page.locator('#chat-sidebar');
				await until(
					async () =>
						await drawer.evaluate(
							(e) => e.matches(':popover-open') && e.classList.contains('active')
						),
					'drawer enters top layer'
				);
				assert.equal(await pane.evaluate((e) => e.inert), true);
				assert.deepEqual(await pane.boundingBox(), initial);
				const sheet = await page.locator('aside').boundingBox();
				assert.ok(sheet.width <= Math.min(width * 0.85, 320) + 1);
				assert.ok(sheet.width > width * 0.7);
				await until(
					async () =>
						await page
							.locator('aside')
							.evaluate((e) => Math.abs(e.getBoundingClientRect().left) < 1),
					'drawer animation completes'
				);
				if (width === 390 && locale === 'en-US' && scheme === 'dark')
					await page.screenshot({ path: join(artifacts, 'drawer-390.png') });
				await page.mouse.click(width - 8, 300);
				assert.equal(await drawer.isVisible(), true, 'drawer remains mounted during exit');
				await until(async () => !(await drawer.isVisible()), 'drawer exits before hiding');
				assert.equal(await pane.evaluate((e) => e.inert), false);
				for (let i = 0; i < 2; i++) {
					await toggle.click();
					await page.keyboard.press('Escape');
					await until(async () => !(await drawer.isVisible()), 'fast drawer close');
				}
				await toggle.click();
				await until(
					async () => await drawer.evaluate((e) => e.classList.contains('active')),
					'open drawer for login'
				);
				await page
					.getByRole('button', { name: locale === 'en-US' ? 'Sign in' : '登录', exact: true })
					.click();
				const modal = page.locator('dialog');
				await modal.waitFor();
				assert.equal(await drawer.isVisible(), false);
				assert.equal(await modal.evaluate((e) => e.matches(':modal')), true);
				await page
					.getByRole('button', { name: locale === 'en-US' ? 'Cancel' : '取消', exact: true })
					.click();
				await modal.waitFor({ state: 'hidden' });
				assert.equal(await pane.evaluate((e) => e.inert), false);
				await context.addCookies(await seed.cookies());
				await api(context, '/profile', 'PATCH', { name: 'E', language: locale, theme: scheme });
				await page.goto(base + '/c/' + question.id);
				await page.locator('main article').first().waitFor();
				await page.locator('main article img').first().waitFor();
				assert.equal(await page.locator('main article img').count(), 2);
				assert.equal(
					await page.locator('main article').first().getAttribute('aria-label'),
					locale === 'en-US' ? 'Your message' : '你的消息'
				);
				await page.locator('#chat-input').fill('Long draft content wraps on a phone. '.repeat(100));
				const grown = await page.locator('#chat-input').evaluate((e) => ({
					h: e.clientHeight,
					scroll: e.scrollHeight,
					limit: parseFloat(getComputedStyle(e).maxHeight)
				}));
				assert.ok(grown.h > 32 && grown.h <= grown.limit + 1 && grown.scroll > grown.h);
				await page.locator('#chat-input').fill('');
				await until(
					async () =>
						await page
							.locator('#chat-input')
							.evaluate((e) => e.getBoundingClientRect().height <= 33),
					'input shrinks after clearing'
				);
				await page
					.locator('input[type=file]')
					.first()
					.setInputFiles([
						{ name: 'one.png', mimeType: 'image/png', buffer: png },
						{ name: 'two.png', mimeType: 'image/png', buffer: png }
					]);
				assert.equal(await page.locator('.image-drafts img').count(), 2);
				assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
				const scroll = page.locator('main');
				await scroll.evaluate((e) => (e.scrollTop = 250));
				const oldScroll = await scroll.evaluate((e) => e.scrollTop);
				await toggle.click();
				await until(
					async () => await drawer.evaluate((e) => e.classList.contains('active')),
					'drawer on conversation'
				);
				await page.mouse.wheel(0, 500);
				await page.mouse.click(width - 8, 300);
				await until(async () => !(await drawer.isVisible()), 'close conversation drawer');
				assert.equal(await scroll.evaluate((e) => e.scrollTop), oldScroll);
				await page.screenshot({ path: join(artifacts, `chat-${width}-${locale}-${scheme}.png`) });
				if (width === 390 && locale === 'en-US' && scheme === 'dark') {
					await toggle.click();
					await until(
						async () => await drawer.evaluate((e) => e.classList.contains('active')),
						'open for rapid reversal'
					);
					await page.evaluate(() => {
						const button = document.querySelector('.mobile-sidebar-trigger');
						button.click();
						setTimeout(() => button.click(), 30);
					});
					await page.waitForTimeout(350);
					assert.equal(await drawer.isVisible(), true);
					assert.equal(await pane.evaluate((e) => e.inert), true);
					await page.keyboard.press('Escape');
					await until(async () => !(await drawer.isVisible()), 'reversed drawer closes');
					assert.equal(await pane.evaluate((e) => e.inert), false);
					await page.locator('#chat-input').focus();
					await page.evaluate(() => {
						__viewport.height = 340;
						__viewport.offsetTop = 80;
						__viewport.dispatchEvent(new Event('resize'));
					});
					await until(
						async () =>
							await page
								.locator('.app-shell')
								.evaluate((e) => Math.abs(e.getBoundingClientRect().height - 340) < 1),
						'visual viewport keyboard compensation'
					);
					const rect = await page.locator('.composer').boundingBox();
					assert.ok(rect.y + rect.height <= 421);
					assert.equal(
						await page.evaluate(() =>
							getComputedStyle(document.documentElement).getPropertyValue('--app-safe-bottom')
						),
						'0px'
					);
					await page.screenshot({ path: join(artifacts, 'simulated-keyboard-390.png') });
					await page.evaluate(() => {
						__viewport.height = 844;
						__viewport.offsetTop = 0;
						__viewport.dispatchEvent(new Event('resize'));
					});
					await until(
						async () =>
							await page
								.locator('.app-shell')
								.evaluate((e) => e.getBoundingClientRect().height === 844),
						'keyboard closes'
					);
					await page.evaluate(() => {
						__viewport.scale = 2;
						__viewport.height = 422;
						__viewport.dispatchEvent(new Event('resize'));
					});
					await until(
						async () =>
							await page.evaluate(
								() => !document.documentElement.style.getPropertyValue('--app-viewport-height')
							),
						'pinch zoom remains native'
					);
					await page.evaluate(() => {
						__viewport.scale = 1;
						__viewport.height = 844;
						__viewport.dispatchEvent(new Event('resize'));
					});
					await page.locator('#chat-input').evaluate((e) => e.blur());
					await page.setViewportSize({ width: 390, height: 700 });
					await until(
						async () =>
							await page
								.locator('.app-shell')
								.evaluate((e) => e.getBoundingClientRect().height === 700),
						'browser chrome expands'
					);
					assert.ok(
						await page.locator('.composer').evaluate((e) => e.getBoundingClientRect().bottom <= 700)
					);
					await page.setViewportSize({ width: 390, height: 844 });
					await until(
						async () =>
							await page
								.locator('.app-shell')
								.evaluate((e) => e.getBoundingClientRect().height === 844),
						'browser chrome collapses'
					);
					await page.setViewportSize({ width: 844, height: 390 });
					await until(async () => await toggle.isVisible(), 'landscape menu remains available');
					assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
					await page.screenshot({ path: join(artifacts, 'landscape-844.png') });
					await page.setViewportSize({ width: 390, height: 844 });
					await page.emulateMedia({ reducedMotion: 'reduce' });
					await toggle.click();
					await until(
						async () => await drawer.evaluate((e) => e.classList.contains('active')),
						'reduced motion drawer'
					);
					assert.equal(
						await page.locator('aside').evaluate((e) => getComputedStyle(e).transitionDuration),
						'0s'
					);
					await page.keyboard.press('Escape');
					await until(async () => !(await drawer.isVisible()), 'reduced motion drawer closes');
				}
				const video = page.video();
				await context.close();
				if (video) renameSync(await video.path(), join(artifacts, 'mobile-demo.webm'));
				console.log(
					`PASS ${width} CSS px ${locale} ${scheme}: welcome, drawer, modal, messages, long drafts, images, scroll restore`
				);
			}
	// No VisualViewport API and the fixed-size field fallback still produce a usable page.
	const fallback = await browser.newContext({
		viewport: { width: 390, height: 844 },
		isMobile: true,
		hasTouch: true
	});
	await fallback.addInitScript(() => {
		Object.defineProperty(window, 'visualViewport', { get: () => null });
		Object.defineProperty(HTMLElement.prototype, 'showPopover', { value: undefined });
		Object.defineProperty(HTMLElement.prototype, 'hidePopover', { value: undefined });
	});
	const fp = await fallback.newPage();
	listen(fp);
	await fp.goto(base);
	await fp.locator('h1').waitFor();
	assert.equal(
		await fp.locator('.app-shell').evaluate((e) => e.getBoundingClientRect().height),
		844
	);
	await fp.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
	await until(
		async () => await fp.locator('#chat-sidebar').isVisible(),
		'fixed drawer fallback opens'
	);
	assert.equal(await fp.locator('#chat-sidebar').getAttribute('popover'), null);
	assert.equal(await fp.locator('.chat-pane').evaluate((e) => e.inert), true);
	await fp.keyboard.press('Escape');
	await until(
		async () => !(await fp.locator('#chat-sidebar').isVisible()),
		'fixed drawer fallback closes'
	);
	assert.equal(await fp.locator('.chat-pane').evaluate((e) => e.inert), false);
	await fallback.close();
	// Chromium safe-area emulation checks our CSS math, not iPhone browser chrome.
	const safeContext = await browser.newContext({
		viewport: { width: 390, height: 844 },
		isMobile: true,
		hasTouch: true,
		locale: 'en-US',
		colorScheme: 'dark'
	});
	const safePage = await safeContext.newPage();
	listen(safePage);
	const cdp = await safeContext.newCDPSession(safePage);
	await cdp.send('Emulation.setSafeAreaInsetsOverride', {
		insets: { top: 47, bottom: 34, left: 0, right: 0 }
	});
	await safePage.goto(base);
	await safePage.locator('h1').waitFor();
	await until(
		async () =>
			(await safePage.locator('.composer').evaluate((e) => getComputedStyle(e).paddingBottom)) ===
			'34px',
		'safe bottom counted once'
	);
	const safeBox = await safePage.locator('.composer-box').boundingBox();
	assert.equal(Math.round(safeBox.y + safeBox.height), 810);
	assert.equal(Math.round((await safePage.locator('.chat-header').boundingBox()).y), 47);
	await safePage.screenshot({ path: join(artifacts, 'safe-area-390.png') });
	await safePage.setViewportSize({ width: 844, height: 390 });
	await cdp.send('Emulation.setSafeAreaInsetsOverride', {
		insets: { top: 0, bottom: 21, left: 47, right: 0 }
	});
	await safePage.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
	await safePage.getByRole('button', { name: 'Sign in', exact: true }).click();
	await until(
		async () =>
			(await safePage.locator('dialog').evaluate((e) => getComputedStyle(e).opacity)) === '1',
		'landscape modal entry'
	);
	const safeModal = await safePage.locator('dialog').boundingBox();
	assert.ok(safeModal.x >= 59 && safeModal.x + safeModal.width <= 832);
	assert.ok(safeModal.y + safeModal.height <= 369);
	await safePage.screenshot({ path: join(artifacts, 'modal-landscape-safe-area.png') });
	await safeContext.close();
	console.log(
		'PASS native Chromium VisualViewport and emulated safe areas: portrait 47/34, landscape left 47/bottom 21, no double padding'
	);
	assert.deepEqual(errors, []);
	writeFileSync(join(artifacts, 'measurements.json'), JSON.stringify(measurements, null, 2));
	console.log(
		'ALL MOBILE LAYOUT CHECKS PASSED (browser simulation; no physical iPhone certification)'
	);
} finally {
	await seed.close();
	await admin.close();
	await browser.close();
}
