import os
import sys
import re
import random
import string
import shutil
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger("CDPPatcher")


class ChromiumBinaryPatcher:
    """
    Automated Binary Hex-Patcher for Chromium, Undetected Chromedriver & Electron Binaries.
    Replaces anti-bot detection signatures directly in binary files:
    - 'cdc_adoQpoasnfa76pfcZLmcfl_Array' -> 'sox_random_hex_array'
    - 'cdc_adoQpoasnfa76pfcZLmcfl_Promise' -> 'sox_random_hex_promise'
    - 'cdc_adoQpoasnfa76pfcZLmcfl_Symbol' -> 'sox_random_hex_symbol'
    - '$cdc_asdjflasutopfhvcZLmcfl_' -> '$sox_random_prefix_str_'
    """

    # The canonical 26-char CDC key used by ChromeDriver
    CDC_REGEX = re.compile(rb"cdc_[a-zA-Z0-9]{22}_")
    CDC_EXACT = b"cdc_adoQpoasnfa76pfcZLmcfl_"

    @staticmethod
    def generate_replacement_cdc() -> bytes:
        """Generates a random 26-byte matching replacement sequence."""
        rand_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=22))
        return f"sox_{rand_chars}_".encode("ascii")

    @classmethod
    def patch_binary(cls, binary_path: str, backup: bool = True) -> Tuple[bool, int, str]:
        """
        Scans and patches binary executable in-place.
        Returns: (success: bool, replacement_count: int, message: str)
        """
        if not os.path.exists(binary_path):
            return False, 0, f"Binary not found: {binary_path}"

        if not os.access(binary_path, os.R_OK | os.W_OK):
            return False, 0, f"Permission denied for binary: {binary_path}"

        try:
            with open(binary_path, "rb") as f:
                content = bytearray(f.read())
        except Exception as e:
            return False, 0, f"Error reading binary: {e}"

        matches = list(cls.CDC_REGEX.finditer(content))
        if not matches:
            return True, 0, f"No CDC signatures found in '{os.path.basename(binary_path)}' (already clean/patched)."

        if backup:
            backup_path = f"{binary_path}.bak"
            if not os.path.exists(backup_path):
                try:
                    shutil.copy2(binary_path, backup_path)
                    logger.info(f"[CDPPatcher] Created backup binary at '{backup_path}'")
                except Exception as ex:
                    logger.warning(f"[CDPPatcher] Failed to create backup: {ex}")

        replacement_count = 0
        for match in matches:
            start, end = match.span()
            target_len = end - start
            rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=target_len - 4))
            replacement = f"sox_{rand_suffix}".encode("ascii")[:target_len]
            content[start:end] = replacement
            replacement_count += 1

        try:
            with open(binary_path, "wb") as f:
                f.write(content)
            logger.info(f"[CDPPatcher] Successfully patched {replacement_count} CDC signatures in '{binary_path}'")
            return True, replacement_count, f"Patched {replacement_count} anti-detect CDC signatures."
        except Exception as e:
            logger.error(f"[CDPPatcher] Failed to write patched binary: {e}")
            return False, replacement_count, f"Write error: {e}"

    @classmethod
    def scan_and_patch_workspace(cls, root_dir: str) -> List[Tuple[str, int]]:
        """Scans workspace for chrome/chromedriver executables (.exe or unix binary) and patches them."""
        results = []
        target_names = ["chromedriver", "chrome", "chromium", "chrome-headless-shell", "msedge"]
        is_win = sys.platform.startswith("win")
        for root, _, files in os.walk(root_dir):
            for file in files:
                file_lower = file.lower()
                if any(t in file_lower for t in target_names) and not file_lower.endswith(".bak"):
                    full_path = os.path.join(root, file)
                    is_candidate = os.path.isfile(full_path) and (
                        is_win or os.access(full_path, os.X_OK) or file_lower.endswith(".exe")
                    )
                    if is_candidate:
                        ok, count, _ = cls.patch_binary(full_path)
                        if ok and count > 0:
                            results.append((full_path, count))
        return results


class CDPRestrictionMitigator:
    """
    Generates high-stealth runtime script protections against CDP and WebDriver introspection.
    Eliminates Cloudflare Turnstile / DataDome / Kasada / Akamai detection vectors.
    """

    @staticmethod
    def generate_cdp_leak_protection_script() -> str:
        return """
        // ============================================================================
        // Senior CDP Runtime Leak & WebDriver Prototype Hardening
        // ============================================================================
        (function() {
            'use strict';

            const nativeToString = Function.prototype.toString;
            const patchedFns = new WeakSet();
            const fnNames = new WeakMap();

            function makeNative(fn, name) {
                if (typeof fn !== 'function') return fn;
                patchedFns.add(fn);
                if (name) {
                    fnNames.set(fn, name);
                    try {
                        Object.defineProperty(fn, 'name', { value: name, configurable: true });
                    } catch(e) {}
                }
                return fn;
            }

            // 1. Bulletproof Function.prototype.toString
            Function.prototype.toString = new Proxy(nativeToString, {
                apply: function(target, thisArg, argArray) {
                    if (patchedFns.has(thisArg)) {
                        const name = fnNames.get(thisArg) || thisArg.name || '';
                        return `function ${name}() { [native code] }`;
                    }
                    return Reflect.apply(target, thisArg, argArray);
                }
            });
            patchedFns.add(Function.prototype.toString);
            fnNames.set(Function.prototype.toString, 'toString');

            // 2. Remove all Automation and Driver Globals
            const automationGlobals = [
                'cdc_adoQpoasnfa76pfcZLmcfl_Array',
                'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
                'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
                '__webdriver_evaluate',
                '__selenium_evaluate',
                '__webdriver_script_function',
                '__webdriver_script_func',
                '__webdriver_script_fn',
                '__fxdriver_evaluate',
                '__fxdriver_unwrapped',
                '__driver_evaluate',
                '__webdriver_unwrapped',
                '__selenium_unwrapped',
                '__fxdriver_unwrap',
                '__nightmare',
                '__phantomas',
                'callPhantom',
                '_phantom',
                'phantom',
                'domAutomation',
                'domAutomationController'
            ];

            for (const g of automationGlobals) {
                try {
                    delete window[g];
                    delete document[g];
                } catch(e) {}
            }

            // 3. Strip navigator.webdriver with correct prototype descriptor
            try {
                const navProto = Object.getPrototypeOf(navigator);
                if (navProto && 'webdriver' in navProto) {
                    delete navProto.webdriver;
                }
                if ('webdriver' in navigator) {
                    delete navigator.webdriver;
                }
                Object.defineProperty(navigator, 'webdriver', {
                    get: makeNative(() => undefined, 'get webdriver'),
                    set: makeNative(() => {}, 'set webdriver'),
                    enumerable: false,
                    configurable: true
                });
            } catch(e) {}

            // 4. Trap CDP Runtime.enable Inspections
            try {
                const origError = window.Error;
                window.Error = makeNative(function Error(...args) {
                    const err = new origError(...args);
                    if (err.stack) {
                        err.stack = err.stack
                            .replace(/at Object\\.evaluate \\(eval at <anonymous>.*\\)/g, '')
                            .replace(/at <anonymous>:\\d+:\\d+/g, '')
                            .replace(/at (cdc_|__webdriver|__playwright|__puppeteer).*\\n/g, '');
                    }
                    return err;
                }, 'Error');
                window.Error.prototype = origError.prototype;
            } catch(e) {}

        })();
        """
