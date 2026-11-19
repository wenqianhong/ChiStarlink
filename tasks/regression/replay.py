"""Replay three synthetic engineering changes against Hypatia's Manila–Dalian test network."""
import argparse
import csv
import hashlib
import io
import json
import math
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from tasks.regression.network import IMAGE

FIXTURE = "test_data/end_to_end"
EXECUTABLE = "build/optimized/scratch/main_satnet/main_satnet"
ROUTES = "dynamic_state_100ms_for_200s"
INTERVAL_NS = 100_000_000
GSL_MBPS = 10.0


def rows(path):
    with path.open() as src:
        return list(csv.reader(src))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_fixture(path):
    # Copy the fixture from the same image as the executable.
    archive = subprocess.check_output(["docker", "run", "--rm", "--network", "none",
                                       IMAGE, "tar", "czf", "-", "-C", FIXTURE, "."])
    with tarfile.open(fileobj=io.BytesIO(archive)) as outer:
        outer.extractall(path)
    with (path / "run/config_ns3.properties").open("a") as out:
        out.write("\ntcp_socket_type=TcpNewReno\n")


def execute(root):
    inputs = io.BytesIO()
    with tarfile.open(fileobj=inputs, mode="w:gz") as archive:
        archive.add(root / "run", arcname="run")
        archive.add(root / "satellite_network_state", arcname="satellite_network_state")
    command = ("mkdir /job && cd /job && tar xzf - && "
               + "/opt/hypatia/ns3-sat-sim/simulator/" + EXECUTABLE
               + " --run_dir=/job/run >&2 && tar czf - run/logs_ns3")
    result = subprocess.run(["docker", "run", "--rm", "-i", "--network", "none",
                             IMAGE, "sh", "-ec", command], input=inputs.getvalue(), capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-4000:])
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        archive.extractall(root)
    log = root / "run/logs_ns3"
    if (log / "finished.txt").read_text().strip() != "Yes":
        raise RuntimeError("Hypatia did not finalize")
    sent = rows(log / "udp_bursts_outgoing.csv")[0]
    received = rows(log / "udp_bursts_incoming.csv")[0]
    send_times = {r[1]: int(r[2]) for r in rows(log / "udp_burst_0_outgoing.csv")}
    receive_log = log / "udp_burst_0_incoming.csv"
    received_events = rows(receive_log) if receive_log.exists() else []
    if len(received_events) != int(received[8]):
        raise RuntimeError("Packet trace count differs from ns-3 UDP counter")
    delays = sorted((int(r[2]) - send_times[r[1]]) / 1e6 for r in received_events)
    return dict(sent_packets=int(sent[8]), received_packets=int(received[8]),
                delivery_ratio=int(received[8]) / int(sent[8]), payload_mbps=float(received[7]),
                p95_delay_ms=delays[math.ceil(len(delays)*.95)-1] if delays else None,
                outgoing_csv=','.join(sent), incoming_csv=','.join(received),
                receive_events_sha256=(digest(receive_log) if receive_log.exists() else hashlib.sha256(b"").hexdigest()))


