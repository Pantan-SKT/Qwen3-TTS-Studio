"""Qwen3-TTS Studio local web application."""
import io
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import traceback
import uuid
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / 'config.env').read_text(encoding='utf-8').splitlines() if (ROOT / 'config.env').exists() else []:
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        if key.strip() in ('HOST','PORT','API_TOKEN','HF_HOME','MOCK_TTS'):
            os.environ.setdefault(key.strip(), value.strip())
if os.getenv('HF_HOME'):
    os.environ['HF_HOME'] = os.environ['HF_HOME'].strip()

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import Engine, MODELS, SPEAKERS, LANGUAGES

DATA = ROOT / 'data'
AUDIO = DATA / 'audio'
REFS = DATA / 'references'
for folder in (AUDIO, REFS):
    folder.mkdir(parents=True, exist_ok=True)
VOICES_FILE = DATA / 'voices.json'
HISTORY_FILE = DATA / 'history.json'
LOG_FILE = DATA / 'studio.log'
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()])
log = logging.getLogger('qwenstudio')

app = FastAPI(title='Qwen3-TTS Studio', version='1.0.2', docs_url='/api/docs')
engine = Engine()
state_lock = threading.RLock()
jobs = {}
queue_lock = threading.Lock()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_json(path, obj):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def auth_check(request):
    token = os.getenv('API_TOKEN', '').strip()
    if token and not secrets.compare_digest(request.headers.get('X-API-Key', ''), token):
        raise HTTPException(401, 'API-Token erforderlich (X-API-Key)')

@app.middleware('http')
async def middleware(request: Request, call_next):
    if request.url.path.startswith('/api/'):
        try:
            auth_check(request)
        except HTTPException as exc:
            return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
    return await call_next(request)

@app.get('/')
def home():
    return FileResponse(ROOT / 'app' / 'static' / 'index.html')

app.mount('/static', StaticFiles(directory=ROOT / 'app' / 'static'), name='static')

@app.get('/api/config')
def config():
    return {'models': {key: {'kind': kind, 'hf': name} for key, (name, kind) in MODELS.items()},
            'speakers': SPEAKERS, 'languages': LANGUAGES, 'version': app.version,
            'auth_required': bool(os.getenv('API_TOKEN', '').strip()), 'mock': engine.mock}

@app.get('/api/status')
def status():
    info = {'model': engine.loaded_key, 'state': engine.state, 'gpu': None, 'mock': engine.mock}
    try:
        output = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
                                 '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3)
        if output.returncode == 0:
            fields = [v.strip() for v in output.stdout.splitlines()[0].split(',')]
            info['gpu'] = dict(name=fields[0], total_mb=int(fields[1]), used_mb=int(fields[2]), utilization=int(fields[3]))
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        pass
    return info

