from __future__ import annotations

import argparse
import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    res = requests.post(
        f"{args.api}/events/pressure-test", params={"total": args.events}, timeout=60
    )
    print(res.status_code)
    print(res.text)


if __name__ == "__main__":
    main()
