FROM chistarlink-oai:dlsim
WORKDIR /ntn
COPY ns3.tgz .
RUN tar xzf ns3.tgz --strip-components=1 && rm ns3.tgz && \
    cmake -S . -B cmake-cache -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DNS3_ENABLED_MODULES="spectrum;propagation;mobility" -DNS3_EXAMPLES=ON -DNS3_TESTS=ON && \
    cmake --build cmake-cache --target three-gpp-ntn-channel-example test-runner libpropagation-test --parallel 6
