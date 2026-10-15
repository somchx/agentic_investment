"""Run the built app against the Neon environment pulled into the repo root."""
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
# Existing local API credentials are fallback values, never overrides for Neon.
load_dotenv(ROOT / 'backend' / '.env')
os.environ.setdefault('PUBLIC_DIR', str(ROOT / 'frontend' / 'dist'))
os.environ['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'backend'), str(ROOT / 'deploy')])
if not (Path(os.environ['PUBLIC_DIR']) / 'index.html').exists():
    raise SystemExit('Run npm run build first.')
subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
               cwd=ROOT / 'backend', check=True)
os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'web:app',
                        '--host', '127.0.0.1', '--port', os.environ.get('PORT', '8012')])
