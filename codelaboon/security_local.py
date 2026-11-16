"""Bounded, read-only checks of explicitly named local configuration files."""
import hashlib
import os
from pathlib import Path
import re
import stat


def audit_local(project, files):
    """No traversal, symlink following, command execution or raw secret retention."""
    root = Path(project).resolve(strict=True)
    if not root.is_dir() or not isinstance(files, list) or not files or len(files) > 100 or any(not isinstance(value, str) for value in files):
        raise ValueError('Provide a project directory and between 1 and 100 explicit files')
    checks, findings = [], []
    for value in dict.fromkeys(files):
        relative = Path(value)
        if relative.is_absolute() or relative.drive or '..' in relative.parts or not relative.parts or ':' in str(value):
            raise ValueError('Audit files must be relative paths inside the project')
        path = root
        for part in relative.parts:
            path = path / part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_reparse_tag', 0):
                raise ValueError('Symlinks and reparse points are not audit inputs')
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Audit inputs must be regular files')
        # Recheck the opened object; O_NOFOLLOW is supported on POSIX.
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('Audit input changed during opening')
            raw = stream.read(65537)
        row = {'file': relative.as_posix(), 'sample_sha256': hashlib.sha256(raw[:65536]).hexdigest(),
               'sample_bytes': min(len(raw), 65536), 'truncated': len(raw) > 65536,
               'permission_check': 'not_supported' if os.name == 'nt' else 'completed'}
        rules = []
        private_key = bool(re.search(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----', raw[:65536]))
        sensitive = private_key or path.name == '.env' or path.name in ('credentials.json', 'credentials', 'id_rsa', 'id_ed25519')
        if private_key:
            rules.append(('private-key-material', 'info', 'Keep private keys outside source control and restrict access; verify whether this file is intended.'))
        if os.name != 'nt' and sensitive and opened.st_mode & 0o077:
            rules.append(('sensitive-file-permissions', 'medium', 'Restrict group/other access according to the intended account ownership.'))
        if os.name != 'nt' and opened.st_mode & 0o002:
            rules.append(('world-writable-config', 'medium', 'Remove write permission for other users and verify file ownership.'))
        for rule, severity, fix in rules:
            findings.append({'rule': rule, 'target': relative.as_posix(), 'severity': severity,
                             'status': 'confirmed_observation', 'remediation': fix,
                             'evidence_sha256': row['sample_sha256']})
        checks.append(row)
    return {'format': 1, 'kind': 'local_configuration_audit', 'checks': checks, 'findings': findings,
            'limitations': 'Explicit files only; bounded samples; no Windows ACL, dependency, malware or exhaustive secret analysis. Use a trusted, quiescent directory; concurrent ancestor replacement is not isolated.'}
