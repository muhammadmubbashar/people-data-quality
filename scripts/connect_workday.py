"""One-shot loopback OAuth/PKCE probe; no tokens/passwords written to disk."""

import argparse
import json
import ssl
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

from people_quality.workday import ConnectionError, Handshake, Tenant, read_workers
from people_quality.workday_enrichment import discover


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("data/local/workday-config.json"))
    parser.add_argument(
        "--discover", action="store_true", help="Inspect documented audit field sources"
    )
    parser.add_argument(
        "--enrich", action="store_true", help="Use previously discovered field metadata"
    )
    args = parser.parse_args()
    tenant = Tenant(**json.loads(args.config.read_text(encoding="utf-8")))
    handshake = Handshake(tenant)
    output = Path("data/local/workday-probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = Path("logs/workday-authorize-url.txt")
    runtime.parent.mkdir(parents=True, exist_ok=True)
    finished = False

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log OAuth codes/query strings.

        def do_GET(self):
            nonlocal finished
            parsed = urlsplit(self.path)
            if self.headers.get("Host") != "127.0.0.1:8766" or parsed.path != "/callback":
                self.send_error(404)
                return
            params = parse_qs(parsed.query)
            code, state = params.get("code", [""])[0], params.get("state", [""])[0]
            status, message = 200, "Connection checked. You may close this tab."
            try:
                with requests.Session() as session:
                    token = handshake.exchange(code, state, session)
                    workers = read_workers(tenant, token, session)
                    if args.discover or args.enrich:
                        metadata = None
                        if args.enrich:
                            metadata = json.loads(
                                Path("data/local/workday-discovery.json").read_text(
                                    encoding="utf-8"
                                )
                            )
                        discovery = discover(tenant, workers, token, session, metadata)
                        Path("data/local/workday-discovery.json").write_text(
                            json.dumps(discovery, indent=2) + "\n", encoding="utf-8"
                        )
                    del token
                evidence = {
                    "checked_at": datetime.now(UTC).isoformat(),
                    "source": "personal_workday_development_tenant",
                    "mode": "read_only_api_probe",
                    "sample_only": True,
                    "received_rows": len(workers["data"]),
                    "response": workers,
                    "audit_imported": False,
                }
                output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
                print(
                    f"Read-only Workday probe succeeded: {len(workers['data'])} rows.", flush=True
                )
                finished = True
            except ConnectionError as exc:
                status, message = 400, str(exc)
                print(message, flush=True)
                finished = handshake.used
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(message.encode())

    with HTTPServer(("127.0.0.1", 8766), Callback) as server:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain("data/local/devtls/cert.pem", "data/local/devtls/key.pem")
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        server.timeout = 1
        runtime.write_text(handshake.authorization_url(), encoding="utf-8")
        print("Waiting for your Workday authorization, maximum ten minutes.", flush=True)
        deadline = time.monotonic() + 600
        try:
            while not finished and time.monotonic() < deadline:
                server.handle_request()
        finally:
            runtime.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
