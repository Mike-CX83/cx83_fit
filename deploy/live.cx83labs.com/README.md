# Prepared deployment for live.cx83labs.com

**Prepared for approval. Nothing deployed.** Mike authorized local release preparation and read only server inspection, with focused tests. Initial hosting uses synthetic health records until the first native server backup and recovery-key custody are verified. Oura ingestion and MCP writes stay disabled. The hostname is `live.cx83labs.com`; it was unresolved at the last read only check. Do not submit dashboard Oura registration as though the pages are live.

Backup update, November 7: **CX83 Labs Google Workspace Drive is authorized and verified as `mike@cx83labs.com`. One actual encrypted synthetic upload and isolated restore passed from the Mac.** Three files, database integrity/counts and restored application queries matched; wrong passwords and tampering were rejected. No real health data was uploaded. `compose.backup.yaml` and the proposed `personal-health-backup.service`/`.timer` are prepared but not installed. The current supplement is `dashboard-drive-backup-verified-20261107.tar.gz`, separate from the original immutable application image/source archives; it includes the corrected importer, three passing credential regression tests, verification evidence and verified Linux tools. Earlier supplements are preserved but superseded. Credentials are excluded from every archive. See `../../docs/OPERATIONS.md` for setup, key custody, Internal audience and scheduling. The production repository remains uninitialized. No standalone provider tokens are reused.

## Tested release

The pinned Python 3.12 Linux amd64 image built using the existing hash locked dependencies. The focused Compose/Traefik TLS smoke passed password/CSRF login, secure cookies, anonymous denial, forwarded-header replacement, static/policy responses, a synthetic browser write and identical retry, and persistence of the record and browser session after container restart. Twelve reads at concurrency two passed; observed memory was 99.07 MiB under the 384 MiB limit. The read only root, dropped capabilities, private file permissions and resource limits were verified. Linux `pip check` passed. No full suite or sustained load benchmark was repeated. See `../../docs/evidence/container-release.json`.

The application image identity is `sha256:67f557de8420e512fdda94ffcc80c260677843a6e0245aa8d90d5b3adf956ee1`. `compose.release.yaml` selects that exact tested image with pulling disabled. The ignored local `output/deploy/` contains its offline image archive, configuration/source archive and `SHA256SUMS`. Loading that image avoids a production build or dependency download. No real database, secret or photo is in either archive. The archive/source checksum is the release identity while local changes remain uncommitted.

## Verified read only target

`vaultstorage-pilot`, `157.245.247.90`, Linux x86_64, Docker 29.8.1. The existing script completed again at 2026-11-06T20:14:46Z with exit 0, no unknown checks and no flagged items. Snapshot: 1.7 GiB available RAM, 1 GiB swap used, 60 GiB disk available, 5% inodes used, 19 running containers. `/opt/personal-health-dashboard`, the dedicated host account and TCP listener 18170 were absent. This is a point snapshot rather than a sustained headroom guarantee. Both independently migrated `oura-personal` and `myfitnesspal-personal` systemd units were active/enabled, with no automatic restarts. Their hosting and personal ChatGPT registrations remain separate from the dashboard.

Read only proxy inspection found `coolify-proxy`, image `traefik:v3.6`, existing networks `coolify` and `vaultstorage-pilot_default`. File provider watches `/traefik/dynamic/`, mounted from `/data/coolify/proxy/dynamic/`. Entry points are `http` and `https`; the existing ACME resolver is `letsencrypt`. The proposed route filename is absent. No full container environment, certificate store or secret file was read or copied.

## Exact change proposed for later approval

1. Add DNS A record `live.cx83labs.com` to `157.245.247.90`, after checking existing authoritative DNS and removing no unrelated record. Do not add AAAA without verified IPv6 routing.
2. Create dedicated root-owned mode 0700 source/config directory `/opt/personal-health-dashboard`, Compose project `personal-health-dashboard`, private named volume `personal-health-dashboard_personal-health-data` and resource limits. The container has its own unprivileged UID/GID 10001; it needs no host login account or Docker-group membership. Create new mode 0600 application configuration. Do not reuse a business environment or token. Initial schema creation is only in this new volume; existing local history stays intact.
3. Create Docker bridge network `personal-health-ingress`. Add it to Coolify's saved proxy configuration using the exact merge fragment `proxy-network.additions.yaml`, preserving every existing field. Save without restarting the proxy. Attach the current `coolify-proxy` to it live with `docker network connect personal-health-ingress coolify-proxy`. Only the dashboard and shared proxy join this new ingress network; the app does not join either business network. Both this saved-config change and live attachment require approval. Keep all current network attachments intact.
4. Apply the base `compose.yaml` plus this folder's override. The base host port remains `127.0.0.1:18170`; no public backend binding. Resource limits remain 384 MiB RAM, 0.75 CPU, 128 processes, read only root filesystem and 32 MiB temporary filesystem, subject to synthetic load verification.
5. Install only this folder's `traefik.yaml` at `/data/coolify/proxy/dynamic/personal-health-dashboard.yaml`. Existing watched file provider supplies the route without editing unrelated routes or restarting the proxy. Use the verified `letsencrypt` resolver. This issues a certificate only after DNS and approval.
6. Load and verify the reviewed image archive. Apply all three Compose files with `--no-build --pull never`. Run explicitly approved initial migrations only in the new dedicated volume. Create the dashboard owner interactively, keeping its password out of chat. Oura remains disabled; do not copy standalone application credentials, tokens or callback settings. MCP writes remain disabled.
7. Verify the real certificate/HTTPS origin, owner login and an authenticated ChatGPT read, followed by an app-only restart and repeated read. Check physical iPhone access with Mike. These are deployment-specific acceptance checks, not another full test suite. Use only synthetic entries initially; real records wait for recovery-key custody and the first successful native server backup. The off-server destination and its synthetic restore are already verified.
8. Install only the new dashboard backup tools/configuration and the two proposed systemd files described below. Securely transfer the dedicated Workspace rclone config and recovery password over the established SSH connection with no secret output. Initialize only the new production backup repository, run the first server backup and then enable only `personal-health-backup.timer`. This adds the isolated backup egress network and scheduled one-shot container; it has no dependency that restarts the dashboard, Oura, MyFitnessPal or business services.

