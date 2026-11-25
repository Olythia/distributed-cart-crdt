# Local CAS implementation.
# The version check and update are protected by the Store lock.
# This provides atomicity within one node, not global linearizability
# across multiple distributed nodes.

def local_compare_and_set(store, user_id, expected_version, new_marker):

    version_key = "CAS:" + user_id

    # 关键：将版本检查和后续修改放在同一个锁保护范围内。
    # Store 使用 RLock，因此内部调用 store.apply() 可以再次获得该锁。
    with store.lock:

        # 读取当前状态
        state = store.get_state()

        current = int(
            state.get("version", {}).get(version_key, 0)
        )

        # 版本不匹配，直接返回失败
        if current != int(expected_version):
            return False, current

        # 版本匹配，执行修改
        def mutate(s, seq):

            new_version = current + 1

            s.setdefault("version", {})[version_key] = new_version

            s.setdefault("cas_values", {})[user_id] = new_marker

            # 注意：必须返回完整状态字典和操作结果
            return s, new_version

        result, updated_state = store.apply(mutate)

        return bool(result), int(result)