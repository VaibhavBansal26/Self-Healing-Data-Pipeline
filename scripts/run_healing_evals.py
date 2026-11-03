from __future__ import annotations

import json
from src.agent_evals import evaluate_agents

if __name__ == "__main__":
    print(json.dumps(evaluate_agents(), indent=2))
