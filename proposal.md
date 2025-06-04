# PCM-Ops Tools Repository Reorganization Proposal

## 1. High-level goals

- Cleanly separate "framework / core" code from "individual tools"
- Allow multiple cloud providers and multiple tools per provider
- Keep tests, seeds, Docker, etc. in predictable places
- Minimise import-path churn and make packaging/distribution easy

## 2. Suggested top-level layout

```tree
pcm_ops_tools/                (repo root)
├── backend/                  (Python, FastAPI, DB, core libs)
│   ├── core/                 (cloud-agnostic helpers, auth, models)
│   ├── providers/
│   │   ├── aws/
│   │   │   ├── __init__.py
│   │   │   ├── common/         (shared AWS utilities like STS, credential caching)
│   │   │   ├── script_runner/   (AWSScriptRunner "tool #1")
│   │   │   ├── ec2_inventory/  (future tool)
│   │   │   └── …               
│   │   ├── azure/
│   │   │   └── …               (future)
│   │   ├── gcp/
│   │   │   └── …               (future)
│   │   └── servicenow/
│   │       └── …               (future CMDB integrations)
│   ├── api/                   (FastAPI routers)
│   ├── db/
│   │   ├── models/
│   │   ├── seeds/
│   │   └── migrations/
│   └── tests/
├── frontend/                  (Streamlit/NiceGUI or alternative)
├── infra/                     (IaC, Dockerfiles, k8s manifests)
└── docs/
```

### Key points

- `providers/*` houses **provider-specific** utils + tools (AWS, Azure, GCP, ServiceNow, etc.)
- Each tool lives in its own subpackage so it can register routes, seeds, CLI, etc. without polluting others
- `core/*` holds anything provider-agnostic (generic auth/session helpers, base schemas, execution-state machinery, logging, config loader, etc.)
- `api/*` imports routers from tools (dynamic discovery or explicit include list) with each tool defining its own API prefix (`/tools/aws/script-runner/...`)
- `tests/*` mirrors package layout (e.g. `tests/providers/aws/script_runner/…`)

## 3. Packaging / imports

- Turn backend into an installable package (`pcm_ops_tools_backend`) via `pyproject.toml`
- Use namespace packages inside `providers`, e.g.:

```python
# backend/providers/aws/__init__.py
from importlib import import_module
from pkgutil import iter_modules

# auto-import all tool subpackages so they can register themselves
for mod in iter_modules(__path__):
    import_module(f"{__name__}.{mod.name}")
```

Each tool can expose:

```python
# backend/providers/aws/script_runner/__init__.py
from .routes import router
from .db_seeds import seed_funcs
```

FastAPI or Alembic can then discover and mount these automatically.

## 4. Migration steps

1. Create the directory scaffolding above (you're already on `directory_reorg` branch)
2. Move existing FastAPI code that is generic into `backend/core`
3. Move AWSScriptRunner assets into `backend/providers/aws/script_runner`
4. Update imports (search-and-replace `app.services.aws...` → `backend.providers.aws.script_runner.services...`, etc.)
5. Adjust tests paths accordingly
6. Add `__init__.py` files to new packages
7. Update poetry/requirements and Dockerfiles to reflect new entrypoints
8. Run tests and fix import breakages

## 5. Decisions

1. **Naming**: We will use `providers/*` as the directory structure for cloud and service providers.
2. **API Structure**: Each tool will define its own API prefix (`/tools/aws/script-runner/...`).
3. **Shared Helpers**: Cross-tool shared AWS helpers (STS, credential caching) will be kept in `providers/aws/common`.
4. **Additional Providers**: Near-term non-AWS integrations will include Azure, GCP, and ServiceNow (for CMDB integration).
