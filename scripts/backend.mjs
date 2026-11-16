import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = resolve(
	root,
	process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'
);
if (!existsSync(python)) {
	console.error('Run npm run setup first to create .venv.');
	process.exit(1);
}
const action = process.argv[2] || 'serve';
const args =
	action === 'backup'
		? ['-m', 'open_webui.manual.backup', ...process.argv.slice(3)]
		: action === 'test'
			? ['-m', 'pytest', 'backend/tests', '-q']
			: ['setup', 'reset', 'migrate'].includes(action)
				? ['-m', 'open_webui.manual.setup', action]
				: [
						'-c',
						'from open_webui import app; app()',
						action,
						'--host',
						process.env.HOST || '127.0.0.1',
						'--port',
						process.env.PORT || '8080'
					];
const result = spawnSync(python, args, {
	cwd: root,
	stdio: 'inherit',
	env: { ...process.env, PYTHONPATH: resolve(root, 'backend') }
});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
