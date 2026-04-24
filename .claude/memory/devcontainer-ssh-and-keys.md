# Dev Containers — SSH Agent Forwarding & Key Loading

## SSH Agent Forwarding

- VS Code automatically forwards the host SSH agent into the container via `SSH_AUTH_SOCK` pointing to a socket at `/tmp/vscode-ssh-auth-<uuid>.sock`
- This happens implicitly — no devcontainer.json config needed
- To disable: set `SSH_AUTH_SOCK` in `containerEnv` to a fixed internal path, which overrides VS Code's injected value
- To replace with a container-internal agent: start `ssh-agent -a <fixed-socket-path>` in a startup script

## SSH Key Loading (Container-Internal Agent)

- Mount the private key from host at a neutral path (e.g. `/run/credentials/gh_claude_ed25519`) as `readonly`
- In a startup script (running as `node`, not root): copy to `/tmp`, `chmod 600`, `ssh-add`, delete temp copy
- Add `github.com` to `known_hosts` via `ssh-keyscan -H github.com`
- `ssh-agent` must bind to the fixed socket path set in `containerEnv.SSH_AUTH_SOCK`
