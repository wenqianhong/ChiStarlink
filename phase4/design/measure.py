"""Summarize native SNS3 statistics. Inputs are the unmodified replay.sh outputs."""
import argparse
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path


def rows(path):
    with path.open() as stream:
        return [line.strip().replace(",", " ").split() for line in stream
                if line.strip() and not line.startswith(("%", "#"))]


def digest(path):
    with path.open("rb") as stream:
        checksum = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
        return checksum.hexdigest()


def summarize(values):
    values = sorted(values)
    if not values or not all(math.isfinite(x) for x in values):
        raise ValueError("Expected finite statistics")
    return {"samples": len(values), "min": min(values), "median": statistics.median(values),
            "max": max(values)}


def trace(root, pattern):
    matches = list(root.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one trace: {pattern}, found {len(matches)}")
    return matches[0]


def scalar(root, name):
    return {key: float(value) for key, value in rows(root / f"stat-{name}-scalar.txt")}


def vhts(root):
    result = {}
    for group in ("global", "per-gw", "per-ut"):
        result[f"{group}_forward_application_kbps"] = scalar(root, f"{group}-fwd-app-throughput")
    result["http_page_load_s"] = scalar(root, "global-fwd-app-plt")["0"]
    result["per_segment_sinr_db"] = {
        seg: summarize([float(row[1]) for row in rows(trace(root, f"stat-global-{seg}-link-sinr-scatter-*.txt"))])
        for seg in ("fwd-feeder", "fwd-user", "rtn-user", "rtn-feeder")
    }
    cr = rows(trace(root, "stat-global-capacity-request-scatter-*.txt"))
    result["request_type_counts"] = dict(collections.Counter(row[3] for row in cr))
    result["requesting_node_ids"] = sorted({int(row[1]) for row in cr})
    grants = [float(row[1]) for row in rows(trace(root, "stat-global-resources-granted-scatter-*.txt"))]
    result["grant_bytes_per_event"] = summarize(grants)
    result["native_global_grant_scalar_bytes"] = scalar(root, "global-resources-granted")["0"]
    result["sha256"] = {f.name: digest(f) for f in sorted(root.glob("stat-global-*.txt"))
                        if any(s in f.name for s in ("link-sinr-scatter", "capacity-request-scatter",
                                                     "resources-granted-scatter", "fwd-app-throughput-scalar"))}
    if len(result["per-ut_forward_application_kbps"]) != 6 or min(result["per-gw_forward_application_kbps"].values()) <= 0:
        raise ValueError("Station coverage mismatch")
    if len(result["requesting_node_ids"]) != 6 or max(grants) <= 0:
        raise ValueError("No complete resource-control loop")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vhts_raw", type=Path)
    print(json.dumps(vhts(parser.parse_args().vhts_raw), indent=2, allow_nan=False))
