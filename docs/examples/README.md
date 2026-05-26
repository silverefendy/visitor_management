# Deployment examples

## `sync_vms.sh.example`

Portable template for post-deploy cache clear and bench restart.

The repository root `sync_vms.sh` is **machine-specific** (hardcoded bench and site). Prefer:

1. Copy `sync_vms.sh.example` to a local script outside git, or
2. Set `BENCH_ROOT` and `SITE_NAME` as in the example and run from CI/CD.

Do not commit site names or server paths into the main branch.

## Android scanner default server

The `android-vms-scanner` app stores the Frappe base URL in the **Server URL** field on device (SharedPreferences). Configure per environment after install; do not rely on a fixed IP in source control.
