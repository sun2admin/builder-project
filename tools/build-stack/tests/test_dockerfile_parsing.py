"""Unit tests for build_stack.analyzers.dockerfile parsing helpers.

Sister file to ``test_dockerfile_paths.py`` (path discovery already covered
there). This file pins the parsing surface:

  * ``_parse_jsonc`` — JSON-with-comments tolerance
  * ``_parse_mount_string`` — devcontainer mount-string → dict
  * ``_parse_devcontainer`` — full devcontainer.json field extraction
  * ``_strip_bash_c`` / ``_split_chain`` — postStart chain decomposition
  * ``_parse_step`` — interpreter-aware step decomposition
  * ``_in_repo_path`` — script path resolution against cloned repo
  * ``_join_continuations`` / ``_parse_dockerfile`` — Dockerfile parsing
  * ``_parse_pip_tokens`` — pip flag handling
  * ``_route_env_credentials`` — env-key → credential-bucket routing
  * ``_compose_inbound_ports`` — docker-compose port extraction
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from build_stack.analyzers import dockerfile as df
from build_stack.analyzers.schema import AnalysisResult


# ─── _parse_jsonc ─────────────────────────────────────────────────────────────

def test_parse_jsonc_strips_line_comments():
    assert df._parse_jsonc('{"a": 1 // trailing\n}') == {"a": 1}


def test_parse_jsonc_strips_block_comments():
    assert df._parse_jsonc('{"a": /* mid */ 2}') == {"a": 2}


def test_parse_jsonc_real_devcontainer_idiom():
    """Real devcontainer.json files use both styles freely."""
    text = textwrap.dedent('''\
        {
          // top-of-file comment
          "name": "x",
          /* block
             comment */
          "image": "node"
        }
    ''')
    out = df._parse_jsonc(text)
    assert out == {"name": "x", "image": "node"}


# ─── _parse_mount_string ──────────────────────────────────────────────────────

def test_parse_mount_string_volume_default_type():
    out = df._parse_mount_string("source=v,target=/t")
    assert out == {"name": "v", "target": "/t", "type": "volume"}


def test_parse_mount_string_explicit_bind():
    out = df._parse_mount_string("source=/host,target=/in,type=bind")
    assert out["type"] == "bind"
    assert out["name"] == "/host"


def test_parse_mount_string_consistency_preserved():
    """consistency=cached/delegated/consistent matters for macOS perf."""
    out = df._parse_mount_string("source=v,target=/t,consistency=cached")
    assert out.get("consistency") == "cached"


def test_parse_mount_string_readonly_flag():
    out = df._parse_mount_string("source=v,target=/t,readonly")
    assert out.get("readonly") is True


def test_parse_mount_string_handles_extra_whitespace():
    out = df._parse_mount_string(" source = v , target = /t ")
    assert out["name"] == "v"
    assert out["target"] == "/t"


# ─── _parse_devcontainer ──────────────────────────────────────────────────────

def _write_dc(repo: Path, data: dict) -> None:
    (repo / ".devcontainer").mkdir(exist_ok=True)
    (repo / ".devcontainer" / "devcontainer.json").write_text(json.dumps(data))


def test_parse_devcontainer_missing_file_returns_empty(tmp_path):
    out = df._parse_devcontainer(tmp_path)
    assert out["capabilities"] == []
    assert out["volumes"] == []
    assert out["remote_user"] == ""


def test_parse_devcontainer_malformed_json_returns_empty(tmp_path):
    (tmp_path / ".devcontainer").mkdir()
    (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{not valid")
    out = df._parse_devcontainer(tmp_path)
    assert out["capabilities"] == []


def test_parse_devcontainer_run_args_eq_and_space_forms(tmp_path):
    """Both `--cap-add=X` and `--cap-add X` flags strip down to bare cap name."""
    _write_dc(tmp_path, {"runArgs": ["--cap-add=NET_ADMIN", "--cap-add NET_RAW"]})
    out = df._parse_devcontainer(tmp_path)
    assert "NET_ADMIN" in out["capabilities"]
    assert "NET_RAW" in out["capabilities"]


def test_parse_devcontainer_mounts_string_form(tmp_path):
    _write_dc(tmp_path, {"mounts": ["source=v,target=/t,type=volume"]})
    out = df._parse_devcontainer(tmp_path)
    assert out["volumes"] == [{"name": "v", "target": "/t", "type": "volume"}]


def test_parse_devcontainer_mounts_dict_form(tmp_path):
    _write_dc(tmp_path, {"mounts": [
        {"source": "v", "target": "/t", "type": "bind", "consistency": "cached"},
    ]})
    out = df._parse_devcontainer(tmp_path)
    assert out["volumes"][0]["consistency"] == "cached"
    assert out["volumes"][0]["type"] == "bind"


def test_parse_devcontainer_post_start_list_joined_with_amp(tmp_path):
    """postStartCommand can be a list — it must be normalized to ' && '-joined string."""
    _write_dc(tmp_path, {"postStartCommand": ["a.sh", "b.sh"]})
    out = df._parse_devcontainer(tmp_path)
    assert out["post_start"] == "a.sh && b.sh"


def test_parse_devcontainer_post_start_dict_values_joined(tmp_path):
    """Spec also allows a dict-of-named-commands; we stringify by value join."""
    _write_dc(tmp_path, {"postStartCommand": {"firewall": "fw.sh", "ssh": "ssh.sh"}})
    out = df._parse_devcontainer(tmp_path)
    # dict iteration order is insertion order in py3.7+
    assert "fw.sh" in out["post_start"]
    assert "ssh.sh" in out["post_start"]


def test_parse_devcontainer_wait_for_list_normalized_to_empty(tmp_path):
    """waitFor of list/dict (invalid per spec but seen in the wild) → empty string."""
    _write_dc(tmp_path, {"waitFor": ["postStartCommand"]})
    out = df._parse_devcontainer(tmp_path)
    assert out["wait_for"] == ""


def test_parse_devcontainer_extensions_under_customizations(tmp_path):
    _write_dc(tmp_path, {
        "customizations": {"vscode": {"extensions": ["a.b", "c.d"]}},
    })
    out = df._parse_devcontainer(tmp_path)
    assert out["extensions"] == ["a.b", "c.d"]


def test_parse_devcontainer_threads_workspace_and_lifecycle(tmp_path):
    _write_dc(tmp_path, {
        "remoteUser": "claude",
        "workspaceMount": "source=$,target=/ws,type=bind",
        "workspaceFolder": "/ws",
        "shutdownAction": "stopContainer",
    })
    out = df._parse_devcontainer(tmp_path)
    assert out["remote_user"] == "claude"
    assert out["workspace_mount"].startswith("source=")
    assert out["workspace_folder"] == "/ws"
    assert out["shutdown_action"] == "stopContainer"


# ─── _strip_bash_c ────────────────────────────────────────────────────────────

def test_strip_bash_c_unwraps_double_quoted():
    assert df._strip_bash_c('bash -c "echo hi && echo bye"') == "echo hi && echo bye"


def test_strip_bash_c_unwraps_single_quoted():
    assert df._strip_bash_c("sh -c 'echo hi'") == "echo hi"


def test_strip_bash_c_passthrough_when_not_wrapped():
    assert df._strip_bash_c("echo hi") == "echo hi"


# ─── _split_chain ─────────────────────────────────────────────────────────────

def test_split_chain_simple_two_steps():
    assert df._split_chain("a && b") == ["a", "b"]


def test_split_chain_does_not_split_inside_quotes():
    """`echo "a && b"` is one command, not two."""
    assert df._split_chain('echo "a && b"') == ['echo "a && b"']


def test_split_chain_handles_bash_c_unwrap():
    """Outer bash -c ... is unwrapped before splitting."""
    out = df._split_chain('bash -c "fw.sh && ssh.sh"')
    assert out == ["fw.sh", "ssh.sh"]


def test_split_chain_empty_returns_empty():
    assert df._split_chain("") == []


def test_split_chain_strips_whitespace_around_steps():
    assert df._split_chain("  a   &&   b  ") == ["a", "b"]


def test_split_chain_drops_trailing_empty_step():
    assert df._split_chain("a &&") == ["a"]


# ─── _parse_step ──────────────────────────────────────────────────────────────

def test_parse_step_strips_sudo_prefix():
    s = df._parse_step("sudo /usr/local/bin/init-firewall.sh")
    assert s.sudo is True
    assert s.script == "/usr/local/bin/init-firewall.sh"


def test_parse_step_interpreter_invocation():
    """`bash script.sh args` → script=script.sh (interpreter discarded)."""
    s = df._parse_step("bash /workspace/init.sh arg1 arg2")
    assert s.script == "/workspace/init.sh"
    assert s.args == "arg1 arg2"


def test_parse_step_interpreter_with_flags():
    """`python3 -u script.py` → flags skipped, script picked correctly."""
    s = df._parse_step("python3 -u /tmp/run.py")
    assert s.script == "/tmp/run.py"


def test_parse_step_versioned_interpreter():
    """`python3` strips trailing digits → matches _INTERPRETERS check."""
    s = df._parse_step("python3 /tmp/run.py")
    assert s.script == "/tmp/run.py"


def test_parse_step_non_interpreter_command():
    """Plain script invocation → script=head, args=rest."""
    s = df._parse_step("/usr/local/bin/init-firewall.sh --strict")
    assert s.script == "/usr/local/bin/init-firewall.sh"
    assert s.args == "--strict"


def test_parse_step_raw_preserved():
    raw = "sudo /tmp/x.sh foo"
    s = df._parse_step(raw)
    assert s.raw == raw


# ─── _in_repo_path ────────────────────────────────────────────────────────────

def test_in_repo_path_workspace_prefix_resolves(tmp_path):
    """`/workspace/<repo>/scripts/x.sh` → strip prefix, resolve in tmp_path."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.sh").write_text("")
    rel = df._in_repo_path(tmp_path, "/workspace/repo/scripts/x.sh")
    assert rel == "scripts/x.sh"


