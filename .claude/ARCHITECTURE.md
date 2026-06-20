# Architecture Conventions

Canonical folder layout and import-dependency schema for this project. Deviations from this layout should be documented in `CLAUDE.md`.

## Structure

```
app/
  app.py              # FastAPI entry point
  dash_app.py         # Dash entry point (main server)
  typer_app.py        # CLI entry point (data seeding commands)
  constants.py        # Global / cross-package constants

  assets/
    img/
        icons/        # Icons used throughout the app

  db_model/           # SQLModel table definitions + DB operations
    retrievers/       # Read-only ORM queries (one file per domain entity)
    inserters/        # Write operations
    deleters/         # Delete operations

  domain_model/       # Pure Python enums / value objects (no DB dependency)

  methodo/            # All methodologies for backend and to serve data to front-end
    validation/       # Methodologies related to user input validation
    export/           # Methodologies related to user DB-data exports

  pages/              # Dash page modules, one subdirectory per module/page
    common/           # Shared Dash components and stores
    module_*/         # One subdirectory per top-level module
    page_*/           # One subdirectory per top-level page

seeders/              # Dataset inserters

tests/
  unitary/
  functional/

config/               # local.yaml / prod.yaml
```

Not every layer will be present (e.g. apps without custom icons skip `assets/img/icons`). When a layer exists, it must follow the names and roles above.

## Dependency schema

Modules under `app/` must respect this directed dependency graph:

```
app/
    domain_model/  # Cannot import from any other app/ module
    db_model/      # Can only import from app/domain_model and itself
    methodo/       # Can import from app/domain_model, app/db_model and itself
    pages/         # Can import from all of the above and itself
        common/    # Components imported into multiple sections or directly into a page
        section/   # Subdirectories grouping components that form a page section
```

- `domain_model/` stays pure (no SQLModel, no Dash, no IO) so its types can be reused as boundary contracts without circularity.
- `db_model/` is the only layer that knows about persistence.
- `methodo/` is where computation lives — it may read from the DB layer but never exposes Dash or HTTP concerns.
- `pages/` is the only layer that knows about Dash.

## File-naming conventions inside `pages/`

- `c_*.py` — files containing **components only** (no callbacks)
- `cb_*.py` — files containing **callbacks** (and the components they wire up)
- `m_*.py` — methodological helpers too specific or front-end-oriented to belong in `app/methodo/` or `app/db_model/`

## Import conventions

- Import from the `__init__.py` closest to root (e.g. `from app.db_model import Project`), except when the importing file is within the same sub-package — then import directly from the sibling module.
- One symbol per line from the same module.
- Group order: **stdlib → third-party → `app.*` local**, separated by blank lines.
- No wildcard imports.
- Long import lines that exceed the line-length limit are exempt from that limit.
- Place DB-coupled classes under `app/db_model/`. Pure Python types go under `app/domain_model/`.
