---
name: Init Scripts Must Never Be Baked Into the Image
description: init-ssh.sh and init-gh-token.sh must never be included in the container image — only init-firewall.sh belongs there
type: feedback
---

init-ssh.sh and init-gh-token.sh must NEVER be copied into the container image or suggested as candidates for the image.

**Why:** These scripts handle user credentials and SSH keys — they are project/environment concerns, not image concerns. The image is a shared artifact that should contain only OS-level infrastructure (firewall rules via init-firewall.sh). Credential handling belongs in the project repo and is injected at container startup via the workspace bind mount.

**How to apply:** When suggesting where init scripts live, init-firewall.sh goes in the image (needs NOPASSWD sudo baked in), and init-ssh.sh and init-gh-token.sh always go in the project repo's scripts/ directory, called via their full path in postStartCommand.