def test_in_repo_path_relative_path_direct_match(tmp_path):
    (tmp_path / "init.sh").write_text("")
    assert df._in_repo_path(tmp_path, "init.sh") == "init.sh"


def test_in_repo_path_absolute_outside_workspace_returns_none(tmp_path):
    """Absolute paths not under /workspace/ are baked into the image."""
    assert df._in_repo_path(tmp_path, "/usr/local/bin/init-firewall.sh") is None


def test_in_repo_path_no_match_returns_none(tmp_path):
    assert df._in_repo_path(tmp_path, "ghost.sh") is None


def test_in_repo_path_empty_input():
    assert df._in_repo_path(Path("/tmp"), "") is None


# ─── _join_continuations ──────────────────────────────────────────────────────

def test_join_continuations_folds_backslash():
    text = "RUN apt-get install \\\n  jq \\\n  curl\n"
    joined = df._join_continuations(text)
    assert any("apt-get install" in line and "jq" in line and "curl" in line for line in joined)


def test_join_continuations_preserves_non_continuation_lines():
    text = "FROM node:20\nRUN echo hi\n"
    joined = df._join_continuations(text)
    assert "FROM node:20" in joined
    assert "RUN echo hi" in joined


def test_join_continuations_handles_trailing_continuation():
    """File ending mid-continuation: buffer must still be flushed."""
    joined = df._join_continuations("RUN x \\\n   y")
    assert any("x" in line and "y" in line for line in joined)


