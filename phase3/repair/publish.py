"""Publish checked replay data, keeping all retained inputs, solutions and detailed retained traces local."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from replay import HERE, SCENES, SPECS


def extrema(rows, field):
    values = [float(row[field]) for row in rows]
    return min(values), max(values)


def catalog_entry(spec, rows, broken, fixed):
    task = spec["id"]
    load = spec["offered_mbps"]
    mins, maxs = extrema(rows, "true_range_m")
    lowest, highest = extrema(rows, "true_elev_deg")
    lowgas, highgas = extrema(rows, "gas_db")
    mode_set = ", ".join(str(n) for n in sorted({int(row["mcs"]) for row in rows}))
    prbs = ", ".join(str(n) for n in sorted({int(row["prbs"]) for row in rows}))
    m = broken["metrics"]
    n = fixed["metrics"]
    q95 = "无收包" if m["p95_delay_ms"] is None else f"{m['p95_delay_ms']:.3f} ms"
    case_start = SCENES["target"]["start_from_epoch_s"] + int(task[1:]) % 7
    return {
        "id": task,
        "type": "跨层故障修复",
        "title": spec["title"],
        "parent": spec["parent"],
        "prompt": spec["problem"]
        + f" 只修改 input/{task}/adapter.py。以 {load:g} Mbit/s 发送下行 UDP，交付率与有效吞吐均需达到合同量的 98%，p95 不超过 {spec['max_p95_ms']:g} ms；旧版消息须继续正常。",
        "units": {
            "轨道与接入": f"TLE 历元后第 {case_start} 秒开始，覆盖 12 s。上海站目标仰角 {lowest:.2f}–{highest:.2f}°、单程斜距 {mins / 1000:.1f}–{maxs / 1000:.1f} km；准入门限 {rows[0]['min_elev_deg']}°。",
            "射频与传播": f"按单向业务分配发射功率 {float(rows[0]['tx_w']):g} W、载频 {float(rows[0]['carrier_hz']) / 1e9:g} GHz、接收噪温 {float(rows[0]['rx_temp_k']):g} K 重算 C/N₀。P.676-12 晴空气体衰减 {lowgas:.4f}–{highgas:.4f} dB，每时刻仅扣一次。",
            "NR 物理层": f"使用 OAI 的实测 SNR 括点和 TB 计数，15 kHz SCS；保持实际占用带宽≤{float(rows[0]['bandwidth_hz']) / 1e6:g} MHz。此目标参考运行选取 {prbs} PRB、MCS {mode_set}；有效速率为每时隙 TBS×成功率后按时隙频率换算。",
            "网络与业务": f"ns-3.31 使用本轮逐时容量、单程传播及任务处理延迟。端侧至少交付 98%，UDP 有效吞吐 ≥{load * 0.98:.3f} Mbit/s，p95 ≤{spec['max_p95_ms']:g} ms。",
            "故障与回归": f"改动限于 {spec['field']} 的接口解码；初版触发与留出均须出现业务退化，旧格式必须通过。修复后触发、旧格式和留出三场景都须达标。",
        },
        "evidence": f"触发场景接收包 {m['received_packets']}/{m['sent_packets']} → {n['received_packets']}/{n['sent_packets']}，吞吐 {m['payload_mbps']:.3f} → {n['payload_mbps']:.3f} Mbit/s，p95 {q95} → {n['p95_delay_ms']:.3f} ms。初始与参考的六次判定均符合预期。",
    }


def main(full):
    summary = json.loads((full / "summary.json").read_text())
    rows = summary["rows"]
    keys = {(r["id"], r["version"], r["case"]) for r in rows}
    expected = {
        (t, v, c)
        for t in SPECS
        for v in ("initial", "reference")
        for c in ("target", "regression", "holdout")
    }
    if keys != expected or len(rows) != 198 or not all(r["matched"] for r in rows):
        raise ValueError("Complete, validated 198-cell matrix required")
    lookup = {(r["id"], r["version"], r["case"]): r for r in rows}
    public = []
    catalog = []
    for r in rows:
        j = full / r["id"] / r["version"] / r["case"] / "judgment.json"
        metric = r["metrics"]
        keep = {
            k: r[k]
            for k in (
                "id",
                "case",
                "version",
                "expected_pass",
                "passed",
                "matched",
                "checks",
                "curve_sha256",
            )
        }
        keep.update(
            {
                k: metric[k]
                for k in (
                    "sent_packets",
                    "received_packets",
                    "payload_mbps",
                    "p95_delay_ms",
                    "delivery_ratio",
                )
            }
        )
        keep["judgment_sha256"] = hashlib.sha256(j.read_bytes()).hexdigest()
        public.append(keep)
    evidence = HERE / "evidence"
    with (evidence / "initial-target-traces.jsonl.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as logs:
            for task, spec in SPECS.items():
                for version in ("initial", "reference"):
                    with (full / task / version / "target" / "layers.csv").open() as f:
                        layers = list(csv.DictReader(f))
                    if version == "initial":
                        logs.write(
                            (
                                json.dumps(
                                    {"id": task, "target_layers": layers},
                                    ensure_ascii=False,
                                )
                                + "\n"
                            ).encode()
                        )
                    else:
                        catalog.append(
                            catalog_entry(
                                spec,
                                layers,
                                lookup[task, "initial", "target"],
                                lookup[task, "reference", "target"],
                            )
                        )
    (HERE / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    )
    (evidence / "results.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        len(catalog),
        "tasks;",
        len(public),
        "trials;",
        dict(Counter(r["parent"] for r in catalog)),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", type=Path, default=HERE / ".private/full")
    main(p.parse_args().full)
