import json, os, sys, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
U = os.environ.get("MAKEFUN_ENV_URL") or sys.exit("MAKEFUN_ENV_URL is not set")
def post(path, body):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res: return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: HTTP {e.code} {e.read().decode(errors='replace')}")
while True:
    g = post("/game", {})
    if g["status"] == "done": break
    while g["status"] == "your_move":
        g = post("/move", {"game": g["game"], "move": engine.best_move(g["fen"], g["legal_moves"])})
    print(f"game {g['game']}: {g['outcome']} by {g['reason']}", file=sys.stderr)
print(f"done: {g.get('wins')} won, {g.get('draws')} drawn, {g.get('losses')} lost", file=sys.stderr)
