FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[api,google]"
EXPOSE 8000
CMD ["python", "api_server.py"]
