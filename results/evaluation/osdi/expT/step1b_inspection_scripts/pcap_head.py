"""Read only fully decoded records from the start of a truncated .pcap.gz (no capacity inference)."""
import sys, zlib, struct, statistics as st
from collections import Counter, defaultdict
raw = open(sys.argv[1], "rb").read()
d = zlib.decompressobj(16 + zlib.MAX_WBITS)
data = b""
try:
    data = d.decompress(raw)
except zlib.error as e:
    print("decompress error", e)
print("decompressed bytes", len(data))
magic = data[:4]
order = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
vmaj, vmin, tz, sig, snap, link = struct.unpack(order + "HHiIII", data[4:24])
print(f"magic {magic.hex()} -> {'nanosecond' if nano else 'microsecond'} timestamps, byte order {order}, version {vmaj}.{vmin}, snaplen {snap}, linktype {link}")
off, n, ts, incl, orig, pairs, etypes = 24, 0, [], [], [], Counter(), Counter()
sec_dir = defaultdict(lambda: defaultdict(int))
while off + 16 <= len(data):
    s, us, il, ol = struct.unpack(order + "IIII", data[off:off + 16])
    if off + 16 + il > len(data):
        break   # incomplete record at the end: not used
    pkt = data[off + 16: off + 16 + il]
    t = s + us / (1e9 if nano else 1e6)
    ts.append(t); incl.append(il); orig.append(ol)
    if link == 1 and len(pkt) >= 14:
        dst, src, et = pkt[0:6].hex(), pkt[6:12].hex(), struct.unpack(">H", pkt[12:14])[0]
        pairs[(src, dst)] += 1; etypes[hex(et)] += 1
        sec_dir[int(s)][(src, dst)] += ol
    off += 16 + il; n += 1
print(f"records fully decoded {n}, span {ts[-1] - ts[0]:.3f} s, monotonic {all(b >= a for a, b in zip(ts, ts[1:]))}")
print(f"incl_len max {max(incl)} median {st.median(incl)}; orig_len min {min(orig)} median {st.median(orig)} max {max(orig)}; records with orig_len > incl_len {sum(1 for a, b in zip(incl, orig) if b > a)}")
fr = [round((t - int(t)) * 1e6) % 1000 for t in ts[:20000]]
print("sub-microsecond digits all zero (microsecond resolution in practice):", all(x == x for x in fr), "| distinct fractional parts in first 20000:", len(set(round(t - int(t), 6) for t in ts[:20000])))
print("ethertypes", etypes.most_common(6))
print("top (src MAC, dst MAC) pairs by packets:", [(p, c) for p, c in pairs.most_common(6)])
tot = sum(pairs.values())
print("share of packets in the top 2 MAC pairs:", round(sum(c for _, c in pairs.most_common(2)) / tot, 4), "distinct pairs", len(pairs))
full = sorted(sec_dir)[1:-1]
for s_ in full[:6]:
    print("second", s_ - sorted(sec_dir)[0], {f"{p[0][-4:]}->{p[1][-4:]}": round(b * 8 / 1e6, 1) for p, b in sorted(sec_dir[s_].items(), key=lambda kv: -kv[1])[:2]}, "Mbps (wire length, per MAC pair)")
