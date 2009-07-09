from sys import stdin, stdout, stderr, argv
from math import sqrt
from struct import calcsize, pack, unpack

CELL_DB = 'cell.db'
LA_DB = 'la.db'

def dump_cell_db():
    cell_db = file(CELL_DB, 'rb')
    format = '!HHHHffff'
    format_size = calcsize(format)
    data = cell_db.read(format_size)
    while data:
        print unpack(format, data)
        data = cell_db.read(format_size)
    cell_db.close()

def dump_la_db():
    la_db = file(LA_DB, 'rb')
    format = '!HHHffff'
    format_size = calcsize(format)
    data = la_db.read(format_size)
    while data:
        print unpack(format, data)
        data = la_db.read(format_size)
    la_db.close()

if __name__=="__main__":
    dump_cell_db()
    dump_la_db()
