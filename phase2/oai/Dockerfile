FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS compiler
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential automake autoconf bison flex libtool cmake ninja-build pkg-config git ca-certificates python3 python3-yaml xxd libconfig-dev libyaml-cpp-dev libsctp-dev libssl-dev zlib1g-dev libreadline-dev libcap-dev libblas-dev liblapack-dev && rm -rf /var/lib/apt/lists/*
COPY asn1c.tgz simde.tgz /tmp/
RUN mkdir -p /tmp/asn1c /tmp/simde && tar xzf /tmp/asn1c.tgz -C /tmp/asn1c --strip-components=1 && \
    cd /tmp/asn1c && autoreconf -iv && CFLAGS='-O2 -fno-strict-aliasing' ./configure --prefix=/opt/asn1c && make -j8 && make install && \
    tar xzf /tmp/simde.tgz -C /tmp/simde --strip-components=1 && cp -r /tmp/simde /usr/include/simde && rm -rf /tmp/asn1c /tmp/simde /tmp/*.tgz
WORKDIR /opt/oai
COPY oai.tgz /tmp/
RUN tar xzf /tmp/oai.tgz --strip-components=1 && rm /tmp/oai.tgz
COPY CPM.cmake /opt/cpm/cpm/CPM_0.40.1.cmake
RUN cmake -S . -B build -GNinja -DCMAKE_BUILD_TYPE=Release -DCPM_SOURCE_CACHE=/opt/cpm -DT_TRACER=OFF -DOAI_VRTSIM=OFF && \
    cmake --build build --target nr_dlsim dfts params_libconfig --parallel 10
WORKDIR /opt/oai/build
ENV LD_LIBRARY_PATH=/opt/oai/build
