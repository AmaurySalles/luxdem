# Testing Conventions

## Test runner

- **Runner**: Python's built-in `unittest`, discovered under `tests/`.
- **Layout**:
  - `tests/unitary/` — unit tests (fast, no external dependencies)
  - `tests/functional/` — functional / integration tests (may hit DB, filesystem, mocks)
- **Discovery command**: `python3 -m unittest discover tests`

## Running tests

### Inside the Docker container

```bash
# Full suite
docker exec luxdem_backend python3 -m unittest discover tests

# Single test
docker exec luxdem_backend python3 -m unittest tests.unitary.<module>.<TestClass>.<test_method>
```

### Via Makefile

```bash
make all-tests    # Full suite inside the container
```

Run `make help` to see the full list of test targets.

## Conventions

- Test files are named `test_<thing>.py` to match `unittest` discovery defaults.
- Test classes inherit from `unittest.TestCase`.
- Avoid hitting real external services in `tests/unitary/` — mock instead.
- Fixtures and shared setup live alongside the tests they support, not in a global conftest (we do not use pytest).
- Long-running setup (DB seeding, config loading) is amortised via `setUpClass` / `tearDownClass` rather than `setUp` / `tearDown` where possible.

## When tests are required

Do not write new tests unless the user explicitly asks, or you have fixed a bug and the user has asked for a regression test.
