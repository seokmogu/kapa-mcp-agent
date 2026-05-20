from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the KAPA Windows Agent.")
    parser.add_argument("--config", help="Path to config.local.json")
    parser.add_argument("--host", help="Bind host, e.g. 127.0.0.1 or a Tailscale IP")
    parser.add_argument("--port", type=int, help="Bind port")
    parser.add_argument("--token", help="Optional shared token required by API clients")
    parser.add_argument("--artifact-dir", help="Artifact output directory")
    parser.add_argument("--log-dir", help="Log directory")
    args = parser.parse_args()

    if args.config:
        os.environ["KAPA_AGENT_CONFIG"] = args.config
    if args.host:
        os.environ["KAPA_AGENT_BIND_HOST"] = args.host
    if args.port:
        os.environ["KAPA_AGENT_PORT"] = str(args.port)
    if args.token:
        os.environ["KAPA_AGENT_TOKEN"] = args.token
    if args.artifact_dir:
        os.environ["KAPA_AGENT_ARTIFACT_DIR"] = args.artifact_dir
    if args.log_dir:
        os.environ["KAPA_AGENT_LOG_DIR"] = args.log_dir

    from kapa_agent.main import run

    run()


if __name__ == "__main__":
    main()
