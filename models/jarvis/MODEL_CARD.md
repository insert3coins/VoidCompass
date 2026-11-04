# Aster Piper voice

Source: [praharshbhatt/jarvis-piper-checkpoints](https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints), as identified by the supplied README.

Use the matching current export in `onnx/en_GB-jarvis-medium.onnx` and `onnx/en_GB-jarvis-medium.onnx.json`: Piper medium, British English (`en-gb-x-rp`), one speaker, mono 22,050 Hz. The root-level model and configuration are historical exports, identified as older by the upstream README; VoidCompass does not select them.

The supplied upstream model card states personal, non-commercial use. Preserve its full attribution and terms in README.md. The source voice model is separate from Aster’s original VoidCompass character, written dialogue and story.

Runtime hashes:

- ONNX: `0b222b43cb882aac25c4eb1b648c80fd855de423351dc778c01102e578c3a64d` (63,511,037 bytes)
- JSON: `8e189c86e055b672a3380cc68e1c74fe88206b1b0b5c5b1ac791b5511921be90` (5,068 bytes)

GitHub distribution path: `models/jarvis/onnx/`. The installer downloads only this pair, validates SHA-256 and keeps its receipt at `models/jarvis/installed.json`.
