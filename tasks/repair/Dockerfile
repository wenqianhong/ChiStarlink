FROM python:3.10.21-slim@sha256:9d53d8d4c0e882f61913025db53b3aec4ef74336082a9ab47d8a14e9e8329b00
ENV PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
COPY requirements.txt /tmp/repair-requirements.txt
RUN python -m pip install --no-cache-dir pip==25.3 && python -m pip install --resume-retries 5 --disable-pip-version-check --no-cache-dir -r /tmp/repair-requirements.txt
WORKDIR /work
