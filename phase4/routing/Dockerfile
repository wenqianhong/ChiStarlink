FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libegl1 libdbus-1-3 libxkbcommon-x11-0 libfontconfig1 libxrender1 libx11-xcb1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-plotting.txt /opt/easysat/
RUN pip install --no-cache-dir -r /opt/easysat/requirements-plotting.txt
ENV QT_QPA_PLATFORM=offscreen
WORKDIR /src
