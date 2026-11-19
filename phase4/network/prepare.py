"""Extract just a single, unchanged released 100-flow Kuiper experiment."""
import argparse
import tarfile
from pathlib import Path
from download import sha256, SHA256

TOPO='kuiper_630_isls_plus_grid_ground_stations_top_100_algorithm_free_one_only_over_isls'
DYNAMIC='dynamic_state_100ms_for_200s'
RUN='run_loaded_tm_pairing_10_Mbps_for_10s_with_udp'
STATIC=('tles.txt','isls.txt','ground_stations.txt','gsl_interfaces_info.txt','description.txt')


def prepare(archive, destination):
    if sha256(archive)!=SHA256:
        raise ValueError('Archive is not the upstream v1 paper reproduction release')
    run='temp_data/ns3_experiments_traffic_matrix_load_runs/'+RUN+'/'
    state='temp_data/satellite_networks_state_gen_data/'+TOPO+'/'
    names={run+f:'run/'+f for f in ['config_ns3.properties','udp_burst_schedule.csv']}
    for f in ['udp_bursts_incoming.csv','udp_bursts_outgoing.csv','finished.txt']:
        names[run+'logs_ns3/'+f]='published/'+f
    for f in STATIC:
        names[state+f]='network/'+f
    for t in range(0,10_000_000_000,100_000_000):
        for prefix in ['fstate','gsl_if_bandwidth']:
            path=f'{DYNAMIC}/{prefix}_{t}.txt'
            names[state+path]='network/'+path
    with tarfile.open(archive,'r|gz') as src:
        for member in src:
            if member.name in names:
                dest=destination/names.pop(member.name)
                dest.parent.mkdir(exist_ok=True,parents=True)
                dest.write_bytes(src.extractfile(member).read())
            if not names:
                break
    if names:
        raise ValueError(f'Missing archive members: {list(names)[:8]}')
    print('Selected 100 / 2000 native routing epochs and one published 10-second run.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();prepare(a.archive,a.destination)
