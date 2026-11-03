"""Record the Postgres-outage scenario for real and render it as a terminal GIF.

Every line in the GIF comes from an actual run: the consumer's own log output, row
counts read from Postgres, and the timings measured while it ran. Idle gaps are
shortened for playback (the clock in the corner shows real elapsed time).

Requires the integration stack to be up:
    docker compose -f tests/integration/docker-compose.yml up -d --wait
    RUN_INTEGRATION=1 PYTHONPATH=.:tests/integration python scripts/make_demo_gif.py

Needs Pillow (`pip install pillow`). Output: docs/assets/self-healing-demo.gif
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests" / "integration")]

os.environ.update(
    {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:19092",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "55442",
        "POSTGRES_DB": "pipeline_db",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "REDIS_HOST": "127.0.0.1",
        "REDIS_PORT": "56379",
        "RAW_TOPIC": "it_demo_raw",
        "DLQ_TOPIC": "it_dead_letter_events",
        "ENABLE_TERMINAL_HUMAN_APPROVAL": "false",
    }
)
os.environ.pop("OPENAI_API_KEY", None)

OUT = ROOT / "docs" / "assets" / "self-healing-demo.gif"
BATCH = 40

# --------------------------------------------------------------------------- capture

START = time.time()
LINES: list[tuple[str, str]] = []  # (kind, text)
STATE = {"pg": "UP", "stored": 0, "total": BATCH * 2}
SNAPSHOTS: list[tuple[float, list[tuple[str, str]], dict]] = []


def snapshot() -> None:
    SNAPSHOTS.append((time.time() - START, list(LINES), dict(STATE)))


def emit(kind: str, text: str) -> None:
    LINES.append((kind, text))
    snapshot()


def set_state(**kw) -> None:
    changed = {k: v for k, v in kw.items() if STATE.get(k) != v}
    if changed:
        STATE.update(changed)
        snapshot()


def stored(tag: str) -> int | None:
    import psycopg2

    try:
        with psycopg2.connect(
            connect_timeout=2,
            host="127.0.0.1",
            port=55442,
            dbname="pipeline_db",
            user="postgres",
            password="postgres",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM orders WHERE customer_id LIKE %s",
                    (f"cust-{tag}%",),
                )
                return int(cur.fetchone()[0])
    except Exception:
        return None


def publish(topic: str, tag: str, start: int, n: int) -> None:
    from confluent_kafka import Producer

    producer = Producer({"bootstrap.servers": "localhost:19092"})
    for i in range(start, start + n):
        event = {
            "event_id": f"{tag}-{i:04d}",
            "customer_id": f"cust-{tag}",
            "amount": 10.0 + i,
            "currency": "USD",
            "status": "paid",
        }
        producer.produce(topic, key=event["event_id"], value=json.dumps(event))
    producer.flush(30)


MAX_CHARS = 84
noted = [False]


def new_consumer_lines(consumer, seen: list[int]) -> None:
    """Emit consumer log lines written since the last call, collapsing repeats."""
    text = (
        consumer.log_path.read_text(errors="replace")
        if consumer.log_path.exists()
        else ""
    )
    lines = [ln for ln in text.splitlines() if ln.startswith("Processing failed")]
    for ln in lines[seen[0] :]:
        line = "consumer | " + ln.split("\n")[0]
        if len(line) > MAX_CHARS:
            line = line[: MAX_CHARS - 1] + "…"
        emit("log", line)
        if not noted[0]:
            noted[0] = True
            emit(
                "note",
                "           ↳ the same message is retried with growing delays; nothing is skipped or dead-lettered",
            )
    seen[0] = len(lines)


def run_scenario() -> None:
    from chaos import ConsumerProcess, compose, wait_service_healthy
    from confluent_kafka.admin import AdminClient, NewTopic

    topic = os.environ["RAW_TOPIC"] + f"_{uuid.uuid4().hex[:5]}"
    admin = AdminClient({"bootstrap.servers": "localhost:19092"})
    for fut in admin.create_topics([NewTopic(topic, 1, 1)]).values():
        fut.result(timeout=15)
    tag = f"demo{uuid.uuid4().hex[:4]}"
    consumer = ConsumerProcess(topic)
    seen = [0]

    emit(
        "cmd",
        "$ python -m src.consumer          # the real consumer, in its own process",
    )
    consumer.start()
    time.sleep(4)
    publish(topic, tag, 0, BATCH)
    emit("info", f"producer  | published {BATCH} orders")
    while (stored(tag) or 0) < BATCH:
        set_state(stored=stored(tag) or 0)
        time.sleep(0.4)
    set_state(stored=BATCH)
    emit("ok", f"postgres  | {BATCH}/{BATCH} orders stored")

    emit("cmd", "$ docker compose stop postgres     # chaos: database goes down")
    compose("stop", "postgres")
    set_state(pg="DOWN")
    publish(topic, tag, BATCH, BATCH)
    emit("info", f"producer  | published {BATCH} more orders while Postgres is down")
    end = time.time() + 9
    while time.time() < end:
        new_consumer_lines(consumer, seen)
        time.sleep(0.5)

    emit("cmd", "$ docker compose start postgres    # database comes back")
    t_up = time.time()
    compose("start", "postgres")
    wait_service_healthy("postgres")
    set_state(pg="UP")
    last = BATCH
    while True:
        n = stored(tag)
        if n is not None and n != last:
            last = n
            set_state(stored=n)
        new_consumer_lines(consumer, seen)
        if n is not None and n >= BATCH * 2:
            break
        if time.time() - t_up > 120:
            raise TimeoutError("consumer did not drain the backlog")
        time.sleep(0.3)
    recovery = time.time() - t_up
    emit(
        "ok",
        f"postgres  | {BATCH * 2}/{BATCH * 2} orders stored, {recovery:.1f}s after Postgres returned",
    )

    import psycopg2

    with psycopg2.connect(
        host="127.0.0.1",
        port=55442,
        dbname="pipeline_db",
        user="postgres",
        password="postgres",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COUNT(DISTINCT event_id) FROM orders WHERE customer_id LIKE %s",
                (f"cust-{tag}%",),
            )
            rows, distinct = cur.fetchone()
    emit(
        "result",
        f"result    | stored {rows}/{BATCH * 2}   duplicates {rows - distinct}   lost {BATCH * 2 - distinct}",
    )
    consumer.stop()
    if (rows, distinct) != (BATCH * 2, BATCH * 2):
        raise SystemExit(f"scenario did not end clean: rows={rows} distinct={distinct}")


# --------------------------------------------------------------------------- render

W, H = 960, 540
COLORS = {
    "bg": "#0d1117",
    "bar": "#161b22",
    "text": "#c9d1d9",
    "dim": "#8b949e",
    "green": "#3fb950",
    "red": "#f85149",
    "yellow": "#d29922",
    "blue": "#58a6ff",
    "line": "#30363d",
}
KIND_COLOR = {
    "cmd": "blue",
    "info": "text",
    "log": "yellow",
    "ok": "green",
    "result": "green",
    "note": "dim",
}
MAX_LINES = 14


def render() -> None:
    from PIL import Image, ImageDraw, ImageFont

    font_path = next(
        p
        for p in (
            "/System/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/Monaco.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        )
        if Path(p).exists()
    )
    body = ImageFont.truetype(font_path, 15)
    small = ImageFont.truetype(font_path, 13)
    title = ImageFont.truetype(font_path, 17)

    def frame(t: float, lines, state) -> Image.Image:
        img = Image.new("RGB", (W, H), COLORS["bg"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 64], fill=COLORS["bar"])
        d.text(
            (24, 12),
            "Self-healing pipeline: Postgres outage while events flow",
            font=title,
            fill=COLORS["text"],
        )
        pg_color = COLORS["green"] if state["pg"] == "UP" else COLORS["red"]
        d.ellipse([24, 42, 34, 52], fill=pg_color)
        d.text((42, 38), f"postgres {state['pg']}", font=small, fill=pg_color)
        d.text(
            (190, 38),
            f"stored {state['stored']}/{state['total']}",
            font=small,
            fill=COLORS["text"],
        )
        d.text((W - 150, 38), f"real time {t:5.1f}s", font=small, fill=COLORS["dim"])
        y = 84
        for kind, text in lines[-MAX_LINES:]:
            d.text((24, y), text, font=body, fill=COLORS[KIND_COLOR[kind]])
            y += 26
        bar_y = H - 34
        d.rectangle([24, bar_y, W - 24, bar_y + 10], fill=COLORS["line"])
        frac = min(1.0, state["stored"] / state["total"])
        d.rectangle(
            [24, bar_y, 24 + int((W - 48) * frac), bar_y + 10],
            fill=pg_color if state["pg"] == "UP" else COLORS["red"],
        )
        return img

    frames, durations = [], []
    prev_t = 0.0
    for i, (t, lines, state) in enumerate(SNAPSHOTS):
        gap = t - prev_t if i else 0.8
        prev_t = t
        if frames:
            durations[-1] = int(min(max(gap, 0.12), 0.9) * 1000)
        frames.append(frame(t, lines, state))
        durations.append(150)
    durations[-1] = 4500  # hold the final result
    quantized = [f.convert("P", palette=Image.ADAPTIVE, colors=32) for f in frames]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        OUT,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    print(
        f"{OUT.relative_to(ROOT)}: {len(frames)} frames, {OUT.stat().st_size / 1024:.0f} KB, {sum(durations) / 1000:.0f}s playback"
    )


if __name__ == "__main__":
    run_scenario()
    render()
