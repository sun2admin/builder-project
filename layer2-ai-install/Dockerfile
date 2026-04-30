# layer2-ai-install: Conditional AI tool installation (:claude, :gemini)
# Base: ghcr.io/sun2admin/layer1-ai-depends:latest
# Variants: :claude (Claude Code + claude user), :gemini (Gemini CLI + gemini user)

ARG BASE_IMAGE=ghcr.io/sun2admin/layer1-ai-depends:latest
FROM ${BASE_IMAGE}

# ─── Layer 1: Install AI tool based on variant ──
ARG AI_TYPE=claude

RUN if [ "$AI_TYPE" = "gemini" ]; then \
    npm install -g @google/gemini-cli; \
else \
    npm install -g @anthropic-ai/claude-code; \
fi && \
npm cache clean --force

# ─── Layer 2: Create user and setup environment ──
ARG USERNAME=${AI_TYPE}

RUN useradd -m -s /bin/bash ${USERNAME} && \
    mkdir -p /commandhistory && \
    touch /commandhistory/.bash_history && \
    chown -R ${USERNAME} /commandhistory && \
    mkdir -p /home/${USERNAME}/.claude /home/${USERNAME}/.ssh /run/credentials && \
    chmod 700 /home/${USERNAME}/.ssh && \
    chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.claude /home/${USERNAME}/.ssh && \
    mkdir -p /usr/local/share/npm-global && \
    chown -R ${USERNAME}:${USERNAME} /usr/local/share/npm-global && \
    chown -R ${USERNAME}:${USERNAME} /opt/venv && \
    echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" \
        > /etc/sudoers.d/${USERNAME}-firewall && \
    chmod 0440 /etc/sudoers.d/${USERNAME}-firewall

# ─── Layer 3: Set system-wide environment ──
RUN printf 'export NPM_CONFIG_PREFIX=/usr/local/share/npm-global\nexport PATH="$PATH:/usr/local/share/npm-global/bin"\nexport SHELL=/bin/bash\nexport EDITOR=nano\nexport VISUAL=nano\n' >> /etc/profile.d/ai-user.sh

USER ${USERNAME}
