import requests
import time
import random
import argparse
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed


HOTSPOT_USER = "fault-test-05"

NORMAL_USERS = [
    "normal-user-01",
    "normal-user-02",
    "normal-user-03",
    "normal-user-04",
    "normal-user-05",
    "normal-user-06",
    "normal-user-07",
    "normal-user-08",
    "normal-user-09",
    "normal-user-10"
]


def percentile(values, p):
    if not values:
        return 0

    values = sorted(values)
    index = int((len(values) - 1) * p)

    return values[index]


def send_request(url, user_id):
    start = time.perf_counter()

    try:
        response = requests.get(
            url + "/state",
            params={"user_id": user_id},
            timeout=10
        )

        elapsed = (time.perf_counter() - start) * 1000

        return {
            "success": response.status_code == 200,
            "time": elapsed
        }

    except requests.RequestException:
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "success": False,
            "time": elapsed
        }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default="http://localhost:8001"
    )

    parser.add_argument(
        "--requests",
        type=int,
        default=1000
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=20
    )

    parser.add_argument(
        "--hotspot-ratio",
        type=float,
        default=0.5
    )

    args = parser.parse_args()

    tasks = []

    for _ in range(args.requests):
        if random.random() < args.hotspot_ratio:
            user_id = HOTSPOT_USER
        else:
            user_id = random.choice(NORMAL_USERS)

        tasks.append(user_id)

    print("========== 热点压力测试 ==========")
    print("目标节点：", args.url)
    print("总请求数：", args.requests)
    print("并发线程：", args.workers)
    print("热点请求比例：", args.hotspot_ratio)
    print("热点用户：", HOTSPOT_USER)
    print("=================================")

    results = []

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:

        futures = [
            executor.submit(send_request, args.url, user_id)
            for user_id in tasks
        ]

        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.perf_counter() - start_time

    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    times = [r["time"] for r in results]

    avg_time = statistics.mean(times) if times else 0

    qps = len(results) / total_time if total_time else 0

    print("\n========== 测试结果 ==========")
    print("总请求数：", len(results))
    print("成功请求：", success)
    print("失败请求：", failed)
    print("成功率：", round(success / len(results) * 100, 2), "%")
    print("总耗时：", round(total_time, 3), "秒")
    print("QPS：", round(qps, 2))
    print("平均响应时间：", round(avg_time, 3), "ms")
    print("P95响应时间：", round(percentile(times, 0.95), 3), "ms")
    print("P99响应时间：", round(percentile(times, 0.99), 3), "ms")
    print("==============================")

    print("\n节点监控数据：")

    metrics = requests.get(
        args.url + "/admin/metrics",
        timeout=10
    ).json()

    print(metrics)


if __name__ == "__main__":
    main()