"""Read-only collector for a personal, non-commercial study of desktop CNC discussions on Reddit.

Uses the official Reddit Data API with an application-only OAuth token (no user login,
read access only). It never posts, comments, votes or sends messages.

Usage:
  python3 reddit_reader.py collect   # search the configured subreddits and fetch comment trees
  python3 reddit_reader.py refresh   # re-check stored items and drop anything deleted or removed
  python3 reddit_reader.py purge     # delete the whole dataset (also runs automatically after DELETE_AFTER)
"""
import base64, datetime as dt, json, os, sqlite3, subprocess, sys, time, urllib.parse, urllib.request

SUBREDDITS = ["Makera", "CarveraAir", "hobbycnc", "CNC", "Machinists", "CNCmachining"]
KEYWORDS = ["makera", "carvera", "z1"]
OFFICIAL_ACCOUNTS = {"makera_offical", "Makera-Krystal", "Makera-Link"}  # the brand's own accounts
DELETE_AFTER = dt.date(2027, 4, 13)        # whole dataset is deleted after this date
MIN_INTERVAL = 1.0                          # seconds between requests (<= 60 requests/minute)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "study.sqlite")
USER_AGENT = "python:cnc-reddit-study:v0.1 (by /u/{})"


def secret(name):
    """Credentials come from environment variables or the macOS Keychain, never from the code."""
    if os.environ.get(name.upper()):
        return os.environ[name.upper()]
    return subprocess.run(["security", "find-generic-password", "-s", name, "-w"],
                          capture_output=True, text=True, check=True).stdout.strip()


class Reddit:
    def __init__(self):
        self.ua = USER_AGENT.format(secret("reddit_username"))
        self.last = 0.0
        auth = base64.b64encode(f"{secret('reddit_client_id')}:{secret('reddit_client_secret')}".encode()).decode()
        req = urllib.request.Request("https://www.reddit.com/api/v1/access_token",
                                     data=b"grant_type=client_credentials",
                                     headers={"Authorization": f"Basic {auth}", "User-Agent": self.ua})
        self.token = json.load(urllib.request.urlopen(req, timeout=30))["access_token"]

    def get(self, path, **params):
        wait = MIN_INTERVAL - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        url = "https://oauth.reddit.com" + path + "?" + urllib.parse.urlencode({**params, "raw_json": 1})
        req = urllib.request.Request(url, headers={"Authorization": f"bearer {self.token}", "User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=30) as r:
            self.last = time.time()
            remaining = float(r.headers.get("X-Ratelimit-Remaining", 100))
            reset = float(r.headers.get("X-Ratelimit-Reset", 0))
            if remaining < 5:  # stay well inside the published limit
                time.sleep(reset + 1)
            return json.load(r)


def minimal(kind, d):
    """Keep only the fields the study needs. Usernames are dropped except the brand's official accounts."""
    return {
        "id": d["name"], "kind": kind, "subreddit": d.get("subreddit"),
        "created_utc": int(d.get("created_utc", 0)),
        "title": d.get("title") if kind == "post" else None,
        "text": d.get("selftext") if kind == "post" else d.get("body"),
        "score": d.get("score"), "num_comments": d.get("num_comments"),
        "link_id": d.get("link_id") if kind == "comment" else d.get("name"),
        "is_official": 1 if d.get("author") in OFFICIAL_ACCOUNTS else 0,
    }


def is_gone(d):
    text = d.get("selftext") if d.get("name", "").startswith("t3_") else d.get("body")
    return d.get("author") == "[deleted]" or text in ("[deleted]", "[removed]") or bool(d.get("removed_by_category"))


def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, kind TEXT, subreddit TEXT,
                   created_utc INTEGER, title TEXT, text TEXT, score INTEGER, num_comments INTEGER,
                   link_id TEXT, is_official INTEGER)""")
    return con


def save(con, rows):
    con.executemany("INSERT OR REPLACE INTO items VALUES (:id,:kind,:subreddit,:created_utc,:title,:text,"
                    ":score,:num_comments,:link_id,:is_official)", rows)
    con.commit()


def walk(children, out):
    for c in children or []:
        if c.get("kind") != "t1":
            continue
        if not is_gone(c["data"]):
            out.append(minimal("comment", c["data"]))
        replies = c["data"].get("replies")
        if isinstance(replies, dict):
            walk(replies["data"]["children"], out)


def collect(api, con):
    for sub in SUBREDDITS:
        for kw in KEYWORDS:
            after = None
            while True:
                page = api.get(f"/r/{sub}/search", q=kw, restrict_sr=1, sort="new", t="all", limit=100, after=after or "")
                posts = [p["data"] for p in page["data"]["children"] if not is_gone(p["data"])]
                save(con, [minimal("post", p) for p in posts])
                for p in posts:
                    if p.get("num_comments"):
                        tree = api.get(f"/r/{sub}/comments/{p['id']}", limit=500, depth=10)
                        out = []
                        walk(tree[1]["data"]["children"], out)
                        save(con, out)
                after = page["data"].get("after")
                if not after:
                    break
            print(f"r/{sub} '{kw}': done", flush=True)


def refresh(api, con):
    """Re-query every stored item and drop those deleted or removed on Reddit."""
    ids = [r[0] for r in con.execute("SELECT id FROM items")]
    dropped = 0
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        alive = {c["data"]["name"]: c["data"] for c in api.get("/api/info", id=",".join(batch))["data"]["children"]}
        gone = [x for x in batch if x not in alive or is_gone(alive[x])]
        con.executemany("DELETE FROM items WHERE id = ?", [(x,) for x in gone])
        for x, d in alive.items():
            if x not in gone:
                con.execute("UPDATE items SET score = ? WHERE id = ?", (d.get("score"), x))
        dropped += len(gone)
    con.commit()
    print(f"refresh: {len(ids)} checked, {dropped} dropped")


def purge():
    if os.path.exists(DB):
        os.remove(DB)
    print("dataset deleted")


def main(cmd):
    if dt.date.today() > DELETE_AFTER or cmd == "purge":
        return purge()
    con = db()
    api = Reddit()
    {"collect": collect, "refresh": refresh}[cmd](api, con)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "collect")
