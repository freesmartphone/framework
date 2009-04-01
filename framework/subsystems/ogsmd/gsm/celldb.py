from sys import stdin, stdout, stderr, argv
from math import sqrt
from struct import calcsize, pack, unpack

CELL_DB = '/etc/freesmartphone/ogsmd/cell.db'
LA_DB = '/etc/freesmartphone/ogsmd/la.db'

class SimpleCenter(object):
    # FIXME port pyproj to the neo and use it
    def __init__(self):
        self.points = []

    def addPoint(self, point):
        self.points.append(point)

    def calc(self):
        if not self.points:
            return None
        x_min = min([point[0] for point in self.points])
        x_max = max([point[0] for point in self.points])
        x_mid = (x_min+x_max)/2
        x_size = x_max-x_min
        y_min = min([point[1] for point in self.points])
        y_max = max([point[1] for point in self.points])
        y_mid = (y_min+y_max)/2
        y_size = y_max-y_min
        z_min = min([point[2] for point in self.points])
        z_max = max([point[2] for point in self.points])
        z_mid = (z_min+z_max)/2
        z_size = z_max-z_min
        size = sqrt(x_size**2 + y_size**2 + z_size**2) 
        return (x_mid, y_mid, z_mid, size, len(self.points))

class ProjCenter(object):
    def __init__(self):
        from pyproj import Proj, transform
        self.pwgs84 = Proj(proj='lonlat',datum='WGS84')
        self.pecef = Proj(proj='geocent', datum='WGS84')
        self.points = []

    def addPoint(self, point):
        self.points.append(point)

    def calc(self):
        if not self.points:
            return None
        ecefs = []
        for lat, long, alt in self.points:
            ecefs.append(transform(self.pwgs84, self.pecef, long, lat, alt))
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
        long, lat, alt = transform(self.pecef, self.pwgs84, x_mid, y_mid, z_mid)
        return (lat, long, alt, size, len(ecefs))

Center = SimpleCenter

def find(f, format, pattern_format, pattern_data):
    format_size = calcsize(format)
    pattern_size = calcsize(pattern_format)
    pattern = pack(pattern_format, *pattern_data)
    l = 0
    f.seek(0, 2)
    r = f.tell()/format_size
    while l < r:
        m = (r+l)/2
        f.seek(m*format_size)
        data = f.read(format_size)
        if pattern == data[:pattern_size]:
            return unpack(format, data)
        elif pattern<data[:pattern_size]:
            r = m
        elif data[:pattern_size]<pattern:
            l = m
        if l+1==r:
            return None

def get_cell(mcc, mnc, lac, cid):
    cell_db = file(CELL_DB, 'rb')
    result = find(cell_db, '!HHHHffff', '!HHHH', (mcc, mnc, lac, cid))
    cell_db.close()
    if result:
        return result[4:]
    else:
        return None

def get_center(mcc, mnc, cells):
    center = Center()
    cell_db = file(CELL_DB, 'rb')
    for lac, cid in cells:
        cell = find(cell_db, '!HHHHffff', '!HHHH', (mcc, mnc, lac, cid))
        if cell:
            center.addPoint(cell[4:7])
    cell_db.close()
    return center.calc()

def get_la(mcc, mnc, lac):
    la_db = file(LA_DB, 'rb')
    result = find(la_db, '!HHHffff', '!HHH', (mcc, mnc, lac))
    la_db.close()
    if result:
        return result[3:]
    else:
        return None

if __name__=="__main__":
    cell_count = (len(argv)-3)/2

    mcc, mnc = map(eval, argv[1:3])
    laccids = map(eval, argv[3:3+cell_count*2])

    cells = []
    for i in range(cell_count):
        cells.append(laccids[i*2:i*2+2])

    for lac, cid in cells:
        print 'Cell 0x%04x 0x%04x:' % (lac, cid), get_cell(mcc, mnc, lac, cid)

    print 'Center:', get_center(mcc, mnc, cells)

    print 'LA 0x%04x:' % lac, get_la(mcc, mnc, lac)
