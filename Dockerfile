FROM python:3.12-slim AS rhvoice-build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git g++ scons pkg-config \
    && rm -rf /var/lib/apt/lists/*

# RHVoice core plus only the pieces we need: the Spanish language data and
# the Mateo voice (the free blind-community voice).
RUN git clone --depth 1 https://github.com/RHVoice/RHVoice.git /rhvoice \
    && cd /rhvoice \
    && git submodule update --init --depth 1 \
         external/libs/boost data/languages/Spanish data/voices/Mateo src/scripts/Spanish

WORKDIR /rhvoice
RUN scons -j2 && scons install prefix=/opt/rhvoice

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng libgomp1 curl libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=rhvoice-build /opt/rhvoice /opt/rhvoice
ENV LD_LIBRARY_PATH=/opt/rhvoice/lib

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Free Piper Spanish voices, rendered locally by piper-tts at synth time.
RUN mkdir -p /app/piper-voices \
    && base="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es" \
    && for spec in \
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
