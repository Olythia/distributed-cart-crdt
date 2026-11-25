# Distributed Shopping Cart KV Store

第一阶段可运行基础版：Python 3.11 + Flask + SQLite + Docker Compose + OR-Set + Version Vector。

## 启动
在项目根目录 PowerShell 执行：
```powershell
docker compose up -d --build
docker compose ps
```
节点地址：A `http://localhost:8001`，B `:8002`，C `:8003`。

## 添加、查询
```powershell
$body = @{user_id="1001"; product_id="A001"; product_name="商品A"; quantity=2; request_id="req-001"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/add -ContentType "application/json" -Body $body
Invoke-RestMethod "http://localhost:8001/state?user_id=1001"
```
再查询B/C。首次同步等待约2秒。

## 删除
```powershell
$body = @{user_id="1001"; product_id="A001"; quantity=1} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/remove -ContentType "application/json" -Body $body
```

## 当前阶段边界
- OR-Set采用 add 集合与 tombstone 集合并集，删除只删除本副本已观察到的实例。
- Version Vector记录各副本因果序号。
- SQLite事务保存状态与序号，Docker bind mount持久化数据库。
- `request_id`目前在发起节点本地去重；尚不能宣称跨节点端到端幂等。
- `/cas` 是单节点本地CAS，不是跨副本线性一致CAS。
- `/admin/partition` 是复制链路级应用层隔离模拟，不是操作系统/真实网络层断网。
- traffic接口可模拟复制延迟和重复投递。实验结论必须注明模拟层级。
- 后续阶段应加入跨节点复制请求去重、可靠操作日志、节点D迁移、时钟回拨注入、响应丢失代理、压测统计和图表；本包不伪称这些实验已全部实现。

## 测试
在本机安装Python 3.11后，在项目根目录：
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="."
pytest -q
```
