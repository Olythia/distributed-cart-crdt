FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY node/ /app/node/

CMD ["python", "-m", "node.server"]