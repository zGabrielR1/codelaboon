# RC41 adds a defensive local security gate

- Local audits flag GitHub token and Stripe live-secret patterns in explicitly listed files. Findings reference the file, first matching line, and sampled evidence digest and do not contain matched values. Token validity is not checked.
- Use `--fail-on high` in CI. The command writes the report before returning exit status 2 for findings at or above the selected threshold. The release workflow applies this gate to Codelaboon's own release configuration.
- On systems with no-follow directory handles, the auditor opens files relative to those handles and rejects symlink ancestors. Platform limitations are recorded in the report.

```sh
codelaboon security audit-local --project . --file config/providers.toml.example \
  --file pyproject.toml --fail-on high --output local-security.json
```
