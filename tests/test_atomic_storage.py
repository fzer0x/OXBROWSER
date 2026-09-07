import os
import unittest
import tempfile
import shutil
from storage.profile_manager import ProfileManager
from storage.crypto_vault import ZeroKnowledgeCryptoVault

class TestAtomicStorageAndVault(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="soxbot_test_storage_")
        self.pm = ProfileManager(profiles_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        ZeroKnowledgeCryptoVault.lock_vault()

    def test_atomic_write_profile_plain(self):
        pdata = self.pm.create_default_profile_data("Test Plain Profile")
        pid = pdata["id"]
        res = self.pm.save_profile(pdata)
        self.assertTrue(res)

        # Ensure file exists and contains valid JSON
        json_path = self.pm.get_profile_json_path(pid)
        self.assertTrue(os.path.exists(json_path))

        loaded = self.pm.load_profile(pid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["name"], "Test Plain Profile")

    def test_zero_knowledge_vault_unlock_lock(self):
        master_pwd = "SuperSecretMasterPassword!2026"
        unlocked = ZeroKnowledgeCryptoVault.set_session_master_password(master_pwd)
        self.assertTrue(unlocked)
        self.assertTrue(ZeroKnowledgeCryptoVault.is_vault_unlocked())
        self.assertEqual(ZeroKnowledgeCryptoVault.get_session_password(), master_pwd)

        # Save encrypted profile
        pdata = self.pm.create_default_profile_data("Encrypted Profile")
        pid = pdata["id"]
        pdata["encrypted"] = True
        save_res = self.pm.save_profile(pdata)
        self.assertTrue(save_res)

        enc_path = self.pm.get_profile_enc_path(pid)
        self.assertTrue(os.path.exists(enc_path))
        self.assertFalse(os.path.exists(self.pm.get_profile_json_path(pid)))

        # Load while vault is unlocked
        loaded = self.pm.load_profile(pid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["name"], "Encrypted Profile")

        # Lock vault
        ZeroKnowledgeCryptoVault.lock_vault()
        self.assertFalse(ZeroKnowledgeCryptoVault.is_vault_unlocked())
        self.assertIsNone(ZeroKnowledgeCryptoVault.get_session_password())

        # Load should fail without password
        loaded_locked = self.pm.load_profile(pid)
        self.assertIsNone(loaded_locked)

        # Load with explicit password should succeed
        loaded_explicit = self.pm.load_profile(pid, master_password=master_pwd)
        self.assertIsNotNone(loaded_explicit)
        self.assertEqual(loaded_explicit["name"], "Encrypted Profile")

if __name__ == "__main__":
    unittest.main()
