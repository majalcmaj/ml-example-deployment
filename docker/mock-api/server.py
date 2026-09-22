"""Zero-dependency stub of the remote sales API, for local development only.

Serves prepared sales history on GET and accepts forecasts on POST. Reads the
bundled CSV once at startup — stdlib only, deliberately not a uv workspace
member so it stays out of uv.lock and out of the app images.
"""

import csv
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CSV_PATH = "/srv/data/sales.csv"
PORT = 8080
TOKEN = os.environ.get("MOCK_API_TOKEN", "")

log = logging.getLogger("mock-api")


def load_sales(path: str) -> list[dict]:
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        return [
            {"Date": row["Date"], "Menu": row["Menu"], "Total_Qty": int(row["Total_Qty"])}
            for row in reader
        ]


SALES = load_sales(CSV_PATH)


class Handler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def _log_request(self, status: int) -> None:
        log.info(
            "%s %s status=%d correlation_id=%s authorization=%s",
            self.command,
            self.path,
            status,
            self.headers.get("X-Correlation-ID", "-"),
            "present" if self.headers.get("Authorization") else "absent",
        )

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            self._send_json(200, {"status": "ok"})
            return
        if path == "/api/recent-sales":
            if not self._authorized():
                self._log_request(401)
                self._send_json(401, {"error": "unauthorized"})
                return
            query = parse_qs(urlparse(self.path).query)
            history_days = int(query.get("history_days", ["28"])[0])
            wanted_dates = set(sorted({row["Date"] for row in SALES}, reverse=True)[:history_days])
            records = [row for row in SALES if row["Date"] in wanted_dates]
            self._log_request(200)
            self._send_json(200, {"records": records})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path == "/api/demand-forecast":
            if not self._authorized():
                self._log_request(401)
                self._send_json(401, {"error": "unauthorized"})
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body)
            predictions = payload.get("predictions", [])
            log.info(
                "received forecast forecast_date=%s generated_at_utc=%s predictions=%d",
                payload.get("forecast_date"),
                payload.get("generated_at_utc"),
                len(predictions),
            )
            self._log_request(200)
            self._send_json(200, {"status": "accepted", "received": len(predictions)})
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("mock-api listening on :%d (loaded %d sales rows)", PORT, len(SALES))
    server.serve_forever()
