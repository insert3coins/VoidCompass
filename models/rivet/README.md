# Rivet — Piper voice

**Chosen by the user on 26 November 2026: Northern English Male, British-English male (medium).**

Keep this matching pair together:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `en_GB-northern_english_male-medium.onnx` | 63,201,294 | `57a219ae8e638873db7d18893304be5069c42868f392bb95c3ff17f0690d0689` |
| `en_GB-northern_english_male-medium.onnx.json` | 4,847 | `69557ed3d974463453e9b0c09dd99a7ed0e52b8b87b64b357dbeeb2540a97d47` |

## Source

- [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/en/en_GB/northern_english_male/medium), tag `v1.0.0`, revision `375a0fe641dea077c2a47b4e9a056d6da521eed3`.
- Trained on OpenSLR 83 (UK and Ireland English dialect speech, Google), **CC BY-SA 4.0**: credited as such, and any changed model must carry the same licence. The card is kept unchanged in [UPSTREAM_MODEL_CARD.md](UPSTREAM_MODEL_CARD.md); URLs, sizes and hashes are in [SOURCE.json](SOURCE.json).
- Fine-tuned (upstream) from the U.S. English lessac voice, as most Piper medium voices are.
- The v1.0.0 build loads in the app's pinned engine (Piper 2023.11.14-2); newer builds need Piper 1.5.

## Verified sample

[samples/northern_english_male.wav](samples/northern_english_male.wav): raw output from the app's engine at `length_scale=1.0`, 16.01 seconds of mono 16-bit PCM at 22,050 Hz, synthesised in 1.46 s. Script: [samples/script.txt](samples/script.txt).
