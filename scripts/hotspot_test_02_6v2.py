import argparse
import random
import time
import requests

from concurrent.futures import ThreadPoolExecutor, as_completed


def send_request(url, user_id):
    """
    向指定节点发送购物车状态查询请求
    """
    start_time = time.perf_counter()

    try:
        response = requests.get(
            f"{url}/state",
            params={"user_id": user_id},
            timeout=10
        )

        elapsed = (time.perf_counter() - start_time) * 1000

        if response.status_code == 200:
            return {
                "success": True,
                "latency": elapsed,
                "node_url": url
            }

        return {
            "success": False,
            "latency": elapsed,
            "node_url": url,
            "error": f"HTTP {response.status_code}"
        }

    except requests.RequestException as e:
        elapsed = (time.perf_counter() - start_time) * 1000

        return {
            "success": False,
            "latency": elapsed,
            "node_url": url,
            "error": str(e)
        }


def percentile(values, percent):
    """
    计算百分位响应时间
    """
    if not values:
        return 0

    values = sorted(values)

    index = int(len(values) * percent / 100)

    if index >= len(values):
        index = len(values) - 1

    return values[index]


def get_node_metrics(url):
    """
    获取节点的请求监控指标
    """
    try:
        response = requests.get(
            f"{url}/admin/metrics",
            timeout=5
        )

        if response.status_code == 200:
            return response.json()

    except requests.RequestException as e:
        print(f"获取节点 {url} 监控指标失败：{e}")

    return None


def get_node_cache(url):
    """
    获取节点的缓存统计信息
    """
    try:
        response = requests.get(
            f"{url}/admin/cache",
            timeout=5
        )

        if response.status_code == 200:
            return response.json()

    except requests.RequestException as e:
        print(f"获取节点 {url} 缓存信息失败：{e}")

    return None


def main():
    parser = argparse.ArgumentParser(
        description="分布式购物车热点负载测试"
    )

    parser.add_argument(
        "--url",
        default=None,
        help="单节点测试地址，例如 http://localhost:8001"
    )

    parser.add_argument(
        "--nodes",
        default=None,
        help="多节点地址，使用英文逗号分隔"
    )

    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
        help="请求总数"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="并发线程数"
    )

    parser.add_argument(
        "--hotspot-ratio",
        type=float,
        default=0.5,
        help="热点用户请求比例"
    )

    parser.add_argument(
        "--hotspot-user",
        default="fault-test-05",
        help="热点用户ID"
    )

    args = parser.parse_args()

    # 确定测试节点
    if args.nodes:
        nodes = [
            item.strip().rstrip("/")
            for item in args.nodes.split(",")
            if item.strip()
        ]
    elif args.url:
        nodes = [args.url.rstrip("/")]
    else:
        nodes = ["http://localhost:8001"]

    if not nodes:
        print("错误：没有配置有效的节点地址")
        return

    if args.requests <= 0 or args.workers <= 0:
        print("错误：请求数量和线程数必须大于0")
        return

    if not 0 <= args.hotspot_ratio <= 1:
        print("错误：热点比例必须在0到1之间")
        return

    print("=" * 60)
    print("分布式购物车热点负载测试")
    print("=" * 60)

    print(f"请求总数：{args.requests}")
    print(f"并发线程：{args.workers}")
    print(f"热点比例：{args.hotspot_ratio}")
    print(f"热点用户：{args.hotspot_user}")

    print("\n参与测试的节点：")

    for node in nodes:
        print(f"  {node}")

    # 生成请求任务
    tasks = []

    random.seed(42)

    for i in range(args.requests):

        # 按热点比例生成用户
        if random.random() < args.hotspot_ratio:
            user_id = args.hotspot_user
        else:
            normal_id = random.randint(1, 10)
            user_id = f"normal-user-{normal_id:02d}"

        # 多节点轮询分配
        node_url = nodes[i % len(nodes)]

        tasks.append((node_url, user_id))

    # 统计每个节点分配到的请求数
    print("\n各节点分配请求数量：")

    node_task_counts = {}

    for node in nodes:
        count = sum(1 for task in tasks if task[0] == node)
        node_task_counts[node] = count
        print(f"  {node}: {count} 个请求")

    print("\n开始执行压力测试……")

    results = []

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:

        futures = [
            executor.submit(send_request, node_url, user_id)
            for node_url, user_id in tasks
        ]

        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.perf_counter() - start_time

    # 统计测试结果
    success_results = [
        item for item in results if item["success"]
    ]

    failed_results = [
        item for item in results if not item["success"]
    ]

    latencies = [
        item["latency"] for item in success_results
    ]

    success_count = len(success_results)
    failed_count = len(failed_results)

    success_rate = (
        success_count / args.requests * 100
    )

    qps = (
        args.requests / total_time
        if total_time > 0 else 0
    )

    average_latency = (
        sum(latencies) / len(latencies)
        if latencies else 0
    )

    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)

    print("\n" + "=" * 60)
    print("压力测试结果")
    print("=" * 60)

    print(f"请求总数：{args.requests}")
    print(f"成功请求：{success_count}")
    print(f"失败请求：{failed_count}")
    print(f"成功率：{success_rate:.2f}%")
    print(f"总耗时：{total_time:.3f} 秒")
    print(f"QPS：{qps:.2f}")
    print(f"平均响应时间：{average_latency:.3f} ms")
    print(f"P95响应时间：{p95:.3f} ms")
    print(f"P99响应时间：{p99:.3f} ms")

    if failed_results:
        print("\n失败请求示例：")

        for item in failed_results[:5]:
            print(
                f"节点：{item['node_url']}，"
                f"错误：{item.get('error', '未知错误')}"
            )

    # 获取每个节点的监控数据
    print("\n" + "=" * 60)
    print("各节点请求监控情况")
    print("=" * 60)

    for node in nodes:

        metrics = get_node_metrics(node)

        print(f"\n节点：{node}")

        if metrics:
            print(f"节点名称：{metrics.get('node')}")
            print(
                f"总请求数："
                f"{metrics.get('total_requests')}"
            )
            print(
                f"读取请求数："
                f"{metrics.get('read_requests')}"
            )
            print(
                f"平均读取耗时："
                f"{metrics.get('average_read_time_ms')} ms"
            )
            print(
                f"最大读取耗时："
                f"{metrics.get('max_read_time_ms')} ms"
            )
            print(
                f"请求路径统计："
                f"{metrics.get('path_counts')}"
            )

        else:
            print("未能获取监控数据")

    # 获取每个节点的缓存数据
    print("\n" + "=" * 60)
    print("各节点缓存统计情况")
    print("=" * 60)

    for node in nodes:

        cache = get_node_cache(node)

        print(f"\n节点：{node}")

        if cache:
            print(f"缓存条目：{cache.get('cache_entries')}")
            print(f"缓存命中：{cache.get('cache_hits')}")
            print(f"缓存未命中：{cache.get('cache_misses')}")
            print(f"缓存命中率：{cache.get('hit_rate')}%")
            print(f"缓存TTL：{cache.get('ttl_seconds')}秒")

        else:
            print("未能获取缓存数据")

    print("\n测试结束。")


if __name__ == "__main__":
    main()