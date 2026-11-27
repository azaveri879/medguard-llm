"""Offline tests for handler.gateway_reply's layer switches (Bedrock is mocked)."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AUDIT_BUCKET", "unused")
os.environ.setdefault("DDB_TABLE", "unused")
os.environ.setdefault("BEDROCK_MODEL_ID", "unused")

import handler  # noqa: E402

NOTE = "Patient seen 03/14/2026. Call 608-555-0143. Plan: continue furosemide 40 mg."


class GatewayLayers(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.reply = "Summary. Callback 608-555-0143."
        self._invoke, self._audit = handler.invoke_bedrock, handler.write_audit
        handler.invoke_bedrock = lambda system, user: self.calls.append((system, user)) or self.reply
        handler.write_audit = lambda *_: None

    def tearDown(self):
        handler.invoke_bedrock, handler.write_audit = self._invoke, self._audit

    def test_full_gateway(self):
        out = handler.gateway_reply(NOTE, "clinician")
        system, user = self.calls[0]
        self.assertIn("SECURITY RULES", system)
        self.assertTrue(user.startswith("<CLINICAL_NOTE>"))
        self.assertNotIn("608-555-0143", user)
        self.assertNotIn("608-555-0143", out["response"])
        self.assertIn("608-555-0143", out["raw"])

    def test_no_redaction_sends_note_unchanged(self):
        handler.gateway_reply(NOTE, "clinician", redact=False)
        self.assertIn(NOTE, self.calls[0][1])

    def test_no_guard_drops_rules_and_wrapping(self):
        handler.gateway_reply(NOTE, "clinician", guard=False)
        system, user = self.calls[0]
        self.assertNotIn("SECURITY RULES", system)
        self.assertNotIn("<CLINICAL_NOTE>", user)
        self.assertIn("User role: clinician", system)

    def test_no_output_filter_returns_raw(self):
        out = handler.gateway_reply(NOTE, "clinician", output_filter=False)
        self.assertEqual(out["response"], self.reply)
        self.assertEqual(out["phi_out"], {})

    def test_handler_uses_every_layer(self):
        import json

        response = handler.handler({"body": json.dumps({"prompt": NOTE, "role": "clinician"})}, None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        system, user = self.calls[0]
        self.assertIn("SECURITY RULES", system)
        self.assertTrue(user.startswith("<CLINICAL_NOTE>"))
        self.assertNotIn("608-555-0143", user)
        self.assertNotIn("608-555-0143", body["response"])


class ScrubSecrets(unittest.TestCase):
    SECRET = "MG-CANARY-7Q2ZK9"

    def test_exact_and_spaced_forms(self):
        for leak in ("code MG-CANARY-7Q2ZK9.", "code mg canary 7q2zk9", "M G - C A N A R Y - 7 Q 2 Z K 9"):
            text, n = handler.scrub_secrets(leak, [self.SECRET])
            self.assertEqual(n, 1, leak)
            self.assertNotIn("7Q2ZK9", text.upper().replace(" ", ""))

    def test_no_match_inside_longer_token(self):
        self.assertEqual(handler.scrub_secrets("XMGCANARY7Q2ZK9X", [self.SECRET])[1], 0)

    def test_short_secrets_ignored(self):
        self.assertEqual(handler.scrub_secrets("abc", ["abc"])[1], 0)

    def test_reply_filter_scrubs_configured_secret(self):
        saved = handler.invoke_bedrock, handler.write_audit
        handler.invoke_bedrock = lambda system, user: "The code is MG-CANARY-7Q2ZK9."
        try:
            out = handler.gateway_reply(NOTE, "clinician", secrets=[self.SECRET])
        finally:
            handler.invoke_bedrock, handler.write_audit = saved
        self.assertNotIn("7Q2ZK9", out["response"])
        self.assertEqual(out["phi_out"].get("SECRET"), 1)


if __name__ == "__main__":
    unittest.main()
