import httpx
r = httpx.get("http://127.0.0.1:8000/health")
print("Health:", r.json())

# Now trigger an investigation
import json
payload = {
    "incident_id": "DEMO-001",
    "incident_type": "ML Performance Degradation",
    "severity": "HIGH",
    "symptoms": {"accuracy": 0.713, "latency": 0.18, "error_rate": 0.178}
}
r2 = httpx.post("http://127.0.0.1:8000/api/investigate", json=payload)
print("Investigate:", r2.json())

# Poll for status until resolved
import time
for i in range(30):
    time.sleep(2)
    r3 = httpx.get("http://127.0.0.1:8000/api/incidents/DEMO-001")
    if r3.status_code == 200:
        state = r3.json()
        status = state.get("investigation_status", "UNKNOWN")
        logs = state.get("logs", [])
        print(f"\n--- Poll #{i+1} | Status: {status} ---")
        if logs:
            print(f"  Latest log: {logs[-1]}")
        if status in ("RESOLVED", "FAILED", "AWAITING_APPROVAL"):
            print("\n=== FINAL STATE ===")
            print(f"  Root Cause: {state.get('confirmed_root_cause')}")
            print(f"  Confidence: {state.get('confidence', 0)*100:.1f}%")
            print(f"  Risk Level: {state.get('risk_level')}")
            if state.get("final_report"):
                fr = state["final_report"]
                print(f"  Description: {fr.get('root_cause_description')}")
                print(f"  Fix: {fr.get('fix_description')}")
                print(f"  Experiments Run: {fr.get('experiments_run')}")
                print(f"  Hypotheses Falsified: {fr.get('hypotheses_falsified')}")
            print(f"\n  Full log ({len(logs)} entries):")
            for log in logs:
                print(f"    {log}")
            break
    else:
        print(f"  Poll #{i+1}: Incident not yet available ({r3.status_code})")
