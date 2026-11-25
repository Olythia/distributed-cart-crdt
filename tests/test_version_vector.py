from node.version_vector import compare, merge_vectors

def test_vector_compare():
    assert compare({"A":1},{"A":2})=="before"
    assert compare({"A":2},{"B":1})=="concurrent"
    assert merge_vectors({"A":1},{"A":2,"B":1})=={"A":2,"B":1}
