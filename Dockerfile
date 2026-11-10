FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Free Piper Spanish voices, rendered locally by piper-tts at synth time.
RUN mkdir -p /app/piper-voices \
    && base="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es" \
    && for spec in \
         "es_AR/daniela/high/es_AR-daniela-high" \
         "es_MX/claude/high/es_MX-claude-high" \
         "es_MX/ald/medium/es_MX-ald-medium" \
         "es_ES/davefx/medium/es_ES-davefx-medium" \
         "es_ES/sharvard/medium/es_ES-sharvard-medium"; do \
         name=$(basename "$spec"); \
         curl -fsSL "$base/$spec.onnx" -o "/app/piper-voices/$name.onnx" \
         && curl -fsSL "$base/$spec.onnx.json" -o "/app/piper-voices/$name.onnx.json"; \
       done

COPY app.py whatsapp_app.py .

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
