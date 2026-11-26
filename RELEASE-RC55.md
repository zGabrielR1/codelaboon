# RC55 improves release update handling

- The updater uses the normalized version to find the wheel and the original tag to download it from GitHub.
- Malformed release asset metadata produces a clear error before the updater downloads a wheel or checksum manifest.
