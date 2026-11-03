"""Harness for fault-injection tests: run the consumer as a real process and
break the infrastructure underneath it."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Filled by the tests, printed as a table at the end of the session.
RESULTS: list[dict] = []


def compose(*args: str) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=True,
        capture_output=True,
        timeout=180,
    )


def wait_service_healthy(service: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "ps",
                "--format",
                "json",
                service,
            ],
            capture_output=True,
            text=True,
        ).stdout
        for line in out.splitlines():
            if line.strip() and json.loads(line).get("Health") == "healthy":
                return
        time.sleep(1)
    raise TimeoutError(f"{service} did not become healthy within {timeout}s")


class ConsumerProcess:
    """`python -m src.consumer` in its own process, so it can be SIGKILLed."""

    def __init__(self, topic: str, group: str | None = None):
        self.topic = topic
        self.group = group or f"chaos-{uuid.uuid4().hex[:8]}"
        self.log_path = (
            Path(tempfile.mkdtemp(prefix="chaos-consumer-")) / "consumer.log"
        )
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        env = dict(
            os.environ,
            RAW_TOPIC=self.topic,
            CONSUMER_GROUP=self.group,
            PYTHONPATH=str(REPO_ROOT),
        )
        env.pop("OPENAI_API_KEY", None)
        log = open(self.log_path, "ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "src.consumer"],
            cwd=REPO_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    def kill(self) -> None:
        """SIGKILL: no cleanup, no offset commit, like an OOM kill."""
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGKILL)
            self.proc.wait(10)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def log_tail(self, n: int = 40) -> str:
        try:
            return "\n".join(
                self.log_path.read_text(errors="replace").splitlines()[-n:]
            )
        except FileNotFoundError:
            return ""

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.kill()


def record(scenario: str, **fields) -> None:
    RESULTS.append({"scenario": scenario, **fields})
