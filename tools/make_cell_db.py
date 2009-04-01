from sys import stdin, stdout, stderr
from pyproj import Proj, transform
from math import sqrt
from struct import pack

NETWORKS = {
    '20408': (204, 8),
    '20620': (206, 20),
    '20801': (208, 1),
    '21403': (214, 3),
    '22801': (228, 1),
    '22803': (228, 3),
    '23106': (231, 6),
    '23201': (232, 1),
    '23203': (232, 3),
    '23205': (232, 5),
    '23430': (234, 30),
    '24201': (242, 1),
    '24405': (244, 5),
    '26001': (260, 1),
    '26201': (262, 1),
    '26202': (262, 2),
    '26203': (262, 3),
    '26206': (262, 6),
    '26207': (262, 7),
    '31026': (310, 26),
    '310420': (310, 420),
    '72234': (722, 34),
    '722310': (722, 310),
    'simyo': (0, 0),
}

pwgs84 = Proj(proj='lonlat',datum='WGS84')
pecef = Proj(proj='geocent', datum='WGS84')

class Center(object):
    def __init__(self):
        self.points = []

    def addPoint(self, point):
        self.points.append(point)

    def calc(self):
        ecefs = []
        for lat, long, alt in self.points:
            ecefs.append(transform(pwgs84, pecef, long, lat, alt))
        x_min = min([ecef[0] for ecef in ecefs])
        x_max = max([ecef[0] for ecef in ecefs])
        x_mid = (x_min+x_max)/2
        x_size = x_max-x_min
        y_min = min([ecef[1] for ecef in ecefs])
        y_max = max([ecef[1] for ecef in ecefs])
        y_mid = (y_min+y_max)/2
        y_size = y_max-y_min
        z_min = min([ecef[2] for ecef in ecefs])
        z_max = max([ecef[2] for ecef in ecefs])
        z_mid = (z_min+z_max)/2
        z_size = z_max-z_min
        size = sqrt(x_size**2 + y_size**2 + z_size**2) 
        long, lat, alt = transform(pecef, pwgs84, x_mid, y_mid, z_mid)
        return (lat, long, alt, size, len(ecefs))

cells = {}
las = {}

keys = stdin.readline().strip().split(";")

for line in stdin.readlines():
    if not line:
        continue
    data = dict(zip(keys, line.strip().split(";")))
    for key in ['cell_mcc', 'cell_mnc', 'cell_arfcn', 'signal', 'gps_time']:
        data[key] = int(data[key])
    for key in ['cell_la', 'cell_id']:
        data[key] = int(data[key], 16)
    for key in ['gps_lat', 'gps_long', 'gps_alt']:
        data[key] = float(data[key])
    if not data['cell_mcc']<999 or not data['cell_mnc']<999:
        data['cell_mcc'], data['cell_mnc'] = (0, 0)
    if data['cell_mcc']==0 or data['cell_mnc']==0:
        if len(data['provider']) == 4: 
            continue
        elif data['provider'] == '99999':
            continue
        elif data['provider'] in NETWORKS:
            data['cell_mcc'], data['cell_mnc'] = NETWORKS[data['provider']]
        else:
            stderr.write(line)
            continue
    if data['cell_mcc']==0 and data['cell_mnc']==0:
        continue
    cell_key = (data['cell_mcc'], data['cell_mnc'], data['cell_la'], data['cell_id'])
    cell_loc = (data['gps_lat'], data['gps_long'], data['gps_alt'])
    cell = cells.setdefault(cell_key, Center())
    cell.addPoint(cell_loc)
    la_key = cell_key[:-1]
    la = las.setdefault(la_key, Center())
    la.addPoint(cell_loc)

cells = cells.items()
cells.sort()
las = las.items()
las.sort()

cell_db = file('cell.db', 'wb')
for (cell_key, cell) in cells:
    cell_loc = cell.calc()
    print cell_key, cell_loc
    try:
        data = pack('!HHHHffff', *(cell_key+cell_loc)[:-1])
        cell_db.write(data)
    except:
        pass
cell_db.close()

la_db = file('la.db', 'wb')
for (la_key, la) in las:
    la_loc = la.calc()
    print la_key, la_loc
    try:
        data = pack('!HHHffff', *(la_key+la_loc)[:-1])
        la_db.write(data)
    except:
        pass
la_db.close()

