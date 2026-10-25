# docs/pyne/devops

# Concepts

* [Continuous integration](ci.md) - GitHub Actions for lint, Python 3.10–3.13 tests, package build, Docker api+cli smoke, and VS Code extension.
* [Docker](docker.md) - Buildx multi-target images and Compose profiles for the PYNE Pro API.
* [DevOps](index.md) - CI matrices, containers, Nuitka LSP binaries, metadata crypto, and operational invariants for PYNE.
* [Local development](local-dev.md) - Install, test, lint, package, and run PYNE — Make targets after AXIS extraction.
* [Metadata encryption](metadata-crypto.md) - Fernet-encrypted LSP builtinmetadata.json — key lifecycle, CI secrets, integrity hashes, and runtime decrypt.
* [Nuitka build (LSP + CLI)](nuitka-build.md) - Compile pyne-lsp and pyne CLI with Nuitka — onefile vs standalone, CI build script, Anaconda quirks, and artifact layout.
* [Observability](observability.md) - PYNEDEBUG logging, GET /stats runtime counters, health endpoints, gunicorn process model, Cloud Logging, and operational signals.
* [Release](release.md) - Tag-driven CLI + LSP multi-platform Nuitka binaries, wheels, Docker CLI image, VSIX packaging, GitHub Releases, and Marketplace publish.
* [Security](security.md) - API keys, CORS, body limits, secrets hygiene, Fernet metadata keys, and threat-aware defaults for PYNE ops.
