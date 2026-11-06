# Lyra — selected Piper voice

**Selected by the user on 7 November 2026: GLaDOS-style female robot voice.** Stored model assets only; the user will handle app integration.

Keep this matching pair together:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `glados.onnx` | 63,511,038 | `17ea16dd18e1bac343090b8589042b4052f1e5456d42cad8842a4f110de25095` |
| `glados.onnx.json` | 7,097 | `01f5e602e1ec04daec6d54960e4d641b5de305f39186e40bf9b4a47bd757a489` |

## Source

- Downloaded from [rokeya71/VITS-Piper-GlaDOS-en-onnx](https://huggingface.co/rokeya71/VITS-Piper-GlaDOS-en-onnx).
- Pinned revision: `5852e4bfc742fdfc5dafcf94c06305695af37018`.
- The mirror identifies [dnhkng/GLaDOS](https://github.com/dnhkng/GLaDOS) as its upstream project.
- Original filenames and bytes are preserved. Exact URLs, sizes and SHA-256 hashes are recorded in [SOURCE.json](SOURCE.json). The upstream README is preserved unchanged in [UPSTREAM_README.md](UPSTREAM_README.md).
- The mirror labels the model MIT. That metadata does not establish public-domain status for the underlying game recordings or character voice; retain this provenance with the model. Lyra is the app’s original companion identity.

The ONNX was checked against the upstream LFS SHA-256 and size; smaller upstream files were checked against their Git blob hashes. Both model/config SHA-256 hashes were rechecked after moving the selected pair here. The other audition models have been removed from `models/lyra/`.

## Verified sample

[Listen to Lyra’s robot audition](samples/glados.wav). This is raw Piper output with no additional robot effects, using the app’s pinned **Piper 2023.11.14-2 Windows amd64** engine at `length_scale=1.0`.

The model successfully generated 12.299 seconds of mono, 16-bit PCM at 22,050 Hz in a 1.396-second cold synthesis run. This is a single local measurement of the whole audition, not warmed app latency. The script is in [samples/script.txt](samples/script.txt), with results in [samples/GLADOS_RESULT.json](samples/GLADOS_RESULT.json).

App voice registration, GitHub download manifest, receipts, settings, playback and dialogue remain for the user to integrate. No application code was changed for this selection. The model’s supplied JSON is kept unchanged. See [todo-heartbeat.md](../../todo-heartbeat.md) for the pending integration checklist and the existing jaw/eye animation notes.