def configure_trace(root, config, end_ns):
    network = root / "satellite_network_state"
    dynamic = network / ROUTES
    stations = rows(network / "ground_stations.txt")
    station = [float(x) for x in stations[1][2:5]]
    tle = (network / "tles.txt").read_text().splitlines()[1:]
    source, destination = len(tle) // 3, len(tle) // 3 + 1
    next_hop = {}
    serving_entries = {}
    trace = []
    for t in range(0, end_ns, INTERVAL_NS):
        for node, dest, hop, txif, rxif in rows(dynamic / f"fstate_{t}.txt"):
            if int(dest) == destination:
                next_hop[int(node)] = (int(hop), int(txif), int(rxif))
        path = [source]
        while path[-1] != destination:
            neighbor = next_hop[path[-1]][0]
            if neighbor < 0 or neighbor in path:
                raise ValueError(f"No loop-free route at t={t} from {source} to {destination}")
            path.append(neighbor)
        sat_id = path[-2]
        serving_entries[t] = next_hop[sat_id]
        trace.append(dict(time_s=t / 1e9, route=path, tx_if=next_hop[sat_id][1]))
    # Transfer source and inputs via stdin. This permits offline container runs
    # even on desktops with no shared host paths.
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copy(HERE / "geometry_radio.py", stage)
        shutil.copy(HERE.parent / "design/radio.py", stage)
        (stage / "input.json").write_text(json.dumps(dict(station=station, tle=tle,
                                                          samples=trace, config=config)))
        bundle = io.BytesIO()
        with tarfile.open(fileobj=bundle, mode="w:gz") as archive:
            for file in stage.iterdir():
                archive.add(file, arcname=file.name)
        result = subprocess.run(["docker", "run", "--rm", "-i", "--network", "none",
                                 "chistarlink-repair:phase1", "sh", "-ec",
                                 "cd /tmp && tar xzf - && python geometry_radio.py <input.json"],
                                input=bundle.getvalue(), capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        trace = json.loads(result.stdout)
    blocked = set()
    for sample in trace:
        time_ns = round(sample["time_s"] * 1e9)
        sat_id = sample["route"][-2]
        rate = sample["rate_bps"]
        if rate == 0 or sat_id in blocked:
            # Hypatia represents an unavailable next hop using its native drop tuple.
            route = serving_entries[time_ns] if rate else (-1, -1, -1)
            with (dynamic / f"fstate_{time_ns}.txt").open("a") as out:
                print(sat_id, destination, *route, sep=",", file=out)
            if not rate:
                blocked.add(sat_id)
                continue
            blocked.discard(sat_id)
        # The interface is also limited by its own 10 Mbps line rate.
        factor = min(1., rate / (GSL_MBPS * 1e6))
        with (dynamic / f"gsl_if_bandwidth_{time_ns}.txt").open("a") as out:
            print(f'{sat_id},{sample["tx_if"]},{factor:.10f}', file=out)
    return trace


def run_case(fixture, spec, solution, demand, holdout, work, evid):
    root = work / "case"
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(fixture, root, ignore=shutil.ignore_patterns(ROUTES, "logs_ns3"))
    start = holdout.get("start_s", 0)
    duration = holdout.get("duration_s", 8)
    # Half-second drain window; count application bytes over the active flow duration.
    end_ns = round((start + duration + .5) * 1e9)
    route_dir = fixture / "satellite_network_state" / ROUTES
    target_routes = root / "satellite_network_state" / ROUTES
    target_routes.mkdir()
    for t in range(0, end_ns, INTERVAL_NS):
        for prefix in ("fstate", "gsl_if_bandwidth"):
            name = f"{prefix}_{t}.txt"
            shutil.copyfile(route_dir / name, target_routes / name)
    cfg = root / "run/config_ns3.properties"
    cfg.write_text(cfg.read_text().replace("200000000000\n", f"{end_ns}\n"))
    rate = spec[demand]["offered_mbps"]
    (root / "run/udp_burst_schedule.csv").write_text(
        f"0,17,18,{rate},{start * 10**9},{duration * 10**9},,\n")
    config = {**spec[solution]}
    if "rx_diameter_m" in spec[demand]:
        config["rx_diameter_m"] = spec[demand]["rx_diameter_m"]
    if holdout:
        config["noise_k"] = holdout["noise_k"]
    trace = configure_trace(root, config, end_ns)
    metrics = execute(root)
    limits = spec[demand]
    checks = dict(payload=metrics["payload_mbps"] >= limits["min_payload_mbps"],
                  delivery=metrics["delivery_ratio"] >= .98,
                  delay=metrics["p95_delay_ms"] is not None and metrics["p95_delay_ms"] <= 100,
                  power=config["tx_w"] <= limits["max_tx_w"],
                  aperture=config.get("rx_diameter_m", .22) <= .35)
    sample_rates = [r["rate_bps"] for r in trace]
    trace_text = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in trace)
    trace_hash = hashlib.sha256(trace_text.encode()).hexdigest()
    if evid:
        evid.mkdir(parents=True, exist_ok=True)
        (evid / "radio.jsonl").write_text(trace_text)
        for name in ["udp_bursts_outgoing.csv", "udp_bursts_incoming.csv",
                     "udp_burst_0_incoming.csv", "udp_burst_0_outgoing.csv", "finished.txt"]:
            source = root / "run/logs_ns3" / name
            if source.exists():
                shutil.copy(source, evid / name)
    return dict(solution=solution, requirement=demand, holdout=bool(holdout), config=config, limits=limits,
                trace_samples=len(trace), rate_range_bps=[min(sample_rates), max(sample_rates)],
                radio_sha256=trace_hash, first_sample=trace[0], last_sample=trace[-1],
                metrics=metrics, checks=checks, passed=all(checks.values()))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--raw", type=Path, help="Preserve complete radio series and ns-3 packet traces")
    cli.add_argument("--task", choices=["C01", "C02", "C03"])
    cli.add_argument("--candidate", type=Path, help="Score a public proposal for --task against old and new demands")
    cli.add_argument("--private", type=Path, default=HERE / "private", help="Private reference and secondary configurations")
    args = cli.parse_args()
    if args.candidate and not args.task:
        cli.error("--candidate requires --task")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(engine="snkas/hypatia@0ac531c + ns-3.31 main_satnet; OpenSatCom v0.7.0 DVB-S2",
                   image=IMAGE, fixture=FIXTURE, tasks=[])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        fixture = work / "fixture"
        get_fixture(fixture)
        network = fixture / "satellite_network_state"
        with tarfile.open(network / f"{ROUTES}.tar.gz") as archive:
            archive.extractall(network)
        summary["native_200s"] = execute(fixture)
        if summary["native_200s"]["delivery_ratio"] < .95:
            raise RuntimeError("Native fixture baseline failed delivery check")
        for spec in json.loads((HERE / "tasks.json").read_text()):
            if args.task and args.task != spec["id"]:
                continue
            if args.candidate:
                proposal = json.loads(args.candidate.read_text())
                if set(proposal) - set(spec["editable"]):
                    raise ValueError("Candidate changes fields outside editable scope")
                if not all(type(value) in (int, float) and math.isfinite(value) and value > 0
                           for value in proposal.values()):
                    raise ValueError("Engineering parameters must be positive finite numbers")
                spec["candidate"] = {**spec["initial"], **proposal}
                matrix = [("candidate", "old"), ("candidate", "new")]
                scenarios = [{}]
            else:
                ref = json.loads((args.private / f'{spec["id"]}.json').read_text())
                spec["reference"] = {**spec["initial"], **ref}
                matrix = [("initial", "old"), ("initial", "new"), ("reference", "old"), ("reference", "new")]
                scenarios = [{}, json.loads((args.private / "secondary.json").read_text())]
            runs = []
            for holdout in scenarios:
                for solution, demand in matrix:
                    sub = f"{spec['id']}-{'secondary' if holdout else 'main'}-{solution}-{demand}"
                    run = run_case(fixture, spec, solution, demand, holdout, work,
                                   args.raw / sub if args.raw else None)
                    print(sub, run["checks"], round(run["metrics"]["payload_mbps"], 3), flush=True)
                    runs.append(run)
            passed = all(r["passed"] == (r["solution"] != "initial" or r["requirement"] == "old") for r in runs)
            summary["tasks"].append(dict(id=spec["id"], verified=passed, runs=runs))
            args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n")
    if not all(t["verified"] for t in summary["tasks"]):
        raise SystemExit("One or more regression matrices failed")


if __name__ == "__main__":
    main()
