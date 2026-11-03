# Final Demo Video / GIF Guide

A small generated GIF is included at `docs/assets/demo-preview.gif` as a lightweight project preview.

For a real final demo video, record a 60-90 second walkthrough:

1. Start on the Overview page and show all stages healthy.
2. Open Auto-Healer Console.
3. Run `docker compose stop consumer`.
4. Show the terminal-style console: Detect → Plan → Heal Safe → Verify → Remember.
5. Return to Pipeline Map and show the Consumer node recovered.
6. Open AI Engineering and show trajectory, RAG memory, MCP tool trace, and semantic cache.
7. Open Reason Act Verify and Human Approval for record-level healing.

Suggested command:

```bash
./scripts/one_click_demo.sh
```
