# Dev Containers — Implicit VS Code Behavior & Docker Defaults

## VS Code Dev Containers Implicit Behavior

VS Code injects these automatically; none require devcontainer.json config:

- `SSH_AUTH_SOCK` — SSH agent socket forwarded from host
- `REMOTE_CONTAINERS_IPC` — VS Code IPC socket for host communication
- `DEVCONTAINER=true`, `REMOTE_CONTAINERS=true` — environment markers
- `GIT_EDITOR=true` — suppresses interactive git editor prompts
- `/vscode` mount — VS Code server binaries

## Docker Default Capabilities

Docker grants these capabilities by default (beyond what devcontainer.json `runArgs` adds):
`CAP_CHOWN`, `CAP_DAC_OVERRIDE`, `CAP_FOWNER`, `CAP_FSETID`, `CAP_KILL`, `CAP_SETGID`, `CAP_SETUID`, `CAP_SETPCAP`, `CAP_NET_BIND_SERVICE`, `CAP_SYS_CHROOT`, `CAP_MKNOD`, `CAP_AUDIT_WRITE`, `CAP_SETFCAP`

These are implicit — not listed in devcontainer.json.

## Container Shutdown on VS Code Disconnect

- `"shutdownAction": "stopContainer"` in devcontainer.json should stop the container on disconnect
- Only reliably triggered via Command Palette → "Remote: Close Remote Connection", not by just closing the VS Code window
- VS Code user setting `"dev.containers.stopContainers": "always"` is more reliable but must be set manually on the host (cannot be set via devcontainer.json)
- Requires container recreation (Rebuild Container) to take effect after being added to devcontainer.json

## postStartCommand vs postAttachCommand

- `postStartCommand` runs before `waitFor` and before `postAttachCommand`
- Use `postStartCommand` for infrastructure setup (firewall, SSH agent, file copies)
- Use `postAttachCommand` for the main interactive process (e.g. `claude`)
- `waitFor: "postStartCommand"` ensures postStartCommand completes before postAttachCommand runs

## Firewall and iptables in Containers

- `--cap-add=NET_ADMIN` and `--cap-add=NET_RAW` are required in `runArgs` for iptables
- A blanket `iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT` rule added before the DROP policy allows ALL HTTPS outbound, making per-domain ipset rules redundant for HTTPS traffic
- Domain-specific ipset rules are still needed for non-HTTPS protocols or for explicit allowlisting
- iptables rules are kernel-level and scoped to the running container's network namespace — they are NOT persistent filesystem state and cannot be applied during `docker build`. They must be re-applied on every container start via `postStartCommand`

## /workspace is a VS Code Convention

`/workspace` is not a Docker or Claude standard — it is the VS Code Dev Containers default mount target. Docker has no concept of a workspace directory. Without an explicit `workspaceMount`, VS Code mounts the repo at `/workspaces/<repo-name>`. An explicit `workspaceMount` targeting `/workspace` gives a predictable, name-independent path.
