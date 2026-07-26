# Legacy static shell (pre-Solid)

The AXIS product path is:

```text
bun run dev          → Vite + Solid (`src/index.tsx`)
bun run build        → `dist/` served by `axis_pwa_server.py` / CF Pages
```

## What is legacy

| Path | Role |
|------|------|
| `src/main.js` | Old bootstrap (chart.js, topbar.js, …) |
| `style.css` | TV-blue-era tokens |
| `pine-editor.js` | Pre-Solid CM6 wiring |
| `server.ts` | Bun static server for the old tree |
| Root `sw.js` | Service worker for static shell |

## What is current

| Path | Role |
|------|------|
| `src/index.tsx` / `src/app.tsx` | Solid app |
| `src/chart/ChartHost.tsx` | LWC panes (imperative container split from Solid) |
| `src/ui/*` | Topbar, Settings, Results, Logs, … |
| `public/` + `bun run build` | Production PWA assets |

Legacy files remain so `bun test` (static server) and historical scripts keep
working. They are not the shipping UI.
