import os
import json
import uuid
import time
from typing import List, Dict, Optional
import config

class ProxyManager:
    """Manages proxy pool storage, tagging, and bulk operations."""

    def __init__(self, storage_file: str = os.path.join(config.BASE_DIR, "storage", "proxies.json")):
        self.storage_file = storage_file
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        self.proxies: List[Dict] = self.load_proxies()

    def load_proxies(self) -> List[Dict]:
        if not os.path.exists(self.storage_file):
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading proxies: {e}")
            return []

    def save_proxies(self) -> bool:
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.proxies, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving proxies: {e}")
            return False

    def list_proxies(self, sort_speed: bool = True) -> List[Dict]:
        if sort_speed:
            def sort_key(p):
                lat = p.get("latency_ms", -1)
                status = str(p.get("status", ""))
                tags = p.get("tags", [])
                if "Google Proxy" in status or "Google Proxy" in tags:
                    return (-1, lat if (isinstance(lat, (int, float)) and lat > 0) else 999999.0)
                if "Active" in status or "✓" in status:
                    return (0, lat if (isinstance(lat, (int, float)) and lat > 0) else 999999.0)
                elif "Offline" in status or "" in status:
                    return (2, 999999.0)
                return (1, 999999.0)
            return sorted(self.proxies, key=sort_key)
        return self.proxies

    def add_proxy(self, proxy_data: Dict) -> Dict:
        if "id" not in proxy_data or not proxy_data["id"]:
            proxy_data["id"] = str(uuid.uuid4())
        
        proxy_data.setdefault("name", f"Proxy {proxy_data.get('host')}")
        proxy_data.setdefault("type", "http")
        proxy_data.setdefault("host", "")
        proxy_data.setdefault("port", 8080)
        proxy_data.setdefault("username", "")
        proxy_data.setdefault("password", "")
        proxy_data.setdefault("change_ip_url", "")
        proxy_data.setdefault("group", "Default")
        proxy_data.setdefault("tags", ["General"])
        proxy_data.setdefault("status", "Untested")
        proxy_data.setdefault("latency_ms", -1)
        proxy_data.setdefault("ip", "")
        proxy_data.setdefault("country", "")
        proxy_data.setdefault("city", "")
        proxy_data.setdefault("timezone", "")
        proxy_data.setdefault("created_at", time.time())

        self.proxies.append(proxy_data)
        self.save_proxies()
        return proxy_data

    def add_tag_to_proxy(self, proxy_id: str, tag: str) -> bool:
        for i, p in enumerate(self.proxies):
            if p.get("id") == proxy_id:
                tags = list(p.get("tags", []))
                if tag not in tags:
                    tags.append(tag)
                    self.proxies[i]["tags"] = tags
                    return self.save_proxies()
                return True
        return False

    def update_proxy(self, proxy_id: str, new_data: Dict) -> bool:
        for i, p in enumerate(self.proxies):
            if p.get("id") == proxy_id:
                self.proxies[i].update(new_data)
                return self.save_proxies()
        return False

    def delete_proxy(self, proxy_id: str) -> bool:
        self.proxies = [p for p in self.proxies if p.get("id") != proxy_id]
        return self.save_proxies()

    @staticmethod
    def parse_proxy_line(line: str) -> Optional[Dict]:
        """Parses common proxy formats: host:port, host:port:user:pass, user:pass@host:port, type://user:pass@host:port"""
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        p_type = "http"
        if "://" in line:
            parts = line.split("://", 1)
            p_type = parts[0].lower()
            line = parts[1]

        user, pwd, host, port = "", "", "", 8080

        if "@" in line:
            auth_part, host_part = line.split("@", 1)
            if ":" in auth_part:
                user, pwd = auth_part.split(":", 1)
            else:
                user = auth_part
            if ":" in host_part:
                host, port_str = host_part.split(":", 1)
                port = int(port_str) if port_str.isdigit() else 8080
            else:
                host = host_part
        else:
            tokens = line.split(":")
            if len(tokens) == 2:
                host = tokens[0]
                port = int(tokens[1]) if tokens[1].isdigit() else 8080
            elif len(tokens) == 4:
                host = tokens[0]
                port = int(tokens[1]) if tokens[1].isdigit() else 8080
                user = tokens[2]
                pwd = tokens[3]

        if not host:
            return None

        return {
            "id": str(uuid.uuid4()),
            "name": f"{host}:{port}",
            "type": p_type,
            "host": host,
            "port": port,
            "username": user,
            "password": pwd,
            "change_ip_url": "",
            "group": "Default",
            "tags": ["Imported"],
            "status": "Untested",
            "latency_ms": -1,
            "created_at": time.time()
        }

    def import_raw_proxies(self, content: str) -> int:
        count = 0
        for line in content.splitlines():
            parsed = self.parse_proxy_line(line)
            if parsed:
                self.add_proxy(parsed)
                count += 1
        return count
