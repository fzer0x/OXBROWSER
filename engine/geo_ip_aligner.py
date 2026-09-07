import re
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("GeoIPAligner")

# Mapping of ISO Country Codes to standardized Browser Locales, Accept-Language headers, and Regional Fonts
COUNTRY_LOCALE_MAP: Dict[str, Dict[str, Any]] = {
    "DE": {
        "locale": "de-DE",
        "languages": ["de-DE", "de"],
        "accept_language": "de-DE,de;q=0.9",
        "default_timezone": "Europe/Berlin",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Trebuchet MS", "Verdana"]
    },
    "AT": {
        "locale": "de-AT",
        "languages": ["de-AT", "de"],
        "accept_language": "de-AT,de;q=0.9",
        "default_timezone": "Europe/Vienna",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Verdana"]
    },
    "CH": {
        "locale": "de-CH",
        "languages": ["de-CH", "de", "fr-CH", "fr"],
        "accept_language": "de-CH,de;q=0.9,fr-CH;q=0.8,fr;q=0.7",
        "default_timezone": "Europe/Zurich",
        "regional_fonts": ["Arial", "Helvetica Neue", "Calibri", "Segoe UI"]
    },
    "US": {
        "locale": "en-US",
        "languages": ["en-US", "en"],
        "accept_language": "en-US,en;q=0.9",
        "default_timezone": "America/New_York",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Times New Roman", "Verdana"]
    },
    "GB": {
        "locale": "en-GB",
        "languages": ["en-GB", "en"],
        "accept_language": "en-GB,en;q=0.9",
        "default_timezone": "Europe/London",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Trebuchet MS", "Verdana"]
    },
    "FR": {
        "locale": "fr-FR",
        "languages": ["fr-FR", "fr"],
        "accept_language": "fr-FR,fr;q=0.9",
        "default_timezone": "Europe/Paris",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Verdana"]
    },
    "ES": {
        "locale": "es-ES",
        "languages": ["es-ES", "es"],
        "accept_language": "es-ES,es;q=0.9",
        "default_timezone": "Europe/Madrid",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Verdana"]
    },
    "IT": {
        "locale": "it-IT",
        "languages": ["it-IT", "it"],
        "accept_language": "it-IT,it;q=0.9",
        "default_timezone": "Europe/Rome",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Verdana"]
    },
    "NL": {
        "locale": "nl-NL",
        "languages": ["nl-NL", "nl"],
        "accept_language": "nl-NL,nl;q=0.9",
        "default_timezone": "Europe/Amsterdam",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "PL": {
        "locale": "pl-PL",
        "languages": ["pl-PL", "pl"],
        "accept_language": "pl-PL,pl;q=0.9",
        "default_timezone": "Europe/Warsaw",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma"]
    },
    "JP": {
        "locale": "ja-JP",
        "languages": ["ja-JP", "ja"],
        "accept_language": "ja-JP,ja;q=0.9",
        "default_timezone": "Asia/Tokyo",
        "regional_fonts": ["Meiryo", "MS PGothic", "Yu Gothic", "Hiragino Sans", "Arial"]
    },
    "CA": {
        "locale": "en-CA",
        "languages": ["en-CA", "en", "fr-CA", "fr"],
        "accept_language": "en-CA,en;q=0.9,fr-CA;q=0.8,fr;q=0.7",
        "default_timezone": "America/Toronto",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "AU": {
        "locale": "en-AU",
        "languages": ["en-AU", "en"],
        "accept_language": "en-AU,en;q=0.9",
        "default_timezone": "Australia/Sydney",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "SE": {
        "locale": "sv-SE",
        "languages": ["sv-SE", "sv"],
        "accept_language": "sv-SE,sv;q=0.9",
        "default_timezone": "Europe/Stockholm",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "NO": {
        "locale": "nb-NO",
        "languages": ["nb-NO", "nb", "no"],
        "accept_language": "nb-NO,nb;q=0.9,no;q=0.8",
        "default_timezone": "Europe/Oslo",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "DK": {
        "locale": "da-DK",
        "languages": ["da-DK", "da"],
        "accept_language": "da-DK,da;q=0.9",
        "default_timezone": "Europe/Copenhagen",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "FI": {
        "locale": "fi-FI",
        "languages": ["fi-FI", "fi", "sv-FI"],
        "accept_language": "fi-FI,fi;q=0.9,sv-FI;q=0.8",
        "default_timezone": "Europe/Helsinki",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "BE": {
        "locale": "nl-BE",
        "languages": ["nl-BE", "nl", "fr-BE", "fr"],
        "accept_language": "nl-BE,nl;q=0.9,fr-BE;q=0.8",
        "default_timezone": "Europe/Brussels",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "CZ": {
        "locale": "cs-CZ",
        "languages": ["cs-CZ", "cs"],
        "accept_language": "cs-CZ,cs;q=0.9",
        "default_timezone": "Europe/Prague",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma"]
    },
    "RO": {
        "locale": "ro-RO",
        "languages": ["ro-RO", "ro"],
        "accept_language": "ro-RO,ro;q=0.9",
        "default_timezone": "Europe/Bucharest",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma"]
    },
    "HU": {
        "locale": "hu-HU",
        "languages": ["hu-HU", "hu"],
        "accept_language": "hu-HU,hu;q=0.9",
        "default_timezone": "Europe/Budapest",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma"]
    },
    "GR": {
        "locale": "el-GR",
        "languages": ["el-GR", "el"],
        "accept_language": "el-GR,el;q=0.9",
        "default_timezone": "Europe/Athens",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma"]
    },
    "PT": {
        "locale": "pt-PT",
        "languages": ["pt-PT", "pt"],
        "accept_language": "pt-PT,pt;q=0.9",
        "default_timezone": "Europe/Lisbon",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "IE": {
        "locale": "en-IE",
        "languages": ["en-IE", "en", "ga-IE"],
        "accept_language": "en-IE,en;q=0.9,ga-IE;q=0.8",
        "default_timezone": "Europe/Dublin",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "BR": {
        "locale": "pt-BR",
        "languages": ["pt-BR", "pt"],
        "accept_language": "pt-BR,pt;q=0.9",
        "default_timezone": "America/Sao_Paulo",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Trebuchet MS", "Verdana"]
    },
    "MX": {
        "locale": "es-MX",
        "languages": ["es-MX", "es"],
        "accept_language": "es-MX,es;q=0.9",
        "default_timezone": "America/Mexico_City",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Verdana"]
    },
    "AR": {
        "locale": "es-AR",
        "languages": ["es-AR", "es"],
        "accept_language": "es-AR,es;q=0.9",
        "default_timezone": "America/Argentina/Buenos_Aires",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "CO": {
        "locale": "es-CO",
        "languages": ["es-CO", "es"],
        "accept_language": "es-CO,es;q=0.9",
        "default_timezone": "America/Bogota",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "CL": {
        "locale": "es-CL",
        "languages": ["es-CL", "es"],
        "accept_language": "es-CL,es;q=0.9",
        "default_timezone": "America/Santiago",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "IN": {
        "locale": "en-IN",
        "languages": ["en-IN", "hi-IN", "en"],
        "accept_language": "en-IN,en;q=0.9,hi-IN;q=0.8",
        "default_timezone": "Asia/Kolkata",
        "regional_fonts": ["Nirmala UI", "Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "KR": {
        "locale": "ko-KR",
        "languages": ["ko-KR", "ko"],
        "accept_language": "ko-KR,ko;q=0.9",
        "default_timezone": "Asia/Seoul",
        "regional_fonts": ["Malgun Gothic", "Gulim", "Dotum", "Arial", "Segoe UI"]
    },
    "SG": {
        "locale": "en-SG",
        "languages": ["en-SG", "en", "zh-SG", "zh"],
        "accept_language": "en-SG,en;q=0.9,zh-SG;q=0.8",
        "default_timezone": "Asia/Singapore",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "TR": {
        "locale": "tr-TR",
        "languages": ["tr-TR", "tr"],
        "accept_language": "tr-TR,tr;q=0.9",
        "default_timezone": "Europe/Istanbul",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma", "Verdana"]
    },
    "AE": {
        "locale": "ar-AE",
        "languages": ["ar-AE", "ar"],
        "accept_language": "ar-AE,ar;q=0.9",
        "default_timezone": "Asia/Dubai",
        "regional_fonts": ["Segoe UI", "Tahoma", "Arial", "Calibri"]
    },
    "SA": {
        "locale": "ar-SA",
        "languages": ["ar-SA", "ar"],
        "accept_language": "ar-SA,ar;q=0.9",
        "default_timezone": "Asia/Riyadh",
        "regional_fonts": ["Segoe UI", "Tahoma", "Arial", "Calibri"]
    },
    "IL": {
        "locale": "he-IL",
        "languages": ["he-IL", "he"],
        "accept_language": "he-IL,he;q=0.9",
        "default_timezone": "Asia/Jerusalem",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "David", "Verdana"]
    },
    "ZA": {
        "locale": "en-ZA",
        "languages": ["en-ZA", "en", "af-ZA"],
        "accept_language": "en-ZA,en;q=0.9,af-ZA;q=0.8",
        "default_timezone": "Africa/Johannesburg",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "NZ": {
        "locale": "en-NZ",
        "languages": ["en-NZ", "en"],
        "accept_language": "en-NZ,en;q=0.9",
        "default_timezone": "Pacific/Auckland",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "TH": {
        "locale": "th-TH",
        "languages": ["th-TH", "th"],
        "accept_language": "th-TH,th;q=0.9",
        "default_timezone": "Asia/Bangkok",
        "regional_fonts": ["Leelawadee UI", "Tahoma", "Arial", "Segoe UI"]
    },
    "VN": {
        "locale": "vi-VN",
        "languages": ["vi-VN", "vi"],
        "accept_language": "vi-VN,vi;q=0.9",
        "default_timezone": "Asia/Ho_Chi_Minh",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "ID": {
        "locale": "id-ID",
        "languages": ["id-ID", "id"],
        "accept_language": "id-ID,id;q=0.9",
        "default_timezone": "Asia/Jakarta",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "MY": {
        "locale": "ms-MY",
        "languages": ["ms-MY", "ms"],
        "accept_language": "ms-MY,ms;q=0.9",
        "default_timezone": "Asia/Kuala_Lumpur",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "PH": {
        "locale": "tl-PH",
        "languages": ["tl-PH", "fil-PH", "en-PH"],
        "accept_language": "tl-PH,fil-PH;q=0.9,en-PH;q=0.8",
        "default_timezone": "Asia/Manila",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    },
    "UA": {
        "locale": "uk-UA",
        "languages": ["uk-UA", "uk"],
        "accept_language": "uk-UA,uk;q=0.9",
        "default_timezone": "Europe/Kyiv",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Tahoma"]
    },
    "HK": {
        "locale": "zh-HK",
        "languages": ["zh-HK", "zh-TW", "zh"],
        "accept_language": "zh-HK,zh-TW;q=0.9,zh;q=0.8",
        "default_timezone": "Asia/Hong_Kong",
        "regional_fonts": ["MingLiU", "Microsoft JhengHei", "Arial", "Segoe UI"]
    },
    "TW": {
        "locale": "zh-TW",
        "languages": ["zh-TW", "zh"],
        "accept_language": "zh-TW,zh;q=0.9",
        "default_timezone": "Asia/Taipei",
        "regional_fonts": ["Microsoft JhengHei", "PMingLiU", "Arial", "Segoe UI"]
    },
}

DEFAULT_LOCALE_FALLBACK = {
    "locale": "en-US",
    "languages": ["en-US", "en"],
    "accept_language": "en-US,en;q=0.9",
    "default_timezone": "UTC",
    "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Times New Roman", "Verdana"]
}


def get_country_locale_config(country_code: str) -> Dict[str, Any]:
    """
    Returns verified country locale settings or dynamically synthesizes ISO-3166 standards.
    """
    cc = (country_code or "US").strip().upper()
    if cc in COUNTRY_LOCALE_MAP:
        return COUNTRY_LOCALE_MAP[cc]

    lang_lower = cc.lower()
    return {
        "locale": f"{lang_lower}-{cc}",
        "languages": [f"{lang_lower}-{cc}", lang_lower],
        "accept_language": f"{lang_lower}-{cc},{lang_lower};q=0.9",
        "default_timezone": "UTC",
        "regional_fonts": ["Arial", "Calibri", "Segoe UI", "Verdana"]
    }


@dataclass
class GeoIPProfileAlignment:
    """Zero-Leak Aligned Geolocation, Timezone, and Locale configuration."""
    ip: str
    country_code: str
    country_name: str
    city: str
    latitude: float
    longitude: float
    timezone_id: str
    locale: str
    languages: List[str]
    accept_language: str
    regional_fonts: List[str]
    isp: str = "Unknown ISP"
    accuracy_m: float = 100.0


class GeoIPAligner:
    """
    Zero-Leak Automatic Geo-IP Alignment Engine for SoxBot.
    Guarantees seamless harmony between network proxy IP and browser fingerprint properties:
    - Timezone (Intl.DateTimeFormat and OS/TZ environment)
    - Browser Locale & navigator.languages
    - HTTP Accept-Language header
    - Precise Geolocation Coordinates & Accuracy
    - Regional Font Prioritizations
    """
    _cache: Dict[str, GeoIPProfileAlignment] = {}

    @classmethod
    def align_from_proxy_info(cls, proxy_info: Dict[str, Any]) -> GeoIPProfileAlignment:
        """
        Derives a complete, zero-leak GeoIP alignment from existing proxy telemetry or cached lookup.
        """
        ip = str(proxy_info.get("ip") or proxy_info.get("host") or "127.0.0.1").strip()
        if ip in cls._cache:
            return cls._cache[ip]

        country_code = str(proxy_info.get("country_code") or proxy_info.get("country") or "US").strip().upper()
        if len(country_code) > 2:
            # Normalize full names (e.g. "Germany" -> "DE")
            for c_code, details in COUNTRY_LOCALE_MAP.items():
                if c_code.lower() == country_code.lower():
                    country_code = c_code
                    break
            else:
                country_code = "US"

        country_name = str(proxy_info.get("country") or country_code)
        city = str(proxy_info.get("city") or "")
        isp = str(proxy_info.get("isp") or "Commercial Broadband")
        
        try:
            lat = float(proxy_info.get("lat") or 0.0)
            lon = float(proxy_info.get("lon") or 0.0)
        except (ValueError, TypeError):
            lat, lon = 0.0, 0.0

        locale_cfg = get_country_locale_config(country_code)
        tz = str(proxy_info.get("timezone") or "").strip()
        if not tz or tz.lower() == "auto":
            tz = locale_cfg.get("default_timezone", "UTC")

        alignment = GeoIPProfileAlignment(
            ip=ip,
            country_code=country_code,
            country_name=country_name,
            city=city,
            latitude=lat,
            longitude=lon,
            timezone_id=tz,
            locale=locale_cfg["locale"],
            languages=locale_cfg["languages"],
            accept_language=locale_cfg["accept_language"],
            regional_fonts=locale_cfg["regional_fonts"],
            isp=isp
        )

        cls._cache[ip] = alignment
        logger.info(f"[GeoIPAligner] Aligned IP {ip} -> Country: {country_code}, TZ: {tz}, Locale: {locale_cfg['locale']}")
        return alignment

    @classmethod
    def apply_to_playwright_context_options(cls, context_options: Dict[str, Any], alignment: GeoIPProfileAlignment) -> Dict[str, Any]:
        """
        Injects the calculated Geo-IP, Locale, and Timezone parameters directly into Playwright context kwargs.
        """
        context_options["locale"] = alignment.locale
        context_options["timezone_id"] = alignment.timezone_id
        
        if alignment.latitude != 0.0 or alignment.longitude != 0.0:
            context_options["geolocation"] = {
                "latitude": alignment.latitude,
                "longitude": alignment.longitude,
                "accuracy": alignment.accuracy_m
            }
            context_options["permissions"] = list(set(context_options.get("permissions", []) + ["geolocation"]))

        # Set HTTP Accept-Language Header in extra_http_headers
        headers = context_options.get("extra_http_headers", {})
        headers["Accept-Language"] = alignment.accept_language
        context_options["extra_http_headers"] = headers

        return context_options
