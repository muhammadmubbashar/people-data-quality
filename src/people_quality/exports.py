"""Memory-only exports of the demo's synthetic records for Excel practice."""

import csv
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile


def workbook_inputs(snapshots, context, view):
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for source, rows in snapshots.items():
            text = io.StringIO(newline="")
            writer = csv.DictWriter(text, fieldnames=list(rows[0]))
            writer.writeheader()
            for record in rows:
                safe = {
                    key: "'" + value
                    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value
                    for key, value in record.items()
                }
                writer.writerow(safe)
            archive.writestr(f"{source}.csv", text.getvalue())
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "synthetic_only": True,
                    "view": view,
                    "capture_kind": context["capture_kind"],
                    "source_dates": context["source_dates"],
                    "policy": context["policy"],
                },
                indent=2,
            ),
        )
        archive.writestr(
            "START_HERE.txt",
            "Fictional practice data, not a Workday export. "
            "Import IDs as text. Preserve originals. "
            "Check duplicates and source dates before lookups. Compare cost centres and summarise "
            "exceptions. Editing these CSV files does not update the application or any HR system. "
            "Potential spreadsheet formula strings are prefixed with a quote for export safety.",
        )
    return output.getvalue()
