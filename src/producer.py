from __future__ import annotations

from src.event_gateway import publish_demo_events


if __name__ == "__main__":
    result = publish_demo_events(transform=False)
    print(f"Published {result['published_count']} demo events to {result['topic']}")
    for event in result["events"]:
        print(f"Produced event_id={event.get('event_id')}")
