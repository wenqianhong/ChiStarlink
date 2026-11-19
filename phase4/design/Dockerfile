FROM ubuntu:24.04
RUN apt-get update && apt-get install --no-install-recommends -y build-essential cmake ninja-build python3 libxml2-dev libsqlite3-dev bzip2 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY ns-3.48.tar.bz2 satellite.tgz traffic.tgz magister-stats.tgz /tmp/sources/
RUN tar xjf /tmp/sources/ns-3.48.tar.bz2 --strip-components=1 && \
    for module in satellite traffic magister-stats; do mkdir -p contrib/$module && tar xzf /tmp/sources/$module.tgz --strip-components=1 -C contrib/$module; done && rm -rf /tmp/sources
COPY native-build.sh /tmp/native-build.sh
RUN sh /tmp/native-build.sh
COPY data /src/contrib/satellite/data
# TN9 keeps every sampled fading vector in memory; compact allocations fit 220 UTs.
RUN apt-get update && apt-get install --no-install-recommends -y libjemalloc2 && rm -rf /var/lib/apt/lists/*
