"""Bounded, same-host, read-only discovery of actual Workday audit fields."""

import json
import re
from urllib.parse import urlsplit

import requests

from people_quality.workday import ConnectionError


def read_json(tenant, token, session, path, params=None):
    origin = urlsplit(tenant.workers_url)
    if not path.startswith(("/api/", "/ccx/api/")) or ".." in path or "?" in path:
        raise ValueError("Only explicit Workday API paths are allowed")
    url = f"https://{origin.hostname}{path}"
    try:
        with session.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=(5, 30),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                return {"http_status": response.status_code}
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ConnectionError("Workday discovery response exceeds its size limit")
            return {"http_status": 200, "body": json.loads(data)}
    except requests.RequestException:
        raise ConnectionError("Workday field discovery request failed") from None
    except (ValueError, UnicodeError):
        raise ConnectionError("Workday field discovery did not return JSON") from None


def paged_metadata(tenant, token, session, path, maximum=4000):
    rows, seen = [], set()
    for offset in range(0, maximum, 100):
        result = read_json(tenant, token, session, path, {"limit": 100, "offset": offset})
        if result["http_status"] != 200:
            return result
        body = result["body"]
        page = body.get("data", [])
        fresh = [r for r in page if r.get("id") not in seen]
        rows.extend(fresh)
        seen.update(r.get("id") for r in fresh)
        if not fresh or len(rows) >= body.get("total", len(page)) or len(page) < 100:
            return {"http_status": 200, "body": {"total": len(rows), "data": rows}}
    return {"http_status": 200, "body": {"total": len(rows), "data": rows}, "bounded": True}


def discover(tenant, workers, token, session, metadata_cache=None):
    tenant_name = urlsplit(tenant.workers_url).path.rstrip("/").split("/")[-2]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", tenant_name):
        raise ValueError("Unsupported tenant name")
    records = []
    for worker in workers["data"][:5]:
        wid = worker["id"]
        if not re.fullmatch(r"[0-9a-f]{32}", wid):
            raise ValueError("Workday discovery requires a verified WID")
        paths = {
            "staffing": f"/api/staffing/v7/{tenant_name}/workers/{wid}",
            "service_dates": f"/api/staffing/v7/{tenant_name}/workers/{wid}/serviceDates",
            "organisations": f"/api/common/v1/{tenant_name}/workers/{wid}/organizations",
        }
        record = {"workday_id": wid, "sample_worker": worker.get("descriptor", "")}
        for name, path in paths.items():
            record[name] = read_json(
                tenant, token, session, path, {"limit": 100} if name != "staffing" else None
            )
        records.append(record)
    if metadata_cache:
        result = {"records": records, "sample_only": True}
        for key in ("wql_sources", "wql_source", "wql_fields"):
            result[key] = metadata_cache[key]
        sources = result["wql_sources"]
    else:
        sources = paged_metadata(
            tenant,
            token,
            session,
            f"/api/wql/v1/{tenant_name}/dataSources",
        )
        result = {"records": records, "wql_sources": sources, "sample_only": True}
    if sources["http_status"] != 200:
        return result
    source = next((r for r in sources["body"]["data"] if r.get("alias") == "allWorkers"), None)
    if not source:
        return result
    source_id = source["id"]
    if not re.fullmatch(r"[0-9a-f]{32}", source_id):
        raise ConnectionError("Unsupported Workday data-source ID")
    fields = result.get("wql_fields") or paged_metadata(
        tenant, token, session, f"/api/wql/v1/{tenant_name}/dataSources/{source_id}/fields"
    )
    result.update(wql_source=source, wql_fields=fields)
    if fields["http_status"] != 200:
        return result
    candidates = {
        "employee_id": ["employeeID"],
        "worker": ["worker"],
        "cost_centre": ["costCenter"],
        "cost_centre_id": ["costCenter_ID"],
        "fte": ["FTE"],
        "fte_percent": ["FTEPct"],
        "manager_id": ["managerID"],
        "manager": ["manager_EffectiveDated"],
        "hire_date": ["hireDate"],
        "active": ["active", "activeStatus"],
        "terminated": ["terminated"],
        "on_leave": ["onLeave"],
        "termination_date": ["terminationDate"],
        "worker_type": ["workerType"],
    }
    by_alias = {r.get("alias"): r for r in fields["body"]["data"]}
    selected = {}
    for name, aliases in candidates.items():
        match = next((a for a in aliases if a in by_alias), None)
        if match:
            selected[name] = by_alias[match]
    result["selected_fields"] = selected
    ids = [r.get("staffing", {}).get("body", {}).get("workerId", "") for r in records]
    if "employee_id" not in selected or any(not re.fullmatch(r"[A-Za-z0-9_-]+", v) for v in ids):
        return result
    aliases = [f["alias"] for f in selected.values()]
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", a) for a in aliases):
        raise ConnectionError("Unsupported WQL field alias")
    id_list = ", ".join("'" + v + "'" for v in ids)
    query = f"SELECT {', '.join(aliases)} FROM allWorkers WHERE employeeID IN ({id_list})"
    result["query"] = query
    result["wql_data"] = read_json(
        tenant, token, session, f"/api/wql/v1/{tenant_name}/data", {"query": query, "limit": 5}
    )
    managers = {}
    if result["wql_data"]["http_status"] == 200:
        for row in result["wql_data"]["body"].get("data", []):
            manager = row.get("manager_EffectiveDated") or {}
            wid = manager.get("id")
            if wid and wid not in managers:
                if not re.fullmatch(r"[0-9a-f]{32}", wid):
                    raise ConnectionError("Unsupported manager reference")
                managers[wid] = read_json(
                    tenant, token, session, f"/api/staffing/v7/{tenant_name}/workers/{wid}"
                )
    result["manager_references"] = managers
    return result
