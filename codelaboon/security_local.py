"""Bounded, read-only checks of explicitly named local configuration files."""
import errno
import hashlib
import os
from pathlib import Path
import re
import stat


AUDIT_RULESET = "local-config-v1"
SAMPLE_LIMIT = 65536
TOKEN_RULES = {
    'github-token-pattern': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})\b'),
    'stripe-live-secret-pattern': re.compile(rb'\b(?:sk|rk)_live_[A-Za-z0-9]{24,}\b'),
}


def read_sample(root, relative):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NONBLOCK', 0)
    if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY'):
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(root, directory_flags)
        try:
            for part in relative.parts[:-1]:
                try:
                    child = os.open(part, directory_flags, dir_fd=directory)
                except OSError as error:
                    if error.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise ValueError('Audit input ancestors must be directories without symlinks') from error
                    raise
                os.close(directory)
                directory = child
            info = os.stat(relative.name, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Audit inputs must be regular files without symlinks')
            descriptor = os.open(relative.name, flags, dir_fd=directory)
        finally:
            os.close(directory)
        with os.fdopen(descriptor, 'rb') as stream:
            return checked_sample(stream, info)
    path = root
    for part in relative.parts:
        path = path / part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_reparse_tag', 0):
            raise ValueError('Symlinks and reparse points are not audit inputs')
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Audit inputs must be regular files')
    # Recheck the opened object; O_NOFOLLOW is supported on POSIX.
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        return checked_sample(stream, info)


def checked_sample(stream, expected):
    opened = os.fstat(stream.fileno())
    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
        raise ValueError('Audit input changed during opening')
    return stream.read(SAMPLE_LIMIT + 1), opened


def audit_local(project, files):
    """No traversal, symlink following, command execution or raw secret retention."""
    root = Path(project).resolve(strict=True)
    if not root.is_dir() or not isinstance(files, list) or not files or len(files) > 100 or any(not isinstance(value, str) for value in files):
        raise ValueError('Provide a project directory and between 1 and 100 explicit files')
    checks, findings = [], []
    seen = set()
    for value in files:
        relative = Path(value)
        if relative.is_absolute() or relative.drive or '..' in relative.parts or not relative.parts or ':' in str(value):
            raise ValueError('Audit files must be relative paths inside the project')
        if relative in seen:
            continue
        seen.add(relative)
        raw, opened = read_sample(root, relative)
        sample = raw[:SAMPLE_LIMIT]
        row = {'file': relative.as_posix(), 'sample_sha256': hashlib.sha256(sample).hexdigest(),
               'sample_bytes': len(sample), 'truncated': len(raw) > SAMPLE_LIMIT,
               'permission_check': 'not_supported' if os.name == 'nt' else 'completed'}
        rules = []
        private_key = bool(re.search(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----', sample))
        token_lines = {}
        for rule, pattern in TOKEN_RULES.items():
            match = pattern.search(sample)
            if match:
                token_lines[rule] = sample.count(b'\n', 0, match.start()) + 1
        name = relative.name
        sensitive = private_key or bool(token_lines) or name == '.env' or name in ('credentials.json', 'credentials', 'id_rsa', 'id_ed25519')
        if private_key:
            rules.append(('private-key-material', 'info', 'Keep private keys outside source control and restrict access; verify whether this file is intended.'))
        if os.name != 'nt' and sensitive and opened.st_mode & 0o077:
            rules.append(('sensitive-file-permissions', 'medium', 'Restrict group/other access according to the intended account ownership.'))
        if os.name != 'nt' and opened.st_mode & 0o002:
            rules.append(('world-writable-config', 'medium', 'Remove write permission for other users and verify file ownership.'))
        rules.extend((rule, 'high', 'Verify the credential with its owner. If valid, revoke or rotate it and remove it from the file.')
                     for rule in token_lines)
        for rule, severity, fix in rules:
            finding = {'rule': rule, 'target': relative.as_posix(), 'severity': severity,
                       'status': 'suspected_credential' if rule in token_lines else 'confirmed_observation',
                       'remediation': fix, 'evidence_sha256': row['sample_sha256']}
            if rule in token_lines:
                finding['line'] = token_lines[rule]
            findings.append(finding)
        checks.append(row)
    return {'format': 1, 'kind': 'local_configuration_audit', 'ruleset': AUDIT_RULESET,
            'sample_limit': SAMPLE_LIMIT, 'checks': checks, 'findings': findings,
            'limitations': 'Explicit files only; bounded samples; no Windows ACL, dependency, malware or exhaustive secret analysis. Token matches are unverified. On platforms without no-follow directory handles, audit a trusted, quiescent directory.'}
