# bluetape-observability

Opt-in OpenTelemetry API adapters for Bluetape resilience and Redis observer events.

Install this focused distribution directly. It is not part of the default `bluetape`
installation. The package uses caller-owned OpenTelemetry providers and lifecycle; it does not
configure an SDK, exporter, worker, or shutdown hook.
