from node.crdt import empty_state, merge_states, cart_view

def test_merge_is_idempotent_and_add_wins():
    a=empty_state(); a["adds"]["x"]={"user_id":"u","product_id":"p"}
    b=empty_state(); b["adds"]["y"]={"user_id":"u","product_id":"p"}
    b["tombstones"]=["x"]
    merged=merge_states(a,b)
    assert cart_view(merged,"u")["p"]["quantity"] == 1
    assert merge_states(merged,merged)==merged
