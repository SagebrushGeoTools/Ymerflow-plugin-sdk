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

The hook dispatcher (`backend/hooks.py`) collects all callables registered under a given name
(sorted by distribution name, so fan-out order is deterministic) and dispatches via one of three
runner flavours:

- **`hooks.run.*`** — calls each hook in turn, concatenates non-`None`/non-empty return values
  into a single list. Raises the last exception if any hook raised (chained via `__context__`
  onto earlier ones).
- **`hooks.run_async.*`** — same as `run`, but awaits coroutines returned by async hook functions.
- **`hooks.run_first.*`** — calls `hooks.run_first.<name>(default, *args, **kwargs)`. Calls each
  hook in turn and returns the first **non-`None`** result; if none answer, returns `default`.
  Unlike `run`/`run_async`, disagreement between plugins is *not* an error — first-registered
  (by dist-name sort order) silently wins. Only used where exactly one answer is needed (e.g.
  picking a single storage backend for a new project).

There's also `hooks.any_registered(name)`, a plain function (not a namespace) that returns whether
*any* plugin registers a given hook name at all — used to distinguish "no plugins registered" from
"plugins registered but all returned nothing" for callers that only want a fallback in the former
case (e.g. `select_clusters`, below).

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

## Cluster hooks

### `select_clusters`

Restricts which Kubernetes clusters a user may run jobs on. If **no** plugin registers this hook,
every active cluster is allowed (checked via `hooks.any_registered`, not by an empty result — a
registered hook that legitimately returns an empty set means "no clusters allowed", not "fall back
to all").

- **Caller:** `backend/models/cluster.py` `get_allowed_clusters()` — `hooks.run.select_clusters(db, user, project_id, resource_requests)`
- **Runner:** `run` (synchronous)
- **Parameters:**
  - `db` (`sqlalchemy.ext.asyncio.AsyncSession`) — active database session
  - `user` (`backend.models.User`) — the requesting user
  - `project_id` (`str | None`) — project context, if any
  - `resource_requests` (`dict | None`) — `{"cpu": ..., "memory": ...}` if the caller specified resource hints, else `None`
- **Returns:** `list[str]` — cluster ids this plugin allows; the union across all registered plugins is the final allowed set

```python
def select_clusters(db, user, project_id, resource_requests):
    if user.billing_account and user.billing_account.plan == "premium":
        return ["gpu-cluster-1", "gpu-cluster-2"]
    return ["shared-cluster"]
```

### `cluster_provider_handlers`

Registers `ClusterProvider` implementations for `Cluster.cluster_type` values (e.g.
`same-as-backend`, `kubeconfig`, `minikube`). Core registers its own built-in providers through
this exact same hook (see the host's root `setup.py`) — a plugin adding a new cluster type (e.g.
GKE) uses the identical channel core does, with no "core is special" path.

- **Caller:** `backend/services/cluster_providers/__init__.py` `get_cluster_provider()` — `hooks.run.cluster_provider_handlers()`
- **Runner:** `run` (synchronous)
- **Parameters:** none
- **Returns:** `list[tuple[str, type]]` — `(cluster_type, ClusterProviderSubclass)` pairs. A duplicate `cluster_type` across plugins raises `ValueError`.

#### The `Cluster` row

Each admin-configured cluster is a `Cluster` row (`backend/models/cluster.py`). The fields a
`ClusterProvider` cares about:
- `cluster_type` (`str`) — the discriminator dispatched to `get_cluster_provider()`; this is the key you register under
- `provider_config` (`dict`, JSON column) — opaque, provider-specific config (e.g. a parsed kubeconfig dict for `KubeconfigClusterProvider`); the admin UI's matching [`cluster_provider_forms`](frontend-hooks.md#cluster_provider_forms) entry is what edits this
- `namespace` (`str`) — the Kubernetes namespace jobs for this cluster should run in

#### `ClusterProvider` base class

`backend.services.cluster_providers.ClusterProvider` — subclass this and register an instance's
class via `cluster_provider_handlers`.

- `self_service_registration` (class attribute, default `False`) — set `True` for providers that
  can't complete registration synchronously in the admin "Add Cluster" dialog (the config is
  filled in later by something running on the target host, e.g. a setup script the admin
  copy-pastes). See `docs/plans/minikube-cluster-registration-ux.md` in the host repo for the
  out-of-band registration flow this enables (`minikube` is the only built-in provider that sets
  this).
