# RC42 adds local security retests and CI regression checks

Take a baseline before remediation and another report afterward. Generate both with RC42 against the same project and file list. Comparison checks the recorded rule set, sample size limit, permission coverage, and finding evidence before classifying results.

```sh
codelaboon security audit-local --project . --file config/providers.toml.example \
  --output before.json
# After making the intended change, audit the same files again.
codelaboon security audit-local --project . --file config/providers.toml.example \
  --output after.json
codelaboon security compare --before before.json --after after.json \
  --output comparison.json --fail-on-new
```

The report lists new, persisting, no-longer-observed, and inconclusive findings. Results match by file and rule. Findings missing from truncated retest samples are inconclusive. A missing finding warrants independent verification before closing it. The CI option writes the report before returning exit status 2 if new findings are present. Earlier local reports lack rule-set metadata and need to be regenerated.
