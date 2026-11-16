# Implementierungsplan – Qwen3-TTS Studio v1.0

## Ziel
Lokale Standalone-Webanwendung für Qwen3-TTS mit REST-Schnittstelle für spätere EVOKI-/Company-Tools-Anbindung.

## Architektur
Browser (HTML/CSS/JS) → FastAPI → asynchroner Job-Worker (seriell) → Qwen3TTSModel → WAV/Archiv.
Modelle werden lazy geladen und beim Wechsel entladen. Ein einziges GPU-Modell zurzeit. Daten in `data/`.

## Umgesetzte Module
1. Start/Setup (`start.bat`, `update.bat`, Python-venv, Konfiguration)
2. CustomVoice, VoiceDesign, Base/Clone über offizielle `qwen-tts` API
3. Stimmprofile und Transkript-WAV-Referenzen
4. Generierungsjobs, Status, Verlauf, Abspielen, Download, Löschen
5. GPU-Monitor, Model-Unload, Dump/Logs, API-Dokumentation
6. LAN-Bind nur mit API-Token; Standardzugriff 127.0.0.1

## Abnahme / bekannte offene Prüfungen
- API-Smoke-Test mit synthetischem MOCK_TTS-Modell; ohne NVIDIA-Hardware keine reale Audio-Inferenz getestet.
- Zielgerät: NVIDIA-Treiber, CUDA-PyTorch, 1.7B-Speicherverbrauch und Sprechqualität überprüfen.
- Nach erfolgreichem Praxistest: optionale Echtzeitstreaming-API, SSO/Rollen, fortgeschrittene Warteschlange.
