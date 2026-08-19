interface Env {
  PYNE_API: DurableObjectNamespace<import("./src/index").PyneApiContainer>;
  ENVIRONMENT: string;
}
