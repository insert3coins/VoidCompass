---
pretty_name: JARVIS Piper Voice (Medium, en-GB)
license: other
license_name: personal-noncommercial
language:
  - en
task_categories:
  - text-to-speech
tags:
  - piper
  - vits
  - tts
  - onnx
  - knowledge-distillation
  - f5-tts
  - en-GB
  - cpu-inference
  - voice
---

# JARVIS Piper Voice (medium, en-GB)

A small, fast British-English text-to-speech voice in the style of the JARVIS assistant.
It is a [Piper](https://github.com/rhasspy/piper) (VITS) model that runs **faster than real time on a CPU**.
It was **distilled from a larger F5-TTS model**, so it keeps most of the quality at a fraction of the compute.

| | |
|---|---|
| Architecture | Piper / VITS, `medium` quality (about 22 M parameters, 63 MB ONNX) |
| Language / phonemes | English (UK), eSpeak `en-gb-x-rp` |
| Sample rate | 22,050 Hz, mono |
| Start point | `en_GB-alan-medium` Piper checkpoint |
| Training data | 16,179 synthetic clips, 20.6 hours (see below) |
| Speed (CPU, 1 thread) | real-time factor **0.087**, first audio in 85 ms |

> **Use is limited to personal, non-commercial purposes.** Read [License and responsible use](#license-and-responsible-use) before you use or share the audio.

## Listen

Both columns say the same line. The teacher is the large F5-TTS model that the Piper voice learned from.
The lines were never used in training.

| Line | Piper student (this model) | Teacher (F5-TTS) |
|---|---|---|
| At your service, sir. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000000.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000000.mp3"></audio> |
| As always, sir, a great pleasure watching you work. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000001.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000001.mp3"></audio> |
| Good evening, Mr. Stark. Welcome home. Shall I prepare the workshop for you? | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000002.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000002.mp3"></audio> |
| I'm afraid the suit has sustained significant damage. I would strongly advise against flying in these conditions, sir. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000003.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000003.mp3"></audio> |
| Sir, the vehicle is approaching the upper limit of its altitude capacity. Without further modification, the suit will begin to ice over. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000005.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000005.mp3"></audio> |
| Welcome home, sir. I have taken the liberty of compiling a list of everything that went wrong today. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000006.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000006.mp3"></audio> |
| I do not believe that is the best use of our remaining power, sir. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000007.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000007.mp3"></audio> |
| The sample rate of the audio signal is higher than the processing system can handle at this time. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000008.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000008.mp3"></audio> |
| Would you care for some tea, or should I simply call an ambulance? | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000009.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000009.mp3"></audio> |
| Pardon me for asking, sir, but where exactly do you intend to go? | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000010.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000010.mp3"></audio> |
| It appears the light show was a distraction. I am running a full scan now. | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/student/000011.mp3"></audio> | <audio controls src="https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints/resolve/main/samples/teacher/000011.mp3"></audio> |

A longer paragraph (line 4 in the evaluation set) is in `samples/student/000004.mp3` and `samples/teacher/000004.mp3`.

## Files

| Path | What it is |
|---|---|
| `onnx/en_GB-jarvis-medium.onnx` | The model for inference (63 MB). Use this one. |
| `onnx/en_GB-jarvis-medium.onnx.json` | Its Piper config (phoneme map, sample rate, default scales). Keep it next to the `.onnx`. |
| `checkpoints/jarvis-medium-step59998.ckpt` | Final training checkpoint (generator and discriminator, 846 MB). Use it to export again or to continue training. |
| `checkpoints/jarvis-medium-step49998.ckpt` | Checkpoint 10,000 steps earlier. Scores almost the same, so training had levelled off. |
| `samples/` | Demo audio on held-out lines: `student/` (this model) and `teacher/` (F5-TTS). |
| `version_0/`, `en_GB-alan-medium.onnx`, `en_GB-jarvis-medium.onnx.json` (root) | Older files from an earlier, weaker version of this voice. Kept for history. They are **not** the current model. |

Step counts in the names count both optimizers (generator and discriminator), so 59,998 steps is about 30,000 batches.

## Quick start

Install Piper and download this repo:

```bash
pip install piper-tts huggingface_hub
hf download praharshbhatt/jarvis-piper-checkpoints --repo-type dataset \
  --include "onnx/*" --local-dir jarvis
```

Command line:

```bash
echo "Good evening, sir. All systems are online." | \
  piper --model jarvis/onnx/en_GB-jarvis-medium.onnx --output_file hello.wav
```

Python:

```python
import wave
from piper import PiperVoice

voice = PiperVoice.load("jarvis/onnx/en_GB-jarvis-medium.onnx")
with wave.open("hello.wav", "wb") as f:
    voice.synthesize("Good evening, sir. All systems are online.", f)
```

Tips:

- Spell out numbers and times ("seven forty five", not "7:45"). The model was trained on text without digits.
- Write British spellings where you can. The phonemizer is `en-gb-x-rp`.
- Default scales in the config are `noise_scale 0.667`, `length_scale 1.0`, `noise_w 0.8`. Raise `noise_scale` slightly for more variation. Raise `length_scale` to slow the speech.

## Evaluation

All numbers use 50 held-out lines that were never in the training set: 40 film-style lines and 10 lines from the real recordings. "Teacher similarity" is the ECAPA speaker-embedding cosine to the teacher's render of the same line.

| Model | Word error rate | Teacher similarity | Spectral distance (MCD, lower is better) | Pitch-contour correlation | Median pitch |
|---|---|---|---|---|---|
| Previous Piper voice (trained on the real clips) | 0.033 | 0.72 | 279 | 0.26 | 126 Hz |
| Pilot (5% of the data, 1.25 h) | 0.015 | 0.82 | 218 | 0.39 | 109 Hz |
| **This model (all data, 20.6 h)** | **0.015** | **0.88** | **198** | **0.41** | **115 Hz** |
| Teacher (F5-TTS) | 0.048 | 1.00 | 0 | 1.00 | 119 Hz |

Notes:

- The word error rate comes from Whisper `small.en`, with numbers spelled out before comparing. The student is below the teacher because the data filter kept only the clearest teacher clips.
- The MCD values are on a relative scale only. Compare rows with each other, not with other papers.
- The pitch spread of this model (0.146) is lower than the teacher's (0.222). The voice can sound a little calmer and flatter than the teacher on some lines.
- A listening test by the author found the full model clearly better than both the pilot and the previous voice.

### Speed

Measured with `onnxruntime` on an Intel Core i7-11700F. A real-time factor (RTF) below 1 is faster than real time.

| Threads | RTF | First audio | 10.6 s of speech takes |
|---|---|---|---|
| 1 | 0.087 | 85 ms | 0.94 s |
| 2 | 0.060 | 57 ms | 0.66 s |
| 4 | 0.047 | 46 ms | 0.52 s |

The target server is an Intel Xeon E5-2660 v3 (Haswell, 10 cores, CPU only). That chip is slower per core. The expected RTF there is about 0.2 on one thread, which is still real time. This estimate is not a measurement.

## How it was made

1. **Teacher.** F5-TTS (`F5TTS_v1_Base`) was fine-tuned on 120 short real clips of the character voice (about 3 minutes in total). It reads text in the voice but is far too slow on a CPU (RTF 30 to 120).
2. **Corpus.** 26,363 text lines were built from hand-written assistant lines and templates, CMU ARCTIC, Harvard sentences, assistant-style replies, Gutenberg fiction, MultiNLI and Wikipedia. They are 4 to 32 words long, ASCII only, with no digits, acronyms or profanity. The 50 evaluation lines were removed first.
3. **Rendering and quality control.** The teacher rendered every line (16 sampling steps with EPSS). Each clip was checked for word error rate (Whisper), speaker similarity to the reference voice, speaking rate and clipping. 23,768 clips passed the loose generation checks.
4. **Selection.** A stricter filter (word error ≤ 0.05, speaker similarity ≥ 0.75, 1 to 14 s long) kept 16,179 clips (20.6 h). Clips were trimmed, loudness-matched and saved as 22.05 kHz FLAC.
5. **Student.** Piper `medium` was fine-tuned from `en_GB-alan-medium` on the teacher clips only. No real recording was used for the student.
6. **Export.** The final checkpoint was exported to ONNX.

Training settings:

| Setting | Value |
|---|---|
| Optimizer | AdamW, betas (0.8, 0.99) |
| Learning rate | 1e-4, multiplied by 0.93 after each epoch |
| Batch size | 16 |
| Steps | 60,000 (both optimizers counted), about 59 epochs |
| Precision | fp32 |
| Loss weights | `c_mel` 45, `c_kl` 1.0 |
| Segment size | 8,192 samples |
| GPU | one RTX 3090, about 4 steps per second, about 4 hours |

The training code is the archived `rhasspy/piper` repository with small patches: FLAC input with spectrograms computed on the fly, weights-only initialisation, and extra command-line options.

## Limitations

- English only, one voice, no emotion or style control.
- Numbers, times, acronyms and symbols must be written out as words.
- The student can only be as good as the teacher. Mistakes of the teacher, such as an odd stress on a rare word, can carry over.
- Very long sentences (over about 30 words) were rare in the training text. Split long text into sentences.
- Pitch variation is lower than in the teacher.

## License and responsible use

This voice imitates the voice of a real actor, as heard in a commercial film franchise. Treat it with care.

- **Personal, non-commercial use only.** Do not sell it, put it in a product, or use it for advertising.
- **Do not use it to deceive.** Do not present the audio as a real recording of the actor, and do not use it to impersonate a real person. Label generated audio as synthetic.
- **No endorsement.** This project has no connection with the actor, the studio or the rights holders of the character.
- **Upstream terms apply.** The teacher started from pretrained F5-TTS weights, which are released under a non-commercial licence (their training data is Emilia). The student started from a Piper voice checkpoint. Check the terms of both before you do anything beyond personal use.
- **No source audio is included.** This repository has no real recordings and no training clips. It holds only model weights and synthetic demo audio.
- The authors give no warranty. If a rights holder asks for removal, the files will be removed.

## Acknowledgements

- [Piper](https://github.com/rhasspy/piper) by Michael Hansen and the Rhasspy project.
- [F5-TTS](https://github.com/SWivid/F5-TTS) by Chen et al.
- [Whisper](https://github.com/openai/whisper) and [SpeechBrain ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) for automatic quality control.
- The `en_GB-alan-medium` voice used as the starting point.
