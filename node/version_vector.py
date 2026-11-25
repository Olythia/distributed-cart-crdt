def increment(vector, replica):
    result = dict(vector or {})
    result[replica] = int(result.get(replica, 0)) + 1
    return result

def merge_vectors(a, b):
    keys = set(a or {}) | set(b or {})
    return {k: max(int((a or {}).get(k, 0)), int((b or {}).get(k, 0))) for k in keys}

def compare(a, b):
    a, b = a or {}, b or {}
    le = all(int(a.get(k, 0)) <= int(b.get(k, 0)) for k in set(a) | set(b))
    ge = all(int(a.get(k, 0)) >= int(b.get(k, 0)) for k in set(a) | set(b))
    if le and ge: return "equal"
    if le: return "before"
    if ge: return "after"
    return "concurrent"
