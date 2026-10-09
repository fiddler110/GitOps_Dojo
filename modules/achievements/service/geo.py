"""Coarse student location for the cyber map: a pure-python MMDB reader plus the region rules.

PRIVACY RULE (the whole point of this file): a client IP is looked up and then DROPPED. Only a
coarse region comes out of here (city-level lat/lon rounded to 0.5 degrees plus a place label);
no function stores, returns, logs or formats the address, and nothing here raises with it in a
message. The caller passes the X-Forwarded-For text straight in and gets a region (or None) back.

Resolution: an optional offline "IP to City Lite" database from DB-IP (CC BY 4.0: the map page
shows the attribution). With no database, or for a private/loopback address (WSL, a LAN), the
caller falls back to the facilitator's home region (CTF_HOME_REGION, default Toronto) with a small
deterministic per-student jitter so the dots do not stack. Stdlib only.
"""
import hashlib
import ipaddress
import struct

MARKER = b"\xab\xcd\xefMaxMind.com"

# City presets for CTF_HOME_REGION and the facilitator override ("Vancouver", or "lat,lon,Label").
PLACES = {
    "toronto": (43.5, -79.5, "Toronto, ON"), "ottawa": (45.5, -75.5, "Ottawa, ON"),
    "montreal": (45.5, -73.5, "Montreal, QC"), "halifax": (44.5, -63.5, "Halifax, NS"),
    "winnipeg": (49.5, -97.0, "Winnipeg, MB"), "calgary": (51.0, -114.0, "Calgary, AB"),
    "edmonton": (53.5, -113.5, "Edmonton, AB"), "vancouver": (49.0, -123.0, "Vancouver, BC"),
    "victoria": (48.5, -123.5, "Victoria, BC"),
}


# -- MMDB reader ---------------------------------------------------------------------------
class MmdbError(ValueError):
    pass


class Reader:
    """Just enough of the MaxMind DB format (v2) to look up an IP in a City database."""

    def __init__(self, data):
        self.data = data
        start = data.rfind(MARKER)
        if start < 0:
            raise MmdbError("not an MMDB file")
        self._meta_start = start + len(MARKER)
        meta, _ = self._decode(self._meta_start, self._meta_start)
        try:
            self.node_count = meta["node_count"]
            self.record_size = meta["record_size"]
            self.ip_version = meta["ip_version"]
        except (KeyError, TypeError):
            raise MmdbError("bad MMDB metadata")
        if self.record_size not in (24, 28, 32) or self.ip_version not in (4, 6):
            raise MmdbError("unsupported MMDB layout")
        self.node_bytes = self.record_size // 4
        self.tree_size = self.node_bytes * self.node_count
        self.data_start = self.tree_size + 16
        self._v4_root = None

    @classmethod
    def open(cls, path):
        """Map the file instead of reading it: the city database is over 100 MB and the service
        runs in a small container; mapped pages are reclaimable cache, only touched ones load."""
        import mmap
        with open(path, "rb") as f:
            return cls(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ))

    def _node(self, n, bit):
        d, nb = self.data, self.node_bytes
        off = n * nb
        if off + nb > self.tree_size:
            raise MmdbError("corrupt search tree")
        if self.record_size == 24:
            return int.from_bytes(d[off + 3 * bit: off + 3 * bit + 3], "big")
        if self.record_size == 32:
            return int.from_bytes(d[off + 4 * bit: off + 4 * bit + 4], "big")
        mid = d[off + 3]
        if bit == 0:
            return ((mid & 0xF0) << 20) | int.from_bytes(d[off:off + 3], "big")
        return ((mid & 0x0F) << 24) | int.from_bytes(d[off + 4:off + 7], "big")

    def lookup(self, ip):
        """The record dict for IP (an ipaddress object), or None."""
        packed = ip.packed
        if len(packed) == 16 and self.ip_version == 4:
            return None
        node = 0
        if len(packed) == 4 and self.ip_version == 6:
            if self._v4_root is None:
                n = 0
                for _ in range(96):
                    if n >= self.node_count:
                        break
                    n = self._node(n, 0)
                self._v4_root = n
            node = self._v4_root
        for byte in packed:
            for shift in range(7, -1, -1):
                if node >= self.node_count:
                    break
                node = self._node(node, (byte >> shift) & 1)
        if node == self.node_count:
            return None
        if node < self.node_count:
            raise MmdbError("corrupt search tree")
        value, _ = self._decode(self.tree_size + node - self.node_count, self.data_start)
        return value

    # -- data section decoder
    def _decode(self, off, base):
        d = self.data
        if off >= len(d):
            raise MmdbError("corrupt data section")
        ctrl = d[off]
        off += 1
        typ = ctrl >> 5
        if typ == 1:    # pointer
            ss, vvv = (ctrl >> 3) & 3, ctrl & 7
            if ss == 0:
                ptr = (vvv << 8) | d[off]
            elif ss == 1:
                ptr = ((vvv << 16) | int.from_bytes(d[off:off + 2], "big")) + 2048
            elif ss == 2:
                ptr = ((vvv << 24) | int.from_bytes(d[off:off + 3], "big")) + 526336
            else:
                ptr = int.from_bytes(d[off:off + 4], "big")
            off += ss + 1 if ss < 3 else 4
            value, _ = self._decode(base + ptr, base)
            return value, off
        if typ == 0:
            typ = 7 + d[off]
            off += 1
        size = ctrl & 0x1F
        if size == 29:
            size, off = 29 + d[off], off + 1
        elif size == 30:
            size, off = 285 + int.from_bytes(d[off:off + 2], "big"), off + 2
        elif size == 31:
            size, off = 65821 + int.from_bytes(d[off:off + 3], "big"), off + 3
        if typ == 7:    # map
            out = {}
            for _ in range(size):
                key, off = self._decode(off, base)
                out[key], off = self._decode(off, base)
            return out, off
        if typ == 11:   # array
            out = []
            for _ in range(size):
                item, off = self._decode(off, base)
                out.append(item)
            return out, off
        if typ == 14:   # boolean: the size is the value
            return bool(size), off
        raw = d[off:off + size]
        if len(raw) != size:
            raise MmdbError("corrupt data section")
        off += size
        if typ == 2:
            return raw.decode("utf-8", "replace"), off
        if typ == 3:
            return struct.unpack(">d", raw)[0], off
        if typ == 15:
            return struct.unpack(">f", raw)[0], off
        if typ in (5, 6, 9, 10):
            return int.from_bytes(raw, "big"), off
        if typ == 8:
            return int.from_bytes(raw, "big", signed=len(raw) == 4), off
        if typ == 4:
            return raw, off
        raise MmdbError("unsupported MMDB data type")


