from __future__ import annotations

from prometheus_client import make_wsgi_app
from wsgiref.simple_server import make_server
from src.config import METRICS_PORT


def run_metrics_server() -> None:
    app = make_wsgi_app()
    server = make_server("0.0.0.0", METRICS_PORT, app)
    print(f"Prometheus metrics available on :{METRICS_PORT}/metrics")
    server.serve_forever()


if __name__ == "__main__":
    run_metrics_server()
