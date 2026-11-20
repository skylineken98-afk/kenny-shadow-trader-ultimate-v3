"""House disclosure index adapted from Jake Schincariol (MIT, see LICENSE)."""

import datetime as _dt
import io
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/%d%s.zip"
PTR_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/%d/%s.pdf"
FD_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/%d/%s.pdf"
UA = "day-trader-skill/2.0 (+https://github.com/Jakeschincariol/day-trader-skill)"
FILING_TYPES = {
    "P": "Periodic Transaction Report", "O": "Annual report", "A": "Amendment",
    "C": "Candidate report", "X": "Extension", "T": "Termination report",
    "W": "Waiver", "D": "Disclosure (new member or candidate)", "H": "New filer report",
}


class PtrError(Exception):
    pass


# ---------------------------------------------------------------- the index

def iso(mdy):
    """'8/21/2026' or '08/21/2026' -> '2026-08-21' (two-digit years -> 20xx)."""
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$", mdy or "")
    if not m:
        return None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 100:
        year += 2000
    try:
        return _dt.date(year, month, day).isoformat()
    except ValueError:
        return None


def download(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise PtrError("HTTP %s for %s" % (exc.code, url))
    except urllib.error.URLError as exc:
        raise PtrError("could not reach %s: %s" % (url, exc.reason))


def read_index_bytes(data):
    """Index XML bytes from the ZIP (or the XML itself)."""
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if not names:
                raise PtrError("no XML inside the ZIP (files: %s)" % ", ".join(z.namelist()))
            return z.read(names[0])
    return data


def parse_index(xml_bytes, year):
    """Every filing in a <YEAR>FD.xml as a dict, newest first."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise PtrError("index is not valid XML: %s" % exc)
    out = []
    for m in root.iter("Member"):
        f = {c.tag: (c.text or "").strip() for c in m}
        doc = f.get("DocID", "")
        kind = f.get("FilingType", "")
        y = int(f.get("Year") or year)
        url = (PTR_URL if kind == "P" else FD_URL) % (y, doc)
        name = " ".join(x for x in (f.get("Prefix"), f.get("First"), f.get("Last"),
                                    f.get("Suffix")) if x)
        out.append({"doc_id": doc, "type": kind, "type_name": FILING_TYPES.get(kind, kind),
                    "last": f.get("Last", ""), "first": f.get("First", ""), "name": name,
                    "district": f.get("StateDst", ""), "year": y,
                    "filed": iso(f.get("FilingDate", "")), "url": url})
    out.sort(key=lambda r: (r["filed"] or "", r["doc_id"]), reverse=True)
    return out


def load_index(year, offline=None):
    if offline:
        with open(offline, "rb") as fh:
            data = fh.read()
    else:
        data = download(INDEX_URL % (year, "FD"))
    return parse_index(read_index_bytes(data), year)


def member_match(row, member):
    """'pelosi', 'Nancy Pelosi' or 'Pelosi, Nancy' against an index row."""
    member = (member or "").strip().lower()
    if not member:
        return True
    if "," in member:
        last, first = [x.strip() for x in member.split(",", 1)]
    else:
        parts = member.split()
        last, first = parts[-1], " ".join(parts[:-1])
    if row["last"].lower() != last:
        return False
    return not first or row["first"].lower().startswith(first)


def select(rows, members=None, kind="P", since=None):
    out = []
    for r in rows:
        if kind and r["type"] != kind:
            continue
        if members and not any(member_match(r, m) for m in members):
            continue
        if since and (r["filed"] or "") < since:
            continue
        out.append(r)
    return out
