# Nova — Piper voice

**Chosen by the user on 23 November 2026: Cori, British-English female (medium).**

Keep this matching pair together:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `en_GB-cori-medium.onnx` | 63,531,379 | `1899f98e5fb8310154f3c2973f4b8a929ba7245e722b3d3a85680b833d95f10d` |
| `en_GB-cori-medium.onnx.json` | 4,966 | `e262c16d7f192f69d4edd6b4ef8a5915379e67495fcc402f1ab15eeb33da3d36` |

## Source

- [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/en/en_GB/cori/medium), tag `v1.0.0`, revision `375a0fe641dea077c2a47b4e9a056d6da521eed3`.
- Trained by Bryce Beattie on Cori Samuel's LibriVox recordings; the model card gives the dataset licence as **public domain**. The card is kept unchanged in [UPSTREAM_MODEL_CARD.md](UPSTREAM_MODEL_CARD.md); URLs, sizes and hashes are in [SOURCE.json](SOURCE.json).
- The ONNX matches the upstream LFS SHA-256; the config and card match their Git blob hashes.

### Why not the newest Cori

The main branch now carries a 2026 retrain of Cori (Hi-Fi TTS, CC BY 4.0). Its config maps diphthongs such as `aɪ` as single phonemes, which needs Piper 1.5 or later. The app's pinned engine (Piper 2023.11.14-2) refuses to load it, so Nova uses the v1.0.0 build of the same voice.

## Verified sample

[samples/cori.wav](samples/cori.wav): raw output from the app's engine at `length_scale=1.0`, 13.48 seconds of mono 16-bit PCM at 22,050 Hz, synthesised in 0.96 s cold. Script: [samples/script.txt](samples/script.txt).
