"""Inventory release inputs without assigning rights from a file extension or directory.

This local audit is deliberately excluded from the proposed public export: the
working archive can contain personal paths and unpublished research evidence.
"""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/open-source"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def records(value, source, pointer=""):
    if isinstance(value, dict):
        if any(k in value for k in ("license", "licenseUrl", "licence")):
            yield {"evidenceFile": source, "pointer": pointer,
                   **{k: value[k] for k in ("id", "file", "source", "sourceUrl", "title", "author", "license", "licence", "licenseUrl", "sha256", "usage", "status") if k in value}}
        for key, item in value.items():
            yield from records(item, source, pointer + "/" + str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from records(item, source, pointer + "/" + str(i))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((ROOT / "src/tour/vehicle-assets.json").read_text())
    vehicles = []
    for ident, asset in mapping.items():
        quality = ROOT / "public" / asset["quality"].lstrip("/")
        q = json.loads(quality.read_text()) if quality.exists() else {}
        provenance = q.get("sourceProvenance", {})
        notes = json.dumps({"provenance": provenance, "limitations": q.get("limitations", [])}, ensure_ascii=False)
        noncommercial = "NC" in asset.get("license", "")
        unclear = bool(re.search(r"HUMSTER|requires-source|not independently|not.*audited|extracted|CSR2", notes, re.I))
        files = []
        for key in ("file", "trafficFile", "preview", "quality"):
            if key in asset:
                p = ROOT / "public" / asset[key].lstrip("/")
                files.append({"role": key, "file": str(p.relative_to(ROOT)), "exists": p.is_file(),
                              "bytes": p.stat().st_size if p.is_file() else None,
                              "sha256": digest(p) if p.is_file() else None})
        vehicles.append({"id": ident, "declaredLicense": asset.get("license"), "author": asset.get("author"),
                         "source": asset.get("source"), "files": files, "sourceProvenance": provenance,
                         "noncommercial": noncommercial, "ownershipCaveatFound": unclear,
                         "decision": "EXCLUDE_NONCOMMERCIAL" if noncommercial else "HOLD_OWNERSHIP" if unclear else "REVIEW_PRIMARY_SOURCE",
                         "notLegalConclusion": True})
    evidence = []
    for folder in ("references", "assets/vehicles/source", "assets/vehicles/luxury-source"):
        for p in sorted((ROOT / folder).rglob("*.json")):
            if p.name.startswith("._") or p.stat().st_size > 4_000_000:
                continue
            try:
                evidence.extend(records(json.loads(p.read_text()), str(p.relative_to(ROOT))))
            except (ValueError, UnicodeError):
                continue
    files = []
    for p in sorted((ROOT / "public").rglob("*")):
        if not p.is_file() or p.is_symlink() or p.name.startswith("._") or p.name == ".DS_Store":
            continue
        files.append({"file": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
                      "sha256": digest(p), "publicationStatus": "NOT_CLEARED_BY_INVENTORY"})
    result = {"schemaVersion": 1, "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "scope": "Current public directory and declared vehicle runtime inputs; not a whole-drive rights audit",
              "vehicles": vehicles, "provenanceRecords": evidence, "publicFiles": files,
              "summary": {"publicFiles": len(files), "publicBytes": sum(f["bytes"] for f in files),
                          "over100MiB": sum(f["bytes"] > 100 * 1024**2 for f in files),
                          "vehicleDecisions": dict(collections.Counter(v["decision"] for v in vehicles)),
                          "provenanceRecords": len(evidence)},
              "publicReleaseAllowed": False,
              "reason": "File hashes prove identity, not authorship, license completeness or publication permission"}
    (OUT / "asset-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
