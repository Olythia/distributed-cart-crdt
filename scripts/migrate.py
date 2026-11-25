import argparse
import sys
import time
import requests


def migrate(source, target, user_id, batch_size, delay):
    print("=" * 55)
    print("分布式购物车定向数据迁移程序")
    print("=" * 55)

    # 1. 获取源节点完整状态
    print("\n[1] 正在读取源节点数据...")

    try:
        response = requests.get(
            source + "/state",
            timeout=10
        )
        response.raise_for_status()
        state = response.json()

    except requests.RequestException as e:
        print("源节点数据读取失败：", e)
        return False

    raw_state = state.get("cart", {})

    all_adds = raw_state.get("adds", {})
    tombstones = set(raw_state.get("tombstones", []))
    version = state.get("version", {})

    # 2. 只筛选指定用户当前有效的商品记录
    live_adds = {}

    for tag, item in all_adds.items():
        if (
            str(item.get("user_id")) == user_id
            and tag not in tombstones
        ):
            live_adds[tag] = item

    records = sorted(live_adds.items())

    print("源节点数据读取成功")
    print("指定用户：", user_id)
    print("该用户有效商品记录数量：", len(records))
    print("本次不迁移其他用户的历史数据和删除记录")

    if not records:
        print("没有找到可迁移的有效商品记录。")
        return False

    # 3. 分批迁移
    total = len(records)
    total_batches = (total + batch_size - 1) // batch_size

    print("\n[2] 开始分批迁移")
    print("每批记录数量：", batch_size)
    print("总记录数量：", total)
    print("总批次数：", total_batches)

    for i in range(total_batches):
        start = i * batch_size
        end = min(start + batch_size, total)

        batch = records[start:end]

        payload = {
            "adds": dict(batch),
            "tombstones": [],
            "version": version
        }

        print(
            f"\n正在发送第 {i + 1}/{total_batches} 批，"
            f"本批记录数量：{len(batch)}"
        )

        try:
            result = requests.post(
                target + "/internal/sync",
                json=payload,
                timeout=5
            )
            result.raise_for_status()

            print(f"第 {i + 1} 批迁移成功")

        except requests.RequestException as e:
            print("\n迁移中断！")
            print("失败批次：", i + 1)
            print("错误信息：", e)
            print("已经发送的批次不会主动回滚。")
            print("重新启动目标节点后，可以再次执行完整迁移。")
            return False

        if i < total_batches - 1:
            time.sleep(delay)

    print("\n" + "=" * 55)
    print("本次定向数据迁移全部完成！")
    print("迁移用户：", user_id)
    print("迁移记录数量：", total)
    print("迁移批次数：", total_batches)
    print("=" * 55)

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="分布式购物车定向迁移程序"
    )

    parser.add_argument(
        "--source",
        default="http://localhost:8001"
    )

    parser.add_argument(
        "--target",
        default="http://localhost:8004"
    )

    parser.add_argument(
        "--user-id",
        default="fault-test-05"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=3
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        print("每批记录数量必须大于0")
        sys.exit(1)

    success = migrate(
        args.source,
        args.target,
        args.user_id,
        args.batch_size,
        args.delay
    )

    sys.exit(0 if success else 1)