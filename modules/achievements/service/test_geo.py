"""geo.py: the MMDB reader (against a tiny database built here), the trust/proxy rule and the
region fallback. The no-leak test checks that no address text survives into a region."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402


# -- a minimal MMDB writer: IPv4 tree, record size 24 -----------------------------------------
def enc(v):
    def hdr(typ, size):
        ext = typ > 7
        first = (0 if ext else typ << 5)
        if size < 29:
            out = bytes([first | size])
        elif size < 285:
            out = bytes([first | 29, size - 29])
        else:
            raise ValueError
        return out + (bytes([typ - 7]) if ext else b"")
    if isinstance(v, dict):
        return hdr(7, len(v)) + b"".join(enc(k) + enc(x) for k, x in v.items())
    if isinstance(v, list):
        return hdr(11, len(v)) + b"".join(enc(x) for x in v)
    if isinstance(v, str):
        b = v.encode()
        return hdr(2, len(b)) + b
    if isinstance(v, float):
        return hdr(3, 8) + struct.pack(">d", v)
    if isinstance(v, int):
        b = v.to_bytes(max(1, (v.bit_length() + 7) // 8), "big")
        return hdr(6 if len(b) > 2 else 5, len(b)) + b
    raise TypeError(v)


def build_db(entries):
    """entries: [("99.250.10.0/24", record), ...] -> mmdb bytes (IPv4, 24-bit records)."""
    nodes = [[None, None]]     # [left, right]: ("node", i) | ("data", i) | None
    records = []
    for cidr, rec in entries:
        net, bits = cidr.split("/")
        n = 0
        for b in bytes(int(x) for x in net.split(".")):
            n = (n << 8) | b
        bits = int(bits)
        cur = 0
        for i in range(bits):
            bit = (n >> (31 - i)) & 1
            if i == bits - 1:
                nodes[cur][bit] = ("data", len(records))
                break
            nxt = nodes[cur][bit]
            if nxt is None:
                nodes.append([None, None])
                nxt = ("node", len(nodes) - 1)
                nodes[cur][bit] = nxt
            cur = nxt[1]
        records.append(rec)
    count = len(nodes)
    data, offsets = b"", []
    for r in records:
        offsets.append(len(data))
        data += enc(r)

    def val(slot):
        if slot is None:
            return count
        return slot[1] if slot[0] == "node" else count + 16 + offsets[slot[1]]
    tree = b"".join(val(l).to_bytes(3, "big") + val(r).to_bytes(3, "big") for l, r in nodes)
    meta = enc({"node_count": count, "record_size": 24, "ip_version": 4, "database_type": "test"})
    return tree + b"\x00" * 16 + data + geo.MARKER + meta


TORONTO = {"city": {"names": {"en": "Toronto"}}, "subdivisions": [{"names": {"en": "Ontario"}}],
           "country": {"iso_code": "CA", "names": {"en": "Canada"}},
           "location": {"latitude": 43.6532, "longitude": -79.3832}}
VANCOUVER = {"city": {"names": {"en": "Vancouver"}}, "country": {"iso_code": "CA"},
             "location": {"latitude": 49.2827, "longitude": -123.1207}}
DB = build_db([("99.250.10.0/24", TORONTO), ("24.80.10.0/25", VANCOUVER)])


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.r = geo.Reader(DB)

    def test_finds_records_by_prefix(self):
        import ipaddress
        self.assertEqual(self.r.lookup(ipaddress.ip_address("99.250.10.77"))["city"]["names"]["en"], "Toronto")
        self.assertEqual(self.r.lookup(ipaddress.ip_address("24.80.10.5"))["location"]["longitude"], -123.1207)

    def test_misses_are_none(self):
        import ipaddress
        self.assertIsNone(self.r.lookup(ipaddress.ip_address("24.80.10.200")))   # outside the /25
        self.assertIsNone(self.r.lookup(ipaddress.ip_address("8.8.8.8")))
        self.assertIsNone(self.r.lookup(ipaddress.ip_address("2001:db8::1")))      # v6 into a v4 tree

    def test_opens_a_file_by_mapping_it(self):
        import ipaddress
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mmdb") as f:
            f.write(DB)
            f.flush()
            r = geo.Reader.open(f.name)
            self.assertEqual(r.lookup(ipaddress.ip_address("99.250.10.1"))["country"]["iso_code"], "CA")
            loc = geo.Locator(db_path=f.name)
            self.assertEqual(loc.locate("a", "24.80.10.9")["place"], "Vancouver, CA")

    def test_garbage_is_refused(self):
        with self.assertRaises(geo.MmdbError):
            geo.Reader(b"not a database")


class ClientIpTests(unittest.TestCase):
    def test_rightmost_public_wins_over_a_forged_leftmost(self):
        self.assertEqual(str(geo.client_ip("1.2.3.4, 99.250.10.9, 10.0.0.2")), "99.250.10.9")

    def test_private_only_is_none(self):
        for v in ("10.1.2.3", "172.20.0.1, 192.168.1.5", "127.0.0.1", "169.254.1.1", "", None, "junk", "::1"):
            self.assertIsNone(geo.client_ip(v), v)

    def test_ipv6_public(self):
        self.assertEqual(str(geo.client_ip("2606:4700::1111")), "2606:4700::1111")


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.loc = geo.Locator(reader=geo.Reader(DB), home="toronto")

    def test_coarse_rounding(self):
        self.assertEqual(geo.coarse(43.6532, -79.3832), (43.5, -79.5))
        self.assertEqual(geo.coarse(49.2827, -123.1207), (49.5, -123.0))

    def test_lookup_gives_a_coarse_labelled_region(self):
        r = self.loc.locate("alice", "99.250.10.9")
        self.assertEqual((r["lat"], r["lon"], r["place"], r["src"]), (43.5, -79.5, "Toronto, ON", "geoip"))
        self.assertEqual(self.loc.locate("bob", "24.80.10.5")["place"], "Vancouver, CA")

    def test_private_address_falls_back_to_the_home_region_with_jitter(self):
        a = self.loc.locate("alice", "172.19.0.4")
        b = self.loc.locate("bob", "172.19.0.4")
        self.assertEqual((a["src"], a["place"]), ("default", "Toronto, ON"))
        self.assertNotEqual((a["lat"], a["lon"]), (b["lat"], b["lon"]))          # spread, not stacked
        self.assertEqual(a, self.loc.locate("alice", "10.0.0.9"))                # deterministic
        self.assertLess(abs(a["lat"] - 43.5), 0.5)
        self.assertLess(abs(a["lon"] + 79.5), 0.5)

    def test_public_address_with_no_database_uses_the_home_region(self):
        r = geo.Locator(db_path="/nonexistent/db.mmdb", home="Vancouver").locate("alice", "99.250.10.9")
        self.assertEqual((r["src"], r["place"]), ("default", "Vancouver, BC"))

    def test_unknown_public_address_falls_back(self):
        self.assertEqual(self.loc.locate("alice", "8.8.8.8")["src"], "default")

    def test_a_corrupt_database_never_raises(self):
        loc = geo.Locator(reader=geo.Reader(DB[:20] + b"\xff" * 30 + DB[50:]), home="toronto")
        self.assertIn(loc.locate("alice", "99.250.10.9")["src"], ("default", "geoip"))

    def test_no_ip_in_the_region(self):
        for xff in ("99.250.10.9", "1.2.3.4, 24.80.10.5", "172.19.0.4"):
            r = self.loc.locate("alice", xff)
            blob = repr(r)
            for part in xff.replace(" ", "").split(","):
                self.assertNotIn(part, blob)
            self.assertEqual(set(r), {"lat", "lon", "place", "src"})

    def test_labels_are_short(self):
        rec = {"city": {"names": {"en": "Kamloops (Thompson Rivers University)"}}, "country": {"iso_code": "CA"},
               "subdivisions": [{"names": {"en": "British Columbia"}}], "location": {"latitude": 50.67, "longitude": -120.33}}
        self.assertEqual(geo.region_from_record(rec)["place"], "Kamloops, BC")

    def test_parse_place(self):
        self.assertEqual(geo.parse_place("Vancouver")[2], "Vancouver, BC")
        self.assertEqual(geo.parse_place("51.04,-114.07,Calgary HQ"), (51.0, -114.0, "Calgary HQ"))
        self.assertIsNone(geo.parse_place("nowhere", None))
        self.assertIsNone(geo.parse_place("95,10", None))


if __name__ == "__main__":
    unittest.main()
