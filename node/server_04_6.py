import os, uuid, json
from flask import Flask, request, jsonify
from node.storage import Store
from node.crdt import cart_view, live_items
from node.replication import Replicator
from node.idempotency import cached_response
from node.cas import local_compare_and_set

app = Flask(__name__)
NODE_ID = os.getenv("NODE_ID", "A")
store = Store(os.getenv("DB_PATH", "/tmp/cart.db"), NODE_ID)
replicator = Replicator(store, NODE_ID)

# 故障六：热点访问监控
import time
import threading
from collections import defaultdict

metrics_lock = threading.Lock()

hotspot_metrics = {
    "total_requests": 0,
    "read_requests": 0,
    "total_read_time": 0.0,
    "max_read_time": 0.0,
    "path_counts": defaultdict(int)
}


@app.before_request
def record_request_start():
    request._start_time = time.perf_counter()


@app.after_request
def record_request_metrics(response):
    elapsed = time.perf_counter() - getattr(
        request, "_start_time", time.perf_counter()
    )

    with metrics_lock:
        hotspot_metrics["total_requests"] += 1

        path = request.path
        hotspot_metrics["path_counts"][path] += 1

        if path in ["/state", "/get"]:
            hotspot_metrics["read_requests"] += 1
            hotspot_metrics["total_read_time"] += elapsed

            hotspot_metrics["max_read_time"] = max(
                hotspot_metrics["max_read_time"],
                elapsed
            )

    return response

@app.get("/health")
def health():
    return jsonify(ok=True, node=NODE_ID)

@app.get("/state")
def state():
    s = store.get_state()
    uid = request.args.get("user_id")
    return jsonify(node=NODE_ID, version=s.get("version", {}), cart=cart_view(s, uid) if uid else s)

@app.get("/version")
def version():
    v = store.get_state().get("version", {})
    return jsonify(v)

@app.post("/add")
def add():
    d = request.get_json(force=True)
    rid = d.get("request_id")
    old = cached_response(store, rid)
    if old: return jsonify(old)
    uid, pid = str(d["user_id"]), str(d["product_id"])
    qty = int(d.get("quantity", 1))
    if qty < 1 or qty > 100: return jsonify(error="quantity must be 1..100"), 400
    def mutate(s, seq):
        tags = []
        for i in range(qty):
            tag = f"{NODE_ID}:{seq}:{i}:{uuid.uuid4().hex}"
            s["adds"][tag] = {"user_id": uid, "product_id": pid,
                              "product_name": d.get("product_name", pid)}
            tags.append(tag)
        return s, {"added": tags, "quantity_added": qty}
    result, s = store.apply(mutate)
    response = {"node": NODE_ID, **result, "version": s.get("version", {})}
    if rid: store.save_request(rid, response)
    return jsonify(response)

@app.post("/remove")
def remove():
    d = request.get_json(force=True)
    uid, pid = str(d["user_id"]), str(d["product_id"])
    qty = max(1, int(d.get("quantity", 1)))
    def mutate(s, seq):
        dead = set(s["tombstones"])
        candidates = [tag for tag, item in s["adds"].items()
                      if tag not in dead and item["user_id"] == uid and item["product_id"] == pid]
        removed = candidates[:qty]
        s["tombstones"] = sorted(dead | set(removed))
        return s, {"removed": removed, "removed_count": len(removed)}
    result, s = store.apply(mutate)
    return jsonify(node=NODE_ID, **result, version=s.get("version", {}))

@app.get("/get")
def get_product():
    uid, pid = request.args["user_id"], request.args["product_id"]
    s = store.get_state()
    cart = cart_view(s, uid)
    return jsonify(product_id=pid, quantity=cart.get(pid, {}).get("quantity", 0))

@app.post("/internal/sync")
def sync():
    merged = store.merge(request.get_json(force=True))
    return jsonify(ok=True, version=merged.get("version", {}))

@app.post("/admin/replication")
def admin_replication():
    d = request.get_json(force=True)
    replicator.enabled = bool(d.get("enabled", True))
    return jsonify(enabled=replicator.enabled)

@app.post("/admin/partition")
def admin_partition():
    d = request.get_json(force=True)
    peer = d["peer"].rstrip("/")
    replicator.set_peer(peer, bool(d["blocked"]))
    return jsonify(peer=peer, blocked=bool(d["blocked"]))

@app.post("/admin/traffic")
def admin_traffic():
    d = request.get_json(force=True)
    replicator.delay_seconds = max(0, min(10, int(d.get("delay_seconds", 0))))
    replicator.duplicate_count = max(1, min(3, int(d.get("duplicate_count", 1))))
    return jsonify(delay_seconds=replicator.delay_seconds, duplicate_count=replicator.duplicate_count)


@app.post("/admin/chaos/enqueue")
def chaos_enqueue():
    d = request.get_json(force=True)

    peer = str(d["peer"])
    delay_seconds = int(d.get("delay_seconds", 10))
    try:
        result = replicator.enqueue_message(
            peer,
            delay_seconds
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@app.get("/admin/chaos/queue")
def chaos_queue():
    return jsonify(
    node=NODE_ID,
    messages=replicator.get_queue()
    )


@app.post("/admin/chaos/release")
def chaos_release():
    d = request.get_json(force=True)

    message_id = str(d["message_id"])
    result, status_code = replicator.release_message(
        message_id
    )
    return jsonify(result), status_code

@app.post("/cas")
def cas():
    d = request.get_json(force=True)
    ok, version = local_compare_and_set(store, str(d["user_id"]),
                                        int(d["expected_version"]), d.get("value"))
    return jsonify(success=bool(ok), version=version, scope="local-only")

@app.get("/admin/metrics")
def metrics():
    s = store.get_state()

    with metrics_lock:
        total = hotspot_metrics["total_requests"]
        reads = hotspot_metrics["read_requests"]

        avg_time = (
            hotspot_metrics["total_read_time"] / reads
            if reads else 0
        )

        result = {
            "node": NODE_ID,
            "total_requests": total,
            "read_requests": reads,
            "average_read_time_ms": round(avg_time * 1000, 3),
            "max_read_time_ms": round(
                hotspot_metrics["max_read_time"] * 1000, 3
            ),
            "path_counts": dict(hotspot_metrics["path_counts"])
        }

    result["live_items"] = len(live_items(s))
    result["version"] = s.get("version", {})

    return jsonify(result)


@app.post("/admin/reset-metrics")
def reset_metrics():
    with metrics_lock:
        hotspot_metrics["total_requests"] = 0
        hotspot_metrics["read_requests"] = 0
        hotspot_metrics["total_read_time"] = 0.0
        hotspot_metrics["max_read_time"] = 0.0
        hotspot_metrics["path_counts"].clear()

    return jsonify(ok=True, node=NODE_ID)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
