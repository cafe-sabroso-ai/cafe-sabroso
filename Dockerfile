FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /preview
RUN pip install --no-cache-dir fastapi==0.121.2 uvicorn==0.38.0 websockets==16.1.1 httpx==0.28.1 edge-tts==7.3.1
COPY preview_runtime/ /preview/
RUN python -m compileall -q /preview
EXPOSE 10000
CMD ["sh","-c","uvicorn rehearsal_app:app --host 0.0.0.0 --port ${PORT:-10000}"]
