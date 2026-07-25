#!/usr/bin/env python3
"""Rebuild the machine-readable OFAC SDN list from OFAC's own export.

Stdlib only, no dependencies, no API key. Run it and the files in data/ are
regenerated from source.

Nothing here is inferred, enriched or edited. Names, entity types and program
codes are OFAC's own strings. The only transformations are:

  * splitting the bracketed multi-value program column into a list, and
  * joining alternate names (ALT.CSV) onto their primary entry by ent_num.

The publication date is read from the folder OFAC's export URL redirects to
(.../Published/<id>/YYYY-MM-DD/...), never from the clock. A list that displays
its own build date as the publication date tells the reader the data is fresher
than it is, which is the one error in this file that would actually matter.

Usage:  python3 build.py
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

BASE = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports"
SDN_URL = BASE + "/SDN.CSV"
ALT_URL = BASE + "/ALT.CSV"
OFFICIAL_SEARCH = "https://sanctionssearch.ofac.treas.gov/"

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "data")

# OFAC uses the literal string "-0-" for an empty field.
EMPTY = {"-0-", "-0- ", ""}

# Fewer than this many parsed rows means the export format changed under us.
# Shipping a truncated sanctions list is worse than shipping nothing.
MIN_ENTRIES = 5000

SCOPE = (
    "OFAC SDN list primary names and alternate identities only. Does NOT include the OFAC "
    "Consolidated (non-SDN) lists, the Sectoral Sanctions Identifications (SSI) list, EU/UK/UN "
    "or any other jurisdiction's list, and does NOT perform 50 Percent Rule ownership analysis."
)

DISCLAIMER = (
    "Unofficial machine-readable mirror, provided for engineering use. OFAC's own SDN search at "
    + OFFICIAL_SEARCH + " is the authoritative source and should be used for any compliance "
    "decision. Nothing here is legal or compliance advice."
)

FIELDS = [
    {"name": "uid", "type": "integer", "description": "OFAC's own entity number (ent_num) for the designated party."},
    {"name": "name", "type": "string", "description": "Primary designated name, verbatim from OFAC's SDN.CSV."},
    {"name": "type", "type": "string", "description": "individual, entity, vessel or aircraft."},
    {"name": "programs", "type": "array<string>", "description": "OFAC sanctions program codes, e.g. RUSSIA-EO14024, SDGT."},
    {"name": "alternateNames", "type": "array<string>", "description": "AKAs joined from OFAC's ALT.CSV on the same uid."},
]


def fetch(url):
    """Return (body_bytes, effective_url). curl follows OFAC's signed-S3 redirect."""
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "180", "-w", "\n%{url_effective}", url],
        capture_output=True,
    )
    if r.returncode != 0:
        sys.exit("curl failed for %s: %s" % (url, r.stderr.decode()[:300]))
    body, _, eff = r.stdout.rpartition(b"\n")
    if len(body) < 50000:
        sys.exit("suspiciously small download from %s (%d bytes) — refusing to ship" % (url, len(body)))
    return body, eff.decode().strip()


def clean(v):
    v = (v or "").strip()
    return "" if v in EMPTY else v


def split_programs(raw):
    """'[SDGT] [IFSR]' -> ['SDGT', 'IFSR']."""
    out = []
    for part in re.split(r"\]\s*\[", (raw or "").strip().strip("[]")):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def published_date(effective_url):
    m = re.search(r"/(\d{4}-\d{2}-\d{2})/", effective_url)
    return m.group(1) if m else None


def main():
    sdn_raw, sdn_eff = fetch(SDN_URL)
    alt_raw, _ = fetch(ALT_URL)

    published = published_date(sdn_eff)
    if not published:
        sys.exit("could not read the publication date from OFAC's URL — refusing to ship an undated list")

    alts, alt_count = {}, 0
    for row in csv.reader(io.StringIO(alt_raw.decode("utf-8", "replace"))):
        if len(row) < 4:
            continue
        ent, name = clean(row[0]), clean(row[3])
        if not ent or not name:
            continue
        alts.setdefault(ent, [])
        if name not in alts[ent]:
            alts[ent].append(name)
            alt_count += 1

    records, programs, types = [], {}, {}
    for row in csv.reader(io.StringIO(sdn_raw.decode("utf-8", "replace"))):
        if len(row) < 4:
            continue
        ent, name, typ, prog = clean(row[0]), clean(row[1]), clean(row[2]), clean(row[3])
        if not ent or not name:
            continue
        typ = typ or "entity"
        types[typ] = types.get(typ, 0) + 1
        progs = split_programs(prog)
        for p in progs:
            programs[p] = programs.get(p, 0) + 1
        records.append({
            "uid": int(ent),
            "name": name,
            "type": typ,
            "programs": progs,
            "alternateNames": alts.get(ent, []),
        })

    if len(records) < MIN_ENTRIES:
        sys.exit("only %d SDN entries parsed — the export format likely changed; refusing to ship" % len(records))
    records.sort(key=lambda r: r["uid"])

    os.makedirs(OUTDIR, exist_ok=True)

    card = {
        "name": "OFAC Specially Designated Nationals (SDN) List — machine-readable",
        "description": (
            "The U.S. Treasury OFAC SDN list parsed into JSON and CSV: %d designated entries and "
            "%d alternate identities (%d names total), each with its OFAC uid, entity type and "
            "sanctions programs. Published %s by OFAC."
            % (len(records), alt_count, len(records) + alt_count, published)
        ),
        "source": "U.S. Treasury OFAC — Specially Designated Nationals and Blocked Persons List (SDN)",
        "sourceUrl": SDN_URL,
        "altSourceUrl": ALT_URL,
        "officialSearchUrl": OFFICIAL_SEARCH,
        "published": published,
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "counts": {
            "entries": len(records),
            "alternateNames": alt_count,
            "totalNames": len(records) + alt_count,
        },
        "typeCounts": types,
        "topPrograms": sorted(programs.items(), key=lambda kv: -kv[1])[:15],
        "scope": SCOPE,
        "disclaimer": DISCLAIMER,
        "license": "CC0-1.0 (packaging). The underlying list is a U.S. Government work in the public domain (17 U.S.C. 105).",
        "fields": FIELDS,
    }

    payload = dict(card)
    payload["entries"] = records
    with open(os.path.join(OUTDIR, "ofac-sdn.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(OUTDIR, "ofac-sdn.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["uid", "name", "type", "programs", "alternate_names"])
        for r in records:
            w.writerow([r["uid"], r["name"], r["type"],
                        "; ".join(r["programs"]), "; ".join(r["alternateNames"])])

    card["bytes"] = {
        "json": os.path.getsize(os.path.join(OUTDIR, "ofac-sdn.json")),
        "csv": os.path.getsize(os.path.join(OUTDIR, "ofac-sdn.csv")),
    }
    with open(os.path.join(OUTDIR, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(card, fh, ensure_ascii=False, indent=1)

    print("OFAC SDN dataset built")
    print("  OFAC published : %s" % published)
    print("  retrieved      : %s" % card["retrieved"])
    print("  entries        : %d" % len(records))
    print("  alternate names: %d" % alt_count)
    print("  types          : %s" % types)
    print("  json           : %.2f MB" % (card["bytes"]["json"] / 1048576.0))
    print("  csv            : %.2f MB" % (card["bytes"]["csv"] / 1048576.0))


if __name__ == "__main__":
    main()
