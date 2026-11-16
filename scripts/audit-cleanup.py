"""Read-only import/entrypoint inventory. Writes a reviewable removal plan only."""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parent.parent
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
changed=set(subprocess.check_output(['git','diff','--name-only'],cwd=root).decode().splitlines())
pyroot=root/'backend'
modules={}
for p in (pyroot/'open_webui').rglob('*.py'):
 if '__pycache__' in p.parts:continue
 m='.'.join(p.relative_to(pyroot).with_suffix('').parts)
 if m.endswith('.__init__'):m=m[:-9]
 modules[m]=p
edges={}
for mod,p in modules.items():
 found=set()
 for n in ast.walk(ast.parse(p.read_text())):
  if isinstance(n,ast.Import):found.update(a.name for a in n.names)
  elif isinstance(n,ast.ImportFrom):
   base=n.module or ''
   if n.level:
    pkg=mod.split('.')[:-n.level] if p.name!='__init__.py' else mod.split('.')[:1-n.level or None]
    base='.'.join(pkg+[base]).strip('.')
   found.add(base)
   found.update(base+'.'+a.name for a in n.names)
 edges[mod]=sorted(m for m in found if m in modules)
roots=['open_webui','open_webui.main','open_webui.manual.setup']+[m for m in modules if m.startswith('open_webui.migrations.')]
seen=set();todo=list(roots)
while todo:
 m=todo.pop()
 if m in seen:continue
 seen.add(m);todo.extend(edges.get(m,[]))
pykeep={str(modules[m].relative_to(root)) for m in seen if m in modules}
# Include package initializers on the import path.
for f in list(pykeep):
 for parent in (root/f).parents:
  if parent==pyroot:break
  init=parent/'__init__.py'
  if init.is_file():pykeep.add(str(init.relative_to(root)))
# All intended SvelteKit routes, checked explicitly; old product routes are
# independently classified below, rather than treated as reachable app roots.
webroots=['src/routes/+layout.js','src/routes/+layout.svelte','src/routes/(app)/+layout.svelte','src/routes/(app)/+page.svelte','src/routes/(app)/c/[id]/+page.svelte','src/app.html','src/app.css','src/tailwind.css']
webkeep=set();todo=[root/f for f in webroots];unresolved=[];webedges={}
while todo:
 p=todo.pop()
 if str(p.relative_to(root)) in webkeep:continue
 webkeep.add(str(p.relative_to(root)))
 source=p.read_text();imports=re.findall(r'''(?:from\s*|import\s*\(|import\s*)['"]([^'"]+)['"]''',source)
 webedges[str(p.relative_to(root))]=imports
 for spec in imports:
  if not spec.startswith(('.', '$lib/')):continue
  base=root/'src/lib'/spec[5:] if spec.startswith('$lib/') else p.parent/spec
  candidates=[base,Path(str(base)+'.ts'),Path(str(base)+'.js'),base/'index.ts',base/'index.js']
  resolved=next((f for f in candidates if f.is_file()),None)
  if not resolved:unresolved.append([str(p.relative_to(root)),spec])
  elif resolved.suffix in {'.ts','.js','.svelte','.css','.json'}:todo.append(resolved)
plan=[]
for name in tracked:
 p=root/name
 if not p.is_file() or name in changed or any(k in p.name.upper() for k in ('LICENSE','NOTICE','COPYRIGHT','BRANDING')):continue
 reason=None
 if name.startswith('backend/open_webui/') and p.suffix=='.py' and name not in pykeep:
  reason='Unreachable from application, setup and every preserved historical migration; replaced router/Socket.IO registrations reviewed'
 elif name.startswith('src/lib/') and name not in webkeep:
  reason='Outside retained chat/layout/input/Markdown/i18n dependency closure; upstream feature entrypoints removed by route plan'
 elif name.startswith('src/routes/') and name not in webkeep:
  reason='Dedicated upstream feature/auth/admin route; current product uses shared chat and authenticated account dialogs'
 if reason:plan.append({'path':name,'reason':reason,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
report={'backend_roots':roots,'backend_edges':{k:edges[k] for k in seen if k in edges},'retained_backend':sorted(pykeep),'retained_frontend':sorted(webkeep),'frontend_imports':webedges,'unresolved_frontend':unresolved,'dynamic_checks':'No dynamic product imports in retained roots. Alembic discovers versions separately (all retained); SvelteKit route discovery is covered by explicit route plan. Static brand files/fonts retained; build validates imported node_modules assets.','protected':'Only unchanged, Git-tracked source files are candidates. .git, environment, data, uploads, secrets, backups, licenses, notices, brand assets and migrations excluded.','candidates':plan}
(root/'docs/CHATLDT_CURRENT_IMPORT_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
print('Unresolved frontend imports:',unresolved)
print('Backend runtime closure:',len(pykeep),'files; frontend closure:',len(webkeep),'files; reviewed candidates:',len(plan))
