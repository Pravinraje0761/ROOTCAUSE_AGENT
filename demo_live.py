import httpx, time

base = "http://127.0.0.1:8000"

def green(t):
    return t

print("====================================================")
print("  RootCause AI - Live Autonomous Investigation Demo")
print("====================================================")

# 1. Inject a controlled fault into the simulator (preprocessing mismatch)
print("\n[1] Injecting fault: Preprocessing Mismatch (Scenario #104)")
r = httpx.post(f"{base}/simulator/inject?fault_type=preprocessing_mismatch")
print(f"    -> {r.json()}")

# Health check
r = httpx.get(f"{base}/health")
print(f"[1b] Health: {r.json()}")

# 2. Trigger the investigation
print("\n[2] Triggering investigation...")
payload = {
    "incident_id": "DEMO-104",
    "incident_type": "ML Performance Degradation",
    "severity": "HIGH",
    "symptoms": {"accuracy": 0.713, "latency": 0.18, "error_rate": 0.178}
}
r2 = httpx.post(f"{base}/api/investigate", json=payload)
print(f"    -> {r2.json()}")

# 3. Stream progress
print("\n[3] Agent investigation in progress (WebSocket-style polling)...")
prev_logs = 0
approved = False
final_state = None
for i in range(60):
    time.sleep(1.5)
    r3 = httpx.get(f"{base}/api/incidents/DEMO-104")
    if r3.status_code != 200:
        continue
    state = r3.json()
    logs = state.get("logs", [])
    status = state.get("investigation_status")

    # Print new log lines
    for log in logs[prev_logs:]:
        print(f"    AGENT> {log}")
    prev_logs = len(logs)

    if status == "AWAITING_APPROVAL" and not approved:
        print("\n[4] Operator approval required for production patch.")
        print("    Authorizing hotfix...")
        ra = httpx.post(f"{base}/api/incidents/DEMO-104/approve")
        print(f"    -> {ra.json()}")
        approved = True

    if status in ("RESOLVED", "FAILED"):
        final_state = state
        break

# 4. Final report
print("\n\n====================================================")
print("                 FINAL INVESTIGATION REPORT")
print("====================================================")
if final_state:
    print(f"Status:         {final_state.get('investigation_status')}")
    print(f"Root Cause:     {final_state.get('confirmed_root_cause')}")
    print(f"Confidence:     {final_state.get('confidence', 0)*100:.1f}%")
    print(f"Risk Level:     {final_state.get('risk_level')}")
    fr = final_state.get("final_report") or {}
    if fr:
        print(f"Description:    {fr.get('root_cause_description')}")
        print(f"Fix:            {fr.get('fix_description')}")
        print(f"Experiments:    {fr.get('experiments_run')}")
        print(f"Falsified:      {fr.get('hypotheses_falsified')}")
        print(f"Confidence:     {fr.get('confidence', 0)*100:.1f}%")
else:
    print("Investigation did not complete within demo window.")
