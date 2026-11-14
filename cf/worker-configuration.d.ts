interface Env {
    PYNE_API: DurableObjectNamespace<import("./src/index").PyneApiContainer>;
    ENVIRONMENT: string;
    /** Worker secret. Forwarded into the container at start. Optional. */
    ADMIN_TOKEN?: string;
}
