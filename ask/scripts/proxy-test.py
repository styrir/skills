#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('proxy',Path(__file__).with_name('proxy-stream.py'))
proxy=importlib.util.module_from_spec(spec); spec.loader.exec_module(proxy)


class Response:
    headers={}
    def __init__(self, body): self.body=body
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return self.body
    def __iter__(self): return iter(self.body.splitlines(keepends=True))


class ProxyTests(unittest.TestCase):
    def run_case(self, stream, model='claude-opus-5-5', inventory=None):
        with tempfile.TemporaryDirectory() as d:
            config=Path(d)/'config.toml'; prompt=Path(d)/'prompt.md'
            config.write_text('[model.claude-opus-5-5]\nmodel="claude-opus-5-5"\nbase_url="http://127.0.0.1:8318/v1"\napi_key="sk-dummytestkey"\n')
            prompt.write_text('synthetic request')
            calls=[]
            def urlopen(req,timeout):
                calls.append(req)
                if req.full_url.endswith('/models'):
                    return Response(json.dumps({'data': [{'id': x} for x in (inventory if inventory is not None else ['claude-opus-5-5'])]}).encode())
                return Response(stream.encode())
            output=io.StringIO()
            with patch.object(proxy.urllib.request,'urlopen',urlopen),patch('sys.argv',['proxy','--model',model,'--prompt',str(prompt),'--config',str(config)]),contextlib.redirect_stdout(output):
                code=proxy.main()
            self.assertNotIn('sk-dummytestkey',output.getvalue())
            return code,output.getvalue(),calls

    def test_streaming_request_and_complete_finish(self):
        code,output,calls=self.run_case('data: {"model":"claude-opus-5-5","choices":[{"delta":{"content":"ok"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
        self.assertEqual(code,0)
        self.assertIn('EndTurn',output)
        self.assertTrue(json.loads(calls[-1].data)['stream'])

    def test_length_preserves_text_but_fails(self):
        code,output,_=self.run_case('data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n')
        self.assertEqual(code,2); self.assertIn('partial',output); self.assertNotIn('"type": "end"',output)

    def test_missing_finish_fails(self):
        code,output,_=self.run_case('data: {"choices":[{"delta":{"content":"partial"}}]}\ndata: [DONE]\n')
        self.assertEqual(code,2)

    def test_model_substitution_fails(self):
        code,output,_=self.run_case('data: {"model":"other-model","choices":[]}\n')
        self.assertEqual(code,2)

    def test_unknown_model_before_request(self):
        with self.assertRaisesRegex(ValueError,'not configured'):
            self.run_case('',model='unknown')

    def test_unlisted_model_before_consultation(self):
        with self.assertRaisesRegex(ValueError,'absent'):
            self.run_case('',inventory=[])

    def test_nonloopback_denied(self):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write('[model.test]\nbase_url="https://example.com"\napi_key="sk-dummy"\n');f.flush()
            with self.assertRaisesRegex(ValueError,'loopback'): proxy.route('test',f.name)

    def test_redirects_cannot_export_proxy_auth(self):
        with self.assertRaisesRegex(ValueError,'redirects'):
            proxy.NoRedirect().redirect_request(None,None,307,'redirect',{},'https://example.com')


if __name__=='__main__': unittest.main()
