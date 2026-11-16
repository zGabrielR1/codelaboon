"""Conservative comparison of like-for-like assessment reports."""
import json
from pathlib import Path


def read_report(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Assessment report exceeds 8 MiB')
    return json.loads(raw)


def compare(before, after):
    """Absence on retest is not proof of remediation or an attestation."""
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
    def rows(items):
        return [{'target': target, 'rule': rule} for target, rule in sorted(items)]
    return {'format': 1, 'before_scope_id': before['scope_id'], 'after_scope_id': after['scope_id'],
            'new': rows(new - old), 'persisting': rows(new & old), 'not_observed_on_retest': rows(old - new),
            'limitations': 'Report comparison only; not proof of a fix. Verify deployment identity, credentials and response context independently.'}