- `connect(provider_config: dict, namespace: str) -> K8sClient` — **required**, no default.
  Synchronous — just constructs and returns a `K8sClient`, it does not itself open a connection
  (`K8sClient` lazily initializes on first API call). This is the one method every provider must
  implement; everything else is generic dispatch built on top of the client it returns.
- `test_connection(provider_config: dict) -> None` (async) — optional; default implementation
  calls `connect()` then does a timeout-bounded `list_namespace` call to verify reachability. Raise
  a clear exception on failure. Override when a cheaper or more specific check makes sense (e.g.
  validating a token before even attempting a network call).

```python
from backend.services.cluster_providers import ClusterProvider
from backend.services.k8s_client import K8sClient

class GkeClusterProvider(ClusterProvider):
    def connect(self, provider_config, namespace):
        # provider_config is whatever your cluster_provider_forms component wrote to
        # Cluster.provider_config — e.g. {"kubeconfig": {...}} built from a GCP service account
        return K8sClient(namespace=namespace, kubeconfig=provider_config["kubeconfig"])

def cluster_provider_handlers():
    return [("gke", GkeClusterProvider)]
```

This mirrors the built-in `KubeconfigClusterProvider`
(`backend/services/cluster_providers/kubeconfig.py`) almost exactly — most new cluster types are
really just "resolve a kubeconfig dict some other way," so `connect()` can often just delegate to
`K8sClient(namespace=namespace, kubeconfig=<resolved dict>)`.

#### `K8sClient`

`backend.services.k8s_client.K8sClient` is what every `ClusterProvider.connect()` returns — it's
the only class a plugin needs to *return*, never subclass. Construct it as
`K8sClient(namespace=namespace, kubeconfig=kubeconfig_dict_or_None)`:
- `kubeconfig=None` — auto-detect (in-cluster config when running inside K8s, else the local
  kubeconfig); this is what `SameAsBackendClusterProvider` uses
- `kubeconfig={...}` — an already-parsed kubeconfig dict, loaded via
  `kubernetes_asyncio.config.load_kube_config_from_dict`

It lazily initializes (`_ensure_initialized()`) on first API call, exposing `core_api`
(`CoreV1Api`) and `batch_api` (`BatchV1Api`) plus higher-level async methods used by the job
orchestrator: `create_job`, `delete_job`, `get_job_status`, `get_pod_for_job`,
`stream_pod_logs`/`get_pod_logs`, `get_pod_events`/`get_job_events`, `get_job_error_status`/
`get_pod_error_status`, `get_cluster_queue_limits` (reads a Kueue `ClusterQueue`'s CPU/memory
quota), and `watch_job` (an async generator yielding job status updates until a terminal state).
A plugin's `ClusterProvider` never needs to call these itself — it only needs to construct and
return the client; the host calls these methods on it.

## Storage hooks

### `select_storage`

Picks which `StorageBackend` a newly created project provisions its bucket on. Unlike
`select_clusters` (a set of allowed options), this hook picks exactly **one** answer, so it uses
the `run_first` runner: the first plugin to return a non-`None` id wins, and if none do, the
platform default is used.

- **Caller:** `backend/routers/projects.py` project-creation handler — `hooks.run_first.select_storage(default_storage_backend_id, db, user, project)`
- **Runner:** `run_first` (returns first non-`None` result, else the `default` argument)
- **Parameters:**
  - `default` (`str`) — the platform's configured default storage backend id (passed positionally before the rest)
  - `db` (`sqlalchemy.ext.asyncio.AsyncSession`) — active database session
  - `user` (`backend.models.User`) — the user creating the project
  - `project` (`backend.models.Project`) — the new project (already flushed, has an `id`, not yet committed)
- **Returns:** `str | None` — a `StorageBackend.id`, or `None` to defer to the next plugin / the default

```python
def select_storage(default, db, user, project):
    if user.billing_account and user.billing_account.plan == "enterprise":
        return "dedicated-backend-id"
    return None  # defer to the platform default
```

