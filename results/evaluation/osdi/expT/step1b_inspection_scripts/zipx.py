import sys, zipfile, os
z = zipfile.ZipFile(sys.argv[1]); out = sys.argv[2]
for i in z.infolist():
    p = os.path.normpath(os.path.join(out, i.filename))
    assert p.startswith(os.path.abspath(out)), p   # no path traversal
z.extractall(out)
