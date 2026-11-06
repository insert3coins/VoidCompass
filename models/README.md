# Piper voice models

| Folder | Purpose |
| --- | --- |
| [hal9000](hal9000/README.md) | The Watcher's existing voice. |
| [jarvis](jarvis/MODEL_CARD.md) | Aster's existing voice; the selected pair is under `jarvis/onnx/`. |
| [data](data/README.md) | Axiom’s Piper pair, with Commander Data source attribution. |
| [picard](picard/README.md) | Meridian’s Piper pair, with Captain Picard source attribution. |
| [lyra](lyra/README.md) | Selected GLaDOS-style female robot Piper pair; verified source files and sample. App integration will be handled by the user. |

The Data and Picard archives each contain the original `.onnx` model, its matching `.onnx.json`, unchanged upstream README, local source notes and `SOURCE.json` with pinned download URLs, byte lengths and verification hashes. Keep each model with its own matching JSON.

Voice availability and downloads in the app are registered separately in `src/voidcompass/voice/voice_assets.py`; placing a model here preserves it for future work.
