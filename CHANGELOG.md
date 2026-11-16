# Version 1.0.2 (2026-11-05) — RTX 5070 Ti / CUDA Patch

- Diagnose des eingereichten Dumps: NVIDIA-GPU sichtbar via nvidia-smi, aber PyTorch ohne nutzbares CUDA.
- Automatische CUDA-Selbstprüfung bei jedem Start; bei Fehler optionale Reparatur.
- `cuda-repair.bat`: installiert offizielle Torch/Torchaudio CUDA-12.8-Wheels (2.9.1) in bestehende .venv, ohne andere Python-Installationen zu verändern.
- `cuda-diagnostics.bat` und Python-Kerneldiagnose inkl. CUDA-Smoketest.
- Diagnosedump enthält jetzt `cuda.json`, um PyTorch-/CUDA-Probleme genauer zu unterscheiden.
- Daten und Einstellungen bleiben erhalten.

**Tests:** Statische Prüfung und Python-Unit-Tests ohne echte NVIDIA-Hardware; echtes GPU-Modell muss auf dem Zielrechner validiert werden.
