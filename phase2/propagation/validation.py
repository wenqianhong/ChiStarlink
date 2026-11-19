"""Check slant gas loss and the underlying line-by-line specific attenuation against external vectors."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from itur.models import itu676
from gas import gas_loss_db

WORKBOOK_HASH = "e2d8d864c80f59752318548cdd75d818792b44574da6e41dbdc5cb722aab7546"
CSV_HASH = "6a2d649339fedf59f24a96a06b08e1d20348833df0bdb4f4d07ad25b35b79fcd"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slant_vectors(csv_path):
    with csv_path.open(encoding="latin-1") as source:
        rows = csv.DictReader(source)
        next(rows)  # Units row. T is supplied as absolute kelvin and h in km.
        for index, row in enumerate(rows, start=3):
            value = gas_loss_db(float(row['f'])*1e9, float(row['el']), float(row['P']), float(row['T']),
                                float(row['rho']), float(row['V_t']), float(row['h']))
            yield {"row": index, "frequency_ghz": float(row["f"]), "quantity": "slant_dB",
                   "expected": float(row["A_gas"]), "calculated": value}


def specific_vectors(workbook):
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with ZipFile(workbook) as archive:
        sheets = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = next(s for s in sheets.iter(ns + "sheet") if s.get("name") == "P.676-13 SpAtt")
        sheet_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(s.get("Target") for s in relations if s.get("Id") == sheet_id)
        cells = {cell.get("r"): cell.findtext(ns + "v") for cell in
                 ElementTree.fromstring(archive.read("xl/" + target)).iter(ns + "c")}
    # The sheet's frequency sweep uses the labelled dry pressure, temperature and vapour density in E20:E23.
    pressure, temperature, humidity = [float(cells[cell]) for cell in ("E20", "E22", "E23")]
    for r in range(34, 384):
        f = float(cells[f"C{r}"])
        for col, name, func in (("D", "oxygen_dB_per_km", itu676.gamma0_exact),
                                ("E", "water_dB_per_km", itu676.gammaw_exact),
                                ("F", "total_dB_per_km", itu676.gamma_exact)):
            yield {"row": r, "frequency_ghz": f, "quantity": name,
                   "expected": float(cells[f"{col}{r}"]), "calculated": float(func(f, pressure, humidity, temperature).value)}


def check(vectors, tolerance, evidence_path):
    rows = list(vectors)
    for row in rows:
        row["absolute_error"] = abs(row["expected"] - row["calculated"])
        row["pass"] = row["absolute_error"] <= tolerance
    with evidence_path.open("w") as out:
        writer = csv.DictWriter(out, rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {"n_values": len(rows), "passed": sum(row["pass"] for row in rows),
            "max_absolute_error": max(row["absolute_error"] for row in rows), "absolute_tolerance": tolerance}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if digest(args.csv) != CSV_HASH or digest(args.xlsx) != WORKBOOK_HASH:
        raise ValueError("Validation source digest mismatch")
    args.output.mkdir(exist_ok=True, parents=True)
    slant = check(slant_vectors(args.csv), 1e-7, args.output / "slant.csv")
    specific = check(specific_vectors(args.xlsx), 1e-7, args.output / "specific.csv")
    summary = {"itur": "0.4.0", "implemented_recommendation": itu676.get_version(),
               "slant_p676_12_itu_v5_1_via_tagged_upstream": slant,
               "specific_p676_13_itu_v8_3_workbook": specific,
               "csv_sha256": CSV_HASH, "xlsx_sha256": WORKBOOK_HASH}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    raise SystemExit(int(slant["passed"] != slant["n_values"] or specific["passed"] != specific["n_values"]))
