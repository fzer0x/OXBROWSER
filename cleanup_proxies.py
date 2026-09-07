import json
import os

proxy_file = '/home/fzer0x/Schreibtisch/SoxBot/storage/proxies.json'
with open(proxy_file, 'r') as f:
    proxies = json.load(f)

unique_proxies = {}
for p in proxies:
    key = f"{p.get('host')}:{p.get('port')}"
    # Prefer ones with latency > 0
    if key not in unique_proxies:
        unique_proxies[key] = p
    else:
        existing = unique_proxies[key]
        if existing.get('latency_ms', -1) < 0 and p.get('latency_ms', -1) > 0:
            unique_proxies[key] = p

with open(proxy_file, 'w') as f:
    json.dump(list(unique_proxies.values()), f, indent=4)
print(f"Cleaned up duplicates. {len(proxies)} -> {len(unique_proxies)}")
