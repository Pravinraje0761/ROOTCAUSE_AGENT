import httpx
r = httpx.get("http://127.0.0.1:8000/")
print("Root:", r.status_code, r.headers.get("content-type"), len(r.content), "bytes")
r2 = httpx.get("http://127.0.0.1:8000/api/incidents")
print("Incidents:", r2.status_code)
for inc in r2.json():
    print("  -", inc["incident_id"], "|", inc["incident_type"], "|", inc["status"])
