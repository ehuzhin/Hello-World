#!/usr/bin/env python3
"""Offline checks. Never calls n8n or any AI provider."""
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import manage as m

def config():
    c = m.read_json(m.ROOT / "assets/config.example.json")
    c.update(task_id="12345678-1234-4234-8234-123456789abc", openai_model="example-openai-model", anthropic_model="example-claude-model")
    c["credential_ids"] = {k: "test-" + k for k in m.CREDENTIALS}
    return c

class FakeAPI:
    base = "https://example.app.n8n.cloud"
    def __init__(self, remote=None, pages=None):
        self.remote, self.calls = remote, []
        self.pages = pages or [{"data": []}]
    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.startswith("/workflows?"):
            return self.pages.pop(0)
        if method == "GET":
            return copy.deepcopy(self.remote)
        if method == "POST" and path == "/workflows":
            self.remote = dict(body, id="new-id", active=False)
            return self.remote
        if method == "PUT":
            self.remote = dict(body, id="new-id", active=False)
            return self.remote
        raise AssertionError("Unexpected API call")

class Checks(unittest.TestCase):
    def test_deterministic_graph_and_credential_types(self):
        w = m.build(config())
        self.assertEqual(w, m.build(config()))
        self.assertEqual(len(w["nodes"]), 12)
        refs = {k for n in w["nodes"] for k in n.get("credentials", {})}
        self.assertEqual(refs, {"openAiApi", "anthropicApi", "httpHeaderAuth", "dropboxOAuth2Api"})
    def test_placeholders_and_secret_config_rejected(self):
        with self.assertRaises(m.SetupError):
            m.build(m.read_json(m.ROOT / "assets/config.example.json"))
        c = config(); c["api_key"] = "dummy-secret"
        with self.assertRaises(m.SetupError): m.build(c)
    def test_bad_task_ids_and_paths(self):
        for value in ("../tasks", "0" * 32, "00000000-0000-0000-0000-000000000000"):
            c = config(); c["task_id"] = value
            with self.assertRaises(m.SetupError): m.build(c)
        for value in ("relative", "/", "/folder/", "/folder/../other", "/folder\n"):
            c = config(); c["dropbox_folder"] = value
            with self.assertRaises(m.SetupError): m.build(c)
    def test_webhook_auth_is_explicit(self):
        w = m.build(config(), webhook=True)
        trigger = w["nodes"][0]
        self.assertEqual(trigger["parameters"]["authentication"], "headerAuth")
        self.assertEqual(trigger["credentials"]["httpHeaderAuth"]["id"], "test-webhook")
    def test_binary_path_survives_conversion(self):
        w = m.build(config())
        nodes = {n["name"]: n for n in w["nodes"]}
        self.assertIn("$('Report')", nodes["Dropbox Upload"]["parameters"]["path"])
        self.assertEqual(nodes["Text File"]["parameters"]["binaryPropertyName"], "data")
    def test_idempotent_deploy(self):
        api, state = FakeAPI(), {}
        self.assertTrue(m.deploy(api, config(), state)["changed"])
        self.assertFalse(m.deploy(api, config(), state)["changed"])
        self.assertEqual(sum(v[0] == "POST" for v in api.calls), 1)
    def test_paginated_resolution_and_ambiguity(self):
        w = dict(m.build(config()), id="existing", active=False)
        api = FakeAPI(w, [{"data": [], "nextCursor": "next"}, {"data": [{"id": "existing", "name": m.NAME}]}])
        self.assertFalse(m.deploy(api, config(), {})["changed"])
        self.assertIn("cursor=next", api.calls[1][1])
        api = FakeAPI(pages=[{"data": [{"id": "1", "name": m.NAME}, {"id": "2", "name": m.NAME}]}])
        with self.assertRaises(m.SetupError): m.deploy(api, config(), {})
    def test_active_workflow_update_refused(self):
        w = dict(m.build(config()), active=True); w["nodes"] = []
        api = FakeAPI(w)
        with self.assertRaises(m.SetupError): m.deploy(api, config(), {"workflow_id": "x"})
        self.assertFalse(any(v[0] == "PUT" for v in api.calls))
    def test_missing_credentials_stop_before_requests(self):
        c = config(); c["credential_ids"]["dropbox"] = ""
        api = FakeAPI()
        with self.assertRaises(m.SetupError): m.deploy(api, c, {})
        self.assertFalse(api.calls)
    def test_private_state_and_instance_binding(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            m.private_json(p, {"base_url": "https://other.example"})
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(m.SetupError): m.state_for(p, FakeAPI())
    def test_https_and_separate_webhook_auth(self):
        with self.assertRaises(m.SetupError): m.API("http://example.com", "dummy")
        api = m.API("https://example.com", "", require_key=False)
        self.assertEqual(api.base, "https://example.com")
        self.assertIsNone(m.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))
    def test_credentials_reuse_and_partial_save(self):
        class CredAPI:
            def __init__(self): self.calls = []
            def request(self, method, path, body=None):
                self.calls.append((method, path, body))
                if method == "POST": return {"id": "created"}
                return {}
        api, state, saved = CredAPI(), {}, []
        with patch.dict(os.environ, {"ALPECON_OPENAI_API_KEY": "dummy-openai"}, clear=True):
            m.connect_keys(api, state, lambda s: saved.append(copy.deepcopy(s)))
            m.connect_keys(api, state, lambda s: saved.append(copy.deepcopy(s)))
        self.assertEqual(sum(v[0] == "POST" for v in api.calls), 1)
        self.assertEqual(len(saved), 1)
        self.assertNotIn("dummy-openai", json.dumps(state))
    def test_code_nodes_execute_with_mock_inputs(self):
        nodes = {n["name"]: n for n in m.build(config())["nodes"]}
        src = "const run = (code, input, prior={}, execution={id:'42'}) => new Function('$input','$','$execution',code)({first:()=>({json:input})},name=>({first:()=>({json:prior[name]})}),execution);\n"
        src += "const codes = " + json.dumps({k: n["parameters"]["jsCode"] for k, n in nodes.items() if n["type"] == "n8n-nodes-base.code"}) + ";\n"
        src += "const cfg=run(codes.Configuration, {})[0].json;\n"
        src += "const task=run(codes['Validate Task'], {id:cfg.task_id,title:'Test',description:'Harmless'}, {Configuration:cfg})[0].json;\n"
        src += "const plan=run(codes['Validate Plan'],{text:'Draft'})[0].json;\n"
        src += "const report=run(codes.Report,{text:'Checked'},{Configuration:cfg,'Validate Task':task})[0].json;\n"
        src += "if(report.path !== '/ALPECON_AI_TEST/ALPECON_plan_42.txt' || !report.text.includes('Checked')) throw Error('bad report');\n"
        src += "for(const name of ['Validate Plan','Report']) {let failed=false;try{run(codes[name],{text:''})}catch(e){failed=true}if(!failed)throw Error('empty output accepted');}\n"
        webhook_code = m.build(config(), webhook=True)["nodes"][1]["parameters"]["jsCode"]
        src += "const webhookCode = " + json.dumps(webhook_code) + ";\n"
        src += "for(const value of [{},{body:{}},{body:{task_id:null}},{body:{task_id:'../tasks'}}]) {let failed=false;try{run(webhookCode,value)}catch(e){failed=true}if(!failed)throw Error('bad webhook input accepted');}\n"
        result = subprocess.run([os.environ.get("CODEX_PRIMARY_RUNTIME_NODE", "node"), "-e", src], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == "__main__":
    unittest.main(verbosity=2)
