// Preserve source/binary redistribution notices without adding runtime features.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
const out = resolve('static/static/licenses');
mkdirSync(out, { recursive: true });
for (const name of ['LICENSE', 'LICENSE_HISTORY', 'LICENSE_NOTICE'])
	writeFileSync(resolve(out, 'Open-WebUI-' + name + '.txt'), readFileSync(name));
const project = JSON.parse(readFileSync('package.json', 'utf8'));
const queue = [...Object.keys(project.dependencies), 'svelte', '@sveltejs/kit'];
const seen = new Set(),
	notices = [
		'ChatLDT client dependency notices. Open WebUI branding and licenses are retained separately.\n'
	];
while (queue.length) {
	const name = queue.shift();
	if (seen.has(name)) continue;
	seen.add(name);
	const dir = resolve('node_modules', name),
		metadata = resolve(dir, 'package.json');
	if (!existsSync(metadata)) continue;
	const pkg = JSON.parse(readFileSync(metadata, 'utf8'));
	notices.push(
		`\n===== ${pkg.name} ${pkg.version} (${pkg.license || 'see package license'}) =====\n`
	);
	for (const file of readdirSync(dir, { withFileTypes: true }))
		if (file.isFile() && /^(licen[sc]e|notice|copying)([.\-_].*)?$/i.test(file.name))
			notices.push(file.name + '\n' + readFileSync(resolve(dir, file.name), 'utf8'));
	queue.push(...Object.keys(pkg.dependencies || {}));
}
writeFileSync(resolve(out, 'CLIENT-THIRD-PARTY-NOTICES.txt'), notices.join('\n'));
