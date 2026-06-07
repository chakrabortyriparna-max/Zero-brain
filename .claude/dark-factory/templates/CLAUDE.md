# Dark Factory — Code Conventions

## Language & Style

- Follow the existing codebase style. Do not introduce new formatting rules.
- Prefer explicit over clever. Readable code wins over terse one-liners.
- Comment the "why", not the "what". Good code explains itself; comments explain intent.

## Project Types

The factory auto-detects the project type and uses the appropriate tooling:

| Type | Detected By | Checks | Test Runner |
|------|-------------|--------|-------------|
| Python | `pyproject.toml`, `requirements.txt`, `setup.py` | `ruff`, `mypy` | `pytest` |
| JavaScript/TypeScript | `package.json` | `eslint`, `tsc`, `biome` | `vitest`, `jest` |
| Rust | `Cargo.toml` | `cargo clippy`, `cargo fmt` | `cargo test` |
| Go | `go.mod` | `go vet`, `gofmt` | `go test` |

## Change Discipline

- Minimal blast radius. Touch only what's needed to fix the issue.
- No refactoring piggybacking. If the codebase needs cleanup, file a separate issue.
- Add tests for bug fixes. No test = no merge.
- Update docs if the fix changes user-visible behavior.

## Security

- Never hardcode secrets. Use environment variables or existing config mechanisms.
- Validate all external input. Assume hostility from user-supplied data.
- No new dependencies without justification. Prefer the standard library.
- Scan for SQL injection, XSS, command injection, and path traversal in every fix.

## PR Hygiene

- Branch name: `factory/fix-<issue-number>-<short-description>`
- PR title: `Fix #<issue-number>: <description>`
- PR description must include: root cause, fix summary, test plan, and verification steps.
- Keep diffs under 200 lines when possible. Large changes need human pre-approval.
