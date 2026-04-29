"""Paralelni retranslate top 4 problemovych map s overwrite=True."""
import sys
import json
import time
import threading
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8100"
PROJECTS = [
    "lostvikings-m2-v3-final-fp-metric",
    "ngm-indus-valley-civilization-map-v6-final-fp-1",
    "aral-sea-map-test",
    "ngm-2605-barryarm-v8-final2-fp",
    "ngm-byzantine-empire-ad-717-map-cz2",
    "girlions-m1-final-fp-1",
    "ngm-okavango-expeditions-map-v8-final-metric",
]


def trigger_and_poll(pid, results):
    try:
        req = urllib.request.Request(
            f"{BASE}/api/projects/{pid}/translate",
            data=json.dumps({"overwrite": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        body = json.loads(resp.read().decode("utf-8"))
        total = body.get("total_elements", 0)
        print(f"[{pid:50s}] START — {total} elementu")
        last_batch = -1
        t0 = time.time()
        while True:
            time.sleep(3)
            r = urllib.request.urlopen(
                f"{BASE}/api/projects/{pid}/translate/progress", timeout=10
            )
            p = json.loads(r.read().decode("utf-8"))
            st = p.get("status")
            if st == "running":
                b = p.get("batch", 0)
                tb = p.get("total_batches", 0)
                if b != last_batch:
                    print(f"[{pid:50s}] batch {b}/{tb}")
                    last_batch = b
            elif st == "done":
                dt = time.time() - t0
                print(f"[{pid:50s}] DONE — {p.get('translated')} prelozeno za {dt:.0f}s")
                results[pid] = ("ok", p.get("translated"), dt)
                return
            elif st == "error":
                print(f"[{pid:50s}] ERROR: {p.get('error')}")
                results[pid] = ("err", p.get("error"), 0)
                return
            elif st == "idle":
                print(f"[{pid:50s}] idle")
                results[pid] = ("idle", None, 0)
                return
    except Exception as e:
        print(f"[{pid:50s}] EXCEPTION: {e}")
        results[pid] = ("exc", str(e), 0)


results = {}
threads = []
for pid in PROJECTS:
    t = threading.Thread(target=trigger_and_poll, args=(pid, results), daemon=True)
    t.start()
    threads.append(t)
    time.sleep(0.5)  # mírný odstup, aby progress polly nebyly úplně synchronní

for t in threads:
    t.join(timeout=300)

print("\n=== SUMARIZACE ===")
for pid in PROJECTS:
    res = results.get(pid, ("?", None, 0))
    print(f"  {pid:50s} {res}")
