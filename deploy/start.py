"""Single-instance deployment entrypoint; secrets are supplied by the host."""
import os
import subprocess

url = os.environ.get('DATABASE_URL', '')
if not url:
    raise RuntimeError('Set DATABASE_URL to the separate Neon demo database.')
if url.startswith(('postgres://', 'postgresql://')):
    os.environ['DATABASE_URL'] = 'postgresql+psycopg2://' + url.split('://', 1)[1]
subprocess.run(['alembic', 'upgrade', 'head'], check=True)
os.execvp('uvicorn', ['uvicorn', 'web:app', '--host', '0.0.0.0',
                     '--port', os.environ.get('PORT', '10000'), '--workers', '1'])
