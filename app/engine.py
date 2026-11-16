"""Lazy Qwen3 model management. Only one model resides on GPU at a time."""
import gc
import os
import threading
from pathlib import Path

MODELS = {
    "custom-1.7b": ("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "custom"),
    "custom-0.6b": ("Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", "custom"),
    "design-1.7b": ("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "design"),
    "clone-1.7b": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", "clone"),
    "clone-0.6b": ("Qwen/Qwen3-TTS-12Hz-0.6B-Base", "clone"),
}
SPEAKERS = ["Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee"]
LANGUAGES = ["Auto", "German", "English", "French", "Italian", "Spanish", "Portuguese", "Chinese", "Japanese", "Korean", "Russian"]

class Engine:
    def __init__(self):
        self.model = None
        self.loaded_key = None
        self.lock = threading.RLock()
        self.state = "Bereit"
        self.mock = os.getenv("MOCK_TTS", "0") == "1"

    def unload(self):
        with self.lock:
            self.model = None
            self.loaded_key = None
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            self.state = "Bereit"

    def load(self, key):
        if key not in MODELS:
            raise ValueError("Unbekanntes Modell")
        with self.lock:
            if self.loaded_key == key:
                return self.model
            self.unload()
            self.state = "Lade " + key
            if self.mock:
                self.loaded_key = key
                self.state = "Bereit (Testmodus)"
                return None
            import torch
            from qwen_tts import Qwen3TTSModel
            if not torch.cuda.is_available():
                self.state = "Keine CUDA-GPU erkannt"
                raise RuntimeError("CUDA für PyTorch nicht verfügbar. Bitte cuda-repair.bat starten und anschliessend start.bat erneut ausführen.")
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            try:
                model = Qwen3TTSModel.from_pretrained(
                    MODELS[key][0], device_map="cuda:0", dtype=dtype,
                    attn_implementation="sdpa")
            except Exception:
                self.state = "Modell konnte nicht geladen werden"
                raise
            self.model = model
            self.loaded_key = key
            self.state = "Bereit"
            return model

    def generate(self, params, reference, output):
        key = params["model"]
        kind = MODELS[key][1]
        with self.lock:
            model = self.load(key)
            self.state = "Generiere Audio"
            try:
                if self.mock:
                    import numpy as np
                    import soundfile as sf
                    sr = 24000
                    t = np.arange(sr // 2) / sr
                    sf.write(str(output), (0.08 * np.sin(t * 440 * 2 * np.pi)), sr)
                    return sr
                if kind == "custom":
                    kwargs = dict(text=params["text"], language=params["language"], speaker=params["speaker"])
                    if params.get("instruct"):
                        kwargs["instruct"] = params["instruct"]
                    wavs, sr = model.generate_custom_voice(**kwargs)
                elif kind == "design":
                    wavs, sr = model.generate_voice_design(
                        text=params["text"], language=params["language"], instruct=params["instruct"])
                else:
                    if not reference:
                        raise ValueError("Referenzaufnahme fehlt")
                    wavs, sr = model.generate_voice_clone(
                        text=params["text"], language=params["language"],
                        ref_audio=str(reference["path"]),
                        ref_text=reference["transcript"])
                import soundfile as sf
                sf.write(str(output), wavs[0], sr)
                return sr
            finally:
                self.state = "Bereit"
