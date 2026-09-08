import sys, os
sys.path.insert(0, os.getcwd())

from backend.app import workspace as ws

root = os.getcwd()
print("=== CONNECT LOCAL ===")
conn = ws.connect_workspace("local", path=root)
print(conn)

print("\n=== METADATA ===")
meta = ws.get_repo_metadata(conn["root"])
print("branch:", meta["branch"])
print("total_commits:", meta["total_commits"])
print("file_count:", meta["file_count"], "code:", meta["code_file_count"])
print("languages:", meta["languages"])
print("manifests:", meta["manifests"])
print("recent commits (first 3):")
for c in meta["recent_commits"][:3]:
    print("  ", c["hash"], c["author"], c["date"], c["message"][:50])

print("\n=== DEPENDENCY RISKS ===")
dep = ws.scan_dependency_risks(root)
for f in dep:
    print(f"  [{f['severity']}] {f['title']} @ {f['file']}")

print("\n=== GIT RISKS ===")
gr = ws.scan_recent_risk(root)
for f in gr:
    print(f"  [{f['severity']}] {f['title']}")

print("\n=== FULL ANALYSIS ===")
full = ws.analyze_workspace(root)
print("summary:", full["summary"][:200])
print("total findings:", len(full["findings"]))
