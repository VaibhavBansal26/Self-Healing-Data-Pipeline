from __future__ import annotations

import time
from src.dashboard_service import get_pipeline_summary


def main() -> None:
    start = time.perf_counter()
    summary = get_pipeline_summary()
    elapsed = time.perf_counter() - start
    total_processed = summary.get("orders_count", 0) + summary.get("incident_count", 0)
    healed = summary.get("healed_count", 0)
    incident_count = max(summary.get("incident_count", 0), 1)
    print("Pipeline benchmark snapshot")
    print(f"Dashboard query latency: {elapsed * 1000:.2f} ms")
    print(f"Total processed approximation: {total_processed}")
    print(f"Healing success rate: {healed / incident_count:.2%}")
    print(summary)


if __name__ == "__main__":
    main()
