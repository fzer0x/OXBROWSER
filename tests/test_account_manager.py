import unittest
import os
import shutil
import tempfile
from engine.account_manager import AccountManager
from storage.profile_manager import ProfileManager


class TestAccountManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.pm = ProfileManager(profiles_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_platform_presets(self):
        """Verify all requested platforms exist in AccountManager."""
        required = ["google", "instagram", "github", "tiktok", "twitter", "discord", "reddit", "spotify", "facebook", "custom"]
        for p in required:
            info = AccountManager.get_platform_info(p)
            self.assertIsNotNone(info)
            self.assertTrue(len(info["login_url"]) > 0)
            self.assertTrue(len(info["name"]) > 0)

    def test_rfc6238_totp_generation(self):
        """Verify RFC 6238 TOTP 6-digit generation and remaining time countdown."""
        # Standard test base32 secret
        secret = "JBSWY3DPEHPK3PXP"
        code, rem = AccountManager.generate_totp_code(secret)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertTrue(0 <= rem <= 30)

        # Spaces and lowercase tolerance
        code2, _ = AccountManager.generate_totp_code("jbsw y3dp ehpk 3pxp")
        self.assertEqual(code, code2)

        # Empty secret
        empty_code, empty_rem = AccountManager.generate_totp_code("")
        self.assertEqual(empty_code, "")
        self.assertEqual(empty_rem, 0)

    def test_batch_credentials_parser(self):
        """Verify batch credential parser handles delimited text lines and JSON."""
        raw_text = """
        # Comments should be ignored
        google:myuser@gmail.com:SecretPass123:JBSWY3DPEHPK3PXP
        instagram:insta_bot_1:MyPassword!
        github:dev_user:MyDevPass123:JBSWY3DPEHPK3PXP
        tiktok:tiktok_user:TikTokPass99
        custom_user@domain.com:SomePassword!
        """
        accounts = AccountManager.parse_batch_credentials(raw_text)
        self.assertEqual(len(accounts), 5)
        
        self.assertEqual(accounts[0]["platform"], "google")
        self.assertEqual(accounts[0]["username"], "myuser@gmail.com")
        self.assertEqual(accounts[0]["password"], "SecretPass123")
        self.assertEqual(accounts[0]["totp_secret"], "JBSWY3DPEHPK3PXP")

        self.assertEqual(accounts[1]["platform"], "instagram")
        self.assertEqual(accounts[1]["username"], "insta_bot_1")
        self.assertEqual(accounts[1]["password"], "MyPassword!")

        self.assertEqual(accounts[2]["platform"], "github")
        self.assertEqual(accounts[3]["platform"], "tiktok")

        # JSON format parsing
        json_text = """
        [
            {"platform": "spotify", "username": "spot_user", "password": "spot_password", "auto_login_on_launch": true}
        ]
        """
        json_accounts = AccountManager.parse_batch_credentials(json_text)
        self.assertEqual(len(json_accounts), 1)
        self.assertEqual(json_accounts[0]["platform"], "spotify")
        self.assertEqual(json_accounts[0]["username"], "spot_user")
        self.assertTrue(json_accounts[0]["auto_login_on_launch"])

    def test_profile_with_accounts_storage(self):
        """Verify saving and loading profiles with accounts in ProfileManager."""
        pdata = self.pm.create_default_profile_data("Social Farming Profile")
        self.assertIn("accounts", pdata)
        self.assertEqual(pdata["accounts"], [])

        acc1 = AccountManager.create_account_record(
            platform="google",
            username="bot1@gmail.com",
            password="StrongPassword123!",
            totp_secret="JBSWY3DPEHPK3PXP",
            auto_login_on_launch=True
        )
        acc2 = AccountManager.create_account_record(
            platform="instagram",
            username="insta_farmer",
            password="InstaPassword99!"
        )
        pdata["accounts"] = [acc1, acc2]

        saved = self.pm.save_profile(pdata)
        self.assertTrue(saved)

        loaded = self.pm.load_profile(pdata["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.get("accounts", [])), 2)
        self.assertEqual(loaded["accounts"][0]["username"], "bot1@gmail.com")
        self.assertTrue(loaded["accounts"][0]["auto_login_on_launch"])
        self.assertEqual(loaded["accounts"][1]["platform"], "instagram")

    def test_autofill_script_generation(self):
        """Verify JavaScript autofill code generation."""
        acc = AccountManager.create_account_record(
            platform="google",
            username="test@gmail.com",
            password="my_password",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        script = AccountManager.generate_autofill_script(acc)
        self.assertIn("test@gmail.com", script)
        self.assertIn("my_password", script)
        self.assertIn("querySelector", script)


if __name__ == "__main__":
    unittest.main()
