# hoox-pyne-backend

PYNE Pro API backend (Flask) packaged as a standalone wheel.

```bash
pip install hoox-pyne-backend
pyne-backend                 # or: python -m backend / python -m backend.app
```

Environment:

| Var | Default | Meaning |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` to expose) |
| `PORT` | `5002` | HTTP port |
| `ADMIN_TOKEN` | unset | Required for `POST /auth/create_key` (fail-closed) |
| `STORE_BACKEND` | `json` | `json` / `sqlite` / `redis` key store |

The backend depends on `hoox-pyne[pro]` (Flask, gunicorn, gevent, numpy/numba,
matplotlib, redis). The parser/LSP live in the base `hoox-pyne` package; the
`[lsp]` extra adds `pygls`/`lsprotocol`.

This wheel packages the repo's `backend/` directory. Build it from a checkout:

```bash
python -m build --wheel packages/backend
# or: make build-backend-wheel
```
