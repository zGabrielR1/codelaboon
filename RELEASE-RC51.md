# RC51 preserves Python virtual environments during build cleanup

Build cleanup recognizes virtual environments by their `pyvenv.cfg` file. Environments with custom directory names inside source trees are skipped in both normal and dry-run modes. Project build output and Python caches still get cleaned.
