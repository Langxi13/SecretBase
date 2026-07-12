# SecretBase Vault Core

This crate is the V4 reference implementation of the SecretBase Vault V1 envelope and payload contract. It is intentionally independent from FastAPI, desktop packaging, file locking, backups, and user data directories.

The production Web and desktop applications continue to use the Python implementation. This crate exists to prove cross-language compatibility and to prepare a stable boundary for a future Flutter mobile client.

Public operations are limited to in-memory data:

- inspect a Vault V1 header;
- validate a JSON payload;
- decrypt a Vault V1 byte buffer;
- encrypt a validated document with fresh randomness.

The `test-vectors` feature exposes deterministic encryption with caller-provided salt and nonce. It is only for golden-vector verification and must never be used for production writes.

Run checks from this directory:

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --release --all-features
```

The normative format is documented in `docs/vault-format-v1.md` at the repository root.
