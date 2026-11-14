"""Secrets: API keys and passwords.

Each secret is read from an environment variable first, then from <data>/secrets.json (written by the
web UI, file mode 0600). config.yaml never holds secrets, so it can be shared or exported safely.
"""
import json
import os

from . import paths

ENV = {
    'admin_password': 'ADMIN_PASSWORD',
    'push_token': 'PUSH_TOKEN',
    'anthropic_api_key': 'ANTHROPIC_API_KEY',
    'openai_api_key': 'OPENAI_API_KEY',
    'smtp_password': 'SMTP_PASSWORD',
    'remote_token': 'REMOTE_TOKEN',
    'session_secret': 'SESSION_SECRET',
}


def _load():
    p = paths.secrets_file()
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def get(name, default=''):
    env = ENV.get(name)
    if env and os.environ.get(env, '').strip():
        return os.environ[env].strip()
    return _load().get(name, default) or default


def source(name):
    """'env', 'file' or '' (for showing where a secret comes from without revealing it)."""
    env = ENV.get(name)
    if env and os.environ.get(env, '').strip():
        return 'env'
    return 'file' if _load().get(name) else ''


def set(name, value):
    data = _load()
    if value:
        data[name] = value
    else:
        data.pop(name, None)
    p = paths.secrets_file()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def ensure(name, nbytes=24):
    """Return the secret, generating and storing a random one if it doesn't exist yet."""
    val = get(name)
    if not val:
        import secrets as _s
        val = _s.token_urlsafe(nbytes)
        set(name, val)
    return val
