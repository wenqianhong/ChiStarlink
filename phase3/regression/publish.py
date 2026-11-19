"""Verify per-layer traces and assemble the public catalogue and compact evidence."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from replay import HERE, ROOT, TASKS

NAMES = {'tx_w':'星上发射功率','bandwidth_hz':'带宽预算','rx_diameter_m':'接收天线口径',
         'feeder_loss_db':'馈线损耗','pointing_deg':'指向偏差','noise_k':'接收系统噪温',
         'efficiency':'口径效率','dl_fraction':'完整下行时隙份额','mcs':'接收端支持的 MCS',
         'max_tx_w':'功率上限','max_bandwidth_hz':'带宽上限','max_rx_diameter_m':'口径上限',
         'offered_mbps':'UDP 负载','max_p95_ms':'P95 单向时延上限'}
DEFAULTS = {'mcs':[4,8,12,14,16,18,20,26],'noise_k':290.,'pointing_deg':.2,
            'efficiency':.6,'dl_fraction':1.,'feeder_loss_db':1.5}

def pretty(key, value):
    if key=='mcs':
        return '、'.join(map(str,value))
    if key in ('efficiency','dl_fraction'):
        return f'{value*100:g}%'
    scale, unit = {'tx_w':(1,'W'),'max_tx_w':(1,'W'),'rx_diameter_m':(100,'cm'),
                   'max_rx_diameter_m':(100,'cm'),'bandwidth_hz':(1e-6,'MHz'),
                   'max_bandwidth_hz':(1e-6,'MHz'),'pointing_deg':(1,'°'),'feeder_loss_db':(1,'dB'),
                   'noise_k':(1,'K'),'offered_mbps':(1,'Mbps'),'max_p95_ms':(1,'ms')}[key]
    return f'{value*scale:g} {unit}'


def constraints(spec):
    def flatten(req):
        return {**DEFAULTS, **spec['initial'], **req['radio'], **req['limits'],
                'offered_mbps':req['offered_mbps'], 'max_p95_ms':req['max_p95_ms']}
    old, new = flatten(spec['old']),flatten(spec['new'])
    delta = '，'.join(f'{NAMES[k]}由 {pretty(k,v)} 变为 {pretty(k,new[k])}'
                      for k,v in old.items() if k in NAMES and v!=new[k])
    scope='、'.join(NAMES[k] for k in spec['editable'])
    limits=spec['new']
    prompt=(f'马尼拉到大连的中继业务已按 {old["offered_mbps"]:g} Mbps 负载运行。变更后，{delta}。'
            f'在给定设备和轨道配置中，只允许调整{scope}。要求修改后同时通过旧业务与新业务的吞吐、交付率、时延及资源检查。')
    units={'轨道与接入':'沿 17 颗 Kuiper-630 测试星的原生动态转发表，从节点 17 发往节点 18；每 0.1 s 重算目标站末跳，最低仰角 10°。',
           '传播与射频':f'12 GHz 晴空，按斜距、口径与指向计算接收 C/N₀，扣除 ITU-R P.676-12 气体损耗一次。新功率、口径上限分别为 {pretty("max_tx_w",new["max_tx_w"])}、{pretty("max_rx_diameter_m",new["max_rx_diameter_m"])}。',
           'NR 物理层':f'25 PRB 载波内按带宽预算选 2、5、8 或 11 PRB，15 kHz SCS；新带宽上限 {pretty("max_bandwidth_hz",new["max_bandwidth_hz"])}，可用 MCS 为 {pretty("mcs",new["mcs"])}，每秒预算 {round(new["dl_fraction"]*1000)} 个完整下行时隙。只在 OAI 实测 SNR 范围内插值。',
           '网络与业务':f'新需求 UDP 负载 {new["offered_mbps"]:g} Mbps，有效吞吐至少 {limits["min_payload_mbps"]:g} Mbps，交付率至少 98%，P95 单向时延不超过 {new["max_p95_ms"]:g} ms。原生 ns-3 逐包测量。',
           '回归矩阵':f'旧需求保留 {old["offered_mbps"]:g} Mbps 负载，净吞吐至少 {spec["old"]["min_payload_mbps"]:g} Mbps，P95 不超过 {old["max_p95_ms"]:g} ms。主与留出场景均验证旧工程满足旧要求、违反新要求，修改工程满足两套要求。'}
    affected=next((k for k in ('noise_k','pointing_deg','efficiency','feeder_loss_db','rx_diameter_m') if old[k]!=new[k]),None)
    if affected:
        units['传播与射频']+=f'本次终端或链路的{NAMES[affected]}从 {pretty(affected,old[affected])} 变为 {pretty(affected,new[affected])}。'
    return prompt,units


def audit(path, result, measured_points):
    data=(path/'radio.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest()==result['radio_sha256']
    count=0
    for line in data.splitlines():
        r=json.loads(line);count+=1
        assert r['route'][0]==17 and r['route'][-1]==18 and r['route'][-2]==r['sat_id']
        assert 10<=r['elevation_deg']<=90 and math.isclose(r['delay_s']*299792458,r['range_m'])
        assert r['gas_db']>0 and math.isclose(r['cn0_free_space_dbhz']-r['gas_db'],r['cn0_dbhz'])
        assert math.isclose(r['snr_db'],r['cn0_dbhz']-10*math.log10(12*r['prbs']*r['scs_hz']))
        low,high=r['lower_snr_db'],r['upper_snr_db']
        assert low<=r['snr_db']<=high
        for side, point in (('lower',low),('upper',high)):
            original=measured_points[r['prbs'],r['mcs'],point]
            assert (r[f'{side}_errors'],r[f'{side}_trials'],r['tbs_bits'])==original
        alpha=0. if high==low else (r['snr_db']-low)/(high-low)
        bler=(1-alpha)*r['lower_errors']/r['lower_trials']+alpha*r['upper_errors']/r['upper_trials']
        assert math.isclose(bler,r['bler'],abs_tol=1e-12)
        assert round((1-bler)*r['tbs_bits']/r['slot_s'])==r['full_downlink_bps']
        assert round(r['full_downlink_bps']*r['dl_fraction'])==r['rate_bps']==r['native_tx_bps']
    assert count==result['samples']
    receive=(path/'udp_burst_0_incoming.csv').read_bytes()
    assert hashlib.sha256(receive).hexdigest()==result['metrics']['receive_events_sha256']
    assert len(receive.splitlines())==result['metrics']['received_packets']
    return count


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--runs',type=Path,default=HERE/'private/final')
    args=cli.parse_args()
    with (ROOT/'phase2/oai/curves.csv').open() as stream:
        measured_points={(int(r['prbs']),int(r['mcs']),float(r['snr_db'])):
                         (int(r['errors']),int(r['trials']),int(r['tbs_bits'])) for r in csv.DictReader(stream)}
    catalog=[]; all_results=[]; samples=0
    for cid,spec in TASKS.items():
        result=json.loads((args.runs/f'{cid}.json').read_text())
        if not result['verified']:
            raise ValueError(f'{cid} failed its regression matrix')
        assert len(result['runs'])==8 and len({r['stage'] for r in result['runs']})==8
        for r in result['runs']:
            assert r['passed']==r['expected']
            samples+=audit(args.runs/cid/r['stage'], r, measured_points)
        old=next(r for r in result['runs'] if r['stage']=='main-initial-new')
        ref=next(r for r in result['runs'] if r['stage']=='main-reference-new')
        measured=ref['metrics']
        labels={'payload':'吞吐','delivery':'交付率','delay':'时延','power':'功率','spectrum':'频谱','aperture':'口径'}
        failed='、'.join(labels[k] for k,passed in old['checks'].items() if not passed)
        evidence=(f'两套场景的 8 次判定均符合预期。主场景旧工程违反新{failed}约束，修改后收到 '
                  f'{measured["received_packets"]}/{measured["sent_packets"]} 包，净吞吐 {measured["payload_mbps"]:.3f} Mbps，'
                  f'P95 单向时延 {measured["p95_delay_ms"]:.2f} ms。')
        prompt,units=constraints(spec)
        catalog.append(dict(id=cid,type='③ 需求变更',title=spec['title'],prompt=prompt,
                            units=units,evidence=evidence,parent=spec['parent']))
        all_results.append(result)
    release=dict(engine='Phase 2 OAI measured profile + native Hypatia main_satnet',
                 curves_sha256=hashlib.sha256((ROOT/'phase2/oai/curves.csv').read_bytes()).hexdigest(),
                 tasks_sha256=hashlib.sha256((HERE/'tasks.json').read_bytes()).hexdigest(),
                 audited_radio_samples=samples,results=all_results)
    (HERE/'evidence.json').write_text(json.dumps(release,indent=2,ensure_ascii=False)+'\n')
    (HERE/'catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+'\n')
    print(len(catalog),'accepted;',samples,'radio/network samples audited')


if __name__=='__main__':
    main()
