import sqlite3, json, threading
from node.crdt import empty_state, merge_states
from node.version_vector import increment

class Store:
    def __init__(self, path, replica):
        self.path, self.replica = path, replica
        self.lock = threading.RLock()
        self._init()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, response TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS counters (replica TEXT PRIMARY KEY, seq INTEGER NOT NULL)")
            c.execute("INSERT OR IGNORE INTO state(id,body) VALUES(1,?)", (json.dumps(empty_state()),))
            c.execute("INSERT OR IGNORE INTO counters(replica,seq) VALUES(?,0)", (self.replica,))

    def get_state(self):
        with self.connect() as c:
            return json.loads(c.execute("SELECT body FROM state WHERE id=1").fetchone()["body"])

    def apply(self, mutator):
        with self.lock, self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            state = json.loads(c.execute("SELECT body FROM state WHERE id=1").fetchone()["body"])
            seq = c.execute("SELECT seq FROM counters WHERE replica=?", (self.replica,)).fetchone()["seq"] + 1
            state, result = mutator(state, seq)
            state.setdefault("version", {})
            state["version"][self.replica] = max(state["version"].get(self.replica, 0), seq)
            c.execute("UPDATE counters SET seq=? WHERE replica=?", (seq, self.replica))
            c.execute("UPDATE state SET body=? WHERE id=1", (json.dumps(state),))
            c.commit()
            return result, state

    def merge(self, incoming):
        with self.lock, self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            current = json.loads(c.execute("SELECT body FROM state WHERE id=1").fetchone()["body"])
            merged = merge_states(current, incoming)
            c.execute("UPDATE state SET body=? WHERE id=1", (json.dumps(merged),))
            c.commit()
            return merged

    def get_request(self, request_id):
        with self.connect() as c:
            row = c.execute("SELECT response FROM requests WHERE request_id=?", (request_id,)).fetchone()
            return json.loads(row["response"]) if row else None

    def save_request(self, request_id, response):
        with self.connect() as c:
            c.execute("INSERT OR REPLACE INTO requests(request_id,response) VALUES(?,?)",
                      (request_id, json.dumps(response)))