### `storage_protocol_handlers`

Registers `StorageProtocolHandler` implementations for `StorageBackend.protocol` values (e.g.
`minio`, `gcs`, `s3`). Core registers its own built-in handlers through this exact same hook (see
the host's root `setup.py`) — a plugin adding a new protocol (e.g. Azure) uses the identical
channel core does, with no "core is special" path.

- **Caller:** `backend/services/storage_protocols/__init__.py` `get_protocol_handler()` — `hooks.run.storage_protocol_handlers()`
- **Runner:** `run` (synchronous)
- **Parameters:** none
- **Returns:** `list[tuple[str, type]]` — `(protocol, StorageProtocolHandlerSubclass)` pairs. A duplicate `protocol` across plugins raises `ValueError`.

#### The `StorageBackend` row

Each admin-configured storage backend is a `StorageBackend` row (`backend/models/storage_backend.py`).
The fields a `StorageProtocolHandler` cares about:
- `protocol` (`str`) — the discriminator dispatched to `get_protocol_handler()`; this is the key you register under
- `endpoint` (`str | None`) — service URL (e.g. a MinIO endpoint); typically empty for real cloud protocols that resolve endpoints implicitly (GCS/S3 SDKs)
- `bucket_prefix` (`str`) — prefix used to derive a per-project bucket/container name
- `credential_strategy` (`str`, default `static-key`) — which `CredentialStrategy` (`backend/services/storage_credentials.py`) mints project credentials; `static-key` persists what `provision()` returns, other strategies call `mint()` per use
- `config` (`dict`, JSON column) — opaque, protocol-specific connection config (e.g. MinIO admin access/secret key); the admin UI's matching [`storage_protocol_forms`](frontend-hooks.md#storage_protocol_forms) entry is what edits this

#### `StorageProtocolHandler` base class

`backend.services.storage_protocols.StorageProtocolHandler` — subclass this and register an
instance's class via `storage_protocol_handlers`. All three methods are **required** (no
defaults — protocols are too different from each other for a shared implementation, unlike
`ClusterProvider.test_connection`):

- `provision(project, backend) -> dict` (sync) — one-time setup at project creation: bucket /
  service-account / policy creation. Returns credentials to persist for `static-key` use, or `{}`
  if this protocol never persists a long-lived credential.
- `mint(project, backend) -> dict` (sync) — mint a fresh credential on demand:
  `{"credentials": {...}, "expires_at": datetime | None}`. Only called for backends using a
  non-`static-key` credential strategy.
- `test_connection(backend) -> None` (async) — validate connectivity/credentials only, no side
  effects; safe to call repeatedly from the admin UI before any project exists to provision for.

```python
from backend.services.storage_protocols import StorageProtocolHandler

class AzureProtocolHandler(StorageProtocolHandler):
    def provision(self, project, backend) -> dict:
        # backend.endpoint / backend.bucket_prefix / backend.config are this row's fields —
        # read connection config from backend.config, never from global settings, so every
        # admin-added backend of this protocol is provisioned identically
        return create_container_and_credentials(
            project.id, backend.bucket_prefix, backend.config["account_key"],
        )

    def mint(self, project, backend) -> dict:
        raise NotImplementedError("short-lived Azure SAS token minting not implemented yet")

    async def test_connection(self, backend) -> None:
        client = get_azure_client(backend.endpoint, backend.config["account_key"])
        await asyncio.to_thread(lambda: client.list_containers())

def storage_protocol_handlers():
    return [("azure", AzureProtocolHandler)]
```

This mirrors the built-in `MinioProtocolHandler` (`backend/services/storage_protocols/minio.py`)
almost exactly — reading connection config from `backend.config` (never from global settings) is
the load-bearing convention: it's what lets an admin register multiple backends of the same
protocol (e.g. two separate MinIO clusters) and have each provision independently.

There is no shared "storage client" class analogous to `K8sClient` — each protocol handler talks
to its own SDK directly (e.g. `minio.Minio`, `google.cloud.storage`) inside `provision()`/`mint()`/
`test_connection()`; only the four-method `StorageProtocolHandler` shape is standardized.
