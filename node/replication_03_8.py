import os
import threading
import time
import uuid
import requests


class Replicator:

    def __init__(self, store, node_id):
        self.store = store
        self.node_id = node_id

        self.peers = [
            p.strip()
            for p in os.getenv("PEERS", "").split(",")
            if p.strip()
        ]

        self.enabled = True
        self.blocked = set()

        self.delay_seconds = 0
        self.duplicate_count = 1

        # 故障八：模拟系统时钟偏移量，单位为秒
        self.clock_offset_seconds = 0

        # 故障注入：可控消息队列
        self.message_queue = []
        self.queue_lock = threading.RLock()

        self.running = True

        # 启动自动同步线程
        self.thread = threading.Thread(
            target=self.loop,
            daemon=True
        )
        self.thread.start()

    def _now(self):
        """
        获取模拟系统时间。
        正常情况下偏移量为0；
        故障注入时可以设置为-60，模拟时钟回拨60秒。
        """
        return time.time() + self.clock_offset_seconds

    # 原有自动同步循环
    def loop(self):
        while self.running:

            if self.enabled:

                for peer in self.peers:

                    if peer in self.blocked:
                        continue

                    try:
                        if self.delay_seconds:
                            time.sleep(self.delay_seconds)

                        payload = self.store.get_state()

                        for _ in range(max(1, self.duplicate_count)):
                            requests.post(
                                peer + "/internal/sync",
                                json=payload,
                                timeout=2
                            )

                    except requests.RequestException:
                        pass

            time.sleep(1)

    # 设置节点复制连接
    def set_peer(self, peer, blocked):
        if blocked:
            self.blocked.add(peer)
        else:
            self.blocked.discard(peer)

    # 创建一条延迟消息
    def enqueue_message(self, peer, delay_seconds=10):

        peer = peer.rstrip("/")

        if peer not in self.peers:
            raise ValueError(
                "目标节点不是当前节点配置的复制节点"
            )

        delay_seconds = max(
            0,
            min(120, int(delay_seconds))
        )

        # 保存当前状态快照
        payload = self.store.get_state()

        message = {
            "message_id": uuid.uuid4().hex,
            "peer": peer,
            "payload": payload,
            "created_at": self._now(),
            "ready_at": self._now() + delay_seconds,
            "delay_seconds": delay_seconds
        }

        with self.queue_lock:
            self.message_queue.append(message)

        return {
            "message_id": message["message_id"],
            "peer": peer,
            "delay_seconds": delay_seconds,
            "snapshot_version": payload.get("version", {}),
            "queue_length": len(self.message_queue)
        }

    # 查看消息队列
    def get_queue(self):

        with self.queue_lock:
            return [
                {
                    "message_id": item["message_id"],
                    "peer": item["peer"],
                    "delay_seconds": item["delay_seconds"],
                    "remaining_seconds": max(
                        0,
                        round(
                            item["ready_at"] - self._now(),
                            2
                        )
                    ),
                    "snapshot_version": item["payload"].get(
                        "version", {}
                    )
                }
                for item in self.message_queue
            ]

    # 手动发送指定消息
    def release_message(self, message_id):

        with self.queue_lock:

            message = next(
                (
                    item for item in self.message_queue
                    if item["message_id"] == message_id
                ),
                None
            )

            if message is None:
                return {
                    "success": False,
                    "error": "消息不存在"
                }, 404

            remaining = message["ready_at"] - self._now()

            if remaining > 0:
                return {
                    "success": False,
                    "error": "消息延迟时间尚未结束",
                    "remaining_seconds": round(
                        remaining, 2
                    )
                }, 409

            peer = message["peer"]
            payload = message["payload"]

            try:
                response = requests.post(
                    peer + "/internal/sync",
                    json=payload,
                    timeout=5
                )

                response.raise_for_status()

            except requests.RequestException as exc:
                return {
                    "success": False,
                    "error": str(exc)
                }, 502

            self.message_queue.remove(message)

            return {
                "success": True,
                "message_id": message_id,
                "peer": peer,
                "snapshot_version": payload.get(
                    "version", {}
                )
            }, 200