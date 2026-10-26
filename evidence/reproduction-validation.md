# Reproduction checks

- Windows x64, Python 3.14.3, NVIDIA sm89.
- Clean virtual environment and locked Python dependencies: passed.
- Release archive extraction and per-file SHA-256 verification: passed.
- Sampling contract tests: 2 passed; SSE protocol tests: 3 passed.
- JDK 21 bridge build and -Xverify:all restoration regression: passed.
- Dual-backend smoke requests: 6/6 parseable, no truncation.
- Complete recorded game trials and task failures: see README.
- Live orchestration entry point uses the validated bridge; a new full paired game trial was not part of the packaging checks.
