"""Independently audit all raw phase-three design records, then build the public catalog."""
import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from replay import CASES, CURVE, HERE, ROOT, TABLE_SHA256, bind_table

LABELS=("main_initial","main_reference","holdout_initial","holdout_reference","regression_reference")
NAMES={"station":"接收站","min_elev_deg":"最低仰角（°）","start_offset_s":"预约偏移（s）",
       "tx_w":"发射功率（W）","noise_k":"系统噪温（K）","rx_diameter_m":"接收口径（m）",
       "pointing_deg":"跟踪偏差（°）","bandwidth_hz":"带宽（Hz）","mcs":"MCS 目录",
       "feeder_loss_db":"馈线损耗（dB）","tx_gain_dbi":"发射增益（dBi）","dl_slots_per_s":"每秒可用下行时隙数"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_trace(folder, table, radio_hash):
    path=folder/"radio.jsonl"
    if digest(path)!=radio_hash:
        raise ValueError(f"Trace hash disagrees with judge: {path}")
    allrows=[json.loads(line) for line in path.read_text().splitlines()]
    with (folder/"trace.csv").open() as f:
        net=list(csv.DictReader(f))
    assert len(net)==len(allrows)
    for r,n in zip(allrows,net):
        assert r["time_s"]==float(n["time_s"]) and r["rate_bps"]==int(n["rate_bps"])
        assert math.isclose(r["range_m"]/299792458.,float(n["delay_s"]))
        if r["prbs"] is None:
            assert r["rate_bps"]==0
            continue
        key=r["prbs"],r["mcs"]
        lo=table[(*key,r["lower_snr_db"])]
        hi=table[(*key,r["upper_snr_db"])]
        for side, row in (("lower",lo),("upper",hi)):
            assert int(row["errors"])==r[side+"_errors"] and int(row["trials"])==r[side+"_trials"]
            assert int(row["tbs_bits"])==r["tbs_bits"] and float(row["slot_s"])==r["slot_s"]
        assert math.isclose(r["cn0_free_space_dbhz"]-r["gas_db"],r["cn0_dbhz"])
        assert math.isclose(r["snr_db"],r["cn0_dbhz"]-10*math.log10(r["prbs"]*12*r["scs_hz"]),abs_tol=1e-9)
        a,b=r["lower_snr_db"],r["upper_snr_db"]
        w=(r["snr_db"]-a)/(b-a) if b>a else 0
        bler=(1-w)*int(lo["errors"])/int(lo["trials"])+w*int(hi["errors"])/int(hi["trials"])
        assert math.isclose(bler,r["bler"],abs_tol=1e-9)
        assert abs(r["full_downlink_rate_bps"]-(1-bler)*r["tbs_bits"]/r["slot_s"])<=.500001
        assert r["rate_bps"]==round(r["full_downlink_rate_bps"]*(r["downlink_slots_per_s"]/1000))
    return len(allrows)


def render_catalog(s,runs):
    m={k:v["metrics"] for k,v in runs.items()}
    q=s["limits"]
    mutable="、".join(NAMES[k] for k in s["choices"])
    range_text="；".join(f'{NAMES[k]}可选 {json.dumps(v,ensure_ascii=False,separators=(",", "、"))}'
                       for k,v in s["choices"].items())
    return dict(id=s["id"],parent=s["parent"],type="完整通信链路设计",title=s["title"],
        prompt=f'{s["title"]}。{s["description"]}在原工程中配置{mutable}，为 {s["offered_mbps"]:.3f} Mbps 的 UDP 业务提供 {s["duration_s"]} 秒连续服务；有效吞吐至少 {s["min_payload_mbps"]:.3f} Mbps。提交可执行配置，并验证另一过境时段可用。',
        units={
          "轨道与接入":f'使用 Hypatia 合成 TLE，站点为{"、".join(s["stations"])}。主窗口自 TLE 历元后 {s["start_s"]} 秒起，1 秒采样；预约题将选择的时间偏移施加于窗口。低于所选仰角的采样容量为零。',
          "传播与射频":f'{s["fixed"]["frequency_hz"]/1e9:g} GHz 晴空链路，OpenSatCom 预算逐点扣除 ITU P.676 气体损耗。峰值功率 ≤{q["tx_w"]:g} W，平均功率 ≤{q["mean_tx_w"]:g} W，EIRP ≤{q["eirp_dbw"]:g} dBW，口径 ≤{q["rx_diameter_m"]:g} m。',
          "波形与物理层":f'在 ≤{q["bandwidth_hz"]/1e6:g} MHz 内使用实测完整 PRB（15 kHz 子载波）。按当前 C/N₀ 查 OAI PDSCH 曲线，逐时刻折算 TBS 和 BLER；下行时隙配额按有效容量比例施加。',
          "网络与业务":f'ns-3 单向 UDP，主场景与留出场景均须达到 {s["min_payload_mbps"]:.3f} Mbps、交付率 ≥98%、p95 时延 ≤30 ms；低负载回归以 0.15 Mbps 发包，最低有效吞吐 0.14 Mbps，同样检查交付率和时延。',
          "允许修改的配置":range_text},
        evidence=f'主窗口有效吞吐由 {m["main_initial"]["payload_mbps"]:.3f} 升至 {m["main_reference"]["payload_mbps"]:.3f} Mbps，参考 p95 为 {m["main_reference"]["p95_delay_ms"]:.2f} ms。独立留出窗口由 {m["holdout_initial"]["payload_mbps"]:.3f} 升至 {m["holdout_reference"]["payload_mbps"]:.3f} Mbps；低负载回归为 {m["regression_reference"]["payload_mbps"]:.3f} Mbps。5 组判定均符合预期。')


def main(folder):
    bind_table()
    with CURVE.open() as stream:
        table={(int(r["prbs"]),int(r["mcs"]),float(r["snr_db"])):r for r in csv.DictReader(stream)}
    catalog=[]
    evidence=[]
    skipped=[]
    samples=0
    for cid,spec in CASES.items():
        record=json.loads((folder/cid/"summary.json").read_text())
        if not record["verified"]:
            skipped.append(cid);continue
        runs=record["runs"]
        assert set(runs)==set(LABELS)
        for label,r in runs.items():
            assert r["passed"]==r["expected_pass"]==label.endswith("_reference")
            n=audit_trace(folder/cid/label,table,r["radio_sha256"])
            assert n==r["samples"]==spec["duration_s"]
            samples+=n
        catalog.append(render_catalog(spec,runs))
        evidence.append(record)
    files=[HERE/"specs.json",HERE/"replay.py",HERE/"verify.py",ROOT/"tasks/design/tasks.json",
           ROOT/"phase2/cases/replay.py",ROOT/"phase2/cases/worker.py",ROOT/"phase2/cases/radio.py",
           ROOT/"phase2/cases/nr.py",ROOT/"phase2/propagation/gas.py",ROOT/"tasks/regression/network.py",
           ROOT/"tasks/regression/service-link.cc",CURVE]
    payload={"accepted_cases":len(catalog),"filtered_cases":skipped,"scored_runs":len(catalog)*5,
             "radio_samples_audited":samples,"oai_curve_sha256":TABLE_SHA256,
             "public_inputs_sha256":{str(p.relative_to(ROOT)):digest(p) for p in files},
             "images":{t:subprocess.check_output(["docker","image","inspect","--format","{{.Id}}",t],text=True).strip()
                       for t in ("chistarlink-itur:phase2","chistarlink-hypatia:0ac531c")},
             "families":dict(Counter(CASES[row["id"]]["family"] for row in catalog)),"tasks":evidence}
    (HERE/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n")
    (HERE/"evidence/matrix.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    print(f'{len(catalog)} accepted, {len(skipped)} filtered, {samples} radio epochs checked')
    if skipped:
        raise SystemExit(1)

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--raw",type=Path,default=HERE/"private/runs")
    main(cli.parse_args().raw)