The current Traefik container cannot route to a host loopback port using its own `127.0.0.1`. This dedicated ingress network resolves that topology without publishing a new public port or connecting the app to a business network. Trusting forwarded headers is contingent on this boundary and Traefik replacing the upstream protocol/host headers. Confirm that boundary during runtime testing. Shared host and shared TLS termination provide logical separation only.

The persistence mechanism is Coolify's saved **Servers > target server > Proxy > Configuration**, not a disk-only Compose edit. Before merging, recheck the live configuration and preserve a private copy. At preparation, its SHA256 was `c3bcbca689a051b2a683b00eea67463a8d13c2a7b86e07481ce219599c6123ba`. The current `traefik` service lists `coolify` and `vaultstorage-pilot_default`; keep both and append `personal-health-ingress`, plus its top-level external network definition. Saving makes the addition survive a later Coolify proxy recreation; live attachment applies it without a proxy restart now. If the saved configuration cannot be accessed or preserving this delta would trigger a shared proxy restart, stop before routing and resolve that detail. Do not edit Coolify's database or generated file as a substitute. [Official Coolify configuration behavior](https://coolify.io/docs/core/networking/proxy/traefik/overview).

## Commands are a preview, not authorization

Review rendered Compose without a real `.env` using a disposable checkout and synthetic variables. On the target, after approval, all application commands must explicitly use:

```sh
docker --host unix:///var/run/docker.sock compose \
  --project-directory /opt/personal-health-dashboard \
  -p personal-health-dashboard \
  -f /opt/personal-health-dashboard/compose.yaml \
  -f /opt/personal-health-dashboard/deploy/live.cx83labs.com/compose.override.yaml \
  -f /opt/personal-health-dashboard/deploy/live.cx83labs.com/compose.release.yaml \
  config --quiet
```

After explicit approval, create `/root/health-dashboard-stage-20261106` mode 0700 only if absent and transfer the reviewed archives/checksums there. Verify SHA256SUMS before extraction or `docker image load`. Refuse an existing target path, image mismatch, route filename, ingress network or conflicting volume unless its ownership is separately established. Record the existing container IDs and personal connector unit states as a preservation baseline. Recheck current capacity and port availability. Extract `dashboard-source-config.tar.gz` into the new `/opt/personal-health-dashboard`, then apply `dashboard-drive-backup-verified-20261107.tar.gz` there to update the reviewed backup files. The supplement contains no credentials; do not restore older backup helper versions afterward.

After reviewing all earlier changes, use this exact Compose function and deliberate commands in the new target directory:

```sh
cd /opt/personal-health-dashboard
health_compose() {
  docker --host unix:///var/run/docker.sock compose \
    --project-directory /opt/personal-health-dashboard \
    -p personal-health-dashboard \
    -f /opt/personal-health-dashboard/compose.yaml \
    -f /opt/personal-health-dashboard/deploy/live.cx83labs.com/compose.override.yaml \
    -f /opt/personal-health-dashboard/deploy/live.cx83labs.com/compose.release.yaml "$@"
}
python3 scripts/prepare_env.py --hostname live.cx83labs.com --builtin-oauth
docker --host unix:///var/run/docker.sock image load --input /root/health-dashboard-stage-20261106/dashboard-linux-amd64.tar
# Verify loaded image identity against compose.release.yaml before proceeding.
health_compose config --quiet
health_compose run --rm --no-deps app python manage.py migrate --noinput
health_compose run --rm --no-deps app python manage.py createsuperuser --username owner
health_compose up -d --no-build --pull never app
```

Do not run these commands before approval or use an existing staging directory as an overwrite target. The dedicated secret is generated on the server and never printed. The new data directory is 0700 and database/files are created with umask 077. Uvicorn access logging and Django payload logging remain disabled. There is no automatic deployment script, proxy restart, host reboot or connector restart.

The post-approval boundaries still requiring real verification are public DNS/TLS, native host runtime/backup, actual ChatGPT owner consent/read and physical iPhone access. The shared host has finite resources; the personal smoke workload is not a promise for bulk imports or many concurrent users. Key custody remains an owner step before actual health records. The dedicated local migration test VM was used; the coursework Docker context was untouched.

## Exact proposed backup activation

This section is included in the later deployment approval, not local preparation authorization. `tools/restic` and `tools/rclone` are the verified Linux amd64 binaries installed mode 0555 by the supplement. Bind-mounted script is read only. Privately copy the existing dedicated `secrets/backup/rclone/rclone.conf` and `secrets/backup/restic-password` from the Mac over SSH, never through chat or command-line values. On the server, their credential directories are owned by UID/GID 10001, mode 0700; files are 0600. The config directory must stay writable for rclone token refresh. Retain the protected Mac copy and save the recovery password independently in the owner's password manager. No credentials are included in unit files or logs.

Using the existing exact Compose function above, define and run the first deliberate backup after the new app schema exists:

```sh
health_backup_compose() {
  health_compose -f /opt/personal-health-dashboard/deploy/live.cx83labs.com/compose.backup.yaml --profile backup "$@"
}
health_backup_compose config --quiet
health_backup_compose run --rm --no-deps --pull never backup \
  python /ops/backup.py backup --private-root /data \
  --repository rclone:health_dashboard_backup:cx83-personal-health-dashboard/restic \
  --restic /run/tools/restic --rclone /run/tools/rclone \
  --rclone-config /run/rclone/rclone.conf \
  --password-file /run/secrets/restic-password --initialize
```

Initialization refuses nonempty targets; do not adopt the synthetic proof repository as production. Capture the first snapshot ID without source data. Only after that command succeeds, verify the Docker path in the unit, install `personal-health-backup.service` and `.timer` root-owned mode 0644 under `/etc/systemd/system/`, reload systemd and enable/start **only this new timer**. Proposed time is 03:15 America/Chicago with up to 15 minutes jitter and missed-run catchup. Normal scheduled runs omit initialization. The backup container has 384 MiB RAM, 0.5 CPU and 64-process limits, a read only root and its own egress network. There is no automatic retention deletion or business service change.

Rollback first disables only `personal-health-backup.timer`, lets any active backup finish, then follows dashboard rollback below. Retain credentials and the encrypted repositories. Do not revoke this OAuth client, delete cloud files or alter standalone provider registrations as routine rollback.

## Registration URLs reserved by this design

| Field | Exact intended URL | Current state |
| --- | --- | --- |
| Website | `https://live.cx83labs.com/` | Existing authenticated dashboard root, not publicly deployed |
| Privacy policy | `https://live.cx83labs.com/privacy/` | Implemented and tested locally; not hosted |
| Terms | `https://live.cx83labs.com/terms/` | Implemented and tested locally; not hosted |
| Oura redirect | `https://live.cx83labs.com/integrations/oura/callback/` | Implemented with synthetic OAuth tests; real consent not tested |
| ChatGPT MCP | `https://live.cx83labs.com/mcp` | Existing local endpoint, not publicly deployed |

These are selected future addresses, not reachable registration prerequisites or tested callback URLs. The local policy pages, callback, encrypted storage and ingestion are implemented and tested. See `../../docs/OURA_SETUP.md`. After an explicitly authorized initial deployment, verify public pages and exact redirects before submitting registration and completing real Oura consent. Keep Oura disabled in that initial stage. After registration, the optional `compose.oura.yaml` overlay mounts the dedicated client secret and token key; its merged configuration was checked with temporary synthetic files. No real secret file was created. Both files must be readable by application UID 10001 with no group or other access. Configuration parsing does not verify target runtime mounts or TLS.

## Rollback boundary

For this first hosting only, if acceptance fails:

1. Move only the newly installed `/data/coolify/proxy/dynamic/personal-health-dashboard.yaml` into the root-only deployment evidence directory, withdrawing this hostname's route through the watched file provider. Do not restart Traefik.
2. Run `health_compose stop app` with the exact project/files above. Do not stop another container or either personal connector unit.
3. Run `docker --host unix:///var/run/docker.sock network disconnect personal-health-ingress coolify-proxy` only if this deployment added that attachment. Remove only the new network entry from Coolify's saved proxy configuration, preserving the prior configuration and both original networks. Save without restart.
4. Remove only the DNS A record created by this deployment if it still matches the recorded value and ownership. Leave unrelated records intact.
5. Retain the app volume, generated `.env`, reviewed archives and private execution evidence for recovery. First deployment needs no reverse schema migration. Confirm the original 19 container IDs/status and both connector unit states still match the baseline.

Do not run `down -v`, prune Docker resources, replace shared credentials or roll back schema. Later releases require retaining the previous image and a verified encrypted backup before migrations. Dashboard rollback never starts the stopped Mac connector runtimes.
