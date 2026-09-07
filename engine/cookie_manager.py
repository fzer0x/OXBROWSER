import json
import os
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger("CookieManager")

class CookieManager:
    """Manages import and export of JSON / Netscape cookies for browser profiles."""

    @staticmethod
    def parse_netscape_cookies(content: str) -> List[Dict]:
        """Parses Netscape HTTP Cookie File format into JSON cookie list."""
        cookies = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain = parts[0]
                include_subdomains = parts[1].upper() == "TRUE"
                path = parts[2]
                secure = parts[3].upper() == "TRUE"
                expiry = int(parts[4]) if parts[4].isdigit() else None
                name = parts[5]
                value = parts[6]

                cookie: Dict[str, Any] = {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path,
                    "secure": secure,
                    "httpOnly": False
                }
                if expiry:
                    cookie["expiry"] = expiry
                cookies.append(cookie)
        return cookies

    @classmethod
    def parse_cookie_text(cls, content: str) -> List[Dict]:
        content = content.strip()
        if not content:
            return []
        if content.startswith("[") or content.startswith("{"):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
            except Exception:
                pass
        return cls.parse_netscape_cookies(content)

    @classmethod
    def import_cookies_from_file(cls, file_path: str) -> List[Dict]:
        if not os.path.exists(file_path):
            return []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()

        return cls.parse_cookie_text(content)

    @classmethod
    def extract_cookies_from_user_data(cls, user_data_dir: str) -> List[Dict[str, Any]]:
        """Extracts live session & persistent cookies directly from browser SQLite databases in user_data_dir."""
        import sqlite3, glob, shutil, tempfile
        if not os.path.exists(user_data_dir):
            return []

        extracted_cookies: List[Dict[str, Any]] = []

        # 1. Firefox / Camoufox (cookies.sqlite)
        sqlite_files = glob.glob(os.path.join(user_data_dir, "**", "cookies.sqlite"), recursive=True)
        for sf in sqlite_files:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
                tmp_db = tf.name
            try:
                shutil.copy2(sf, tmp_db)
                conn = sqlite3.connect(tmp_db)
                c = conn.cursor()
                c.execute("SELECT host, name, value, path, expiry, isSecure, isHttpOnly FROM moz_cookies")
                rows = c.fetchall()
                for r in rows:
                    domain, name, value, path, expiry, is_sec, is_http = r
                    exp_val = int(expiry / 1000) if expiry and expiry > 1000000000000 else expiry
                    extracted_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path or "/",
                        "secure": bool(is_sec),
                        "httpOnly": bool(is_http),
                        "expiry": exp_val
                    })
                conn.close()
            except Exception:
                pass
            finally:
                if os.path.exists(tmp_db):
                    try:
                        os.remove(tmp_db)
                    except Exception:
                        pass

        # 2. Chromium (Cookies)
        chrome_files = glob.glob(os.path.join(user_data_dir, "**", "Cookies"), recursive=True)
        for cf in chrome_files:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
                tmp_db = tf.name
            try:
                shutil.copy2(cf, tmp_db)
                conn = sqlite3.connect(tmp_db)
                c = conn.cursor()
                c.execute("SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly FROM cookies")
                rows = c.fetchall()
                for r in rows:
                    domain, name, value, path, expires_utc, is_sec, is_http = r
                    extracted_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path or "/",
                        "secure": bool(is_sec),
                        "httpOnly": bool(is_http),
                        "expiry": expires_utc
                    })
                conn.close()
            except Exception:
                pass
            finally:
                if os.path.exists(tmp_db):
                    try:
                        os.remove(tmp_db)
                    except Exception:
                        pass

        return extracted_cookies

    @classmethod
    def get_profile_cookies(cls, profile_path: str) -> List[Dict[str, Any]]:
        """Loads and merges all cookies from cookies.json and live browser user_data SQLite databases."""
        cookie_json_path = os.path.join(profile_path, "cookies.json")
        json_cookies = cls.import_cookies_from_file(cookie_json_path) if os.path.exists(cookie_json_path) else []

        user_data_dir = os.path.join(profile_path, "user_data")
        sqlite_cookies = cls.extract_cookies_from_user_data(user_data_dir)

        cookie_map: Dict[str, Dict[str, Any]] = {}
        for c in json_cookies + sqlite_cookies:
            key = f"{c.get('domain', '')}:{c.get('name', '')}"
            if key and key != ":":
                cookie_map[key] = c

        merged = list(cookie_map.values())
        if merged and (not json_cookies or len(merged) > len(json_cookies)):
            cls.save_cookies_to_file(merged, cookie_json_path)

        return merged

    @classmethod
    def get_profile_storage_count(cls, profile_path: str) -> int:
        """Calculates total local storage and IndexedDB items stored in user_data directory."""
        user_data_dir = os.path.join(profile_path, "user_data")
        if not os.path.exists(user_data_dir):
            return 0
        
        count = 0
        import glob
        # 1. Firefox webappsstore.sqlite & storage/default
        webapps = glob.glob(os.path.join(user_data_dir, "**", "webappsstore.sqlite"), recursive=True)
        for wf in webapps:
            try:
                count += max(1, int(os.path.getsize(wf) / 1024))
            except Exception:
                pass
        
        # 2. Chromium Local Storage & IndexedDB folders
        storage_dirs = glob.glob(os.path.join(user_data_dir, "**", "Local Storage", "leveldb"), recursive=True)
        idb_dirs = glob.glob(os.path.join(user_data_dir, "**", "IndexedDB"), recursive=True)
        for sd in storage_dirs + idb_dirs:
            try:
                for _, _, files in os.walk(sd):
                    count += len(files)
            except Exception:
                pass
        return count

    @classmethod
    def get_profile_metrics(cls, profile_path: str) -> Dict[str, int]:
        """Returns unified dictionary with cookie count and storage items count."""
        cookies = cls.get_profile_cookies(profile_path)
        storage_items = cls.get_profile_storage_count(profile_path)
        return {
            "cookies": len(cookies),
            "storage_items": storage_items
        }

    @classmethod
    def sync_cookies_to_profile(cls, profile_path: str, cookies: List[Dict[str, Any]]) -> bool:
        """Saves cookies to cookies.json AND synchronizes pre-launch SQLite databases in user_data."""
        cookie_json_path = os.path.join(profile_path, "cookies.json")
        user_data_dir = os.path.join(profile_path, "user_data")
        os.makedirs(user_data_dir, exist_ok=True)
        
        # 1. Update/Write cookies.json
        if cookies:
            cls.save_cookies_to_file(cookies, cookie_json_path)
        else:
            if os.path.exists(cookie_json_path):
                try:
                    os.remove(cookie_json_path)
                except Exception:
                    pass
        
        # 2. Synchronize / Clean Firefox / Camoufox cookies.sqlite databases
        if os.path.exists(user_data_dir):
            import sqlite3, glob, time
            sqlite_files = glob.glob(os.path.join(user_data_dir, "**", "cookies.sqlite"), recursive=True)
            # If no cookies.sqlite exists yet in profile, initialize one at user_data_dir root for Firefox/Camoufox
            if not sqlite_files:
                sqlite_files = [os.path.join(user_data_dir, "cookies.sqlite")]

            for sf in sqlite_files:
                try:
                    conn = sqlite3.connect(sf, timeout=2.0)
                    c = conn.cursor()
                    # Ensure table exists even for fresh/unopened profiles
                    c.execute("""CREATE TABLE IF NOT EXISTS moz_cookies (
                        id INTEGER PRIMARY KEY,
                        originAttributes TEXT NOT NULL DEFAULT '',
                        name TEXT,
                        value TEXT,
                        host TEXT,
                        path TEXT,
                        expiry INTEGER,
                        lastAccessed INTEGER,
                        creationTime INTEGER,
                        isSecure INTEGER,
                        isHttpOnly INTEGER,
                        inBrowserElement INTEGER DEFAULT 0,
                        sameSite INTEGER DEFAULT 0,
                        schemeMap INTEGER DEFAULT 0,
                        isPartitionedAttributeSet INTEGER DEFAULT 0,
                        updateTime INTEGER,
                        CONSTRAINT moz_uniqueid UNIQUE (name, host, path, originAttributes)
                    )""")
                    c.execute("DELETE FROM moz_cookies")
                    if cookies:
                        c.execute("PRAGMA table_info(moz_cookies)")
                        col_info = set(r[1] for r in c.fetchall())
                        now_usec = int(time.time() * 1000000)
                        now_sec = int(time.time())
                        for item in cookies:
                            name = str(item.get("name", "")).strip()
                            val = str(item.get("value", ""))
                            domain = str(item.get("domain", "")).strip()
                            if not domain and "url" in item:
                                from urllib.parse import urlparse
                                domain = urlparse(str(item["url"])).hostname or ""
                            if not name or not domain:
                                continue
                            path = str(item.get("path", "/") or "/").strip()
                            is_sec = 1 if item.get("secure", False) else 0
                            is_http = 1 if item.get("httpOnly", False) else 0
                            expiry = item.get("expiry") or item.get("expires") or (now_sec + 31536000)
                            if isinstance(expiry, (int, float)) and expiry > 10000000000:
                                expiry = int(expiry / 1000)
                            else:
                                try:
                                    expiry = int(float(expiry))
                                except (ValueError, TypeError):
                                    expiry = now_sec + 31536000

                            ss = str(item.get("sameSite", "")).lower()
                            ss_int = 1 if "lax" in ss else (2 if "strict" in ss else 0)

                            col_values = {
                                "originAttributes": "",
                                "name": name,
                                "value": val,
                                "host": domain,
                                "path": path,
                                "expiry": expiry,
                                "lastAccessed": now_usec,
                                "creationTime": now_usec,
                                "isSecure": is_sec,
                                "isHttpOnly": is_http,
                                "inBrowserElement": 0,
                                "sameSite": ss_int,
                                "schemeMap": 0,
                                "isPartitionedAttributeSet": 0,
                                "updateTime": now_usec,
                            }
                            active_keys = [k for k in col_values if k in col_info]
                            placeholders = ["?"] * len(active_keys)
                            sql = f"INSERT OR REPLACE INTO moz_cookies ({', '.join(active_keys)}) VALUES ({', '.join(placeholders)})"
                            c.execute(sql, [col_values[k] for k in active_keys])
                    conn.commit()
                    try:
                        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
                    conn.close()
                except Exception as e_sql:
                    logger.debug(f"Pre-launch SQLite cookie sync note for {sf}: {e_sql}")

        return True

    @staticmethod
    def save_cookies_to_file(cookies: List[Dict], file_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving cookies to {file_path}: {e}")
            return False

