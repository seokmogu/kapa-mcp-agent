# Functional And API Spec

## Agent Configuration

`config.local.json`:

```json
{
  "bind_host": "127.0.0.1",
  "port": 8765,
  "artifact_dir": "artifacts",
  "log_dir": "logs",
  "auth_token": null,
  "default_window_patterns": {
    "kapa_hub_plus": ".*(KAPA\\s*HUB|KAPA-HUB).*",
    "kais": ".*(부동산통합업무시스템|KAIS).*"
  },
  "recipes": {}
}
```

Environment variables override config:

- `KAPA_AGENT_CONFIG`
- `KAPA_AGENT_BIND_HOST`
- `KAPA_AGENT_PORT`
- `KAPA_AGENT_ARTIFACT_DIR`
- `KAPA_AGENT_LOG_DIR`
- `KAPA_AGENT_TOKEN`

## HTTP API

### `GET /health`

Returns:

```json
{
  "ok": true,
  "platform": "windows",
  "bind_host": "127.0.0.1",
  "port": 8765,
  "artifact_dir": "artifacts",
  "recipes": []
}
```

### `GET /diagnostics`

Returns dependency and configuration status.

### `GET /windows?backend=uia`

Returns visible top-level windows.

Window item:

```json
{
  "handle": 123456,
  "title": "KAPA HUB PLUS",
  "class_name": "...",
  "process_id": 1111,
  "process_name": "example.exe",
  "visible": true
}
```

### `GET /programs/{program}/probe`

Supported initial program keys:

- `kapa_hub_plus`
- `kais`

Returns matching windows based on configured title regex.

### `POST /uia/dump`

Request:

```json
{
  "selector": {
    "handle": null,
    "title_re": ".*KAPA.*",
    "title_contains": null,
    "process_name": null,
    "backend": "uia"
  },
  "max_depth": 4,
  "max_nodes": 300
}
```

Returns a UIA tree with:

- `name`
- `control_type`
- `automation_id`
- `class_name`
- `handle`
- `rectangle`
- `children`

### `POST /input/type`

Request:

```json
{
  "text": "서울특별시 ...",
  "selector": {
    "title_re": ".*KAPA.*",
    "backend": "uia"
  },
  "paste": true,
  "submit": false
}
```

### `POST /input/hotkey`

Request:

```json
{
  "keys": "^c",
  "selector": {
    "title_re": ".*KAPA.*",
    "backend": "uia"
  }
}
```

Uses pywinauto key syntax.

### `POST /input/click`

Request:

```json
{
  "x": 100,
  "y": 200,
  "selector": {
    "title_re": ".*KAPA.*",
    "backend": "uia"
  },
  "button": "left"
}
```

Coordinates are absolute screen coordinates.

### `GET /clipboard`

Returns:

```json
{
  "text": "..."
}
```

### `POST /clipboard`

Request:

```json
{
  "text": "..."
}
```

### `POST /screen/screenshot`

Request:

```json
{
  "monitor": 1,
  "name": "diagnostic.png"
}
```

Returns:

```json
{
  "artifact": {
    "id": "...",
    "name": "...",
    "path": "...",
    "size": 1000,
    "modified_at": 0
  },
  "width": 1920,
  "height": 1080,
  "black_ratio": 0.97
}
```

High `black_ratio` means screenshots are likely blocked or unusable.

### `POST /files/recent`

Request:

```json
{
  "folders": [],
  "patterns": ["*.xlsx", "*.xls", "*.csv", "*.pdf"],
  "minutes": 30,
  "limit": 20
}
```

If `folders` is empty, the Agent checks common export folders:

- Downloads
- Documents
- Desktop

### `POST /files/collect`

Same request as `/files/recent`, but copies files into artifact storage.

### `POST /jobs`

Request:

```json
{
  "task": "search_address",
  "program": "kapa_hub_plus",
  "params": {
    "address": "서울특별시 ..."
  },
  "outputs": ["clipboard", "export_file"]
}
```

Returns:

```json
{
  "id": "...",
  "status": "queued",
  "task": "search_address",
  "result": null,
  "error": null
}
```

### `GET /jobs/{job_id}`

Returns job status.

### `GET /artifacts`

Returns collected artifacts.

### `GET /artifacts/{artifact_id}`

Downloads an artifact.

## MCP Tools

Current tools:

- `agent_health`
- `agent_diagnostics`
- `list_windows`
- `probe_program`
- `dump_uia`
- `send_hotkey`
- `type_text`
- `click_screen`
- `read_clipboard`
- `write_clipboard`
- `capture_screenshot`
- `recent_export_files`
- `collect_export_files`
- `search_address`
- `run_recipe`
- `get_job`
- `list_artifacts`
- `read_artifact_text`

## Recipe Step Spec

Supported actions:

- `wait`
- `hotkey`
- `type_text`
- `click`
- `read_clipboard`
- `write_clipboard`

Placeholder interpolation:

```text
{{address}}
```

comes from job params.

## First Target Recipe Spec

`kapa_hub_plus.search_address` must eventually:

1. Focus the KAPA HUB PLUS search area.
2. Input address or parcel.
3. Trigger search.
4. Wait until result changes.
5. Extract result through clipboard, export, or UIA.
6. Save result as artifact.

The exact selectors remain field-calibration outputs.