# ─── _parse_dockerfile ────────────────────────────────────────────────────────

def test_parse_dockerfile_extracts_base_image():
    out = df._parse_dockerfile("FROM node:22-slim AS builder\n")
    assert out["base"] == "node:22-slim"


def test_parse_dockerfile_apt_get_install_packages():
    out = df._parse_dockerfile(
        "RUN apt-get update && apt-get install -y jq curl git\n"
    )
    pkgs = set(out["packages"])
    assert {"jq", "curl", "git"}.issubset(pkgs)


def test_parse_dockerfile_apt_install_short_form():
    out = df._parse_dockerfile("RUN apt install -y vim\n")
    assert "vim" in out["packages"]


def test_parse_dockerfile_apk_add_alpine():
    out = df._parse_dockerfile("RUN apk add bash curl\n")
    assert "bash" in out["packages"]
    assert "curl" in out["packages"]


def test_parse_dockerfile_npm_global_install():
    out = df._parse_dockerfile(
        "RUN npm install -g @anthropic-ai/claude-code typescript\n"
    )
    assert "@anthropic-ai/claude-code" in out["js_global"]
    assert "typescript" in out["js_global"]


def test_parse_dockerfile_pip_install_picks_packages():
    out = df._parse_dockerfile("RUN pip install requests pytest\n")
    assert "requests" in out["py_installs"]
    assert "pytest" in out["py_installs"]


def test_parse_dockerfile_pip_install_dash_r_skipped():
    """`pip install -r requirements.txt` → no per-package extraction.
    The -r form imports a list; treating its arg as a package name is a bug."""
    out = df._parse_dockerfile("RUN pip install -r requirements.txt\n")
    assert out["py_installs"] == []


def test_parse_dockerfile_go_install_with_at_version():
    """go install requires `@version` — pkgs without `@` are filtered out."""
    out = df._parse_dockerfile("RUN go install golang.org/x/tools/gopls@latest\n")
    assert "golang.org/x/tools/gopls@latest" in out["go_installs"]


def test_parse_dockerfile_env_directive_eq_form():
    out = df._parse_dockerfile("ENV NODE_ENV=production DEBUG=1\n")
    assert "NODE_ENV" in out["env_vars"]
    assert "DEBUG" in out["env_vars"]


def test_parse_dockerfile_env_directive_legacy_form():
    out = df._parse_dockerfile("ENV NODE_ENV production\n")
    assert "NODE_ENV" in out["env_vars"]


def test_parse_dockerfile_expose_port():
    out = df._parse_dockerfile("EXPOSE 3000 8080/tcp\n")
    assert 3000 in out["expose_ports"]
    assert 8080 in out["expose_ports"]


