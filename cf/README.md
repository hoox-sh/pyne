# PYNE Pro API on Cloudflare Containers

Production Flask/gunicorn API (`Dockerfile` target `api`) behind a Worker.

```bash
cd cf
npm install
npm run deploy
# optional:
# npx wrangler secret put ADMIN_TOKEN
```

Worker: `https://pyne-api-container.<account>.workers.dev`  
Health: `/` and `/health` (proxied into the container).  
Worker-only ready check: `/__cf/ready`.

`standard-2` (1 vCPU / 6 GiB). Named instance `api` keeps the IR cache warm.
Set `?instance=` to address another instance (max 2).
