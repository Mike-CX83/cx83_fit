# Deployment preflight

Status updated November 6, 2026: Mike authorized and the existing script completed the read only inspection at 2026-11-06T12:54:54Z, exit 0. Target: established `vaultstorage-pilot`, `157.245.247.90`. Available RAM 1.8 GiB, swap use 1 GiB, available disk 61 GiB, inode use 5%, 19 running containers. Proposed application path/account and port 18170 were unused at inspection. No services, credentials or configuration were changed. This supersedes the historical SSH permission failure; it is not a capacity guarantee or deployment approval.

Mike selected `live.cx83labs.com` for preparation. The exact unexecuted topology and routing proposal is in `../deploy/live.cx83labs.com/README.md`, with Compose and Traefik files. The existing bridge based proxy requires a dedicated ingress network attachment, which is explicitly part of the later approval. Local merged Compose parsing passed using synthetic environment values. DNS, TLS, runtime testing and proxy network attachment persistence remain pending.

## Read-only inspection

After the intended host and SSH access have been explicitly authorized, run the committed script from an authorized administrator terminal. Replace `AUTHORIZED_SSH_HOST` with the verified host alias or destination. Do not paste private keys, tokens or passwords into a command or report.

```sh
ssh AUTHORIZED_SSH_HOST 'bash -s' < scripts/server_preflight.sh
```

The script uses the existing SSH session and prints only an explicit set of inspection fields. It does not create a remote file. It does not use `sudo`, install packages, start or stop containers, modify a firewall, bind a port, change a proxy, read application secrets, print environment variables or change Docker contexts. Docker commands target the local Unix socket explicitly, avoiding accidental inspection of a configured remote Docker context.

It checks kernel/platform, uptime/load, available memory, filesystem bytes and inodes for `/opt`, the intended application path and account, current TCP listeners on port `18170`, local Docker availability, running container names and published ports, configured resource limits, and a single usage snapshot. Docker resource limits of zero generally mean no explicit constraint. A free port is not reserved by the inspection.

Exit code `0` means that the implemented checks completed without unknowns or flagged review items. It is not a deployment approval. Exit code `2` means a check was unavailable or an item needs review. A preexisting application directory or account deliberately requires review; never overwrite or reuse it automatically. If Docker access is denied, use an appropriately authorized administrative session later rather than changing permissions from this script.

## Intended separation

| Component | Proposed dedicated boundary | Verification before deployment |
| --- | --- | --- |
| Source and configuration | `/opt/personal-health-dashboard` | Confirm destination is unused or belongs to this exact project; inspect permissions before copying |
| Service account | `personal-health-dashboard` | Confirm UID/GID and dedicated ownership; no inherited business application credentials |
| Compose project | `personal-health-dashboard` | Confirm no name collision; review the resolved service definition without exposing secrets |
| Database | One private SQLite file in a dedicated application volume | Dedicated owner, restricted permissions, persistent mount and tested restart behavior |
| Photos and backups | Dedicated private storage and separately protected encrypted backup destination | No public media path; verify access controls and isolated restore before real data |
| Network | Dedicated application network; host binding `127.0.0.1:18170` only | Confirm free TCP port immediately before launch; no host networking or joining business networks |
| Credentials | New application session secret and dedicated OAuth registration | Do not borrow business app keys, mailbox tokens or database credentials |
| Public access | Separate approved HTTPS route | Any domain, reverse proxy or firewall change requires explicit authorization and a reviewed configuration change |

Sharing the droplet provides logical separation, not complete physical isolation. Do not connect the application to the CX83 business mailbox. No personal health records, photos, credentials or source data belong in business coordination messages.

## Required decisions after inspection

1. Record the actual host identity, inspection time, relevant existing services and resource measurements in a private deployment record. Container names and ports may reveal infrastructure details; retain the report privately.
2. Check sustained memory, CPU and disk headroom against representative synthetic application use. The console snapshot alone cannot support a zero-cost or capacity claim. Confirm backup disk headroom and retention as well as application storage.
3. Verify the chosen Python and Docker runtime compatibility. Resolve and audit dependencies, run Django deployment checks, and complete the browser, MCP and persistence test loop before production placement.
4. Review a dedicated deployment definition with bounded CPU, memory and process limits. Choose limits from measurements; do not impose untested values or alter existing containers.
5. Obtain authorization for the exact new deployment and any required domain, reverse proxy, firewall or production migration changes. The read-only script is not permission for those changes.
6. Following authorization, verify loopback binding, HTTPS, owner login, scoped MCP access, private records, restart persistence, usable export and an encrypted backup restored into an isolated test location. Stop and correct failures before importing personal history.

No Docker daemon, container, service, volume, network, account, database, domain or proxy was changed during preparation of these files.
