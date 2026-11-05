"""Private, atomic local TUI conversation storage."""
import json
import os
from pathlib import Path
import secrets
from datetime import datetime, timezone


def save_session(root, session):
    folder = Path(root) / 'sessions'
    folder.mkdir(parents=True, exist_ok=True)
    identifier = session['id']
    if not isinstance(identifier, str) or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
        raise ValueError('Invalid session identifier')
    record = dict(session, updated_at=datetime.now(timezone.utc).isoformat())
    target = folder / (identifier + '.json')
    temporary = folder / (identifier + '.' + secrets.token_hex(6) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def list_sessions(root):
    sessions = []
    for path in (Path(root) / 'sessions').glob('*.json'):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(item, dict) or item.get('id') != path.stem:
                continue
            if not all(isinstance(item.get(k), str) for k in ('id','title','provider','model','updated_at')):
                continue
            messages = item.get('messages')
            if not isinstance(messages, list) or any(not isinstance(m,dict) or m.get('role') not in ('user','assistant','system') or not isinstance(m.get('content'),str) for m in messages):
                continue
            sessions.append(item)
        except (ValueError, OSError):
            continue
    return sorted(sessions, key=lambda item: item['updated_at'], reverse=True)
