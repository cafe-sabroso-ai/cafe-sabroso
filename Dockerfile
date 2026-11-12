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

COPY app.py whatsapp_app.py webapp.py .

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]

# Tested web release. Keep bot entrypoints and dependencies unchanged.
COPY web1431-*.b64 /tmp/web1431/
RUN cat /tmp/web1431/web1431-*.b64 | base64 -d > /tmp/web1431.tar.xz \
    && echo "6e44c5383e22b7e33f4d22f841e5fd1530d11bdbca88cdfedc01e4301727a174  /tmp/web1431.tar.xz" | sha256sum -c - \
    && python -c "import tarfile; tarfile.open('/tmp/web1431.tar.xz').extractall('/app')" \
    && rm -rf /tmp/web1431 /tmp/web1431.tar.xz

# Approved disconnect/reconnect-only overlay, with input/output integrity checks.
RUN python -c "import base64; exec(base64.b64decode('IyBEaXNjb25uZWN0L3JlY29ubmVjdC1vbmx5IHBhdGNoLiBWZXJpZnkgYmFzZSBhbmQgcmVzdWx0IGJlZm9yZSBjaGFuZ2luZyBydW50aW1lLgpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgKaW1wb3J0IGhhc2hsaWIsIGpzb24sIGJhc2U2NCwgbHptYQpwPVBhdGgoJy9hcHAvd2ViYXBwLnB5JykKb3JpZ2luYWw9cC5yZWFkX2J5dGVzKCkKYXNzZXJ0IGhhc2hsaWIuc2hhMjU2KG9yaWdpbmFsKS5oZXhkaWdlc3QoKT09J2ViZDY0ZmUxNjlkMzNhMmY1YWQzNjFmZTc0YTAzMzhjYWQyMTU2YmRmYWFhYzJiODBhZmU0YzcxMjM3YmI4OTInLCAnVW5leHBlY3RlZCB3ZWIgcnVudGltZSBiYXNlJwpsaW5lcz1vcmlnaW5hbC5kZWNvZGUoKS5zcGxpdGxpbmVzKFRydWUpCmNoYW5nZXM9anNvbi5sb2Fkcyhsem1hLmRlY29tcHJlc3MoYmFzZTY0LmI2NGRlY29kZSgnL1RkNldGb0FBQVRtMXJSR0FnQWhBUllBQUFCMEwrV2o0QlpsQjZKZEFDM2d3d2JqVVFRSnZ6aHcxdXIzNWkxNFhReWhLaElBRndyd3hPa25kWjIycWxSYWlCSlV3UWk4Nk5HU1MvS1N5dGJkcmhkZ2FLa2dkVjcvNkRWT09SYkJCUm1saTN4UlNxWlVpdUcvUDRRMWJ6T1QrUDZFMGRWRHZkV1hVVGo3NzgraTlZREhTYTdWcVQvMkUzTEcrV2JQd2t4bTkrRGIxSmc5SzluMC9teTRkdU1jS0dtSWtoK2FrWmpMK1BOWHpiM2c4WmNvUlBOOEZPL2NXRG1wNFpjMytNMWNqWi9SVXdWaXVQeVhrbG4vV0xWTEpiTFNZd0FXMG92SjMzSGpJZnlMRW5WQjFXV2V3cURRbG12U2ttNnpGbmg0UEhESDhGTTc5YkorZHU5dDVyWW5jc1cyaXRPRVg4RlFDWk1MUURGZG5PeHd0bHlCTmFRSTFwL2VRTnpyaDJsYjRRcklPcW5mWHUrUUQ4azEzTFRDWG9nR1BCN3JoRnhhZG9TQk1rQW9mMmNiS0FjaW40WHg4WUZWRWVPZGtQcXdpb2lqa1JtdVQxV09wMW9aclBlLzBCcXIyc29wMVNWbGFRT044bjRMTC8rV1NRMktYVnhoS3BFTGN5aDU4cU5PNThCOEhVSHQyeDhLWmZKR0E5SUZ3NDBWQlBYR0MxWFpjaDhEcFd6cDN1N0JQbXlXTUVHb3Rwa2dxK1J3RWhZY05iaGNHYkVveHlxbWduaGQ0bWlIYWVyblQydEQ4SzNWdUFNTEJXU3hUdTV6aW4vdzVxaFdTUTBUOXBITGp2LzFnRkVCZCtoSzgveHRWdjFnWGRRL3ZMT3RzTUxQOHo1WDFYNEMyeFNzQVJGZmh5dGM3UVdnem1EK3NhcXVJTTdDRlpKL2E2b2VydmhjbG8wckRUcnBsT3RXMi8vWjJiR0E2OEhTS01zcFdseXVYaytZZmR3cmdyY3FJaVFBMnI3dUI0cmM2TVNtaWR5MDU4NmFhZFpDYTI5aEJaK3RuNVVmZEEwbVdXbTcwNGt5NUNPQnpYbWM1ZC9LNHNoQTIwcFZKR3RRTzg2aHhJbXVMV0xHRVB3bkVoZGJYankwdUVsL0RNaU5peTNlbncwRUlFOWFZL3BweWhBbmdRZzRGTEZvb2U2R2VzR1dZWVFuam82c2J3cUtkYlIxb09wMVZoZENJOWxJWm93aFZKVk93K25pYkNXTU9QUmhjcHVUNElSUVF5Mm1MaWlheHlFc094T0cxUE5vZXVYcnFuR0VvYnBoZHcxelBWeDBNVWdQVzN5cVRCM0Z0Qitra3BiS1ArVlJ3dzkrZ2FQdldKb2Z0TmlHcDI5em9FQTU1RnEvNXBPV0dPZS90c0tMd1gwTTAvM3JyaDg5bWpGZkx6WlNhNXlXdVM2UmFDY0NDUHhIdEFINGhhRFYwRjV4bi9qeVJMeEQ5aUlhN2hXM3ZFaExnWmZ4djJXSzdLdkdSQVEvaElRSnpZM1pjZnNINzl6RHpkR3pFR1RINGtKNWF6Z1E3SStIczRRNWIyWGhrT25mdG5CTUZFVmpKKzEwZzd0N3lsdkFjaG5kQUg0N1A1VS9GZ1dPaFNKdG94NVlxV29JOHo4bzdPbkpIS1l2SHRVUXFmcGFEKzRwNlUvVTFESUdoTU13blN4MkR2dXBkMUw1Q2hpbnhRK2J1UDY5UGViYlJQa2ZabFhPSFg5SVd6U3paSzZlMldYeld2QWNYL0RKN3lwQmxYTnQzVEtqVjBNZTkySFVZcS9qM0ZtNDNMSXN2M1BmdER3em1QNWdVeHYzdmxqRG5tYlg3VXZpb0ZhUnpqaU43ZW9UT3ZBWUVRZlR1R0ZLS3cxT093MUdFOXBURjh3NVF4Y2E2cU9GTEZIMTNpMjRiZVgxUUZIRzBwejA3c0k1d2EwdDFrS2gxejFWdzlJZ0VpQ0FCNk0rTDkyRERxNkdxbWNkV3hCZG5KeHlwckhONnB5eXVReHFPT0dvOGJrVGZLeDA0WnU1QVQyWGozQVVqeWJzL0RWeGx0TlZyelo1UzMwUSsva0pLYWpER3ZmS3p3WFF1ZEg4aHNVQkwxcUs1bUJmN0RFNTIveldzOWZxNGFGMmM3NGxQb05TSEg1djdtUHpUZ2xZVGlsSjhMMXp0RkdTSEhQOXNxWm1Ud0hsdFF0Ly9xUTVDTSs2dElvaGxDeTVVZmQ0MERISXl0TzBoa3Fjdy8vbXpVdXRPSmtaZEozZ1YzSUo4clVFZUVpcGdyR2xJQmoxQkFiV21mT05pT2FVbmo0a0l0N2dyWUtCUkVBdFJmT0pTT0V3ZzJvcDBTQ1B3RlZHTDJyN0ViTnd5UC9qR1p6SlVHTmRCdllqaEtZcS9lTno2VlhLb25HTm9JRmUyZzRuWVU4elFaUndMYytyM09zSGNTcHYxRm5oenFWZ283NG9TSEVrV290aWZKbmh3OXNRR1I2M25TdnVCZmV3R1U0eStva1BLRDUxWStuQUdDQXBJRlhCM1RYaHovTVU2eTVUQS9OcGgzRWZma0VJbGZpQUZtc0FlTXBScmU2YmR1V2tKUnMxTFluQjR0a3crYlZXZkZRcUp6c1RFR3YrNEdlRWlTZ1FMWjFxSWlwb1V5K0tpbFo0ZkRaaTljMUVZRmRjUUZBNnJRaGw2cW5CT2JiTlJHc0JBVFlDYWJXYXZNVXBYS2p6ZkVOV09HSHN5dHRsN0hFNVVmenJ5VkpOQ1B4aEx5QXdVVVJjekNuREpnMEJwMU9JaUc3UHBWeEo3Z1BIck4wMkdBejhsZi9pY0tNMjdkV0lwZGRoam1QckxZeTFrY002b0I0enFXRTd4MWNnY0krUm51ZEcxNlNLWEVLbEluUkhqdDZWN2U0L2RPWlA4RC82V1FCWEFZejNyckJtalZTSHdFQUVnd0ZCa3pYOHhFV3FMdlFZZ0NmVXhpYkZYMkRTaG9tZnBBYTdJQkk3a1lYOWNDUlF5WXY0YmVwRjFjUng2SU10SE1Cek1BUlhmV3UwaHdRbWpQUW9qdmM5TDMra2tERmVTMDE2aHJ2VzVpM2VXWHRoYWNzK2VjSU52VjlHTEZScmVhVEM1VTNJV01QWWFNRW1rM2dBUFBoS3Znb1NHK3BNeWlRbGFQSFN3NlNCRDlJMkhFd1JFOVJNQmd4N0FWVU9tU0ZoQmVXN2xQbWFkajcyaW9XdTVZUFBaUFJpZDltVTVwcVBZWmpiTmNWTUJ4dXRXME9ocmF1eVpINFFpMWNsZHRzVENJL2NpVENQU01ycmxpVHJuYlNaWFhxUkxTaTliY0RxNiswZi9EUk1pbmtnRTV2SEFzV285a3FqSy9yTHFaUk9RSGIzT0NaeTNvQjFqenB0UmNKQllqbUU3YkNVUXBUa3dSN05hdVVEQXdpM1d1QnZ0b3JiWVVmTC9vK2R6RThXZFN0ci9oYlJlUkJLaHZYZW8zaDZIbDdJVTIwUzNKb0FBQUI4ZGw0UDBzaEhPQUFCdmcvbUxBQUFhWkNHbzdIRVovc0NBQUFBQUFSWldnPT0nKSkpCmZvciBzdGFydCxlbmQscmVwbGFjZW1lbnQgaW4gcmV2ZXJzZWQoY2hhbmdlcyk6CiAgICBsaW5lc1tzdGFydDplbmRdPXJlcGxhY2VtZW50CnJlc3VsdD0nJy5qb2luKGxpbmVzKS5lbmNvZGUoKQphc3NlcnQgaGFzaGxpYi5zaGEyNTYocmVzdWx0KS5oZXhkaWdlc3QoKT09JzMyMTcyZWJkMmU0ZjcwMDc5NDY2ZmRlMjNlNWZhZDk5MzU0ZDM3YzFjNmZjZjcwZWQ3Y2E2ZTRjYmFlYjQwMmInLCAnVW5leHBlY3RlZCBkaXNjb25uZWN0IHBhdGNoIHJlc3VsdCcKcC53cml0ZV9ieXRlcyhyZXN1bHQpCg=='))"

# Approved El Chavo405 only. No other WIP is included.
COPY chavo405data.b64 apply_chavo405.py /tmp/
RUN python /tmp/apply_chavo405.py && rm /tmp/chavo405data.b64 /tmp/apply_chavo405.py
