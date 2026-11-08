# DigitalOcean deployment package

**Prepared only. Not executed.** The sole intended target is the user's existing `vaultstorage-pilot` DigitalOcean droplet. No alternative hosting is provisioned. This package does not connect to, alter, restart or replace any existing integration or service.

Latest November 6 checkpoint: the focused Linux amd64 container release proof passed, the base/application image digests are pinned, and an offline image plus source/configuration package is prepared locally. Fresh read only preflight passed with 1.7 GiB available RAM, 60 GiB free disk and 19 existing containers. Follow the updated [exact initial hosting and rollback plan](../deploy/live.cx83labs.com/README.md) rather than the historical build commands below. No full suite was repeated. Initial hosting is proposed with synthetic records only until encrypted backup storage/key custody is chosen. Standalone Oura and MyFitnessPal are already independent server services; this dashboard does not use their credentials or control their startup.

The approved hostname for preparation is `live.cx83labs.com`. See [exact proposed changes](../deploy/live.cx83labs.com/README.md) and `DEPLOYMENT_PREFLIGHT.md` for the successful November 6 read only inspection. Deployment remains deferred.

## Deliberate isolation

Use `/opt/personal-health-dashboard` as a distinct source/configuration directory. Compose project `personal-health-dashboard` owns a separate application container, bridge network and persistent volume. Do not join the existing Coolify network or reuse business volumes, environment files, database credentials, OAuth registrations or client tokens. Health data never belongs in business agent messages.

The application port is bound only to `127.0.0.1:18170`. There are no automatic proxy labels, public bindings or migrations in container startup. Default MCP writes remain disabled. The container runs as UID 10001, drops Linux capabilities, uses a read only root filesystem, and has limited temporary space and resources. These controls are authored, not verified by a container run.

The memory/CPU limits are initial safeguards requiring a synthetic workload test, not a capacity guarantee. Confirm port 18170 is free with the read-only preflight. Sharing the host provides logical, not physical isolation.

## Gates before executing

1. Obtain explicit deployment authorization and verify the current session can access the existing droplet. The authorized November 6 read only preflight succeeded. This does not authorize remote changes.
2. Run `scripts/server_preflight.sh` on the target read only. Confirm disk, existing ports, Docker/Compose versions and available resources. Preserve a baseline of existing container names/status without logging their secrets.
3. Preserve the existing hash locked dependencies and repeat the advisory and installation checks on the intended platform. All 41 locked dependencies passed the local November 6 audit. The Docker build intentionally requires the lock and cannot silently fall back to broad package resolution.
4. Run domain, Django and real HTTP MCP tests against an isolated synthetic database. Run model/migration consistency checks. Pin the Python image digest after verifying the image and compatibility. Test Docker build and resource usage.
5. Choose and authorize the personal hostname and exact TLS/reverse proxy route. Existing proxy files are not changed by this package. Do not enable `DASHBOARD_TRUST_PROXY` until the selected proxy removes untrusted incoming forwarded headers and the backend is reachable only through the intended path. Test that HTTPS does not redirect in a loop.
6. Create a dedicated `.env` using `scripts/prepare_env.py --hostname <approved-hostname>`. Add `--builtin-oauth` to configure the implemented personal issuer at that HTTPS origin, with writes disabled. This script refuses to overwrite any existing file and prints no secret. Keep it mode 600. Follow `MCP_SETUP.md` and verify actual ChatGPT account consent independently of existing connections.
7. Explicitly authorize the first persistent schema migration and proxy change. Run migrations as a deliberate command, not on startup; create the owner account interactively. Confirm owner account matches `OWNER_USERNAME`.
8. Complete browser to database to authenticated MCP verification, retries and restart. Verify actual ChatGPT access separately. iPhone install and desktop rendering must be checked on the HTTPS deployment.

## Prepared container commands

These are instructions, not an execution log. Do not run them until the gates above are satisfied.

```sh
docker compose build
docker compose run --rm app python manage.py check --deploy
# Explicitly authorized schema creation:
docker compose run --rm app python manage.py migrate
docker compose run --rm app python manage.py createsuperuser --username owner
docker compose up -d app
```

The command uses `owner` only if that is the chosen configured account. Uvicorn access logs are disabled. Configure only the correct trusted forwarding boundary for the approved deployment. A proxy route on an existing shared server is an independent authorized change, not implied by running Compose.

## Preservation and rollback

Do not stop any existing containers. Before updating this application, retain the previous image and test an encrypted data backup/restore. Stop or replace only this application's container if a smoke test fails. Never use `docker compose down -v` as routine rollback; it would destroy the personal history volume. Schema rollback must be planned against the actual migration and backup, not improvised.

Encrypted application backups, usable exports and a synthetic restic restore proof are implemented. Select and verify the real destination/key custody before scheduling them; see `OPERATIONS.md`. Existing weekly DigitalOcean snapshots do not replace the application's encrypted backup/restore procedure.
