import requests
import threading
import concurrent.futures
import json
import time
BASE_URL = "http://localhost:8001"
# 每组测试使用一个独立的 user_id
TEST_ROUNDS = 20
results = []
def send_cas(user_id, expected_version, client_name, barrier):
    """
    模拟一个客户端提交 CAS 请求。
    两个客户端通过 Barrier 尽量同时发起请求。
    """
    data = {
        "user_id": user_id,
        "expected_version": expected_version,
        "value": client_name
    }
    barrier.wait()
    start = time.perf_counter()
    try:
        response = requests.post(
            BASE_URL + "/cas",
            json=data,
            timeout=10
        )
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "client": client_name,
            "status_code": response.status_code,
            "result": response.json(),
            "elapsed_ms": round(elapsed, 3)
        }
    except Exception as e:
        return {
            "client": client_name,
            "error": str(e)
        }
print("=" * 60)
print("故障七：两个客户端并发执行 CAS")
print("=" * 60)
for round_number in range(1, TEST_ROUNDS + 1):
    user_id = f"fault-test-07-{round_number}"
    # 获取当前版本号
    version_response = requests.get(
        BASE_URL + "/version",
        timeout=10
    )
    version_data = version_response.json()
    version_key = "CAS:" + user_id
    expected_version = int(
        version_data.get(version_key, 0)
    )
    # 两个客户端共用同一个同步屏障
    barrier = threading.Barrier(2)
    print(f"\n第 {round_number} 组测试")
    print("用户 ID：", user_id)
    print("共同预期版本号：", expected_version)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        future_a = executor.submit(
            send_cas,
            user_id,
            expected_version,
            f"Client-A-{round_number}",
            barrier
        )
        future_b = executor.submit(
            send_cas,
            user_id,
            expected_version,
            f"Client-B-{round_number}",
            barrier
        )
        result_a = future_a.result()
        result_b = future_b.result()
    print("客户端 A：")
    print(json.dumps(result_a, ensure_ascii=False, indent=2))
    print("客户端 B：")
    print(json.dumps(result_b, ensure_ascii=False, indent=2))
    success_count = sum(
        1
        for result in [result_a, result_b]
        if result.get("result", {}).get("success") is True
    )
    print("本组成功请求数：", success_count)
    results.append({
        "round": round_number,
        "user_id": user_id,
        "expected_version": expected_version,
        "client_a": result_a,
        "client_b": result_b,
        "success_count": success_count
    })
    time.sleep(0.1)
# 汇总实验结果
single_success = sum(
    1 for item in results
    if item["success_count"] == 1
)
double_success = sum(
    1 for item in results
    if item["success_count"] == 2
)
zero_success = sum(
    1 for item in results
    if item["success_count"] == 0
)
summary = {
    "total_rounds": TEST_ROUNDS,
    "single_success_rounds": single_success,
    "double_success_rounds": double_success,
    "zero_success_rounds": zero_success,
    "details": results
}
with open(
    "cas_concurrency_result.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("\n" + "=" * 60)
print("实验汇总")
print("=" * 60)
print("总测试组数：", TEST_ROUNDS)
print("一个成功、一个失败：", single_success)
print("两个都成功：", double_success)
print("两个都失败：", zero_success)
print("\n结果已保存到：cas_concurrency_result.json")