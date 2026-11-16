# Qwen3-TTS Studio 1.0.2

Lokale, browserbasierte Sprachgenerierung mit den offiziellen Qwen3-TTS-Modellen.

## Start auf Windows 11

1. NVIDIA-Grafiktreiber installieren bzw. aktualisieren. `nvidia-smi` in PowerShell prüfen.
2. `start.bat` prueft automatisch Python 3.12 (64-bit). Fehlt es, bietet das Skript die Installation mit Windows `winget` an (nur nach Zustimmung). Alternativ Python 3.12 von python.org installieren.
3. ZIP entpacken und `start.bat` doppelklicken. Beim ersten Start wird `.venv` angelegt und `requirements.txt` installiert. Dies kann erheblich dauern und mehrere GB beanspruchen.
4. Browser: `http://127.0.0.1:7865`.
5. Im Studio eine Funktion auswählen und `Audio generieren` drücken. Das ausgewählte Qwen-Modell wird erst dann aus Hugging Face heruntergeladen. Eine Internetverbindung ist dafür erforderlich.

**CUDA-Fix für RTX 5070 Ti:** Die App prüft beim Start, ob PyTorch die GPU wirklich mit CUDA nutzen kann. Wenn nicht, wird die Installation der CUDA-12.8-Variante von PyTorch 2.9.1 angeboten. Dies ist ein grosser Download. Alternativ `cuda-repair.bat` doppelklicken. `cuda-diagnostics.bat` zeigt den Zustand. Die vorhandene `.venv`, `config.env` und der Ordner `data` bleiben erhalten. Zum Aktualisieren ZIP **über** den bestehenden App-Ordner entpacken, ohne dessen Nutzerdaten zu löschen. Beim ersten Sprachversuch wird das ausgewählte Modell heruntergeladen.

**Wichtig:** Installation und echte GPU-Sprachgenerierung wurden nicht auf der Ziel-Workstation getestet. Für NVIDIA-Beschleunigung ist eine passende CUDA-fähige PyTorch-Installation erforderlich. Wenn `torch.cuda.is_available()` false ist, bitte NVIDIA-Treiber und PyTorch-CUDA-Wheel anhand der offiziellen PyTorch-Anleitung installieren. Auf Windows wird bewusst `sdpa` statt FlashAttention 2 verwendet.

## Funktionen

- CustomVoice 1.7B / 0.6B; VoiceDesign 1.7B; VoiceClone (Base) 1.7B / 0.6B.
- Bibliothek für Stimmprofile, lokale WAV-Referenzen, Audio-Verlauf, WAV-Download.
- GPU-Anzeige, Modellwechsel mit automatischem Entladen, manueller Unload, ZIP-Diagnose.
- REST-API und OpenAPI unter `/api/docs`; Jobs asynchron, eine GPU-Generierung gleichzeitig.
- Alle Daten unter `data/`, getrennt von Programmdateien. Backup durch Kopieren dieses Ordners im ausgeschalteten Zustand.

## Referenzaufnahmen

VoiceClone erwartet eine WAV-Datei mit 1 bis 90 Sekunden Länge und einen wortgetreuen Transkripttext. Benutze nur Stimmen mit Einwilligung/entsprechender Berechtigung. Andere Formate vorab in WAV konvertieren. Aufnahmen und Audios werden lokal gespeichert und können einzeln gelöscht werden.

## LAN-Betrieb (optional)

In `config.env` einstellen:

```
HOST=0.0.0.0
PORT=7865
API_TOKEN=EIN_LANGER_ZUFAELLIGER_GEHEIMER_TOKEN
```

Danach `start.bat` neu starten. Zugriff über `http://WORKSTATION-IP:7865` und API-Key im Dialog angeben. Für Produktionsbetrieb **HTTPS-Reverse-Proxy, Firewall/Freigaben und Benutzerzugriff** konfigurieren; der einzelne gemeinsame Token ist keine vollständige Benutzer- oder Rollenverwaltung. Port 7865 muss für gewünschte Clients erreichbar sein. Browser-Token wird für die Dauer des Tabs in sessionStorage gehalten.

## API-Beispiel

```
POST /api/generate
Content-Type: application/json
X-API-Key: <nur falls eingerichtet>

{"text":"Guten Tag","model":"custom-1.7b","language":"German","speaker":"Ryan","instruct":"Warm und freundlich"}
```

Response enthält `id`; danach `GET /api/jobs/{id}` wiederholt abfragen. Bei `state=done` Audio über `GET /api/audio/{id}` laden. FastAPI-Dokumentation unter `/api/docs`.

## Diagnose

Der Dump-Button erzeugt eine ZIP mit Serverstatus und Logs. Die Logs enthalten keine generierten Audios oder ganze Texte, können aber Fehler-/Dateipfadinformationen enthalten. **Bitte vor Weitergabe kurz prüfen.**

## Grenzen v1.0

- Keine Echtzeit-/Chunk-Streaming-Schnittstelle; zuerst wird die vollständige WAV-Datei generiert. EVOKI-Echtzeitintegration ist ein Folgeschritt.
- Deutsch offiziell unterstützt; Schweizerdeutsch ist nicht separat ausgewiesen und muss qualitativ getestet werden.
- Kein Einsatz auf extern erreichbarem Internet ohne zusätzliche Authentifizierung, TLS und Absicherung.
- Keine automatische Modellvorabinstallation; Download bei Bedarf, mit entsprechender Wartezeit.
- Für den Wechsel oder das Entladen wird die laufende Generierung abgewartet.
