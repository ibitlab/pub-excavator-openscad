#!/usr/bin/env python3
"""Об'єм STL (ASCII або binary), см³. Використання: stl_volume.py file.stl"""
import sys, struct
def tris(path):
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:1000]:
        v = []
        for line in data.decode('ascii', 'ignore').splitlines():
            line = line.strip()
            if line.startswith('vertex'):
                v.append(tuple(float(x) for x in line.split()[1:4]))
                if len(v) == 3: yield v; v = []
    else:
        n = struct.unpack('<I', data[80:84])[0]
        for i in range(n):
            o = 84 + i * 50 + 12
            f = struct.unpack('<9f', data[o:o + 36])
            yield [f[0:3], f[3:6], f[6:9]]
vol = 0.0
for a, b, c in tris(sys.argv[1]):
    vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
print(f"{abs(vol) / 1000.0:.3f}")
