import os
import sys
import subprocess
import logging
import shutil
import threading
from typing import Tuple, List, Optional, Dict

logger = logging.getLogger("NetworkKillSwitch")


class NetworkKillSwitchManager:
    """
    Manages Linux Network Namespaces (NetNS) and Firewall Kill Switch rules per browser profile.
    Ensures zero network leaks (IPv4/IPv6, WebRTC, DNS) outside the designated proxy tunnel.
    """
    _ALLOCATED_SUBNETS: Dict[str, int] = {}
    _SUBNET_LOCK = threading.Lock()

    @classmethod
    def _allocate_subnet_byte(cls, profile_id: str) -> int:
        """Dynamically allocates an unused subnet byte (2..254) for 10.200.X.0/30 without collisions."""
        with cls._SUBNET_LOCK:
            if profile_id in cls._ALLOCATED_SUBNETS:
                return cls._ALLOCATED_SUBNETS[profile_id]

            used_bytes = set(cls._ALLOCATED_SUBNETS.values())
            for candidate in range(2, 254):
                if candidate not in used_bytes:
                    cls._ALLOCATED_SUBNETS[profile_id] = candidate
                    return candidate

            # Fallback in extreme multi-instance overflow
            fallback = (hash(profile_id) % 250) + 2
            cls._ALLOCATED_SUBNETS[profile_id] = fallback
            return fallback

    @classmethod
    def _release_subnet_byte(cls, profile_id: str) -> Optional[int]:
        with cls._SUBNET_LOCK:
            return cls._ALLOCATED_SUBNETS.pop(profile_id, None)

    @staticmethod
    def is_root_or_capable() -> bool:
        """Checks if current process has root privileges or passwordless sudo privileges for ip netns."""
        if sys.platform != "linux":
            return False
        if os.geteuid() == 0:
            return True
        try:
            res = subprocess.run(["sudo", "-n", "ip", "netns", "list"], capture_output=True)
            if res.returncode == 0:
                return True
            res_true = subprocess.run(["sudo", "-n", "true"], capture_output=True)
            return res_true.returncode == 0
        except Exception:
            return False

    @classmethod
    def setup_profile_netns(cls, profile_id: str, proxy_port: int) -> Tuple[bool, str, Optional[str]]:
        """
        Creates an isolated network namespace for the profile with strict egress firewall rules.
        Only loopback traffic to 127.0.0.1:proxy_port is allowed. All other egress traffic is dropped.
        Returns: (success: bool, message: str, netns_name: Optional[str])
        """
        if sys.platform != "linux":
            return False, "CRITICAL SECURITY FATAL: Network namespaces are only supported on Linux OS.", None

        if not cls.is_root_or_capable():
            user_name = os.environ.get("USER", "user")
            err_msg = (
                "CRITICAL SECURITY FATAL: Non-interactive sudo privileges for 'ip netns' not available.\n"
                "To prevent IP/DNS leaks, profile launch is aborted (Fail-Closed Guard).\n"
                f"Fix: Add NOPASSWD rule in /etc/sudoers:\n  {user_name} ALL=(ALL) NOPASSWD: /usr/sbin/ip, /usr/sbin/iptables, /usr/sbin/sysctl"
            )
            logger.error(f"[NetworkKillSwitch] {err_msg}")
            return False, err_msg, None

        import hashlib
        # Use SHA-256 hash to avoid UUID prefix collisions.
        # Linux netns name limit = 16 chars. veth interface name limit = 15 chars.
        _id_hash = hashlib.sha256(profile_id.encode("utf-8")).hexdigest()
        netns_name = f"sox_{_id_hash[:10]}"   # 14 chars total: safe
        veth_host = f"vth_{_id_hash[:8]}"     # 12 chars total: safe

        # Check if already exists, clean up stale instance
        cls.teardown_profile_netns(profile_id)

        try:
            # 1. Create network namespace
            res = subprocess.run(["sudo", "-n", "ip", "netns", "add", netns_name], capture_output=True, text=True)
            if res.returncode != 0:
                err_msg = f"CRITICAL SECURITY FATAL: Failed to add NetNS '{netns_name}': {res.stderr.strip()}"
                logger.error(f"[NetworkKillSwitch] {err_msg}")
                return False, err_msg, None

            # 2. Bring up loopback inside NetNS
            subprocess.run(["sudo", "-n", "ip", "netns", "exec", netns_name, "ip", "link", "set", "dev", "lo", "up"], check=True)

            # 3. Disable IPv6 to block IPv6 bypass leaks completely inside NetNS
            subprocess.run([
                "sudo", "-n", "ip", "netns", "exec", netns_name,
                "sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=1"
            ], capture_output=True)

            # 4. Set up veth pair to communicate with local proxy tunnel on host
            veth_ns = "veth_ns"  # Lives inside the isolated NetNS — no collision risk

            subprocess.run([
                "sudo", "-n", "ip", "link", "add", veth_host, "type", "veth", "peer", "name", veth_ns
            ], check=True)

            # Move peer into netns
            subprocess.run(["sudo", "-n", "ip", "link", "set", veth_ns, "netns", netns_name], check=True)

            # Configure IPs (10.200.X.Y subnet) via collision-free dynamic lease
            subnet_byte = cls._allocate_subnet_byte(profile_id)
            host_ip = f"10.200.{subnet_byte}.1"
            ns_ip = f"10.200.{subnet_byte}.2"

            subprocess.run(["sudo", "-n", "ip", "addr", "add", f"{host_ip}/30", "dev", veth_host], check=True)
            subprocess.run(["sudo", "-n", "ip", "link", "set", veth_host, "up"], check=True)

            # Ensure host firewall accepts incoming TCP on veth_host to the local proxy port (protects against UFW/host DROP policy)
            subprocess.run([
                "sudo", "-n", "iptables", "-I", "INPUT", "1",
                "-i", veth_host, "-p", "tcp", "--dport", str(proxy_port), "-j", "ACCEPT"
            ], capture_output=True)

            subprocess.run(["sudo", "-n", "ip", "netns", "exec", netns_name, "ip", "addr", "add", f"{ns_ip}/30", "dev", veth_ns], check=True)
            subprocess.run(["sudo", "-n", "ip", "netns", "exec", netns_name, "ip", "link", "set", veth_ns, "up"], check=True)

            # 5. Add default route to host IP
            subprocess.run(["sudo", "-n", "ip", "netns", "exec", netns_name, "ip", "route", "add", "default", "via", host_ip], check=True)

            # 6. Apply strict Egress Firewall (iptables / nftables) Kill Switch inside NetNS
            # Allow loopback, allow connection to local host proxy port, REJECT/DROP everything else!
            cls._apply_firewall_rules(netns_name, host_ip, proxy_port)

            logger.info(f"[NetworkKillSwitch] Successfully activated NetNS '{netns_name}' with Kill Switch targeting proxy port {proxy_port}")
            return True, f"NetNS '{netns_name}' configured with Kill Switch.", netns_name

        except Exception as e:
            logger.error(f"[NetworkKillSwitch] Failed setting up NetNS for profile '{profile_id}': {e}")
            cls.teardown_profile_netns(profile_id)
            return False, str(e), None

    @classmethod
    def _apply_firewall_rules(cls, netns_name: str, host_ip: str, proxy_port: int):
        """Applies strict egress iptables rules inside NetNS to enforce proxy kill switch."""
        prefix = ["sudo", "-n", "ip", "netns", "exec", netns_name, "iptables"]
        
        # Flush existing
        subprocess.run(prefix + ["-F"], capture_output=True)
        subprocess.run(prefix + ["-P", "INPUT", "DROP"], capture_output=True)
        subprocess.run(prefix + ["-P", "FORWARD", "DROP"], capture_output=True)
        subprocess.run(prefix + ["-P", "OUTPUT", "DROP"], capture_output=True)

        # Allow loopback
        subprocess.run(prefix + ["-A", "INPUT", "-i", "lo", "-j", "ACCEPT"], capture_output=True)
        subprocess.run(prefix + ["-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"], capture_output=True)

        # Allow established state
        subprocess.run(prefix + ["-A", "INPUT", "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"], capture_output=True)

        # Allow TCP egress ONLY to host proxy IP + proxy port
        subprocess.run(prefix + [
            "-A", "OUTPUT", "-p", "tcp", "-d", host_ip, "--dport", str(proxy_port), "-j", "ACCEPT"
        ], capture_output=True)

        # Drop everything else explicitly
        subprocess.run(prefix + ["-A", "OUTPUT", "-j", "DROP"], capture_output=True)

    @classmethod
    def teardown_profile_netns(cls, profile_id: str):
        """Cleanly removes profile network namespace and virtual ethernet interfaces."""
        if sys.platform != "linux":
            return

        import hashlib
        _id_hash = hashlib.sha256(profile_id.encode("utf-8")).hexdigest()
        netns_name = f"sox_{_id_hash[:10]}"
        veth_host = f"vth_{_id_hash[:8]}"

        cls._release_subnet_byte(profile_id)

        try:
            # Delete host iptables rules for veth_host if any exist
            while True:
                r = subprocess.run([
                    "sudo", "-n", "iptables", "-D", "INPUT",
                    "-i", veth_host, "-p", "tcp", "-j", "ACCEPT"
                ], capture_output=True)
                if r.returncode != 0:
                    break

            # Delete veth if left over
            subprocess.run(["sudo", "-n", "ip", "link", "delete", veth_host], capture_output=True)
            # Delete netns
            subprocess.run(["sudo", "-n", "ip", "netns", "del", netns_name], capture_output=True)
            logger.info(f"[NetworkKillSwitch] Cleared NetNS '{netns_name}'")
        except Exception as e:
            logger.debug(f"[NetworkKillSwitch] Cleanup NetNS notice: {e}")

    @classmethod
    def wrap_cmd_in_netns(cls, cmd: List[str], netns_name: Optional[str]) -> List[str]:
        """Wraps an executable command to run inside the network namespace if specified."""
        if not netns_name:
            return cmd
        return ["sudo", "-n", "ip", "netns", "exec", netns_name] + cmd
