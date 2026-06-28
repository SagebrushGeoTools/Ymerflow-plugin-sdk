# Backend Hook Reference

Backend hooks are implemented as Python functions or coroutines registered as **setuptools entry
points** in the `nagelfluh.hooks` group. The entry point **name** selects the hook; the value
points to the callable. Only [backend plugins](README.md) (pip-installed Python packages) can
provide these.

```python
# setup.py / pyproject.toml
entry_points={
    'nagelfluh.hooks': [
        'register_routers = my_plugin:register_routers',
        'frontend_bundles  = my_plugin:frontend_bundles',
    ],
}
```

The hook dispatcher (`backend/hooks.py`) collects all callables registered under a given name,
calls each in turn, and:
- For `hooks.run.*` — concatenates non-`None` return values into a single list
- For `hooks.run_async.*` — same, but awaits coroutines
- Raises the last exception if any hook raised (chained via `__context__`)

> Source-path references below point at the **host application** repository (see the
> [overview](README.md) for context).

## Lifecycle / registration hooks

### `register_routers`

Called once at application startup. Allows a plugin to mount additional FastAPI routers (API
endpoints, static file mounts, etc.) on the application.

- **Caller:** `backend/main.py` startup event — `hooks.run.register_routers(app)`
- **Runner:** `run` (synchronous)
- **Parameters:**
  - `app` (`fastapi.FastAPI`) — the running FastAPI application instance
- **Returns:** `None` (return value is ignored)

```python
from fastapi import APIRouter

router = APIRouter(prefix="/my-plugin")

@router.get("/status")
async def status():
    return {"ok": True}

def register_routers(app):
    app.include_router(router)
```

### `register_models`

Called once when `backend/models/__init__.py` is first imported (before any database operation).
Allows a plugin to declare additional SQLAlchemy ORM models that should be part of the shared
metadata and picked up by Alembic.

- **Caller:** `backend/models/__init__.py` — `hooks.run.register_models()`
- **Runner:** `run` (synchronous)
- **Parameters:** none
- **Returns:** `None` (return value is ignored)

```python
from backend.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey

class MyPluginModel(Base):
    __tablename__ = "my_plugin_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    value = Column(String(255))

def register_models():
    pass  # importing this module registers MyPluginModel via Base metadata
```

### `frontend_bundles`

Called once at startup. Returns descriptors for pre-built frontend plugin bundles that ship
inside the Python package (built at `pip install` time, not in a Kubernetes pod).

- **Caller:** `backend/plugin_assets.py` — `hooks.run.frontend_bundles()`
- **Runner:** `run` (synchronous)
- **Parameters:** none
- **Returns:** `list[dict]` — each dict may contain:
  - `dist_dir` (str, **required**) — absolute path to the compiled `dist/` directory on disk
  - `name` (str, optional) — Module Federation remote name; falls back to `package.json`'s `nagelfluh.remoteName`
  - `display_name` (str, optional) — human-readable label shown in the Plugin Manager; falls back to `name`

```python
import os

def frontend_bundles():
    dist = os.path.join(os.path.dirname(__file__), 'frontend_dist')
    return [{'dist_dir': dist, 'name': 'my_plugin', 'display_name': 'My Plugin'}]
```

## User hooks

### `user_created`

Called after a new user successfully signs up, while the database transaction is still open.
Intended for post-registration side effects such as creating billing accounts or sending welcome
emails.

- **Caller:** `backend/routers/auth.py` signup handler — `await hooks.run_async.user_created(db, user)`
- **Runner:** `run_async` (coroutines are awaited)
- **Parameters:**
  - `db` (`sqlalchemy.ext.asyncio.AsyncSession`) — the active database session (transaction not yet committed)
  - `user` (`backend.models.User`) — the newly created user (already flushed, has an `id`)
- **Returns:** `None` (return value is ignored)

```python
async def user_created(db, user):
    billing_account = BillingAccount(user_id=user.id, credits=0)
    db.add(billing_account)
    # no need to commit — the caller commits after this hook returns
```

### `user_query_options`

Called whenever a `User` row is loaded from the database. Allows plugins to inject SQLAlchemy
eager-load options so that plugin-owned relationships are available on the `user` object without
additional queries.

- **Caller:** `backend/routers/auth.py` (login, signup, get-account, update-preferences) — `hooks.run.user_query_options()`
- **Runner:** `run` (synchronous)
- **Parameters:** none
- **Returns:** `list[sqlalchemy.orm.interfaces.LoaderOption]` — options passed to `.options(*opts)` when selecting `User`

```python
from sqlalchemy.orm import selectinload
from .models import BillingAccount  # relationship on User

def user_query_options():
    return [selectinload(User.billing_account)]
```

### `user_to_dict`

Called inside `User.to_dict()` to let plugins inject extra fields into the serialised user
object returned by the API.

- **Caller:** `backend/models/user.py` `User.to_dict()` — `hooks.run.user_to_dict(self)`
- **Runner:** `run` (synchronous)
- **Parameters:**
  - `user` (`backend.models.User`) — the user instance being serialised
- **Returns:** `list[dict]` — each dict is merged (via `dict.update()`) into the base user dict

```python
def user_to_dict(user):
    account = user.billing_account  # eager-loaded via user_query_options
    if account is None:
        return []
    return [{'credits': account.credits, 'plan': account.plan}]
```

## Job lifecycle hooks

### `job_pre_run`

Called just before a process job is dispatched to Kubernetes. Raise
`backend.exceptions.UserError` to abort the job with a user-visible error message; any other
exception is logged and also aborts the job.

- **Caller:** `backend/models/process.py` `ProcessVersion.run_task()` — `await hooks.run_async.job_pre_run(db, user, process, process_version)`
- **Runner:** `run_async` (coroutines are awaited)
- **Parameters:**
  - `db` (`sqlalchemy.ext.asyncio.AsyncSession`) — active database session
  - `user` (`backend.models.User`) — user who owns the process
  - `process` (`backend.models.Process`) — the process being run
  - `process_version` (`backend.models.ProcessVersion`) — the specific version about to run
- **Returns:** `None` (return value is ignored)
- **Side effects:** Raising `UserError` marks the process version as `FAILED` with the error message in the log

```python
from backend.exceptions import UserError

async def job_pre_run(db, user, process, process_version):
    account = user.billing_account
    if account is None or account.credits <= 0:
        raise UserError("Insufficient credits to run this process.")
    # Optionally place a hold here and release in job_completed
```

### `job_completed`

Called after a job finishes (whether it succeeded or failed), while the database transaction is
still open. Intended for billing, usage tracking, or notification side effects.

- **Caller:** `backend/models/process.py` `ProcessVersion.handle_job_completion()` — `await hooks.run_async.job_completed(db, process, process_version, runtime_seconds, status)`
- **Runner:** `run_async` (coroutines are awaited)
- **Parameters:**
  - `db` (`sqlalchemy.ext.asyncio.AsyncSession`) — active database session (transaction not yet committed)
  - `process` (`backend.models.Process`) — the completed process
  - `process_version` (`backend.models.ProcessVersion`) — the specific version that ran; `process_version.started_at` and `process_version.completed_at` are set
  - `runtime_seconds` (`float`) — wall-clock duration from job start to completion
  - `status` (`str`) — `"succeeded"` or `"failed"`
- **Returns:** `None` (return value is ignored)

```python
async def job_completed(db, process, process_version, runtime_seconds, status):
    account = process_version.process.owner.billing_account
    if account and status == "succeeded":
        cost = compute_cost(runtime_seconds)
        account.credits -= cost
        # transaction is committed by the caller
```
