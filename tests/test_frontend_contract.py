import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


INDEX = Path(__file__).resolve().parents[1] / "index.html"


class ElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class FrontendContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")
        cls.elements = ElementCollector()
        cls.elements.feed(cls.html)

    def attributes_for_id(self, element_id):
        for _, attrs in self.elements.elements:
            if attrs.get("id") == element_id:
                return attrs
        self.fail(f"Missing element #{element_id}")

    def function_body(self, name):
        match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\([^)]*\)\s*\{{", self.html)
        self.assertIsNotNone(match, f"Missing function {name}")
        start = match.end()
        depth = 1
        for index in range(start, len(self.html)):
            if self.html[index] == "{":
                depth += 1
            elif self.html[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.html[start:index]
        self.fail(f"Unclosed function {name}")

    def test_supabase_credentials_and_rpc_are_removed(self):
        self.assertNotIn("supabase.co", self.html)
        self.assertNotIn("SUPABASE_", self.html)
        self.assertNotIn("callProfileRpc", self.html)

    def test_login_form_has_owner_sabrina_max_and_pin(self):
        select = self.attributes_for_id("profileNameInput")
        pin = self.attributes_for_id("profilePinInput")
        self.assertEqual("select", next(tag for tag, attrs in self.elements.elements if attrs.get("id") == "profileNameInput"))
        self.assertEqual("password", pin["type"])
        self.assertEqual("6", pin["minlength"])
        self.assertEqual("64", pin["maxlength"])
        for name in ("Owner", "Sabrina", "Max"):
            self.assertIn(f'value="{name}"', self.html)
        self.assertTrue(select)

    def test_login_dialog_is_viewport_bounded(self):
        dialog_rule = re.search(r"\.profile-dialog\s*\{(.*?)\}", self.html, re.DOTALL)
        self.assertIsNotNone(dialog_rule)
        self.assertIn("width: 500px", dialog_rule.group(1))
        self.assertIn("max-width: calc(100vw - 28px)", dialog_rule.group(1))
        field_rule = re.search(r"\.profile-field\s*\{(.*?)\}", self.html, re.DOTALL)
        self.assertIn("min-width: 0", field_rule.group(1))

    def test_frontend_uses_same_origin_api_and_bearer_token(self):
        self.assertIn('const SESSION_KEY = "sabrinaEnglish:session"', self.html)
        self.assertIn('apiRequest("/api/auth/login"', self.html)
        self.assertIn('apiRequest("/api/profile"', self.html)
        self.assertIn("headers.Authorization = `Bearer ${sessionToken}`", self.html)

    def test_local_write_precedes_sync(self):
        body = self.function_body("scheduleProfileSync")
        self.assertLess(
            body.index("localStorage.setItem(PROFILE_UPDATED_KEY"),
            body.index("setTimeout(saveProfileToServer"),
        )

    def test_409_merges_and_retries_once(self):
        body = self.function_body("saveProfileToServer")
        self.assertIn("error.status === 409", body)
        self.assertIn("mergeProfileStates(error.payload.current.state", body)
        self.assertIn("retryOnConflict", body)
        self.assertIn("saveProfileToServer(false)", body)

    def test_offline_and_expired_session_keep_local_data(self):
        self.assertIn('window.addEventListener("online"', self.html)
        self.assertIn('document.addEventListener("visibilitychange"', self.html)
        body = self.function_body("handleExpiredSession")
        self.assertIn("localStorage.removeItem(SESSION_KEY)", body)
        self.assertNotIn("localStorage.removeItem(STORAGE_KEY)", body)
        self.assertNotIn("localStorage.clear", body)

    def test_existing_learning_features_remain_present(self):
        for element_id in (
            "lessonGrid",
            "streakText",
            "progressFill",
            "startReview",
            "favoritesContent",
            "exportData",
            "importData",
        ):
            self.attributes_for_id(element_id)
        self.assertIn("speechSynthesis", self.html)
        self.assertIn("function mergeProfileStates", self.html)


if __name__ == "__main__":
    unittest.main()
