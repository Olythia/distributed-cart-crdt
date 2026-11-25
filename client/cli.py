import argparse, requests, json
p=argparse.ArgumentParser()
p.add_argument("--node", default="http://localhost:8001")
p.add_argument("action", choices=["add","remove","state","get"])
p.add_argument("--user", default="1001"); p.add_argument("--product", default="A001")
p.add_argument("--name", default="商品A"); p.add_argument("--quantity", type=int, default=1)
p.add_argument("--request-id", default=None)
a=p.parse_args()
if a.action in ("add","remove"):
    body={"user_id":a.user,"product_id":a.product,"product_name":a.name,"quantity":a.quantity}
    if a.request_id: body["request_id"]=a.request_id
    r=requests.post(a.node+"/"+a.action,json=body)
elif a.action=="state": r=requests.get(a.node+"/state",params={"user_id":a.user})
else: r=requests.get(a.node+"/get",params={"user_id":a.user,"product_id":a.product})
print(json.dumps(r.json(),ensure_ascii=False,indent=2))
