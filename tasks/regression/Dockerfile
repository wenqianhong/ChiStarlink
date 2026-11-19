FROM ubuntu:20.04@sha256:8feb4d8ca5354def3d8fce243717141ce31e2c428701f6682bd2fafe15388214
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3 libopenmpi-dev openmpi-bin unzip ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/hypatia
COPY hypatia.tgz basic-sim.tgz /tmp/
RUN tar xzf /tmp/hypatia.tgz --strip-components=1 && \
    tar xzf /tmp/basic-sim.tgz --strip-components=1 -C ns3-sat-sim/simulator/contrib/basic-sim && rm /tmp/*.tgz
RUN cd ns3-sat-sim && unzip -q ns-3.31.zip && cp -r ns-3.31/. simulator/ && rm -rf ns-3.31 && cd simulator && \
    python3 waf configure --build-profile=optimized --enable-mpi --disable-python --out=build/optimized && \
    python3 waf build -j8
WORKDIR /opt/hypatia/ns3-sat-sim/simulator
ENV LD_LIBRARY_PATH=/opt/hypatia/ns3-sat-sim/simulator/build/optimized/lib
COPY service-link.cc scratch/service-link.cc
RUN python3 waf build --target=service-link -j8
