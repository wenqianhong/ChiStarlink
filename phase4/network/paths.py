"""Trace each scheduled flow through the native forwarding and interface tables."""
import csv
import json
from collections import Counter
from pathlib import Path
from prepare import DYNAMIC


def interfaces(net):
    graph={}
    for line in (net/'isls.txt').read_text().splitlines():
        a,b=map(int,line.split())
        for x,y in [(a,b),(b,a)]:
            neighbours=graph.setdefault(x,{})
            neighbours[y]=len(neighbours)
    return graph


def matrix(schedule):
    with schedule.open() as f:
        return [(int(r[1]),int(r[2])) for r in csv.reader(f)]


def delta(path):
    state={}
    for row in path.read_text().splitlines():
        a,b,h,i,j=map(int,row.split(','))
        state[a,b]=(h,i,j)
    return state


def trace(state,src,dst,graph):
    route=[src]
    while route[-1]!=dst:
        a=route[-1]
        b,i,j=state[a,dst]
        if b in route or b<0:
            raise ValueError(f'unreachable or looping path {src}->{dst}')
        if a in graph and b in graph and (graph[a][b],graph[b][a])!=(i,j):
            raise ValueError(f'Incorrect ISL interfaces {a}->{b}')
        route.append(b)
    return tuple(route)


def audit(base,modified,schedule):
    graph=interfaces(base)
    for file in base.rglob('*'):
        if file.is_file() and not file.name.startswith('fstate_'):
            assert file.read_bytes()==(modified/file.relative_to(base)).read_bytes()
    traffic=matrix(schedule)
    original={};current={};observed=[]
    sample=None
    previous=None;changes=0
    for ts in range(0,10_000_000_000,100_000_000):
        f=Path(DYNAMIC)/f'fstate_{ts}.txt'
        original.update(delta(base/f));current.update(delta(modified/f))
        old=[trace(original,*pair,graph) for pair in traffic]
        new=[trace(current,*pair,graph) for pair in traffic]
        for before,after in zip(old,new):
            assert before[:2]==after[:2] and before[-2:]==after[-2:]
            assert all(sat in graph for sat in after[1:-1])
            for node in (after[0],after[-2]):
                assert original[node,after[-1]]==current[node,after[-1]]
            assert len(after)<=len(before)+4
            if sample is None and before!=after:
                sample={'original':before,'submitted':after}
        edges=lambda paths:Counter((a,b) for path in paths for a,b in zip(path[1:-2],path[2:-1]))
        if previous is not None:
            changes+=sum(p[:2]!=q[:2] or p[-2:]!=q[-2:] for p,q in zip(previous,old))
        previous=old
        observed.append({'time_ns':ts,'rerouted_flows':sum(a!=b for a,b in zip(old,new)),
                         'max_extra_isl_hops':max(len(b)-len(a) for a,b in zip(old,new)),
                         'max_concurrent_routes_before':max(edges(old).values()),
                         'max_concurrent_routes_after':max(edges(new).values())})
    return {'epochs':len(observed),'validated_paths':len(observed)*len(traffic),
            'observed_attachment_changes':changes,'example':sample,'ticks':observed}