def test_parse_dockerfile_extra_binary_via_curl_release_url():
    out = df._parse_dockerfile(
        'RUN curl -L https://github.com/x/y/releases/download/v1/tool.tar.gz -o /tmp/x\n'
    )
    assert "tool.tar.gz" in out["binaries"]


def test_parse_dockerfile_continuation_apt_install():
    """Backslash-continuation in apt-get install must be folded before parsing."""
    text = "RUN apt-get install -y \\\n    jq \\\n    curl\n"
    out = df._parse_dockerfile(text)
    pkgs = set(out["packages"])
    assert "jq" in pkgs and "curl" in pkgs


# ─── _parse_pip_tokens ────────────────────────────────────────────────────────

def test_parse_pip_tokens_skips_value_flags():
    """`-r requirements.txt` → both tokens skipped (-r consumes its value)."""
    out = df._parse_pip_tokens("-r requirements.txt requests")
    assert out == ["requests"]


def test_parse_pip_tokens_skips_bare_flags():
    """`--upgrade` has no value → just skip the flag itself."""
    out = df._parse_pip_tokens("--upgrade requests")
    assert out == ["requests"]


def test_parse_pip_tokens_skips_shell_separators():
    out = df._parse_pip_tokens("requests && pytest")
    assert out == ["requests", "pytest"]


# ─── _route_env_credentials ───────────────────────────────────────────────────

def test_route_env_api_key_suffix():
    r = AnalysisResult()
    df._route_env_credentials(["ANTHROPIC_API_KEY", "OPENAI_API_KEY"], r)
    assert "ANTHROPIC_API_KEY" in r.credentials_required.api_keys
    assert "OPENAI_API_KEY" in r.credentials_required.api_keys


def test_route_env_secret_suffix_routes_to_api_keys():
    """`_SECRET` suffix → api_keys bucket too (e.g. STRIPE_SECRET)."""
    r = AnalysisResult()
    df._route_env_credentials(["STRIPE_SECRET"], r)
    assert "STRIPE_SECRET" in r.credentials_required.api_keys


def test_route_env_token_or_pat():
    r = AnalysisResult()
    df._route_env_credentials(["GITHUB_TOKEN", "GITHUB_PAT"], r)
    assert "GITHUB_TOKEN" in r.credentials_required.tokens
    assert "GITHUB_PAT" in r.credentials_required.tokens


def test_route_env_database_and_other_buckets():
    r = AnalysisResult()
    df._route_env_credentials(
        ["DATABASE_URL", "REDIS_URL", "POSTGRES_HOST", "SENTRY_DSN"], r,
    )
    assert set(r.credentials_required.other) == {
        "DATABASE_URL", "REDIS_URL", "POSTGRES_HOST", "SENTRY_DSN",
    }


def test_route_env_unrecognized_key_ignored():
    """Random keys without a known pattern are dropped from credentials_required."""
    r = AnalysisResult()
    df._route_env_credentials(["RANDOM_VAR", "MY_CONFIG"], r)
    assert r.credentials_required.api_keys == []
    assert r.credentials_required.tokens == []
    assert r.credentials_required.other == []


def test_route_env_routing_is_exclusive_per_key():
    """Each key lands in at most one bucket (first match wins by precedence)."""
    r = AnalysisResult()
    df._route_env_credentials(["FOO_API_KEY", "BAR_TOKEN"], r)
    assert "FOO_API_KEY" not in r.credentials_required.tokens
    assert "BAR_TOKEN" not in r.credentials_required.api_keys


# ─── _compose_inbound_ports ───────────────────────────────────────────────────

def test_compose_inbound_ports_extracts_from_yaml(tmp_path):
    (tmp_path / "docker-compose.yml").write_text(textwrap.dedent('''\
        services:
          web:
            ports:
              - "8080:80"
              - "3000:3000"
    '''))
    ports = df._compose_inbound_ports(tmp_path)
    assert 8080 in ports
    assert 3000 in ports


def test_compose_inbound_ports_caps_at_20(tmp_path):
    """Bash skill `head -20` parity. A 30-port file should yield ≤ 20."""
    lines = "services:\n  web:\n    ports:\n"
    for i in range(30):
        lines += f'      - "{8000 + i}:80"\n'
    (tmp_path / "docker-compose.yml").write_text(lines)
    ports = df._compose_inbound_ports(tmp_path)
    assert len(ports) <= 20


def test_compose_inbound_ports_no_compose_file(tmp_path):
    assert df._compose_inbound_ports(tmp_path) == []


def test_compose_inbound_ports_skips_dot_git(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "docker-compose.yml").write_text(
        'services:\n  x:\n    ports:\n      - "9999:80"\n'
    )
    assert df._compose_inbound_ports(tmp_path) == []
