import { Container } from "@cloudflare/containers";

/**
 * Production PYNE Pro API (gunicorn) on Cloudflare Containers.
 * Stateless evaluate — one named instance keeps the IR cache warm.
 */
export class PyneApiContainer extends Container<Env> {
    defaultPort = 8080;
    requiredPorts = [8080];
    sleepAfter = "10m";
    enableInternet = true;
    // Container class requests `http://${pingEndpoint}`. A leading slash becomes
    // `http:///health`, which never hits Flask. Host + path, same as the docs.
    pingEndpoint = "localhost/health";
    envVars: Record<string, string> = {
        HOST: "0.0.0.0",
        PORT: "8080",
        FLASK_ENV: "production",
        FLASK_DEBUG: "0",
        PYNE_COMPILE_PREWARM: "0",
        // Match docker/entrypoint-api.sh and docker-compose.prod.yml. gthread is
        // required for flask-sock (gunicorn.socket). One worker: session state is
        // in-process. Threads stay high because each live WebSocket holds one.
        GUNICORN_WORKERS: "1",
        GUNICORN_WORKER_CLASS: "gthread",
        GUNICORN_THREADS: "100",
        GUNICORN_TIMEOUT: "120",
        GUNICORN_MAX_REQUESTS: "5000",
        GUNICORN_MAX_REQUESTS_JITTER: "200",
        FREE_TIER_LIMITS: "1",
        STORE_BACKEND: "sqlite",
        PYTHONPATH: "/app/src:/app",
        // Optional hosted runner: set PYNE_RUNNER=1 (and PYNE_RUNNER_SCHEDULER=1)
        // via wrangler vars / secrets. Off by default — container stays evaluate-only.
        PYNE_RUNNER: "0",
        PYNE_RUNNER_SCHEDULER: "0",
        PYNE_RUNNER_DB: "/data/runner.db",
    };

    constructor(ctx: ConstructorParameters<typeof Container>[0], env: Env) {
        super(ctx, env);
        // Worker secrets are not injected into the container process. Forward the
        // admin token at instance start so Flask sees the same ADMIN_TOKEN.
        const admin = env.ADMIN_TOKEN?.trim();
        if (admin) {
            this.envVars = { ...this.envVars, ADMIN_TOKEN: admin };
        }
    }

    override onStart(): void {
        console.log("pyne-api container started");
    }

    override onStop(params: { exitCode?: number; reason?: string }): void {
        console.log(
            "pyne-api container stopped",
            params.exitCode,
            params.reason,
        );
    }

    override onError(error: unknown): void {
        console.error("pyne-api container error", error);
        throw error;
    }
}

export default {
    async fetch(request: Request, env: Env): Promise<Response> {
        const url = new URL(request.url);
        if (url.pathname === "/__cf/ready") {
            return Response.json({ ok: true, service: "pyne-api-container" });
        }
        const name = url.searchParams.get("instance") || "api";
        const container = env.PYNE_API.getByName(name);
        return container.fetch(request);
    },
};
