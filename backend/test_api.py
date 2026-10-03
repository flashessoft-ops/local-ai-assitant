"""Run with: .venv/Scripts/python -m unittest backend.test_api"""
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

temporary = tempfile.TemporaryDirectory()
os.environ["CHAT_DB"] = os.path.join(temporary.name, "test.db")
from backend.main import app


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.topic = self.client.post("/api/topics", json={}).json()["id"]
        self.url = f"/api/topics/{self.topic}"

    def tearDown(self):
        self.client.delete(self.url)

    @patch("backend.main.httpx.post")
    def test_history_persistence_and_cascade(self, post):
        post.return_value = httpx.Response(200, json={"message": {"content": "Hello!"}}, request=httpx.Request("POST", "http://localhost"))
        result = self.client.post(self.url + "/messages", json={"content": "Hello"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual([m["role"] for m in result.json()], ["user", "assistant"])
        self.assertEqual(self.client.get(self.url + "/messages").json(), result.json())
        self.client.post(self.url + "/messages", json={"content": "Next"})
        self.assertEqual(post.call_args.kwargs["json"]["messages"], [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hello!"}, {"role": "user", "content": "Next"}])
        topic = next(t for t in self.client.get("/api/topics").json() if t["id"] == self.topic)
        self.assertEqual(topic["title"], "Hello")
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertEqual(self.client.get(self.url + "/messages").status_code, 404)

    @patch("backend.main.httpx.post", side_effect=httpx.ConnectError("offline"))
    def test_failure_is_retryable_without_saved_messages(self, post):
        self.assertEqual(self.client.post(self.url + "/messages", json={"content": "Hi"}).status_code, 502)
        self.assertEqual(self.client.get(self.url + "/messages").json(), [])

    def test_blank_message_and_missing_topic(self):
        self.assertEqual(self.client.post(self.url + "/messages", json={"content": "  "}).status_code, 422)
        self.assertEqual(self.client.get("/api/topics/999999/messages").status_code, 404)


if __name__ == "__main__":
    unittest.main()
