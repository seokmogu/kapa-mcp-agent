# Remote Update

The agent updates itself from GitHub. There is **no controller-side update
server** and **no inbound network requirement** — the target PC only needs
outbound HTTPS to `github.com` / `api.github.com`. During calibration, when the
MCP client runs on the same PC as the agent, no Tailscale is needed at all.

Two things update independently:

| What | Changes | Channel | Restart? |
| --- | --- | --- | --- |
| Recipes (`recipes/*.json`) | constantly during calibration | GitHub pull or direct push | no (hot reload) |
| Agent binary (`kapa-agent.exe`) | rarely (new action types) | GitHub Releases | yes (watchdog swap) |

## Recipe updates

Recipes live in the repo under `recipes/<name>.json`:

```json
{ "name": "kapa_hub_plus.search_address", "description": "...", "steps": [ ... ] }
```

Files ending in `.template.json` are ignored (scaffolding). The agent's active
recipe set = `recipes_dir/*.json` merged with any inline `recipes` in
`config.local.json` (inline wins, for quick local experiments).

Three ways to change recipes on a running agent, fastest first:

1. **Direct push (no commit)** — inner calibration loop.
   `PUT /config/recipes` with `{"recipes": {...}}`. Validated, backed up,
   written to `recipes_dir`, hot-reloaded. MCP tool: `push_recipes`.
2. **GitHub pull** — promote a versioned recipe.
   Commit/push `recipes/*.json` to the repo, then
   `POST /admin/update-recipes?ref=main`. The agent fetches the recipe files via
   the GitHub Contents API, validates, backs up, writes, hot-reloads. MCP tool:
   `update_recipes_from_github`.
3. **Local edit + reload** — `POST /admin/reload` re-reads `recipes_dir` from
   disk.

Every change snapshots the current `recipes_dir` into `recipes_dir/.backup/<ts>/`.
`POST /admin/rollback` restores the most recent snapshot exactly (files added
after the snapshot are removed). MCP tool: `rollback_recipes`.

Invalid recipes (unknown action, malformed steps) are rejected with HTTP 422 and
never applied, so a bad push cannot brick the agent.

## Agent binary updates

1. Tag a release: `git tag v0.3.0 && git push origin v0.3.0`.
2. GitHub Actions (`.github/workflows/release.yml`) builds `kapa-agent.exe` (and
   `kapa-watchdog.exe`) on a `windows-latest` runner with PyInstaller, computes
   SHA-256 sidecars, and attaches them to the release.
3. On the target, `POST /admin/update-agent` downloads the latest release asset
   (`github.asset_name`, default `kapa-agent.exe`) and verifies its `.sha256`.
   MCP tool: `update_agent_binary`.

How the swap happens depends on how the agent is running:

- **Single EXE (default double-click):** the agent spawns a small detached
  PowerShell swapper, then exits. The swapper waits for the process to end,
  replaces `kapa-agent.exe` (archiving the old one as `kapa-agent.exe.old`), and
  relaunches it. No watchdog needed. A running EXE can't overwrite itself, so the
  swap is done by the short-lived external swapper.
- **Watchdog / source mode (or `?stage_only=true`):** the new binary is staged as
  `kapa-agent.exe.new` with a `.update-pending` marker; `POST /admin/restart`
  exits and `run_watchdog.py` / `kapa-watchdog.exe` performs the swap on relaunch.

## First-time install (one EXE)

The repo is public, so installation is just downloading one file:

> https://github.com/seokmogu/kapa-mcp-agent/releases/latest/download/kapa-agent.exe

Double-click it. No config file is required — the agent boots on
`127.0.0.1:8765` with baked-in defaults (github repo, no token needed for a
public repo) and zero recipes, then pulls recipes on demand.

For managed deployments the repo also provides `scripts/install.ps1` (installs
to a dir, optional `-RegisterTask` ONLOGON, optional `-Token` for a private
repo) and `kapa-watchdog.exe`, but neither is required for the single-EXE flow.

## Deployment layout

```
<install dir>/
  kapa-watchdog.exe        # launch this (ONLOGON task or manually)
  kapa-agent.exe           # managed/swapped by the watchdog
  config.local.json        # host/port/token + github.token  (never committed)
  recipes/                 # working copy, updated by pull/push
```

Run the watchdog, not the agent, so updates can be applied:

```powershell
.\kapa-watchdog.exe
```

During source-based calibration the watchdog falls back to
`python -m kapa_agent.main`, so the same restart/update flow works without
building an EXE.

## Authentication & secrets

- The GitHub token is a **fine-grained, read-only** PAT scoped to this repo
  (Contents: Read-only, Metadata: Read-only). It lives only in
  `config.local.json` (gitignored) or `KAPA_AGENT_GITHUB_TOKEN`. It is never
  logged or written back to disk by the agent.
- For a public repo the token may be omitted.
- The agent's own API token (`auth_token`) is separate and gates all `/admin`
  and `/config` endpoints.

## Configuration

`config.local.json`:

```json
{
  "recipes_dir": "recipes",
  "github": {
    "repo": "seokmogu/kapa-mcp-agent",
    "ref": "main",
    "token": "github_pat_...",
    "asset_name": "kapa-agent.exe"
  }
}
```

Env overrides: `KAPA_AGENT_RECIPES_DIR`, `KAPA_AGENT_GITHUB_REPO`,
`KAPA_AGENT_GITHUB_REF`, `KAPA_AGENT_GITHUB_TOKEN`, `KAPA_AGENT_GITHUB_ASSET`.

## Endpoint summary

| Endpoint | Purpose |
| --- | --- |
| `GET /version` | running version, recipe hash, github config |
| `PUT /config/recipes` | direct push recipes (hot reload) |
| `POST /admin/reload` | re-read recipes from disk |
| `POST /admin/update-recipes?ref=` | pull recipes from GitHub |
| `POST /admin/rollback` | restore last recipe snapshot |
| `POST /admin/update-agent` | download + stage latest EXE from Releases |
| `POST /admin/restart` | exit for watchdog relaunch/swap |
