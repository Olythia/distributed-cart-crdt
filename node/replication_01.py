import os, threading, time, requests
from node.crdt import merge_states

class Replicator:
    def __init__(self, store, node_id):
        self.store, self.node_id = store, node_id
        self.peers = [p.strip() for p in os.getenv("PEERS", "").split(",") if p.strip()]
        self.enabled = True
        self.blocked = set()
        self.delay_seconds = 0
        self.duplicate_count = 1
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while self.running:
            if self.enabled:
                for peer in self.peers:
                    if peer in self.blocked: continue
                    try:
                        if self.delay_seconds: time.sleep(self.delay_seconds)
                        payload = self.store.get_state()
                        for _ in range(max(1, self.duplicate_count)):
                            requests.post(peer + "/internal/sync", json=payload, timeout=2)
                    except requests.RequestException:
                        pass
            time.sleep(1)

    def set_peer(self, peer, blocked):
        if blocked: self.blocked.add(peer)
        else: self.blocked.discard(peer)
