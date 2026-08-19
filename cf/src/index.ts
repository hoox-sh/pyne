import { Container } from "@cloudflare/containers";

/**
 * Production PYNE Pro API (gunicorn) on Cloudflare Containers.
 * Stateless evaluate — one named instance keeps the IR cache warm.
 */
export class PyneApiContainer extends Container {
  defaultPort = 8080;
  requiredPorts = [8080];
  sleepAfter = "10m";
  enableInternet = true;
  pingEndpoint = "/health";
  envVars = {
    HOST: "0.0.0.0",
    PORT: "8080",
    FLASK_ENV: "production",
    FLASK_DEBUG: "0",
    PYNE_COMPILE_PREWARM: "0",
    GUNICORN_WORKERS: "1",
    GUNICORN_THREADS: "4",
    GUNICORN_TIMEOUT: "60",
    FREE_TIER_LIMITS: "1",
    STORE_BACKEND: "sqlite",
    PYTHONPATH: "/app/src:/app",
  };

  override onStart(): void {
    console.log("pyne-api container started");
  }

  override onStop(): void {
    console.log("pyne-api container stopped");
  }

  override onError(error: unknown): void {
    console.error("pyne-api container error", error);
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
