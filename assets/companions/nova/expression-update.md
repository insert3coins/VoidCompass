# Nova expression art update

Extract this ZIP at the SurveyAnalysis project root. It overlays the existing Nova PNG collection and supplies the seven corresponding 256 px deck sprite sheets. Open `assets/companions/nova/preview.html` to audition the artwork. It starts on the new on-watch idle.

| Clip | Playback | Event or use |
| --- | --- | --- |
| idle | 96 frames at 15 fps, looping | On watch. Breathing, weight shift, eye refocus and blink. |
| idle-settled | 90 frames at 15 fps, looping | Resting. A longer breath and an uneven double blink. |
| goodnight | 54 frames at 18 fps, once | Sign-off. Keep frame 53 displayed for sleep. |
| downcast | 32 frames at 16 fps, once | Sad. Frame 15 is the held pose. |
| wary | 32 frames at 16 fps, once | Worry or suspicion. Frame 16 is the held pose. |
| glance-left, glance-right | 24 frames each at 24 fps, once | Toward the corresponding side of the screen. Hold frame 9 while tracking a target, then play the release. |

The existing deck renderer already requests `idle`. For the remaining events, the selection logic is in `web/assets/nova-hologram.js`. Map `sad` to `downcast` and `worry` to `wary`. The glance directions are from the viewer's perspective. All indices above are zero-based. Speech and its independent blink layer keep their existing files and timing.
