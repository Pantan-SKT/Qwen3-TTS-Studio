"""Execute with: python -m unittest discover -s tests -v (MOCK mode; no GPU)."""
import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['MOCK_TTS'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from app import main

class Smoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
    def test_web(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertIn('Text zu Sprache', self.client.get('/').text)
        self.assertEqual(self.client.get('/api/config').status_code, 200)
        self.assertEqual(self.client.get('/api/status').status_code, 200)
    def test_generation_and_history(self):
        body={'text':'Test Test', 'model':'custom-0.6b', 'language':'German', 'speaker':'Ryan'}
        r=self.client.post('/api/generate',json=body)
        self.assertEqual(r.status_code,200, r.text)
        job=r.json()['id']
        for _ in range(60):
            r=self.client.get('/api/jobs/'+job)
            if r.json()['state'] in ('done','error'): break
            time.sleep(.1)
        self.assertEqual(r.json()['state'],'done',r.text)
        self.assertTrue(self.client.get('/api/audio/'+job).content[:4] == b'RIFF')
        self.assertEqual(self.client.delete('/api/history/'+job).status_code,200)
        self.assertEqual(self.client.get('/api/audio/'+job).status_code,404)
    def test_models_validate(self):
        self.assertEqual(self.client.post('/api/generate',json={'text':'ok','model':'bad'}).status_code,400)
        self.assertEqual(self.client.post('/api/generate',json={'text':'ok','model':'clone-1.7b'}).status_code,400)
    def test_voice_library(self):
        r=self.client.post('/api/voices',json={'name':'Test','kind':'custom','speaker':'Ryan'})
        self.assertEqual(r.status_code,200,r.text)
        vid=r.json()['id']
        self.assertEqual(self.client.delete('/api/voices/'+vid).status_code,200)
    def test_diagnostics(self):
        r=self.client.get('/api/diagnostics')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.content[:2],b'PK')

if __name__=='__main__': unittest.main()
