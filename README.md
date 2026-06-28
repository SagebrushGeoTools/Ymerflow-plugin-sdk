# ymerflow-plugin-sdk

The SDK for authoring **Ymerflow** frontend plugins. It ships two coupled halves from one repo:

| Half | Path | Published as | Purpose |
|------|------|--------------|---------|
| Python build harness | `ymerflow_plugin_build/` (repo root) | pip, via git URL | Resolves an npm `name@version` and runs the real `npm`/`vite` Module-Federation build with `shared` pinned to the host's singleton versions. |
| npm authoring SDK | `js/` | npm: `ymerflow-plugin-sdk` | The `registerHook`/`hooks`/`useHook` shim + the Vite federation preset (`ymerflow-plugin-sdk/vite-preset`). |

The two halves emit the **same** Module-Federation `shared` block; `tests/test_vite_preset_consistency.py`
asserts they never drift apart.

## Consuming it

**Python (from another `setup.py`):**

```python
install_requires=[
    "ymerflow-plugin-build @ git+ssh://git@github.com/SagebrushGeoTools/Ymerflow-plugin-sdk.git",
]
```

or directly: `pip install "git+ssh://git@github.com/SagebrushGeoTools/Ymerflow-plugin-sdk.git"`

CLI / in-process build:

```bash
python -m ymerflow_plugin_build <npm_name> <version> <out_dir> --source <npm_source_dir>
```

```python
from ymerflow_plugin_build import build_frontend
build_frontend(npm_name, npm_version, out_dir, npm_source_dir=src)
```

**JavaScript (plugin author):**

```jsonc
// package.json
"devDependencies": { "ymerflow-plugin-sdk": "^1.0.0" }
```

```js
import { registerHook } from 'ymerflow-plugin-sdk'
registerHook('widgets', () => [{ name: 'MyWidget', component: MyWidget }])
```

## Host-contract names (intentionally NOT `ymerflow`-prefixed)

These are the runtime bridge / marker names shared with the host app and the build pipeline. They are
**deliberately left on their original `nagelfluh`/`NAGELFLUH` spelling** so the host frontend and the
running cluster keep working; renaming them would be a breaking change, not an SDK rebrand:

- `window.__nagelfluh_registerHook`, `window.__nagelfluh_hooks` — the host window bridge.
- `nagelfluh.remoteName` — the package.json key a plugin uses to declare its MF remote name.
- `NAGELFLUH_SHARED_VERSIONS` — env var the host injects with its shared-singleton versions.

## Documentation

- **[Plugin Author Guide](docs/README.md)** — overview of the plugin system and delivery mechanisms
- **[Authoring a plugin](docs/authoring.md)** — file structure, `package.json`, and the `src/index.js` entry point
- **[Frontend hooks](docs/frontend-hooks.md)** — complete reference of frontend hook points (`widgets`, `dataset_types`, `layer_types`, …)
- **[Backend hooks](docs/backend-hooks.md)** — complete reference of backend Python entry-point hooks
- **[Distributing & building](docs/distributing.md)** — publishing and serving plugins

## Tests

```bash
python tests/test_vite_preset_consistency.py   # requires node on PATH
```

## License

MIT
