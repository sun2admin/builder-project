# Dependency Analysis: connect-rust

**Repo:** anthropics/connect-rust
**Analyzed:** 2026-05-06
**Purpose:** A Tower-based Rust implementation of ConnectRPC, serving Connect, gRPC, and gRPC-Web clients over HTTP with binary or JSON protobuf messages.

---

## Languages & Runtimes
- Languages: rust, shell, go
- Runtime extras: none detected
- Versions: rust 1.88
- Base image: `not specified`

## System Packages
none detected

## Global JS Package Installs *(Dockerfile npm/pnpm/yarn/bun globals)*
none detected

## Dockerfile Python Installs *(`pip` / `pipx` in RUN blocks)*
none detected

## Dockerfile Go Installs *(`go install` in RUN blocks)*
none detected

## Libraries
  - **rust**: anyhow, async-compression, axum, base64, buffa, buffa-codegen, buffa-types, bytes, clap, connectrpc, connectrpc-build, connectrpc-codegen ... (68 more)

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
connectrpc.com, demo.connectrpc.com, docs.rs, github.com, rustwasm.github.io, token.actions.githubusercontent.com

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - post_start_chain: none
  - post_create_chain: none


## Credentials Required
  - Tokens: CARGO_REGISTRY_TOKEN, GITHUB_TOKEN

## MCP Servers
none detected

## Claude Plugins
none detected

## Browser / Test Tools
none detected

## GitHub API Usage
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: aarch64, amd64, arm64, basename, bash, bench, buffa, cargo, ci, cleanup, clippy, cmds, conformance, connectrpc, cp, decode-heavy, deps, desc, dir, dirname, doc, docker, echo-, echo-connectrpc, echo-tonic, edit, env, example, fair, fmt, framework, generate, gh, gitignored, greet, grep, head, inferno-collapse-perf, inferno-flamegraph, jemalloc, jeprof, lint, ln, log-, log-connectrpc, log-connectrpc-noutf8, log-tonic, minimal, mkdir, mktemp, perf, profile, python3, redis-cli, requires, rm, seq, sleep, specs, tar, tasks, tee, tonic, uname, unary, vars, verbose, wasm-pack, x86_64
  - **CI toolchain (GitHub Actions)**: apt-get, attest-build-provenance, cargo, cat, checkout, chmod, cosign, cosign-installer, cp, crate, crates-io-auth, download-artifact, exists, file, gh-release, grep, protoc, rust, sha256sum, shell, skipping, tee, upload-artifact, uploaded

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `apt-get` → `apt`
  - `basename` → `coreutils`
  - `bash` → `bash` (needs: base-files, debianutils)
  - `cat` → `coreutils`
  - `chmod` → `coreutils`
  - `cp` → `coreutils`
  - `dir` → `coreutils`
  - `dirname` → `coreutils`
  - `env` → `coreutils`
  - `fmt` → `coreutils`
  - `gh` → `gh` (needs: libc6)
  - `grep` → `grep` (needs: dpkg)
  - `head` → `coreutils`
  - `ln` → `coreutils`
  - `mkdir` → `coreutils`
  - `mktemp` → `coreutils`
  - `python3` → `python3` (needs: python3.11, libpython3-stdlib)
  - `rm` → `coreutils`
  - `seq` → `coreutils`
  - `sha256sum` → `coreutils`
  - `sleep` → `coreutils`
  - `tar` → `tar`
  - `tee` → `coreutils`
  - `uname` → `coreutils`
  - `x86_64` → `util-linux`