# -- region rules --------------------------------------------------------------------------
def client_ip(xff):
    """The real client from an X-Forwarded-For value: the RIGHT-most public address. Caddy appends
    the peer it saw, so the right end is trusted proxies' work; anything a client prepends sits to
    the left of it. Private/loopback/link-local entries (our own proxies, a LAN) are skipped.
    None when there is no public address. Returns an ipaddress object; callers must not keep it."""
    if not isinstance(xff, str):
        return None
    for part in reversed(xff.split(",")):
        try:
            ip = ipaddress.ip_address(part.strip())
        except ValueError:
            continue
        if ip.is_global:
            return ip
    return None


def coarse(lat, lon):
    """Round to the nearest half degree (about 50 km): a city, never a street."""
    return round(float(lat) * 2) / 2, round(float(lon) * 2) / 2


def parse_place(spec, default=None):
    """A preset name ("Vancouver") or "lat,lon,Label" -> (lat, lon, label), coarsened; else DEFAULT."""
    if not isinstance(spec, str):
        return default
    spec = spec.strip()
    if spec.lower() in PLACES:
        return PLACES[spec.lower()]
    parts = [p.strip() for p in spec.split(",", 2)]
    if len(parts) >= 2:
        try:
            lat, lon = coarse(parts[0], parts[1])
        except ValueError:
            return default
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon, (parts[2][:40] if len(parts) == 3 and parts[2] else "%.1f, %.1f" % (lat, lon))
    return default


def home_region(user, home):
    """HOME (lat, lon, label) with a small deterministic per-student offset (up to ~0.4 degrees),
    so a room on one LAN spreads over the city instead of stacking on one dot."""
    h = hashlib.sha256(("geo:" + str(user)).encode()).digest()
    dlat = (h[0] / 255 - 0.5) * 0.6
    dlon = (h[1] / 255 - 0.5) * 0.8
    return {"lat": round(home[0] + dlat, 2), "lon": round(home[1] + dlon, 2), "place": home[2], "src": "default"}


PROVINCES = {"Ontario": "ON", "Quebec": "QC", "British Columbia": "BC", "Alberta": "AB", "Manitoba": "MB",
             "Saskatchewan": "SK", "Nova Scotia": "NS", "New Brunswick": "NB", "Newfoundland and Labrador": "NL",
             "Prince Edward Island": "PE", "Yukon": "YT", "Northwest Territories": "NT", "Nunavut": "NU"}


def _name(node):
    names = node.get("names") if isinstance(node, dict) else None
    return (names.get("en") if isinstance(names, dict) else None) or None


def region_from_record(rec):
    """A coarse {"lat","lon","place","src"} from a DB-IP/GeoLite city record, or None."""
    if not isinstance(rec, dict):
        return None
    loc = rec.get("location") or {}
    lat, lon = loc.get("latitude"), loc.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    lat, lon = coarse(lat, lon)
    subs = rec.get("subdivisions") or []
    sub = _name(subs[0]) if subs and isinstance(subs[0], dict) else None
    city = _name(rec.get("city"))
    if city:
        city = city.split(" (")[0].strip()      # "Toronto (Old Toronto)" -> "Toronto"
    sub = PROVINCES.get(sub, sub)
    country = (rec.get("country") or {}).get("iso_code") if isinstance(rec.get("country"), dict) else None
    place = ", ".join(x for x in ((city, sub) if city and sub else (city, country) if city else (country,)) if x)
    return {"lat": lat, "lon": lon, "place": (place or _name(rec.get("country")) or "unknown")[:60], "src": "geoip"}


class Locator:
    """db_path: the optional mmdb (a missing or unreadable file just means "no database")."""

    def __init__(self, db_path=None, home="toronto", reader=None):
        self.home = parse_place(home, PLACES["toronto"])
        self.reader = reader
        if reader is None and db_path:
            try:
                self.reader = Reader.open(db_path)
            except (OSError, MmdbError):
                self.reader = None

    def locate(self, user, xff):
        """A region for USER from the X-Forwarded-For text, or the home-region fallback. Never
        returns, stores or logs the address; a bad database answer means the fallback too."""
        ip = client_ip(xff)
        region = None
        if ip is not None and self.reader is not None:
            try:
                region = region_from_record(self.reader.lookup(ip))
            except (MmdbError, IndexError, KeyError, TypeError, ValueError, struct.error, RecursionError):
                region = None
        ip = None
        return region or home_region(user, self.home)
