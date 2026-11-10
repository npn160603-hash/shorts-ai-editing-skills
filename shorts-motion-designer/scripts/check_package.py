"""Validate the portable Skill package's basics (stdlib only)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    'SKILL.md', 'README.md', 'CODEX_START_HERE.md',
    'docs/01-integration-audit.md', 'docs/02-timeline-contract.md',
    'docs/03-creative-rules.md', 'docs/04-implementation-paths.md',
    'docs/05-qa-acceptance.md', 'docs/06-roadmap.md',
    'docs/07-standalone-motion-recipes.md',
    'schemas/shorts-motion-plan.schema.json',
    'examples/shorts-motion-plan.example.json',
    'examples/preset-library.example.json'
]
errors = []
for rel in required:
    if not (ROOT / rel).is_file():
        errors.append(f'Missing: {rel}')

try:
    schema = json.loads((ROOT / 'schemas/shorts-motion-plan.schema.json').read_text(encoding='utf-8'))
    plan = json.loads((ROOT / 'examples/shorts-motion-plan.example.json').read_text(encoding='utf-8'))
    presets = json.loads((ROOT / 'examples/preset-library.example.json').read_text(encoding='utf-8'))
    if schema.get('$schema') != 'https://json-schema.org/draft/2020-12/schema':
        errors.append('Unexpected JSON Schema version')
    if plan.get('version') != '1.0':
        errors.append('Bad example plan version')
    if not presets.get('presets'):
        errors.append('No preset examples')
    duration = plan.get('video', {}).get('durationSec', 0)
    for kind in ('elements','cues'):
        for idx, item in enumerate(plan.get(kind, [])):
            a,b=item.get('startSec', -1),item.get('endSec', -1)
            if not (0 <= a < b <= duration):
                errors.append(f'Invalid time range {kind}[{idx}]')
    if plan.get('safeArea',{}).get('left',0) + plan.get('safeArea',{}).get('right',0) >= 1:
        errors.append('Invalid horizontal safeArea')
    if plan.get('safeArea',{}).get('top',0) + plan.get('safeArea',{}).get('bottom',0) >= 1:
        errors.append('Invalid vertical safeArea')
except Exception as exc:
    errors.append(f'Error parsing examples: {exc}')

if errors:
    print('FAIL\n' + '\n'.join('- '+str(x) for x in errors))
    sys.exit(1)
print('PASS: Skill files and sample JSON basic checks. This does NOT prove runtime integration.')
