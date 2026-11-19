"""Recompute the Case 3 cohorts from raw transmission and arrival events."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import statistics
from pathlib import Path


def summarize(path):
    raw = path.read_bytes()
    data = gzip.decompress(raw) if path.suffix == ".gz" else raw
    generated, received, faults = {}, {}, []
    pairs, directions = set(), set()
    for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig"))):
        key = row["message_id"]
        moment = float(row["simulation_time"])
        if moment >= 200:
            continue
        if row["event_type"] == "generate":
            if key in generated:
                raise ValueError(f"Duplicate generation event {key}")
            generated[key] = moment
            pairs.add(row["pair_id"])
            directions.add(row["direction"])
        elif row["event_type"] == "arrival":
            received.setdefault(key, int(float(row["hop_count"])))
        elif row["event_type"] == "satellite_failure":
            faults.append({"time_s": moment, "event": row["note"]})
    if received.keys() - generated.keys():
        raise ValueError("Received IDs missing from generated traffic")
    result = {}
    for name, start, end in (("normal", 0, 105), ("failure_to_refresh", 105, 150), ("post_refresh", 150, 200)):
        cohort = [msg for msg, t in generated.items() if start <= t < end]
        hops = [received[msg] for msg in cohort if msg in received]
        result[name] = dict(generated=len(cohort), delivered=len(hops),
                            delivery_ratio=len(hops)/len(cohort) if cohort else None,
                            average_hop_count=statistics.mean(hops) if hops else None)
    return dict(sha256=hashlib.sha256(data).hexdigest(), pairs=len(pairs), directions=sorted(directions),
                failures=faults, last_generation_s=max(generated.values(), default=None), phases=result)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("events", type=Path)
    print(json.dumps(summarize(cli.parse_args().events), indent=2))
