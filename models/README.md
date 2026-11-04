# Piper voice models

| Folder | Purpose |
| --- | --- |
| [hal9000](hal9000/README.md) | The Watcher's existing voice. |
| [jarvis](jarvis/MODEL_CARD.md) | Aster's existing voice; the selected pair is under `jarvis/onnx/`. |
| [data](data/README.md) | Commander Data voice archived for future evaluation. |
| [picard](picard/README.md) | Captain Picard voice archived for future evaluation. |

The Data and Picard archives each contain the original `.onnx` model, its matching `.onnx.json`, unchanged upstream README, local source notes and `SOURCE.json` with pinned download URLs, byte lengths and verification hashes. Keep each model with its own matching JSON.

Voice availability and downloads in the app are registered separately in `src/voidcompass/voice/voice_assets.py`; placing a model here preserves it for future work.
