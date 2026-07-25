# OFAC SDN list as JSON and CSV

The U.S. Treasury's **Specially Designated Nationals and Blocked Persons (SDN) list**, parsed
straight from OFAC's own export into two files you can actually load.

**19,254** designated entries · **20,350** alternate identities · **39,604** names total
Rebuilt daily. No API key, no signup, no rate limit.

| Download | Size | |
|---|---|---|
| [`data/ofac-sdn.json`](data/ofac-sdn.json) | 3.6 MB | full records + metadata |
| [`data/ofac-sdn.csv`](data/ofac-sdn.csv) | 1.6 MB | flat, one row per entry |
| [`data/metadata.json`](data/metadata.json) | 3 KB | counts, dates, schema, no records |

```
https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.json
https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.csv
```

## Why this exists

OFAC publishes the SDN list, but it publishes it as a **headerless CSV**, with a **separate
alternate-names file**, a **bracketed multi-value program column**, and the literal string
`-0-` standing in for empty fields. Every team that needs this data writes the same parser, gets
the AKA join subtly wrong, and rediscovers that `[SDGT] [IFSR]` is two programs and not one.

This is that parser's output, rebuilt from source and republished.

## The data

```json
{
  "uid": 36,
  "name": "AEROCARIBBEAN AIRLINES",
  "type": "entity",
  "programs": ["CUBA"],
  "alternateNames": ["AERO-CARIBBEAN"]
}
```

| Field | Type | Description |
|---|---|---|
| `uid` | integer | OFAC's own entity number (`ent_num`) |
| `name` | string | Primary designated name, verbatim from `SDN.CSV` |
| `type` | string | `individual`, `entity`, `vessel` or `aircraft` |
| `programs` | array&lt;string&gt; | Sanctions program codes, e.g. `RUSSIA-EO14024`, `SDGT` |
| `alternateNames` | array&lt;string&gt; | AKAs joined from `ALT.CSV` on the same `uid` |

The JSON file wraps these in an object carrying `published`, `retrieved`, `counts`, `scope` and
`fields`, with the records under `entries`.

### By entity type

| Type | Entries |
|---|---:|
| entity | 9,873 |
| individual | 7,520 |
| vessel | 1,517 |
| aircraft | 344 |

### Largest programs

| Program | Entries |
|---|---:|
| `RUSSIA-EO14024` | 6,353 |
| `SDGT` | 3,249 |
| `IFSR` | 1,540 |
| `SDNTK` | 1,400 |
| `NPWMD` | 1,174 |
| `IRAN-EO13902` | 884 |
| `GLOMAG` | 740 |
| `ILLICIT-DRUGS-EO14059` | 704 |

## Use it

**Python**

```python
import urllib.request, json

url = "https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.json"
data = json.load(urllib.request.urlopen(url))

print(data["published"], data["counts"]["entries"])

names = {e["name"].upper() for e in data["entries"]}
names |= {a.upper() for e in data["entries"] for a in e["alternateNames"]}
print("ACME TRADING" in names)
```

**pandas**

```python
import pandas as pd

df = pd.read_csv("https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.csv")
df[df["programs"].str.contains("RUSSIA-EO14024", na=False)].head()
```

**DuckDB**

```sql
SELECT type, count(*)
FROM 'https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.csv'
GROUP BY type ORDER BY 2 DESC;
```

**JavaScript**

```js
const res = await fetch("https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.json");
const { published, entries } = await res.json();
```

**Shell**

```bash
curl -sL https://raw.githubusercontent.com/kindrat86/ofac-sdn-json/main/data/ofac-sdn.csv -o ofac-sdn.csv
```

## Rebuild it yourself

```bash
python3 build.py
```

Stdlib only, no dependencies. It fetches `SDN.CSV` and `ALT.CSV` from OFAC, joins them, and
writes `data/`. A GitHub Action runs the same script daily and commits only when the output
actually changes.

The build refuses to ship rather than ship something wrong. It exits non-zero if the download is
implausibly small, if fewer than 5,000 entries parse (the export format changed), or if it cannot
read a publication date. **The `published` date is OFAC's own**, read from the folder their export
URL redirects to — never the build date. A sanctions list that displays its build date as its
publication date tells a compliance officer the data is fresher than it is.

## Scope — read this before you rely on it

This covers the **SDN list only**. It does **not** include:

- the OFAC **Consolidated (non-SDN)** lists
- the **Sectoral Sanctions Identifications (SSI)** list
- **EU, UK, UN** or any other jurisdiction's list

It does **not** perform **50 Percent Rule** ownership analysis — an entity owned 50% or more by
one or more blocked persons is itself blocked, whether or not it appears on this list. Matching a
name against these files is not sanctions screening; real screening needs fuzzy matching,
transliteration handling, and ownership resolution.

OFAC's own [sanctions search](https://sanctionssearch.ofac.treas.gov/) is the authoritative
source and should be used for any compliance decision. **Nothing here is legal or compliance
advice.**

## Licence

The SDN list is a work of the U.S. Government and is **in the public domain**
([17 U.S.C. § 105](https://www.law.cornell.edu/uscode/text/17/105)). No rights are claimed over
it here. The parsing and packaging in this repository are released under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

Cite as:

> U.S. Department of the Treasury, Office of Foreign Assets Control. *Specially Designated
> Nationals and Blocked Persons List*. Machine-readable edition,
> https://github.com/kindrat86/ofac-sdn-json

## Related

- **[Screen names in your browser](https://sanctionsai.dev/free/ofac-screening)** — paste a list,
  match it against this data client-side. Nothing is uploaded.
- **[Hosted dataset page](https://sanctionsai.dev/data/ofac-sdn-list/)** — the same files with a
  landing page, if you'd rather link to something readable.
- **[Screening API](https://sanctionsai.dev/docs)** — fuzzy matching, wallet-address screening
  and audit logging, for when name-equality isn't enough. Has a free tier.
