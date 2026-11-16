"""Pure response analysis; never return cookie names or values as evidence."""
from http.cookies import SimpleCookie, CookieError

PROBE_ORIGIN = 'https://codelaboon-probe.invalid'


def browser_observations(headers, https):
    """Analyze policy tokens without copying arbitrary response header values."""
    values = {}
    for name, value in headers:
        values.setdefault(name.lower(), []).append(value)
    def one(name):
        rows = values.get(name, [])
        return rows[0].strip() if len(rows) == 1 else ''
    csp = {}
    for directive in one('content-security-policy').split(';'):
        tokens = directive.strip().lower().split()
        if tokens:
            csp.setdefault(tokens[0], tokens[1:])
    script = csp.get('script-src', csp.get('default-src', []))
    ancestors = csp.get('frame-ancestors', [])
    frame = one('x-frame-options').lower() in ('deny', 'sameorigin') or bool(ancestors and '*' not in ancestors)
    cors = one('access-control-allow-origin')
    result = {
        'cors_reflects_probe_origin': cors == PROBE_ORIGIN,
        'cors_wildcard': cors == '*',
        'cors_credentials': one('access-control-allow-credentials') == 'true',
        'duplicate_policy_headers': any(len(values.get(k, [])) > 1 for k in
            ('access-control-allow-origin', 'access-control-allow-credentials', 'x-frame-options')),
        'html_response': 'text/html' in one('content-type').lower(),
        'framing_restricted': frame,
        'csp_unsafe_eval': "'unsafe-eval'" in script,
        'csp_wildcard_scripts': '*' in script,
        'nosniff_valid': one('x-content-type-options').lower() == 'nosniff',
    }
    if https:
        import re
        match = re.search(r'(?:^|;)\s*max-age\s*=\s*(\d+)\s*(?:;|$)', one('strict-transport-security'), re.I)
        result['hsts_positive_max_age'] = bool(match and match[1].lstrip('0'))
    return result


def cookie_observations(values, https):
    """Return attribute counts, without retaining credential material."""
    counts = dict(parsed=0, unparsed=0, missing_secure=0, missing_httponly=0,
                  missing_samesite=0, insecure_samesite_none=0,
                  invalid_host_prefix=0, invalid_secure_prefix=0)
    for value in values:
        cookie = SimpleCookie()
        try:
            cookie.load(value)
        except CookieError:
            counts['unparsed'] += 1
            continue
        if not cookie:
            counts['unparsed'] += 1
        for morsel in cookie.values():
            counts['parsed'] += 1
            counts['missing_secure'] += int(https and not morsel['secure'])
            counts['missing_httponly'] += int(not morsel['httponly'])
            counts['missing_samesite'] += int(morsel['samesite'].lower() not in ('strict', 'lax', 'none'))
            counts['insecure_samesite_none'] += int(morsel['samesite'].lower() == 'none' and not morsel['secure'])
            counts['invalid_host_prefix'] += int(morsel.key.startswith('__Host-') and
                (not https or not morsel['secure'] or morsel['path'] != '/' or bool(morsel['domain'])))
            counts['invalid_secure_prefix'] += int(morsel.key.startswith('__Secure-') and (not https or not morsel['secure']))
    return counts


def advertised_methods(values):
    # Store known method tokens only: Allow is untrusted server input.
    known = {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'TRACE', 'CONNECT'}
    return sorted({token.strip().upper() for value in values for token in value.split(',')} & known)
