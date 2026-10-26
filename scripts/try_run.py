"""Run one exploration from the command line: python scripts/try_run.py "lawyer" "beliefs..." """
import asyncio, json, sys
sys.path.insert(0, ".")
from backend.pipeline import explore

async def main():
    async def emit(kind, payload):
        if kind == "agent":
            u = payload.get("usage") or {}
            print(f"[{payload['agent']}] {payload['state']}: {payload.get('note','')} "
                  f"{'in=%s cached=%s out=%s $%.5f' % (u['input_tokens'], u['cached_tokens'], u['output_tokens'], u['cost_usd']) if u else ''}")
        elif kind == "blocked":
            print("BLOCKED", payload)
    args = sys.argv[1:] + ["", "", ""]
    out = await explore(args[0], args[1], args[2], session="cli", emit=emit, use_cache="--nocache" not in sys.argv)
    json.dump(out, open("logs/last_run.json", "w"), indent=1)
    print(json.dumps(out.get("totals"), indent=1)); print("rejections:", out.get("rejections"))
asyncio.run(main())
