# Distributing & Building

A plugin's source package is built and served in one of two ways. Both converge on the **same**
content-addressed frontend artifact served from `/plugin-assets/{content_hash}/…`. See the
[overview](README.md) for how the two delivery mechanisms relate.

## As a frontend plugin (built in a Process)

1. Make your package resolvable to the build. The build resolves `name@version` from a
   **server-local directory and/or the public npm registry**, controlled by
   `PLUGIN_NPM_SOURCE_MODE` (`auto` = local-first then registry; `local`; `registry`):
   - **Published to npm** (`auto`/`registry`): just `npm publish` and reference it by `name@version`.
   - **Server-local** (`auto`/`local`, for testing or air-gapped): drop a tarball in
     `PLUGIN_NPM_SOURCE_DIR`:
     ```bash
     npm pack ./my-nagelfluh-plugin       # -> skytem-nagelfluh-plugin-1.2.3.tgz
     cp skytem-nagelfluh-plugin-1.2.3.tgz "$PLUGIN_NPM_SOURCE_DIR"/
     ```
   In `auto` mode a local file overrides the registry for that exact `name@version`.

2. A user starts a build and registers it:
   ```
   POST /plugins/build  { project_id, environment_id, npm_name, npm_version }
   # poll the returned process until done, then:
   POST /plugins        { process_id, process_version, scope: "user" }
   ```
   `POST /plugins/build` runs a `build_frontend_plugin` Process; its output dataset (the built
   `dist/`) lands in the project bucket. `POST /plugins` reads the built `package.json` for
   `nagelfluh.remoteName` + `built_against`, computes a `content_hash`, and creates the
   `Plugin` + `PluginVersion` rows.

3. A user enables it: `POST /plugins/{id}/enable` pins them to the current latest version. From then
   on `GET /plugins/me` lists it with `source: "remote"` and a `base_url` of
   `/plugin-assets/{content_hash}/`, and the frontend MF-loads it at startup.

You can also build locally without a cluster (for testing) — the build routine is standalone:
```bash
python -m ymerflow_plugin_build @skytem/nagelfluh-plugin 1.2.3 ./out --source "$PLUGIN_NPM_SOURCE_DIR"
```

## As the frontend half of a backend plugin (built at `pip install`)

A backend plugin consumes **exactly the same** npm source package. Its `setup.py` builds the source
at install time via a `build_py` command that calls the shared routine and ships the result as
package data:

```python
from setuptools import setup
from setuptools.command.build_py import build_py
from ymerflow_plugin_build import build_frontend

class BuildWithFrontend(build_py):
    def run(self):
        build_frontend(npm_name='@skytem/nagelfluh-plugin', npm_version='1.2.3',
                       out_dir='my_backend_plugin/frontend_dist')
        super().run()

setup(
    name='my-backend-plugin',
    cmdclass={'build_py': BuildWithFrontend},
    package_data={'my_backend_plugin': ['frontend_dist/**/*']},
    entry_points={'nagelfluh.hooks': [
        'frontend_bundles = my_backend_plugin:frontend_bundles',
        'register_routers = my_backend_plugin:register_routers',
    ]},
)
```

The `nagelfluh.hooks` entry points are the [backend hooks](backend-hooks.md) the package provides;
`frontend_bundles` is what makes the bundled `frontend_dist/` discoverable at startup.

The running server never runs npm — the built output ships in the package and is content-addressed
and served from the identical `/plugin-assets/{content_hash}/…` path, so the frontend loads both
kinds indistinguishably.
