#!/bin/sh
set -eu
cd /src
cmake -S . -B build-cmake -GNinja -DCMAKE_BUILD_TYPE=Release \
  -DNS3_EXAMPLES=ON -DNS3_TESTS=OFF '-DNS3_ENABLED_MODULES=satellite;traffic;magister-stats'
cmake --build build-cmake --parallel "${JOBS:-8}" --target sat-vhts-example \
  sat-gw-handover-example sat-constellation-example sat-lora-handover-example sat-dama-onoff-sim-tn9
# Register only the selected upstream system suites with the unmodified ns-3 test driver.
g++ -std=c++23 -I build/include utils/test-runner.cc \
  contrib/satellite/test/satellite-handover-test.cc contrib/satellite/test/satellite-lora-regenerative-test.cc \
  -Wl,--no-as-needed build/lib/libns3.48-*.so -Wl,-rpath,/src/build/lib -o build/sns3-system-tests
