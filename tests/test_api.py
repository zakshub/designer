import asyncio
import copy
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx

from sentinel.__main__ import main
from sentinel.api import MAX_BODY, create_app
from sentinel.auth import Auth, AuthError, ITERATIONS, migrate_auth, password_hash, password_matches
from sentinel.engine import Brain
from sentinel.model import Invalid, ROOT, load_directory, read_json
from sentinel.store import Store

# Explicit test-only credentials, never used for the user's databases.
PASSWORD = "Fixture-only-long-passphrase-2026!"
NEW_PASSWORD = "Another-fixture-only-passphrase!"
SOURCE = "source_accessibility-guidance"
CLAIM = "knowledge_explicit-labels-mobile"
OUTCOME = "project-learning_explicit-labels-mobile"


class TestClient:
    """Exercise ASGI directly using HTTPX's supported transport."""
    def __init__(self, app, base_url):
        self.app, self.base_url = app, base_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, path, **kwargs):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=self.base_url) as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_dir = tempfile.TemporaryDirectory()
        cls.seed = Path(cls.seed_dir.name) / "seed.sqlite3"
        store = Store(cls.seed, True)
        try:
            migrate_auth(store)
            auth = Auth(store)
            cls.admin_id = auth.create_user("admin", PASSWORD, "admin", bootstrap=True)["id"]
            cls.ids = {"admin": cls.admin_id}
            for role in ("viewer", "editor", "reviewer"):
                cls.ids[role] = auth.create_user(role, PASSWORD, role, cls.admin_id)["id"]
        finally:
            store.close()

    @classmethod
    def tearDownClass(cls):
        cls.seed_dir.cleanup()

    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(folder) / "api.sqlite3"
        seed = Store(self.seed, True)
        try:
            seed.backup(self.path)
        finally:
            seed.close()
        self.now = 2_000_000_000
        self.app = create_app(self.path, True, auth_clock=lambda: self.now)
        self.client = self.enterContext(TestClient(self.app, base_url="http://127.0.0.1"))
        self.tokens = {}

    def login(self, username="admin", password=PASSWORD):
        return self.client.post("/v1/auth/login", json={"username": username, "password": password})

    def headers(self, role="admin"):
        if role not in self.tokens:
            response = self.login(role)
            self.assertEqual(response.status_code, 200, response.text)
            self.tokens[role] = response.json()["data"]["access_token"]
        return {"Authorization": "Bearer " + self.tokens[role]}

    def request(self, method, path, role="admin", body=None):
        return self.client.request(method, path, headers=self.headers(role), json=body)

    def ingest(self):
        response = self.request("POST", "/v1/objects", "editor", {"objects": load_directory(ROOT / "examples"), "reason": "Fixture ingestion"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["data"]

    def show(self, object_id):
        return self.request("GET", f"/v1/objects/{object_id}", "viewer").json()["data"]

    def publish(self, object_id):
        obj = self.show(object_id)
        response = self.request("POST", f"/v1/objects/{object_id}/submit", "editor", {"expected": obj["revision"], "reason": "Fixture submission"})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.request("POST", f"/v1/objects/{object_id}/review", "reviewer",
                                {"expected": response.json()["data"]["revision"], "reason": "Simulated fixture review", "decision": "approve"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def test_health_and_authenticated_openapi(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/v1/openapi.json").status_code, 401)
        schema = self.request("GET", "/v1/openapi.json", "viewer")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/v1/objects/{object_id}/review", schema.json()["paths"])

    def test_backup_restores_accounts_sessions_and_authenticated_history(self):
        self.ingest()
        headers = self.headers("viewer")
        original = self.request("GET", f"/v1/objects/{SOURCE}/history", "viewer").json()["data"]
        backup = self.path.with_name("restored.sqlite3")
        store = Store(self.path, True)
        try:
            store.backup(backup)
        finally:
            store.close()
        with TestClient(create_app(backup, True, auth_clock=lambda: self.now), base_url="http://127.0.0.1") as restored:
            self.assertEqual(restored.get("/v1/auth/me", headers=headers).status_code, 200)
            self.assertEqual(restored.get(f"/v1/objects/{SOURCE}/history", headers=headers).json()["data"], original)
            self.assertEqual(restored.post("/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code, 200)

    def test_login_me_logout_and_headers(self):
        response = self.login("reviewer")
        self.assertEqual(response.status_code, 200)
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": "Bearer " + token}
        me = self.client.get("/v1/auth/me", headers=headers)
        self.assertEqual(me.json()["data"]["username"], "reviewer")
        self.assertEqual(me.headers["cache-control"], "no-store")
        self.assertEqual(me.headers["x-content-type-options"], "nosniff")
        self.assertEqual(me.json()["request_id"], me.headers["x-request-id"])
        self.assertEqual(self.client.post("/v1/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/v1/auth/me", headers=headers).status_code, 401)

    def test_missing_invalid_and_expired_tokens(self):
        self.assertEqual(self.client.get("/v1/status").status_code, 401)
        self.assertEqual(self.client.get("/v1/status", headers={"Authorization": "Bearer nonsense"}).status_code, 401)
        headers = self.headers("viewer")
        self.now += 3600
        self.assertEqual(self.client.get("/v1/status", headers=headers).status_code, 401)

    def test_password_and_token_not_stored_plaintext(self):
        token = self.headers()["Authorization"].split()[1]
        store = Store(self.path, True)
        try:
            encoded = store.db.execute("SELECT password_hash FROM api_users WHERE username='admin'").fetchone()[0]
            stored_token = store.db.execute("SELECT token_hash FROM api_sessions").fetchone()[0]
            self.assertNotIn(PASSWORD, encoded)
            self.assertNotEqual(stored_token, token)
            self.assertTrue(password_matches(PASSWORD, encoded))
            self.assertIn(str(ITERATIONS), encoded)
        finally:
            store.close()

    def test_login_error_does_not_reveal_account_existence(self):
        wrong = self.login("viewer", "wrong-password")
        unknown = self.login("nobody", "wrong-password")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json()["error"], unknown.json()["error"])

    def test_login_throttle_and_recovery(self):
        for _ in range(5):
            self.assertEqual(self.login("viewer", "bad-password").status_code, 401)
        response = self.login("viewer")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "300")
        self.now += 301
        self.assertEqual(self.login("viewer").status_code, 200)

    def test_viewer_cannot_write_or_manage_users(self):
        self.assertEqual(self.request("POST", "/v1/objects", "viewer", {"objects": [{}], "reason": "Attempt"}).status_code, 403)
        self.assertEqual(self.request("GET", "/v1/users", "viewer").status_code, 403)
        self.assertEqual(self.request("GET", "/v1/audit/security", "viewer").status_code, 403)

    def test_editor_cannot_approve_and_reviewer_cannot_manage_accounts(self):
        body = {"expected": 1, "reason": "Attempt", "decision": "approve"}
        self.assertEqual(self.request("POST", "/v1/objects/x/review", "editor", body).status_code, 403)
        self.assertEqual(self.request("POST", "/v1/users", "reviewer", {"username": "new-user", "password": PASSWORD, "role": "admin", "reason": "Attempt"}).status_code, 403)

    def test_account_creation_and_no_hash_exposure(self):
        response = self.request("POST", "/v1/users", body={"username": "reader-two", "password": PASSWORD, "role": "viewer", "reason": "Read access"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertNotIn("password_hash", response.text)
        self.assertNotIn(PASSWORD, response.text)
        self.assertEqual(self.login("reader-two").status_code, 200)
        duplicate = self.request("POST", "/v1/users", body={"username": "reader-two", "password": PASSWORD, "role": "viewer", "reason": "Duplicate"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertNotIn("password_hash", self.request("GET", "/v1/users").text)

    def test_deactivation_and_role_changes_revoke_sessions(self):
        old = self.headers("editor")
        response = self.request("PATCH", f"/v1/users/{self.ids['editor']}", body={"role": "viewer", "reason": "Change responsibility"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/v1/auth/me", headers=old).status_code, 401)
        token = self.login("editor").json()["data"]["access_token"]
        self.assertEqual(self.client.get("/v1/auth/me", headers={"Authorization": "Bearer " + token}).json()["data"]["role"], "viewer")
        self.request("PATCH", f"/v1/users/{self.ids['editor']}", body={"active": False, "reason": "Offboarding"})
        self.assertEqual(self.login("editor").status_code, 401)

    def test_last_admin_cannot_be_disabled_or_demoted(self):
        for changes in ({"role": "viewer"}, {"active": False}):
            response = self.request("PATCH", f"/v1/users/{self.admin_id}", body={**changes, "reason": "Attempt"})
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.request("GET", "/v1/auth/me").status_code, 200)

    def test_password_change_revokes_current_session(self):
        old = self.headers("viewer")
        response = self.request("POST", "/v1/auth/password", "viewer", {"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/v1/auth/me", headers=old).status_code, 401)
        self.assertEqual(self.login("viewer", PASSWORD).status_code, 401)
        self.assertEqual(self.login("viewer", NEW_PASSWORD).status_code, 200)

    def test_admin_password_reset(self):
        old = self.headers("viewer")
        response = self.request("POST", f"/v1/users/{self.ids['viewer']}/password", body={"new_password": NEW_PASSWORD, "reason": "Credential recovery"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/v1/auth/me", headers=old).status_code, 401)
        self.assertEqual(self.login("viewer", NEW_PASSWORD).status_code, 200)

    def test_actor_spoofing_and_review_metadata_injection_rejected(self):
        response = self.request("POST", "/v1/objects", "editor", {"objects": load_directory(ROOT / "examples"), "reason": "Attempt", "actor": "reviewer"})
        self.assertEqual(response.status_code, 422)
        self.ingest()
        response = self.request("PATCH", f"/v1/objects/{SOURCE}", "editor", {"expected": 1, "reason": "Attempt", "changes": {"review": {"decision": "approved"}}})
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.show(SOURCE)["review"])

    def test_ingestion_uses_authenticated_author_and_audit_context(self):
        self.ingest()
        self.assertEqual(self.show(SOURCE)["created_by"], "editor")
        history = self.request("GET", f"/v1/objects/{SOURCE}/history", "viewer").json()["data"]
        self.assertEqual(history[0]["actor"], "editor")
        context = history[0]["authentication"]
        self.assertTrue(context["authenticated"])
        self.assertEqual(context["user_id"], self.ids["editor"])
        self.assertEqual(context["role"], "editor")
        self.assertTrue(context["session_id"])
        self.assertTrue(context["request_id"])

    def test_stale_revision_returns_conflict_without_writing(self):
        self.ingest()
        body = {"expected": 1, "reason": "Correction", "changes": {"title": "Updated source"}}
        self.assertEqual(self.request("PATCH", f"/v1/objects/{SOURCE}", "editor", body).status_code, 200)
        self.assertEqual(self.request("PATCH", f"/v1/objects/{SOURCE}", "editor", body).status_code, 409)
        self.assertEqual(self.show(SOURCE)["revision"], 2)

    def test_unknown_objects_and_routes_are_json_errors(self):
        for path in ("/v1/objects/source_missing", "/v1/objects/source_missing/review-packet", "/not-a-route"):
            response = self.request("GET", path, "viewer")
            self.assertEqual(response.status_code, 404)
            self.assertIn("error", response.json())

    def test_body_and_json_boundaries(self):
        response = self.client.post("/v1/auth/login", content=b"x" * (MAX_BODY + 1), headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        for text in ('{"username":"admin","username":"other"}', '{"password":NaN}', '{bad'):
            response = self.client.post("/v1/auth/login", content=text, headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/v1/auth/login", content="x", headers={"Content-Type": "text/plain"}).status_code, 415)

    def test_validation_errors_do_not_echo_credentials(self):
        response = self.client.post("/v1/auth/login", json={"username": "admin", "password": PASSWORD, "extra": PASSWORD})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(PASSWORD, response.text)
        self.assertNotIn("input", response.json()["error"]["details"][0])

    def test_invalid_revisions_and_pagination(self):
        self.ingest()
        response = self.request("POST", f"/v1/objects/{SOURCE}/submit", "editor", {"expected": True, "reason": "Attempt"})
        self.assertEqual(response.status_code, 422)
        response = self.request("GET", "/v1/objects?limit=3&offset=2", "viewer")
        self.assertEqual(response.json()["data"]["total"], 13)
        self.assertEqual(len(response.json()["data"]["items"]), 3)
        self.assertEqual(self.request("GET", "/v1/objects?limit=101", "viewer").status_code, 422)

    def test_no_browser_cors_and_untrusted_hosts(self):
        response = self.client.get("/health", headers={"Origin": "https://untrusted.invalid"})
        self.assertNotIn("access-control-allow-origin", response.headers)
        self.assertEqual(self.client.get("/health", headers={"Host": "untrusted.invalid"}).status_code, 400)

    def test_queue_packet_and_blocked_evaluation_are_read_only(self):
        records = load_directory(ROOT / "pilots/wcag-labels/intake")
        for record in records:
            record["fixture"] = True
        self.request("POST", "/v1/objects", "editor", {"objects": records, "reason": "Fixture copies for testing"})
        queue = self.request("GET", "/v1/review-queue", "viewer")
        self.assertEqual(queue.json()["data"]["pending_count"], 10)
        packet = self.request("GET", "/v1/objects/knowledge_web-visible-label-name/review-packet", "viewer")
        self.assertEqual(len(packet.json()["data"]["dependencies"]), 4)
        evaluation = self.request("POST", "/v1/evaluate", "viewer", {"suite": read_json(ROOT / "pilots/wcag-labels/retrieval-suite.json")})
        self.assertEqual(evaluation.status_code, 200)
        self.assertEqual(evaluation.json()["data"]["status"], "blocked")
        self.assertEqual(self.request("GET", "/v1/status", "viewer").json()["data"]["eligible"], 0)

    def test_complete_api_learning_cycle(self):
        self.ingest()
        for kind in ("source", "evidence", "knowledge", "expert-profile", "reference", "skill", "experiment", "conflict", "project-learning"):
            for obj in load_directory(ROOT / "examples"):
                if obj["type"] != kind:
                    continue
                if kind == "project-learning":
                    self.request("PATCH", f"/v1/objects/{OUTCOME}", "editor", {"expected": 1, "reason": "Pin used revision",
                                 "changes": {"knowledge_revision": self.show(CLAIM)["revision"]}})
                self.publish(obj["id"])
        url = "/v1/retrieve?query=labels&domain=ui&platform=mobile"
        self.assertEqual(len(self.request("GET", url, "viewer").json()["data"]), 2)
        self.assertEqual(self.request("GET", "/v1/skills/skill_review-action-labels/use", "viewer").status_code, 200)
        applied = self.request("POST", f"/v1/objects/{OUTCOME}/apply-outcome", "reviewer", {"expected": 3, "reason": "Use simulated outcome"})
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()["data"]["confidence"], 0.65)
        self.assertEqual(len(self.request("GET", url, "viewer").json()["data"]), 1)
        approved = self.request("POST", f"/v1/objects/{CLAIM}/review", "reviewer", {"expected": 4, "reason": "Simulated outcome review", "decision": "approve"})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["data"]["review"]["actor"], "reviewer")
        self.assertEqual(approved.json()["data"]["review"]["actor_kind"], "fixture")
        self.assertEqual(len(self.request("GET", url, "viewer").json()["data"]), 2)
        self.assertEqual(self.request("POST", f"/v1/objects/{CLAIM}/retire", "reviewer", {"expected": 5, "reason": "Fixture withdrawal"}).status_code, 200)
        self.assertEqual(len(self.request("GET", url, "viewer").json()["data"]), 1)
        history = self.request("GET", f"/v1/objects/{CLAIM}/history", "viewer").json()["data"]
        self.assertTrue(all(h["authentication"]["authenticated"] for h in history))
        self.assertEqual(self.request("POST", "/v1/maintenance/sweep", "reviewer", {"reason": "Due review check"}).status_code, 200)

    def test_rejection_preserves_authenticated_reviewer(self):
        self.ingest()
        self.request("POST", f"/v1/objects/{SOURCE}/submit", "editor", {"expected": 1, "reason": "Submit fixture"})
        response = self.request("POST", f"/v1/objects/{SOURCE}/review", "reviewer", {"expected": 2, "reason": "Need more context", "decision": "reject"})
        self.assertEqual(response.json()["data"]["lifecycle"], "draft")
        self.assertEqual(response.json()["data"]["review"]["actor"], "reviewer")

    def test_security_events_exclude_secrets(self):
        self.login("viewer", "wrong-password")
        self.headers("viewer")
        self.request("GET", "/v1/users", "viewer")
        response = self.request("GET", "/v1/audit/security")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(PASSWORD, response.text)
        self.assertNotIn(self.tokens["viewer"], response.text)
        self.assertIn("role-denied", response.text)
        self.assertIn("login-failed", response.text)


class AuthStorageTests(unittest.TestCase):
    def test_hashes_are_salted_and_password_policy(self):
        first, second = password_hash(PASSWORD), password_hash(PASSWORD)
        self.assertNotEqual(first, second)
        self.assertTrue(password_matches(PASSWORD, first))
        self.assertFalse(password_matches("incorrect", first))
        self.assertFalse(password_matches(PASSWORD, "malformed"))
        with self.assertRaises(Invalid):
            password_hash("short")

    def test_migration_preserves_old_records_and_marks_cli_history(self):
        store = Store(":memory:", True)
        try:
            Brain(store).ingest(load_directory(ROOT / "examples"), "cli-operator", "Fixture baseline")
            before = store.all()
            migrate_auth(store)
            migrate_auth(store)
            self.assertEqual(store.all(), before)
            self.assertFalse(store.history(SOURCE)[0]["authentication"]["authenticated"])
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM api_users").fetchone()[0], 0)
        finally:
            store.close()

    def test_unknown_auth_schema_fails_closed(self):
        store = Store(":memory:")
        try:
            store.db.execute("INSERT INTO metadata VALUES('auth_schema_version','999')")
            with self.assertRaises(Invalid):
                migrate_auth(store)
            self.assertFalse(store.db.execute("SELECT 1 FROM sqlite_master WHERE name='api_users'").fetchone())
        finally:
            store.close()

    def test_audit_context_failure_rolls_back_object_and_history(self):
        store = Store(":memory:", True)
        try:
            migrate_auth(store)
            store.audit_context = {"user_id": "missing", "username": "test", "role": "editor", "session_id": "missing", "request_id": "test"}
            with self.assertRaises(sqlite3.IntegrityError):
                Brain(store).ingest(load_directory(ROOT / "examples"), "test", "Fixture transaction failure")
            self.assertEqual(store.all(), [])
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM history").fetchone()[0], 0)
        finally:
            store.close()

    def test_bootstrap_once_and_hidden_password_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "auth.sqlite3")
            with patch("sentinel.__main__.getpass.getpass", side_effect=[PASSWORD, PASSWORD]), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--db", path, "bootstrap-admin", "operator"]), 0)
            self.assertNotIn(PASSWORD, output.getvalue())
            store = Store(path)
            try:
                with self.assertRaises(AuthError):
                    Auth(store).create_user("second", PASSWORD, "admin", bootstrap=True)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
