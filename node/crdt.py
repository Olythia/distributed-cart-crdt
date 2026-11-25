import json

def empty_state():
    return {"adds": {}, "tombstones": [], "version": {}}

def merge_states(left, right):
    out = {"adds": {}, "tombstones": [], "version": {}}
    for src in (left or empty_state(), right or empty_state()):
        for tag, item in src.get("adds", {}).items():
            out["adds"][tag] = item
        out["tombstones"] = sorted(set(out["tombstones"]) | set(src.get("tombstones", [])))
        for replica, seq in src.get("version", {}).items():
            out["version"][replica] = max(out["version"].get(replica, 0), int(seq))
    return out

def live_items(state, user_id=None):
    dead = set(state.get("tombstones", []))
    return {tag: item for tag, item in state.get("adds", {}).items()
            if tag not in dead and (user_id is None or item["user_id"] == user_id)}

def cart_view(state, user_id):
    grouped = {}
    for tag, item in live_items(state, user_id).items():
        p = item["product_id"]
        if p not in grouped:
            grouped[p] = {"product_name": item.get("product_name", p), "quantity": 0, "items": []}
        grouped[p]["quantity"] += 1
        grouped[p]["items"].append({"item_id": tag, "product_id": p})
    for v in grouped.values():
        v["items"].sort(key=lambda x: x["item_id"])
    return grouped
