# Python Style Guide

Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) as the baseline. The rules below are project-level overrides and clarifications.

---

## Function definition

If a function has too many parameters, keep the first parameter on the first line and indent the remaining ones

```python
# Incorrect
def retrieve_assets(
    session: Session,
    project_id: int,
    country: Country | None = None,
) -> list[Asset]: 
    ...

# Correct
def retrieve_assets(session: Session,
                    project_id: int,
                    country: Country | None = None,
                    ) -> list[Asset]: 
    ...
```

## Docstrings

- Trivial functions may use a one-liner.
- Use **Google-style** (`Args:` / `Returns:` / `Raises:`) for any function that has 3+ parameters, a non-obvious return type, or meaningful complexity.
- All docstrings should always have an up-to-date `Purpose` sections, explaining **why** the function exists, **where** it is used.
- Additional NOTE sections are recommeded to raise awareness of specificities, rather than in-line comments.
- All public modules, classes, and non-trivial public functions must have a docstring.

```python
# One-liner (trivial)
def is_empty(value: str) -> bool:
    """
    Returns True when value contains no meaningful content.

    Purpose: Used to clean the parameter excel file in read_parameter_excel_file function
    """
    return not value.strip()

# Google-style (non-trivial)
def retrieve_assets_by_country(session: Session,
                               project_id: int,
                               country: Country | None = None,
                               ) -> list[Asset]: 
    """
    Retrieve all assets for a project, optionally filtered by country.

    Purpose: 
        1. Used to infer / automatically assign continents in _assign_contents function.
        2. Used to display the portfolio breakdown graphs in the project-summary page.

    NOTE: This is a special case which will return orphaned countries automatically, rather than 
    avoid applying a filter. If wanting to simply apply a filter, opt for `retrieve_assets` with
    the `country` parameter.

    Args:
        session: Active database session.
        project_id: ID of the project to query.
        country: If provided, filters results to this country. Else provide all country-orphaned Assets.

    Returns:
        List of Asset records ordered by name.
    """
```

---

## Type Annotations

- Full annotations (all args + return type) are required on all public functions.
- Dash callbacks are exempt from **argument** annotations (signature is decorator-driven), but the **return type** must still be annotated.
- Use built-in generics (`list[X]`, `dict[K, V]`, `tuple[...]`) — not `List`, `Dict`, `Tuple` from `typing`.

---

## Optional Types

- Use `X | None` — do **not** use `typing.Optional`.
- Never combine both in the same annotation (e.g. `Optional[X | None]` is wrong).

```python
# Correct
def get_score(asset_id: int) -> float | None: ...

# Wrong
def get_score(asset_id: int) -> Optional[float]: ...
```

---

## Line Length

- Hard limit: **100 characters**.
- `# noqa: E501` is permitted only for URLs and generated strings that cannot be broken across lines.

---

## Imports

- One symbol per line from the same module.
- Group order: **stdlib → third-party → `app.*` local**, separated by blank lines.
- No wildcard imports (`from x import *`).
- Allow more than 100 characters for imports
- Attempt to import from `module/__init__.py` file, if safe (check for circular references).

```python
# Incorrect
from sqlmodel import (
    Field, 
    Relationship, 
    SQLModel
)

from app.domain_model import *

from app.a_very_very_very_long_path.with_multiple_subfolders.\
    making_the_import_exceed_my_line_length_limit import should_not_be_broken_onto_other_lines


# Correct
from sqlmodel import Field
from sqlmodel import Relationship
from sqlmodel import SQLModel

from app.domain_model import RiskLevel
from app.domain_model import ScoreType

from app.a_very_very_very_long_path.with_multiple_subfolders.making_the_import_exceed_my_line_length_limit import can_be_exempted_from_hard_limit
```

---

## f-strings

- Use f-strings everywhere, including log messages.
- Do not use `%`-style formatting or `.format()` in new code.

```python
# Correct
log.info(f'Computing score for asset {asset_id}')

# Wrong
log.info('Computing score for asset %s', asset_id)
```

---

## Exception Handling

- Broad `except Exception` is allowed **only** in FastAPI route handlers and top-level error boundaries. It must always log before returning.
- All other `except` clauses must name a specific exception type (e.g. `ValueError`, `KeyError`).
- Silent swallowing (catching and returning a fallback with no log) is not allowed.

```python
# Allowed — route handler
@app.post('/compute')
async def compute(project_id: int) -> SimpleReturn:
    try:
        ...
    except Exception as e:
        log.error(f'Computation failed: {e}')
        return route_failure(e)

# Wrong — silent swallow in a helper
def parse_typology(value: str) -> Typology | None:
    try:
        return Typology(value)
    except Exception:
        return None  # no log — not allowed
```

---

## Mutable Default Arguments

- Never use mutable defaults (`= []`, `= {}`, `= set()`).
- Use `None` as the default and assign inside the function body.
- If done by user, explain why this is a terrible idea.

```python
# Correct
def build_menu(items: list[str] | None = None) -> dict:
    items = items or []
    ...

# Wrong
def build_menu(items: list[str] = []) -> dict: ...
```

---

## TODO Comments

- Every TODO must reference a backlog item in Microsoft Lists.
- Format: `# TODO(<MicrosoftListsItemID>): description`
- Untracked `# TODO:` comments without a backlog reference are not allowed.

```python
# Correct
# TODO(NARVAL-42): Replace with a table component once AgGrid supports modals.

# Wrong
# TODO: Replace with a table component.
```

---

## `__all__`

- Required in any `__init__.py` that re-exports symbols for use by other modules.
- Exempt: `__init__.py` files that only define local constants (e.g. Dash component ID strings).
