FROM python:alpine3.21

COPY . /app/

WORKDIR /app

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8080

CMD ["python", "main.py"]