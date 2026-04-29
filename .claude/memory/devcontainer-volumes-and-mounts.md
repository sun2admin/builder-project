# Dev Containers — Volumes, Mounts & Ownership

## Bind Mounting Files Inside Named Volumes

- On macOS with Docker Desktop, bind mounting a single file inside a directory that is also a named volume is unreliable — the file mount may be silently ignored
- Workaround: mount sensitive files to a neutral staging path (e.g. `/run/credentials/`) outside any named volume, then copy into place via a startup script
- The staging directory must be created in the Dockerfile (`RUN mkdir -p /run/credentials`)
- Scripts that write to named volume paths must run as root (via sudo) because fresh named volumes are root-owned

## Named Volume Ownership

- When Docker creates a new named volume and mounts it over an image directory, the volume root can be root-owned even if the image directory was `chown`-ed to a non-root user
- Workaround: use a sudoers entry to allow the non-root user to run specific init scripts as root

## Docker Image Cache

- VS Code Dev Containers caches the built Docker image
- When new scripts are added to the Dockerfile via `COPY`, the cached image won't have them
- To force a full rebuild: delete the image first (`docker images | grep vsc-`, then `docker rm <stopped-container>` then `docker rmi <image-id>`), then use "Rebuild Container"
- Alternatively: "Rebuild Container Without Cache" (available in some VS Code versions)