class Voice(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str
    speaker: str = ''
    instruct: str = Field(default='', max_length=1200)
    reference_id: str = ''
    language: str = 'German'

@app.get('/api/voices')
def voices():
    return read_json(VOICES_FILE)

@app.post('/api/voices')
def add_voice(voice: Voice):
    if voice.kind not in ('custom', 'design', 'clone'):
        raise HTTPException(400, 'Ungültiger Stimmtyp')
    if voice.kind == 'custom' and voice.speaker not in SPEAKERS:
        raise HTTPException(400, 'Ungültige Standardstimme')
    if voice.kind == 'clone' and not (REFS / (voice.reference_id + '.wav')).is_file():
        raise HTTPException(400, 'Referenzaufnahme nicht vorhanden')
    with state_lock:
        items = read_json(VOICES_FILE)
        record = {'id': uuid.uuid4().hex, 'created': utcnow(), **voice.model_dump()}
        items.insert(0, record)
        write_json(VOICES_FILE, items)
    return record

@app.delete('/api/voices/{voice_id}')
def remove_voice(voice_id: str):
    with state_lock:
        items = read_json(VOICES_FILE)
        updated = [v for v in items if v['id'] != voice_id]
        if len(items) == len(updated):
            raise HTTPException(404, 'Nicht gefunden')
        write_json(VOICES_FILE, updated)
    return {'ok': True}

@app.post('/api/references')
async def upload_reference(file: UploadFile = File(...), transcript: str = Form(...)):
    if not transcript.strip() or len(transcript) > 2000:
        raise HTTPException(400, 'Exakten Referenztext eingeben (max. 2000 Zeichen)')
    data = await file.read(12 * 1024 * 1024 + 1)
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(413, 'Referenzaufnahme zu gross (max. 12 MB)')
    # WAV only avoids hidden ffmpeg dependency and unsafe video/containers.
    try:
        import soundfile as sf
        with sf.SoundFile(io.BytesIO(data)) as src:
            if src.format != 'WAV' or src.channels not in (1, 2) or src.frames / src.samplerate > 90:
                raise ValueError('WAV PCM, Mono/Stereo, höchstens 90 Sekunden erforderlich')
            if src.frames / src.samplerate < 1:
                raise ValueError('Aufnahme ist zu kurz')
            audio = src.read(dtype='float32')
            sr = src.samplerate
    except Exception as e:
        raise HTTPException(400, f'Ungültiges WAV: {e}')
    rid = uuid.uuid4().hex
    import soundfile as sf
    sf.write(str(REFS / (rid + '.wav')), audio, sr, subtype='PCM_16')
    (REFS / (rid + '.json')).write_text(json.dumps({'transcript': transcript.strip(), 'created': utcnow(),
            'original_name': Path(file.filename or 'aufnahme.wav').name}, ensure_ascii=False), encoding='utf-8')
    return {'id': rid, 'filename': (file.filename or 'aufnahme.wav'), 'duration': round(len(audio)/sr, 2)}

@app.get('/api/references')
def list_references():
    result = []
    for path in sorted(REFS.glob('*.json'), reverse=True):
        try:
            result.append({'id': path.stem, **json.loads(path.read_text(encoding='utf-8'))})
        except (ValueError, OSError):
            continue
    return result

@app.delete('/api/references/{rid}')
def delete_reference(rid: str):
    if not re.fullmatch('[0-9a-f]{32}', rid):
        raise HTTPException(400, 'Ungültige ID')
    for path in (REFS / (rid + '.wav'), REFS / (rid + '.json')):
        path.unlink(missing_ok=True)
    return {'ok': True}

class Generation(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    model: str = 'custom-1.7b'
    language: str = 'German'
    speaker: str = 'Ryan'
    instruct: str = Field(default='', max_length=1200)
    reference_id: str = ''


def worker(job_id, params):
    with queue_lock:
        with state_lock:
            jobs[job_id]['state'] = 'running'
            jobs[job_id]['stage'] = 'Modell laden und Audio generieren'
        output = AUDIO / (job_id + '.wav')
        try:
            ref = None
            if params['reference_id']:
                rid = params['reference_id']
                path = REFS / (rid + '.wav')
                metadata = REFS / (rid + '.json')
                if not path.is_file() or not metadata.is_file():
                    raise ValueError('Referenz wurde gelöscht')
                ref = {'path': path, 'transcript': json.loads(metadata.read_text(encoding='utf-8'))['transcript']}
            sr = engine.generate(params, ref, output)
            with state_lock:
                item = {'id': job_id, 'created': utcnow(), 'model': params['model'],
                        'text': params['text'], 'language': params['language'], 'speaker': params['speaker'],
                        'duration_sec': None, 'sample_rate': sr}
                with wave.open(str(output), 'rb') as w:
                    item['duration_sec'] = round(w.getnframes() / w.getframerate(), 2)
                history = read_json(HISTORY_FILE)
                history.insert(0, item)
                write_json(HISTORY_FILE, history[:300])
                jobs[job_id].update(state='done', stage='Fertig', result=item)
            log.info('Completed job %s', job_id)
        except Exception as e:
            output.unlink(missing_ok=True)
            log.exception('Job failed %s', job_id)
            with state_lock:
                jobs[job_id].update(state='error', stage='Fehler', error=f'{type(e).__name__}: {e}')

@app.post('/api/generate')
def generate(req: Generation):
    if req.model not in MODELS or req.language not in LANGUAGES:
        raise HTTPException(400, 'Modell oder Sprache ungültig')
    kind = MODELS[req.model][1]
    if kind == 'custom' and req.speaker not in SPEAKERS:
        raise HTTPException(400, 'Unbekannte Stimme')
    if kind == 'design' and not req.instruct.strip():
        raise HTTPException(400, 'VoiceDesign benötigt eine Stimmbeschreibung')
    if kind == 'clone' and not re.fullmatch('[0-9a-f]{32}', req.reference_id):
        raise HTTPException(400, 'VoiceClone benötigt eine Referenzaufnahme')
    job_id = uuid.uuid4().hex
    with state_lock:
        jobs[job_id] = {'id': job_id, 'state': 'queued', 'stage': 'In Warteschlange', 'created': utcnow()}
        if len(jobs) > 250:
            for key in list(jobs)[:-200]:
                if jobs[key]['state'] in ('done', 'error'):
                    jobs.pop(key, None)
    threading.Thread(target=worker, args=(job_id, req.model_dump()), daemon=True).start()
    return jobs[job_id]

@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    with state_lock:
        if job_id not in jobs:
            raise HTTPException(404, 'Auftrag nicht gefunden (Serverneustart?)')
        return jobs[job_id]

@app.get('/api/history')
def history():
    return read_json(HISTORY_FILE)

@app.get('/api/audio/{audio_id}')
def audio_file(audio_id: str):
    if not re.fullmatch('[0-9a-f]{32}', audio_id):
        raise HTTPException(400, 'Ungültige ID')
    path = AUDIO / (audio_id + '.wav')
    if not path.is_file():
        raise HTTPException(404, 'Audio nicht vorhanden')
    return FileResponse(path, media_type='audio/wav', filename=audio_id + '.wav')

@app.delete('/api/history/{audio_id}')
def remove_history(audio_id: str):
    if not re.fullmatch('[0-9a-f]{32}', audio_id):
        raise HTTPException(400, 'Ungültige ID')
    with state_lock:
        items = read_json(HISTORY_FILE)
        new = [i for i in items if i.get('id') != audio_id]
        if len(items) == len(new):
            raise HTTPException(404, 'Nicht gefunden')
        write_json(HISTORY_FILE, new)
        (AUDIO / (audio_id + '.wav')).unlink(missing_ok=True)
    return {'ok': True}

@app.post('/api/unload')
def unload():
    if not queue_lock.acquire(blocking=False):
        raise HTTPException(409, 'Generierung läuft')
    try:
        engine.unload()
    finally:
        queue_lock.release()
    return {'ok': True}

@app.get('/api/diagnostics')
def diagnostics():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('status.json', json.dumps(status(), indent=2, ensure_ascii=False))
        z.writestr('jobs.json', json.dumps([{k: v for k, v in job.items() if k != 'result'} for job in list(jobs.values())[-30:]], indent=2, ensure_ascii=False))
        z.writestr('environment.txt', 'python=' + __import__('sys').version + '\nplatform=' + __import__('platform').platform() + '\n')
        from .cuda_check import get_diagnostics
        z.writestr('cuda.json', json.dumps(get_diagnostics(), indent=2, ensure_ascii=False))
        # Exclude user speech text and audio as well as tokens from diagnostics.
        if LOG_FILE.exists():
            z.writestr('studio.log', LOG_FILE.read_text(encoding='utf-8', errors='replace')[-40000:])
    stream.seek(0)
    return StreamingResponse(stream, media_type='application/zip',
        headers={'Content-Disposition': 'attachment; filename="qwen3-tts-dump.zip"'})

if __name__ == '__main__':
    import uvicorn
    host = os.getenv('HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost', '::1') and not os.getenv('API_TOKEN', '').strip():
        raise SystemExit('LAN access blocked: set API_TOKEN in config.env first.')
    uvicorn.run(app, host=host, port=int(os.getenv('PORT', '7865')))
