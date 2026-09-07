import os
import unittest
import tempfile
import shutil
from storage.crypto_vault import ZeroKnowledgeCryptoVault
from engine.sandbox.ephemeral_storage import EphemeralStorageManager
from engine.sandbox.sandbox_manager import SandboxManager
from engine.sandbox.virtiofs_manager import VirtiofsDaemonManager


class TestMicroVMAndSecurity(unittest.TestCase):

    def test_argon2id_aes_gcm_crypto(self):
        master_pw = "SuperSecretMasterKey123!$"
        data = {
            "profile_name": "UltraSecureProfile",
            "proxy_pass": "ProxySecretPassword987",
            "cookies": [{"name": "session", "value": "xyz123"}]
        }

        # Encrypt
        enc_b64 = ZeroKnowledgeCryptoVault.encrypt_dict(data, master_pw)
        self.assertIsInstance(enc_b64, str)
        self.assertNotIn("UltraSecureProfile", enc_b64)

        # Decrypt
        dec_data = ZeroKnowledgeCryptoVault.decrypt_dict(enc_b64, master_pw)
        self.assertEqual(dec_data["profile_name"], "UltraSecureProfile")
        self.assertEqual(dec_data["proxy_pass"], "ProxySecretPassword987")

        # Verify Wrong Password raises Exception (GCM Auth Tag Failure)
        with self.assertRaises(Exception):
            ZeroKnowledgeCryptoVault.decrypt_dict(enc_b64, "WrongPassword!")

    def test_ephemeral_ramdisk_storage(self):
        test_dir = tempfile.mkdtemp(prefix="soxbot_ephemeral_test_")
        test_profile_id = "test-ephemeral-uuid-1234"

        try:
            # Mount/allocate RAM disk
            ok, msg = EphemeralStorageManager.mount_ramdisk(test_profile_id, test_dir)
            self.assertTrue(ok)

            # Create dummy sensitive files
            secret_file = os.path.join(test_dir, "sensitive_cookie.txt")
            with open(secret_file, "w") as f:
                f.write("top_secret_session_token_data")

            self.assertTrue(os.path.exists(secret_file))

            # Forensic wipe & unmount
            wipe_ok = EphemeralStorageManager.wipe_and_unmount(test_profile_id, test_dir)
            self.assertTrue(wipe_ok)

            # Confirm 0 trace of file
            self.assertFalse(os.path.exists(secret_file))

        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir, ignore_errors=True)

    def test_system_capabilities(self):
        caps = SandboxManager.check_system_capabilities()
        self.assertIn("cloud_hypervisor", caps)
        self.assertIn("firecracker", caps)
        self.assertIn("virtiofsd", caps)
        self.assertIn("kvm", caps)
        self.assertIn("tmpfs_ram", caps)


if __name__ == "__main__":
    unittest.main()
