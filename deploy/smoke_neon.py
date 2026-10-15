"""HTTP-to-Neon integration smoke test; removes only its temporary user."""
import os
from pathlib import Path
import re
import secrets
import uuid

from dotenv import load_dotenv
import requests
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
BASE = os.environ.get('SMOKE_BASE_URL', 'http://127.0.0.1:8012')
engine = create_engine(os.environ['DATABASE_URL_UNPOOLED'])
email = f'neon-smoke-{uuid.uuid4().hex}@example.com'
password = secrets.token_urlsafe(24) + 'Aa1!'

def check(label, condition):
    assert condition, label
    print(f'PASS {label}', flush=True)

def call(method, path, **kwargs):
    return requests.request(method, BASE + path, timeout=30, **kwargs)

try:
    with engine.connect() as conn:
        check('Neon client TLS', conn.connection.driver_connection.info.ssl_in_use)
        check('Alembic at head', conn.execute(text('select version_num from alembic_version')).scalar() == 'd4e6f8a0b2c4')
        check('No default admin seeded', conn.execute(text("select count(*) from users where email='admin@example.com'")).scalar() == 0)
    page = call('GET', '/')
    check('Built frontend HTTP 200', page.status_code == 200 and '<html' in page.text)
    asset = re.search(r'src="([^"]+\.js)"', page.text).group(1)
    check('Built JavaScript served', call('GET', asset).status_code == 200)
    check('SPA /agent HTTP 200', call('GET', '/agent').status_code == 200)
    check('API health', call('GET', '/api/health').json() == {'ok': True})
    check('Unauthenticated access rejected', call('GET', '/api/auth/me').status_code == 401)
    result = call('POST', '/api/auth/register', json={'email': email, 'password': password, 'full_name': 'Neon smoke test'})
    check('Register writes to Neon', result.status_code == 200)
    result = call('POST', '/api/auth/login', json={'email': email, 'password': password})
    check('Login reads from Neon', result.status_code == 200)
    headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
    check('Authenticated profile read', call('GET', '/api/auth/me', headers=headers).json()['email'] == email)
    result = call('PATCH', '/api/auth/me', headers=headers, json={'email': email, 'full_name': 'Verified Neon profile'})
    check('Profile update HTTP 200', result.status_code == 200)
    with engine.connect() as conn:
        check('Profile persisted through independent connection', conn.execute(text('select full_name from users where email=:email'), {'email': email}).scalar() == 'Verified Neon profile')
    result = call('GET', '/api/reasons', headers=headers)
    check('Seeded thesis rules read', result.status_code == 200 and len(result.json()) == 3)
    new_password = secrets.token_urlsafe(24) + 'Aa2!'
    check('Change password', call('POST', '/api/auth/change-password', headers=headers, json={'current_password': password, 'new_password': new_password}).status_code == 200)
    check('Old token revoked', call('GET', '/api/auth/me', headers=headers).status_code == 401)
    check('New password login', call('POST', '/api/auth/login', json={'email': email, 'password': new_password}).status_code == 200)
finally:
    with engine.begin() as conn:
        conn.execute(text('delete from users where email=:email'), {'email': email})
    engine.dispose()
    print('Temporary smoke user removed', flush=True)
