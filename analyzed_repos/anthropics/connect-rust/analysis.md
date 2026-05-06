# Dependency Analysis: connect-rust

**Repo:** anthropics/connect-rust
**Analyzed:** 2026-04-30
**Purpose:** A Tower-based Rust implementation of ConnectRPC, serving Connect, gRPC, and gRPC-Web clients over HTTP with binary or JSON protobuf messages.

---

## Languages & Runtimes
- Languages: rust, shell
- Runtime extras: none detected
- Versions: rust 1.88
- Base image: `not specified`

## System Packages
none detected

## Libraries
  - **rust**: anyhow, async-compression, axum, base64, buffa, buffa-codegen, buffa-descriptor, buffa-types, bytes, clap, connectrpc, connectrpc-build ... (68 more)

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
demo.connectrpc.com, github.com, rustwasm.github.io

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

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

## Firewall Required
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: bazel, buf, cargo, curl, docker, gh, go, grpc, make, protoc, python3, redis-cli, task, tee, valkey

## Suggested Stack
| Setting | Value |
|---|---|
| Base image (layer1 variant) | `latest` |
| Dockerfile FROM | `rust:1.88` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
