"""Grade native routing interventions against a stock run for the same traffic."""
import argparse
import hashlib
import json
from pathlib import Path
from paths import audit
from run import execute,read_flows


def grade(data,schedule,network,stock,output):
    out=output/'submitted'
    geometry=audit(data/'network',network,schedule)
    if not stock.is_dir():
        execute(data,stock,schedule=schedule)
    execute(data,out,schedule=schedule,network=network)
    before=json.loads((stock/'summary.json').read_text())
    after=json.loads((out/'summary.json').read_text())
    old=read_flows(stock/'udp_bursts_outgoing.csv');new=read_flows(out/'udp_bursts_outgoing.csv')
    from paths import matrix
    for id,pair in enumerate(matrix(schedule)):
        assert tuple(old[id][k] for k in ('src','dst'))==pair
    assert old==new and before['sent']==after['sent']
    ticks=geometry.pop('ticks')
    check={'delivery_gain_ge_5pp':after['delivery']-before['delivery']>=.05,
           'lower_decile_gain_ge_2pp':after['bottom_decile_delivery']-before['bottom_decile_delivery']>=.02}
    summary={'requirements':check,'accepted':all(check.values()),'baseline':before,'reference':after,
             'route_audit':geometry,'ranges':{k:[min(x[k] for x in ticks),max(x[k] for x in ticks)]
                for k in ticks[0] if k!='time_ns'},
             'schedule_sha256':hashlib.sha256(schedule.read_bytes()).hexdigest()}
    (output/'ticks.json').write_text(json.dumps(ticks,indent=2)+'\n')
    (output/'judgment.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    return summary


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ['input','schedule','network','baseline_output','output']:
        cli.add_argument(name,type=Path)
    a=cli.parse_args()
    if not grade(a.input,a.schedule,a.network,a.baseline_output,a.output)['accepted']:
        raise SystemExit(1)
