"""Compare rising/setting times for the phase-one orbit over its first day."""
import argparse
from hashlib import sha256
import json
import os
from math import radians
from pathlib import Path
from urllib.request import urlopen

import jdk4py
import orekit_jpype
from skyfield.api import EarthSatellite, load, wgs84

HERE = Path(__file__).resolve().parent
DATA_REV = '2d6edc9118983d95c51303df05db16ada90b7ee2'
FILES = {
    'tai-utc.dat': '3524e1ae34d67e858873a89e59983bbc5bd100221da898e796c1b36036a310c3',
    'Earth-Orientation-Parameters/IAU-1980/finals.all':
        'b5033594e4ad2481f0b4ead81d72b2e2d2a2d91f9c6367863f91466a450b3990',
    'Earth-Orientation-Parameters/IAU-2000/finals2000A.all':
        '4c2308a3a782f561a84f549ab0e074e745aa950facd9dff56e2e60a7eac8f042',
}


def compare(cache):
    cache.mkdir(exist_ok=True, parents=True)
    for name, checksum in FILES.items():
        dest = cache / Path(name).name
        if not dest.exists():
            with urlopen(f'https://gitlab.orekit.org/orekit/orekit-data/-/raw/{DATA_REV}/{name}', timeout=90) as src:
                dest.write_bytes(src.read())
        if sha256(dest.read_bytes()).hexdigest() != checksum:
            raise ValueError(f'Incorrect Earth orientation data: {dest}')
    os.environ["JAVA_HOME"] = str(jdk4py.JAVA_HOME)
    libs = [p for p in Path(jdk4py.JAVA_HOME).rglob('libjvm.*') if p.suffix in {'.so', '.dylib'}]
    orekit_jpype.initVM(jvmpath=str(libs[0]))
    from java.io import File
    from org.orekit.bodies import GeodeticPoint, OneAxisEllipsoid
    from org.orekit.data import DataContext, DirectoryCrawler
    from org.orekit.frames import FramesFactory, TopocentricFrame
    from org.orekit.propagation.analytical.tle import TLE, TLEPropagator
    from org.orekit.propagation.events import ElevationDetector, EventsLogger
    from org.orekit.propagation.events.handlers import ContinueOnEvent
    from org.orekit.utils import Constants, IERSConventions
    DataContext.getDefault().getDataProvidersManager().addProvider(DirectoryCrawler(File(str(cache.resolve()))))
    earth = OneAxisEllipsoid(Constants.WGS84_EARTH_EQUATORIAL_RADIUS, Constants.WGS84_EARTH_FLATTENING,
                             FramesFactory.getITRF(IERSConventions.IERS_2010, True))
    data = json.loads((HERE.parents[1] / 'tasks/design/tasks.json').read_text())
    t = data['tle']
    orbit = TLE(t['line1'], t['line2'])
    epoch = orbit.getDate()
    sat = EarthSatellite(t['line1'], t['line2'], t['name'], load.timescale(builtin=True))
    results = []
    for name, (lat, lon) in data['stations'].items():
        station = TopocentricFrame(earth, GeodeticPoint(radians(lat), radians(lon), 0.), name)
        detector = ElevationDetector(station).withMaxCheck(10.).withConstantElevation(radians(10.)).withHandler(ContinueOnEvent())
        log = EventsLogger()
        propagator = TLEPropagator.selectExtrapolator(orbit)
        propagator.addEventDetector(log.monitorDetector(detector))
        propagator.propagate(epoch, epoch.shiftedBy(86400.))
        events = list(log.getLoggedEvents())
        times, codes = sat.find_events(wgs84.latlon(lat, lon), sat.epoch, sat.epoch + 1, altitude_degrees=10)
        crossings = [(float((time-sat.epoch)*86400), code == 0) for time,code in zip(times,codes) if code != 1]
        if len(events) != len(crossings) or not events:
            raise ValueError(f'Inconsistent event count: {name}, {len(events)}, {len(crossings)}')
        for ev, (second, rising) in zip(events, crossings):
            if bool(ev.isIncreasing()) != rising:
                raise ValueError(f'Inconsistent crossing direction: {name}')
            sec_orekit = ev.getDate().durationFrom(epoch)
            results.append(dict(station=name, event='rise' if rising else 'set', skyfield_s=second,
                                orekit_s=sec_orekit, abs_delta_s=abs(sec_orekit-second)))
    maximum = max(x['abs_delta_s'] for x in results)
    return dict(orekit_data_commit=DATA_REV, threshold_degrees=10, duration_s=86400, tolerance_s=2,
                matched_events=len(results), max_time_difference_s=maximum, passed=maximum <= 2, events=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path.home() / '.cache/chistarlink/orekit')
    args = parser.parse_args()
    result = compare(args.cache)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
