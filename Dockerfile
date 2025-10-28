FROM python:3.7

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD ["kopf", "run", "--all-namespaces", "main.py", "--verbose"]
