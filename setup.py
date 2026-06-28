"""ymerflow-plugin-build — the shared frontend-plugin build harness (Python half of the SDK).

This is the standalone, dependency-free (stdlib only) build routine that resolves an npm
``name@version`` from a server-local source dir and/or the public npm registry and runs the real
``npm``/``vite`` Module-Federation build with ``shared`` pinned to the host's singleton versions.

It is consumed via a git URL from other projects' ``setup.py`` files, e.g.::

    install_requires=[
        "ymerflow-plugin-build @ git+ssh://git@github.com/SagebrushGeoTools/Ymerflow-plugin-sdk.git",
    ]

The npm half of the SDK (the ``registerHook`` shim + the Vite federation preset) lives alongside
this package under ``js/`` and is published separately to npm as ``ymerflow-plugin-sdk``.
"""

from setuptools import setup, find_packages

setup(
    name="ymerflow-plugin-build",
    version="0.1.0",
    description="Shared frontend-plugin build harness for Ymerflow (Module-Federation remotes).",
    packages=find_packages(include=["ymerflow_plugin_build", "ymerflow_plugin_build.*"]),
    python_requires=">=3.9",
    # Intentionally dependency-free: stdlib only, so it imports cleanly in a Kubernetes runner pod,
    # a backend plugin's build_py step, and local tests alike. npm/vite are invoked as subprocesses.
)
