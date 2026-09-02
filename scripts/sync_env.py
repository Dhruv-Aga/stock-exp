from pathlib import Path

root = Path(__file__).resolve().parent.parent
root_env = root / '.env'
server_env = root / 'server' / '.env'

if not root_env.exists():
    example = root / '.env.example'
    if example.exists():
        root_env.write_text(example.read_text(encoding='utf-8'), encoding='utf-8')
        print('Created .env from .env.example — add your keys before live features work.')

if not server_env.exists():
    example = root / 'server' / '.env.example'
    if example.exists():
        server_env.write_text(example.read_text(encoding='utf-8'), encoding='utf-8')

keys = ('KITE_API_KEY', 'KITE_API_SECRET', 'KITE_ACCESS_TOKEN', 'PORT')
values = {}
if root_env.exists():
    for line in root_env.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        if key in keys:
            values[key] = value

if not server_env.exists():
    server_env.write_text('', encoding='utf-8')

lines = server_env.read_text(encoding='utf-8').splitlines()
out = []
seen = set()
for line in lines:
    if '=' in line and not line.strip().startswith('#'):
        key = line.split('=', 1)[0].strip()
        if key in values:
            out.append(f'{key}={values[key]}')
            seen.add(key)
            continue
    out.append(line)

for key in keys:
    if key in values and key not in seen:
        out.append(f'{key}={values[key]}')

if 'ALLOWED_ORIGINS' not in '\n'.join(out):
    out.append('ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://0.0.0.0:8080')

server_env.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')
print('Synced Kite settings to server/.env')
