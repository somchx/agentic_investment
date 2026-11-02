"""Run with: .venv/bin/python -m unittest discover -s tests -v

Uses an isolated in-memory user table; never changes the application's DB.
"""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "profile-tests-only-secret-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.api.auth import router
from app.config import JWT_ALGORITHM, JWT_SECRET_KEY
from app.db.models import User
from app.security import create_access_token
import db


class AuthProfileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        User.__table__.create(self.engine)
        self.patch = patch.object(db, "SessionLocal", sessionmaker(bind=self.engine))
        self.patch.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.account = self.register("first@example.com", "First User")
        self.headers = {"Authorization": f"Bearer {self.account['access_token']}"}

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.engine.dispose()

    def register(self, email, name):
        response = self.client.post("/api/auth/register", json={"email": email, "password": "Oldpass1!", "full_name": name})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_registration_returns_name_without_secrets(self):
        self.assertEqual(self.account["user"]["full_name"], "First User")
        self.assertEqual(set(self.account["user"]), {"id", "email", "full_name"})
        response = self.client.get("/api/auth/me", headers=self.headers)
        self.assertEqual(response.json(), self.account["user"])
        for name in ("", "   ", "x" * 201):
            response = self.client.post("/api/auth/register", json={"email": "new@example.com", "password": "12345678", "full_name": name})
            self.assertEqual(response.status_code, 422)

    def test_edit_is_persisted_and_only_changes_current_user(self):
        other = self.register("second@example.com", "Second User")
        response = self.client.patch("/api/auth/me", headers=self.headers, json={
            "full_name": "  สมชาย ใจดี  ", "email": "UPDATED@example.com", "id": other["user"]["id"],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["full_name"], "สมชาย ใจดี")
        self.assertEqual(response.json()["email"], "updated@example.com")
        self.assertEqual(db.get_user_by_id(other["user"]["id"])["full_name"], "Second User")
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).json()["full_name"], "สมชาย ใจดี")
        self.assertIsNone(db.verify_user("first@example.com", "Oldpass1!"))
        self.assertIsNotNone(db.verify_user("updated@example.com", "Oldpass1!"))

    def test_duplicate_email_rolls_back_entire_profile_update(self):
        self.register("second@example.com", "Second User")
        response = self.client.patch("/api/auth/me", headers=self.headers, json={"full_name": "Changed", "email": "SECOND@example.com"})
        self.assertEqual(response.status_code, 409)
        response = self.client.get("/api/auth/me", headers=self.headers)
        self.assertEqual(response.json()["full_name"], "First User")
        self.assertEqual(response.json()["email"], "first@example.com")

    def test_profile_validation_and_authentication(self):
        for payload in ({"full_name": "  ", "email": "ok@example.com"}, {"full_name": "Valid", "email": "bad"}):
            self.assertEqual(self.client.patch("/api/auth/me", headers=self.headers, json=payload).status_code, 422)
        self.assertEqual(self.client.patch("/api/auth/me", json={"full_name": "Intruder", "email": "bad@example.com"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/change-password", json={"current_password": "Oldpass1!", "new_password": "Newpass2!"}).status_code, 401)

    def test_wrong_current_password_does_not_log_out_or_change_password(self):
        response = self.client.post("/api/auth/change-password", headers=self.headers, json={"current_password": "Wrongpass1!", "new_password": "Newpass2!"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).status_code, 200)
        self.assertIsNotNone(db.verify_user("first@example.com", "Oldpass1!"))

    def test_password_policy_and_reuse(self):
        for password in ("Short1!", "lowercase1!", "UPPERCASE1!", "NoNumbers!", "NoSpecial1", "A1!" + "x" * 126):
            response = self.client.post("/api/auth/change-password", headers=self.headers, json={"current_password": "Oldpass1!", "new_password": password})
            self.assertEqual(response.status_code, 422, password)
        self.assertEqual(self.client.post("/api/auth/change-password", headers=self.headers, json={"current_password": "Oldpass1!", "new_password": "Oldpass1!"}).status_code, 400)

    def test_password_change_replaces_credentials_and_revokes_old_tokens(self):
        other = self.register("second@example.com", "Second User")
        response = self.client.post("/api/auth/change-password", headers=self.headers, json={"current_password": "Oldpass1!", "new_password": "Newpass2!"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(db.verify_user("first@example.com", "Oldpass1!"))
        self.assertIsNotNone(db.verify_user("first@example.com", "Newpass2!"))
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).status_code, 401)
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        login = self.client.post("/api/auth/login", json={"email": "first@example.com", "password": "Newpass2!"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + other["access_token"]}).status_code, 200)

    def test_legacy_token_works_until_password_changes(self):
        payload = jwt.decode(self.account["access_token"], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        payload.pop("ver")
        headers = {"Authorization": "Bearer " + jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        self.client.post("/api/auth/change-password", headers=headers, json={"current_password": "Oldpass1!", "new_password": "Newpass2!"})
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_deleted_account_and_malformed_subject_are_unauthorized(self):
        for subject in (99999, "invalid"):
            token = create_access_token(subject, "unknown@example.com")
            self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code, 401)


class ProfileMigrationTests(unittest.TestCase):
    def test_existing_accounts_survive_upgrade_and_downgrade(self):
        path = Path(__file__).parents[1] / "alembic/versions/f2c4d6e8a901_add_user_profile.py"
        spec = importlib.util.spec_from_file_location("profile_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password_hash TEXT)"))
            connection.execute(text("INSERT INTO users VALUES (1, 'existing@example.com', 'existing-hash')"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                row = connection.execute(text("SELECT * FROM users")).mappings().one()
                self.assertEqual(row["full_name"], "")
                self.assertEqual(row["token_version"], 0)
                self.assertEqual(row["password_hash"], "existing-hash")
                migration.downgrade()
                self.assertEqual(connection.execute(text("SELECT email FROM users")).scalar_one(), "existing@example.com")
                self.assertNotIn("full_name", {c["name"] for c in inspect(connection).get_columns("users")})
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
