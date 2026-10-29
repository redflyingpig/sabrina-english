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

    def test_login_form_takes_any_username_without_pin(self):
        tag = next(tag for tag, attrs in self.elements.elements if attrs.get("id") == "profileNameInput")
        self.assertEqual("input", tag)
        field = self.attributes_for_id("profileNameInput")
        self.assertEqual("text", field.get("type"))
        self.assertEqual("32", field.get("maxlength"))
        self.assertNotIn("profilePinInput", self.html)
        self.assertNotIn("profilePinInput", self.function_body("loginProfile"))
        self.assertIn("body: { username }", self.function_body("loginProfile"))
        self.assertIn('error.payload?.error === "invalid_username"', self.function_body("loginProfile"))
        self.assertIn("连接失败，请稍后再试。", self.function_body("loginProfile"))
        # The name is a study-profile id, not a fixed roster: no hard-coded options remain.
        self.assertNotIn("<select id=\"profileNameInput\"", self.html)
        for name in ("Owner", "Sabrina", "Max"):
            self.assertNotIn(f'<option value="{name}"', self.html)

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
        self.assertIn("headers.Authorization = `Bearer ${requestToken}`", self.html)
        self.assertIn("sessionIsCurrent(context)", self.html)

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

    def test_completed_lesson_offers_an_unseen_next_batch_in_same_mode(self):
        next_button = self.attributes_for_id("nextBatch")
        self.assertEqual("button", next(
            tag for tag, attrs in self.elements.elements if attrs.get("id") == "nextBatch"
        ))
        self.assertIn("hidden", next_button)
        self.assertIn("function selectNextLessonSet", self.html)
        self.assertIn("SabrinaContent.selectBatch", self.function_body("selectNextLessonSet"))
        self.assertIn("items: contentLibrary", self.function_body("selectNextLessonSet"))
        self.assertIn("nextBatch.hidden = !completed", self.function_body("renderProgress"))
        self.assertIn('nextBatch.addEventListener("click"', self.html)
        self.assertIn("lessonSet = selection.items", self.html)

    def test_learning_pool_is_large_enough_to_delay_repeats(self):
        self.assertNotIn("const lessonBank", self.html)
        self.assertIn('src="/assets/content-library.js"', self.html)
        self.assertIn("SabrinaContent.load", self.html)
        self.assertIn("contentLoading", self.html)
        self.assertIn("contentError", self.html)
        self.assertIn("retryContent", self.html)

    def test_new_history_records_keep_stable_content_ids_and_legacy_history(self):
        mark_body = self.function_body("markLearned")
        self.assertIn("contentId: item.contentId", mark_body)
        self.assertIn("entry.contentId === item.contentId", self.html)
        self.assertIn("SabrinaContent.legacyIdentity", self.html)
        self.assertNotIn("localStorage.removeItem(STORAGE_KEY)", self.function_body("loadContentLibrary"))

    def test_profile_history_loads_before_initial_batch_and_review_can_advance(self):
        initialize = self.function_body("initializeApp")
        self.assertLess(initialize.index("await loadProfileFromServer()"), initialize.rindex("await loadContentLibrary()"))
        self.assertIn("reviewedThisBatch.add(item.contentId)", self.function_body("markLearned"))
        self.assertIn("reviewedAt: new Date().toISOString()", self.function_body("markLearned"))

    def test_backup_controls_are_compact(self):
        backup_section = self.html.split('aria-labelledby="backupTitle"', 1)[1].split("</section>", 1)[0]
        self.assertIn('class="backup-actions"', backup_section)
        self.assertIn('class="small-btn" id="exportData"', backup_section)
        self.assertIn('class="small-btn" id="importData"', backup_section)
        self.assertNotIn('class="tool-grid"', backup_section)

    def test_wordbook_module_is_wired_into_the_page(self):
        self.assertIn('href="/assets/wordbook.css"', self.html)
        self.assertIn('src="/assets/wordbook.js"', self.html)
        self.assertIn('id="wordbookView"', self.html)
        self.assertIn('href="#wordbook"', self.html)
        self.assertIn("SabrinaWordbook.mount(wordbookView", self.html)

    def test_wordbook_progress_is_part_of_profile_sync_and_backup(self):
        self.assertIn("getWordbook()", self.function_body("getProfileState"))
        self.assertIn("WORDBOOK_KEY", self.function_body("applyProfileState"))
        self.assertIn("SabrinaWordbook.merge(cloudState.wordbook, localState.wordbook)", self.function_body("mergeProfileStates"))
        self.assertIn("WORDBOOK_KEY", self.function_body("hasLocalProfileData"))
        self.assertIn('WORDBOOK_KEY = profileStorageKey("wordbook")', self.function_body("setActiveProfile"))
        self.assertIn("wordbook: getWordbook()", self.function_body("exportBackup"))
        self.assertIn("payload.wordbook", self.function_body("importBackup"))

    def test_site_is_titled_go_sabrina_go(self):
        self.assertIn("<title>Go Sabrina Go</title>", self.html)
        self.assertIn("<h1>Go Sabrina Go</h1>", self.html)
        self.assertNotIn("Sabrina English", self.html)

    def test_cantonese_tab_is_wired_into_the_page(self):
        self.assertIn('href="/assets/cantonese.css"', self.html)
        self.assertIn('src="/assets/cantonese-core.js"', self.html)
        self.assertIn('<script type="module" src="/assets/cantonese/app.js"></script>', self.html)
        self.assertIn('href="#cantonese"', self.html)
        self.assertEqual("cantonese", self.attributes_for_id("cantoneseView")["data-view"])
        self.assertIn('view: "cantonese"', self.function_body("parseRoute"))
        self.assertIn("SabrinaCantoneseApp?.render()", self.function_body("renderRoute"))
        self.assertIn("SabrinaCantoneseApp?.reset()", self.function_body("refreshWordbookForSession"))

    def test_cantonese_progress_is_part_of_profile_sync_and_backup(self):
        self.assertIn("getCantonese()", self.function_body("getProfileState"))
        self.assertIn("CANTONESE_KEY", self.function_body("applyProfileState"))
        self.assertIn("SabrinaCantonese.merge(cloudState.cantonese, localState.cantonese)", self.function_body("mergeProfileStates"))
        self.assertIn("CANTONESE_KEY", self.function_body("hasLocalProfileData"))
        self.assertIn('CANTONESE_KEY = profileStorageKey("cantonese")', self.function_body("setActiveProfile"))
        self.assertIn("cantonese: getCantonese()", self.function_body("exportBackup"))
        self.assertIn("payload.cantonese", self.function_body("importBackup"))
        self.assertIn("changed: scheduleProfileSync", self.html)

    def test_cantonese_course_needs_a_session(self):
        data = (INDEX.parent / "assets" / "cantonese" / "data.js").read_text(encoding="utf-8")
        self.assertIn('apiRequest("/api/cantonese/course")', data)
        self.assertNotIn("course.json", data)

    def test_cantonese_styles_are_scoped(self):
        css = (INDEX.parent / "assets" / "cantonese.css").read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        css = re.sub(r"@keyframes[^{]+\{(?:[^{}]*\{[^}]*\})*[^}]*\}", "", css)
        css = re.sub(r"@media[^{]+\{", "", css)
        for selector_list in re.findall(r"(?:^|\})\s*([^{}]+)\{", css):
            for selector in selector_list.split(","):
                self.assertTrue(selector.strip().startswith("#cantoneseView"), selector.strip())

    def test_wordbook_content_needs_a_session(self):
        self.assertIn("Authorization: `Bearer ${sessionToken}`", self.html)
        self.assertNotIn("/wordbook/pages/", self.html.replace("/api/wordbook/pages/", ""))
        self.assertIn("refreshWordbookForSession()", self.function_body("logoutProfile"))
        self.assertIn("refreshWordbookForSession()", self.function_body("handleExpiredSession"))


if __name__ == "__main__":
    unittest.main()
