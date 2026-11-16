import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
const base = process.env.CHATLDT_BROWSER_URL;
const credentials = process.env.CHATLDT_BROWSER_CREDENTIALS_FILE;
if (!base || !credentials) throw Error('Use an isolated fixture and private credentials file.');
const creds = JSON.parse(readFileSync(credentials, 'utf8'));
const stage = process.argv[2] || 'after';
const out = process.env.CHATLDT_TEST_ARTIFACTS || '/private/tmp/chatldt-chat-style';
mkdirSync(out, { recursive: true });
const stateFile = join(out, 'fixture.json');
const browser = await chromium.launch({
	executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
});
async function api(c, path, method = 'GET', data) {
	const s = await (await c.request.get(base + '/api/v1/ldt/session')).json();
	const r = await c.request.fetch(base + '/api/v1/ldt' + path, {
		method,
		headers: { Origin: base, 'x-ldt-csrf': s.csrf },
		data
	});
	if (!r.ok()) throw Error(`${path}: ${r.status()} ${await r.text()}`);
	return r.json();
}
try {
	const a = await browser.newContext(),
		u = await browser.newContext();
	await api(a, '/signin', 'POST', { email: creds.email, password: creds.password });
	await api(u, '/signin', 'POST', { email: creds.user_email, password: creds.user_password });
	let state;
	if (stage === 'before') {
		const q = await api(u, '/send', 'POST', {
			key: crypto.randomUUID(),
			chat_id: crypto.randomUUID(),
			round_id: null,
			turn_version: 0,
			content: '请帮我整理一个简洁的周末阅读计划。',
			attachments: [],
			initial_title: '周末阅读计划 · UI 测试'
		});
		await api(a, '/send', 'POST', {
			key: crypto.randomUUID(),
			chat_id: q.id,
			round_id: q.current_round_id,
			turn_version: q.turn_version,
			content:
				'可以从一个轻松的目标开始。\n\n## 周末阅读计划\n\n- **周六上午**：挑选一本感兴趣的书，阅读 30 分钟。\n- **周日下午**：记录三个想法，留一点时间回顾。\n\n```python\nreading_minutes = 30\nprint("Enjoy your reading time")\n```\n\n阅读不必匆忙，给思考留出空间。',
			attachments: []
		});
		state = { chatId: q.id };
		writeFileSync(stateFile, JSON.stringify(state));
	} else state = JSON.parse(readFileSync(stateFile, 'utf8'));
	for (const [name, role, width, height, scheme, lang, chat] of [
		['guest-welcome-dark', 'guest', 1440, 900, 'dark', 'en-US', false],
		['user-welcome-light', 'user', 1440, 900, 'light', 'zh-CN', false],
		['admin-welcome-dark', 'admin', 1440, 900, 'dark', 'en-US', false],
		['user-chat-dark', 'user', 1440, 900, 'dark', 'zh-CN', true],
		['admin-chat-light', 'admin', 1440, 900, 'light', 'en-US', true],
		['mobile-welcome-dark', 'guest', 390, 844, 'dark', 'zh-CN', false],
		['mobile-chat-light', 'user', 390, 844, 'light', 'zh-CN', true]
	]) {
		const c = await browser.newContext({
			viewport: { width, height },
			locale: lang,
			colorScheme: scheme,
			isMobile: width < 768,
			hasTouch: width < 768
		});
		if (role !== 'guest') {
			await c.addCookies(await (role === 'admin' ? a : u).cookies());
			await api(c, '/profile', 'PATCH', {
				name: role === 'admin' ? 'admin' : 'E',
				language: lang,
				theme: scheme
			});
		}
		const p = await c.newPage();
		// Keep the sidebar fixture identical after other regression suites add chats.
		await p.route('**/api/v1/ldt/chats?*', async (route) => {
			const response = await route.fetch();
			const list = await response.json();
			await route.fulfill({ response, json: list.filter((chat) => chat.id === state.chatId) });
		});
		await p.goto(base + (chat ? '/c/' + state.chatId : ''));
		await p
			.locator(chat ? 'main article' : 'h1')
			.first()
			.waitFor();
		await p.waitForTimeout(450);
		await p.screenshot({ path: join(out, `${stage}-${name}.png`) });
		await c.close();
	}
	console.log(`${stage}: 7 same-state screenshots saved to ${out}`);
} finally {
	await browser.close();
}
