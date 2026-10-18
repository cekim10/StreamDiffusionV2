import sys, zlib, struct
from collections import Counter
data = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(open(sys.argv[1], "rb").read())
off, ts, inc, back, maxback, crossing = 24, None, Counter(), 0, 0.0, 0
prev = None; n = 0; over = 0; jumbo = 0
while off + 16 <= len(data):
    s, us, il, ol = struct.unpack("<IIII", data[off:off + 16])
    if off + 16 + il > len(data): break
    t = s + us / 1e6
    if prev is not None and t < prev:
        back += 1; maxback = max(maxback, prev - t)
        if int(t) != int(prev): crossing += 1
    prev = max(prev or t, t); n += 1
    over += il > 96; jumbo += ol > 1518
    off += 16 + il
print(f"records {n}; backward timestamp steps {back} ({100*back/n:.2f} %), largest {maxback*1e3:.3f} ms, steps that cross a 1 s boundary {crossing}")
print(f"records with incl_len > 96: {over}; records with orig_len > 1518 (larger than a standard Ethernet frame): {jumbo} ({100*jumbo/n:.2f} %)")
