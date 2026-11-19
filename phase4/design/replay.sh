#!/bin/sh
# Run inside the native simulator image from /src. Save results outside the image.
set -eu
cd /src
out=${1:-/out}
mkdir -p "$out/vhts" "$out/dama" "$out/constellation"
bin=/src/build/contrib/satellite/examples/ns3.48
"$bin-sat-vhts-example" --Beams=1_8_20 --NbUtsPerBeam=2 --NbEndUsersPerUt=2 \
  --NbGw=1 --SimLength=24s --RaModel=CRDSA --RngRun=1 --OutputPath="$out/vhts" >"$out/vhts.log" 2>&1
allocator=$(ldconfig -p | awk '/libjemalloc.so.2/{print $NF; exit}')
test -r "$allocator"
LD_PRELOAD="$allocator" "$bin-sat-dama-onoff-sim-tn9" --OutputPath="$out/dama" >"$out/dama.log" 2>&1
"$bin-sat-constellation-example" --OutputPath="$out/constellation" >"$out/constellation.log" 2>&1
for example in gw-handover lora-handover; do
  "$bin-sat-$example-example" >"$out/$example.log" 2>&1
  cp -R "contrib/satellite/data/sims/example-$example" "$out/"
done
for suite in sat-handover-test sat-lora-regenerative-test; do
  build/sns3-system-tests --suite="$suite" --verbose >"$out/$suite.log" 2>&1
done
