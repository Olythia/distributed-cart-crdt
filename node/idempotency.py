# Idempotency records are stored in SQLite. Reuse the same request_id for retries.
def cached_response(store, request_id):
    return store.get_request(request_id) if request_id else None
