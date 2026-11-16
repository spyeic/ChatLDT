import { spawnSync } from 'node:child_process';
import { existsSync, copyFileSync, chmodSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const major = Number(process.versions.node.split('.')[0]);
if (major < 18 || major > 22) {
	console.error(
		`Node ${process.versions.node} is outside the Fork's supported range. Install Node 22, then retry npm run setup.`
	);
	process.exit(1);
}
function run(command, args, options = {}) {
	const r = spawnSync(command, args, { cwd: root, stdio: 'inherit', ...options });
	if (r.error || r.status !== 0) {
		console.error(r.error?.message || `${command} failed (${r.status}). Setup did not complete.`);
		process.exit(r.status || 1);
	}
}
const python = resolve(
	root,
	process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'
);
if (!existsSync(python)) {
	const choices =
		process.platform === 'win32'
			? [
					['py', ['-3.12']],
					['py', ['-3.11']],
					['python', []]
				]
			: [
					['python3.12', []],
					['python3.11', []],
					['python3', []],
					['python', []],
					['python', []]
				];
	let chosen;
	for (const [cmd, args] of choices) {
		const r = spawnSync(
			cmd,
			[...args, '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
			{ encoding: 'utf8' }
		);
		if (r.status === 0 && ['3.11', '3.12'].includes(r.stdout.trim())) {
			chosen = [cmd, args];
			break;
		}
	}
	if (!chosen) {
		console.error(
			'Install Python 3.12 (or 3.11) and expose python3.12 (Windows: py -3.12). No database or credentials changed.'
		);
		process.exit(1);
	}
	run(chosen[0], [...chosen[1], '-m', 'venv', '.venv']);
}
const version = spawnSync(
	python,
	['-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
	{ encoding: 'utf8' }
);
if (!['3.11', '3.12'].includes(version.stdout?.trim())) {
	console.error(
		'Existing .venv is incompatible. Move it aside and create a Python 3.12 virtual environment.'
	);
	process.exit(1);
}
if (!existsSync(resolve(root, 'node_modules/.bin/vite'))) {
	console.error('Run npm ci first, then npm run setup.');
	process.exit(1);
}
if (spawnSync(python, ['-m', 'pip', '--version'], { stdio: 'ignore' }).status !== 0)
	run(python, ['-m', 'ensurepip', '--upgrade']);
run(python, ['-m', 'pip', 'install', '-r', 'backend/requirements.txt']);
if (!existsSync(resolve(root, '.env'))) {
	copyFileSync(resolve(root, '.env.example'), resolve(root, '.env'));
	chmodSync(resolve(root, '.env'), 0o600);
}
run(python, ['-m', 'open_webui.manual.setup', 'setup'], {
	env: { ...process.env, PYTHONPATH: resolve(root, 'backend') }
});
console.log(
	'\nSetup completed. Development: npm run backend:dev (terminal 1), npm run dev (terminal 2). Production: npm run build && npm start. Configure HTTPS and PUBLIC_ORIGIN for production.'
);
