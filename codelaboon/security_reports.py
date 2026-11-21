"""Conservative comparison of like-for-like assessment reports."""
import json
import re
from pathlib import Path


def read_report(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Assessment report exceeds 8 MiB')
    return json.loads(raw)


def finding_rows(items):
    return [{'target': target, 'rule': rule} for target, rule in sorted(items)]


def local_evidence(report):
    from codelaboon.security_local import AUDIT_RULESET, SAMPLE_LIMIT

    if (report.get('kind') != 'local_configuration_audit' or report.get('format') != 1
            or report.get('ruleset') != AUDIT_RULESET or report.get('sample_limit') != SAMPLE_LIMIT):
        raise ValueError('Retest both versions using the same current local auditor')
    checks = report.get('checks')
    findings = report.get('findings')
    if not isinstance(checks, list) or not 1 <= len(checks) <= 100 or not isinstance(findings, list):
        raise ValueError('Invalid local audit coverage or findings')
    files = {}
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError('Invalid local sample evidence')
        target = row.get('file')
        digest = row.get('sample_sha256')
        size = row.get('sample_bytes')
        truncated = row.get('truncated')
        if (not isinstance(target, str) or not target or target in files
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
                or type(size) is not int or not 0 <= size <= SAMPLE_LIMIT
                or type(truncated) is not bool or (truncated and size != SAMPLE_LIMIT)
                or row.get('permission_check') not in ('completed', 'not_supported')):
            raise ValueError('Invalid or duplicate local sample evidence')
        files[target] = row
    indexed = {}
    for row in findings:
        if not isinstance(row, dict):
            raise ValueError('Invalid local audit finding')
        target, rule = row.get('target'), row.get('rule')
        if (not isinstance(target, str) or target not in files or not isinstance(rule, str) or not rule
                or row.get('evidence_sha256') != files[target]['sample_sha256']):
            raise ValueError('Local finding is missing matching sample evidence')
        severity, status = row.get('severity'), row.get('status')
        line = row.get('line')
        if (severity not in ('info', 'medium', 'high')
                or status not in ('confirmed_observation', 'suspected_credential')
                or (line is not None and (type(line) is not int or not 1 <= line <= SAMPLE_LIMIT))):
            raise ValueError('Invalid local finding classification')
        finding = {'target': target, 'rule': rule, 'severity': severity, 'status': status}
        if line is not None:
            finding['line'] = line
        if (target, rule) in indexed:
            raise ValueError('Duplicate local finding')
        indexed[target, rule] = finding
    return files, indexed


def compare_local(before, after):
    before_files, old = local_evidence(before)
    after_files, new = local_evidence(after)
    if before_files.keys() != after_files.keys() or any(
        before_files[name]['permission_check'] != after_files[name]['permission_check'] for name in before_files
    ):
        raise ValueError('Comparison requires the same files and permission-check coverage')
    missing = old.keys() - new.keys()
    inconclusive = {finding for finding in missing if after_files[finding[0]]['truncated']}
    return {
        'format': 1, 'kind': 'local_audit_comparison', 'ruleset': before['ruleset'],
        'new': [new[key] for key in sorted(new.keys() - old.keys())],
        'persisting': [new[key] for key in sorted(new.keys() & old.keys())],
        'not_observed_on_retest': [old[key] for key in sorted(missing - inconclusive)],
        'inconclusive': [old[key] for key in sorted(inconclusive)],
        'limitations': 'Bounded local comparison. Verify that reports refer to the same project and confirm remediation independently.',
    }


def compare(before, after):
    """Absence on retest is not proof of remediation or an attestation."""
    if all(isinstance(report, dict) for report in (before, after)) and any(
        report.get('kind') == 'local_configuration_audit' for report in (before, after)
    ):
        return compare_local(before, after)

    def coverage(report):
        if not isinstance(report, dict) or report.get('format') != 1 or not isinstance(report.get('scope_id'), str) or not report['scope_id']:
            raise ValueError('Compare requires network assessment reports')
        rows = report.get('checks', [])
        if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) or row.get('status') not in ('completed', 'not_applicable') or not isinstance(row.get('target'), str) or not isinstance(row.get('check'), str) for row in rows):
            raise ValueError('Cannot compare incomplete assessment coverage')
        evidence = report.get('evidence')
        if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
            raise ValueError('Comparison requires assessment evidence')
        by_id = {item.get('id'): item for item in evidence if isinstance(item.get('id'), str)}
        for row in rows:
            if row['status'] == 'not_applicable':
                continue
            item = by_id.get(row.get('evidence'), {})
            if item.get('target') != row['target'] or item.get('check') != row['check']:
                raise ValueError('Assessment check is missing matching evidence')
            if item.get('error') and not (row['check'] == 'tls' and item['error'] == 'certificate_verification_failed'):
                raise ValueError('A failed response probe cannot establish comparable coverage')
        return {(row['target'], row['check']) for row in rows}
    if coverage(before) != coverage(after):
        raise ValueError('Comparison requires the same target/check coverage')
    def indexed(report):
        findings = report.get('findings')
        if not isinstance(findings, list) or any(not isinstance(row, dict) or not isinstance(row.get('target'), str) or not isinstance(row.get('rule'), str) for row in findings):
            raise ValueError('Invalid assessment findings')
        return {(row['target'], row['rule']) for row in findings}
    old, new = indexed(before), indexed(after)
    return {'format': 1, 'before_scope_id': before['scope_id'], 'after_scope_id': after['scope_id'],
            'new': finding_rows(new - old), 'persisting': finding_rows(new & old), 'not_observed_on_retest': finding_rows(old - new),
            'limitations': 'Report comparison only; not proof of a fix. Verify deployment identity, credentials and response context independently.'}
