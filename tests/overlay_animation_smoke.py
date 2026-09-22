"""Optional headless DOM/animation checks; no screenshots or native windows.

Run: .venv/Scripts/python tests/overlay_animation_smoke.py
Requires the development-only Playwright installation.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parents[1] / "web"


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            from urllib.parse import urlsplit
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
                return
            if path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=(
                    path.read_text(encoding="utf-8")
                    + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => { window.renderHeartbeat = options.render; }};"
                ))
            else:
                route.fulfill(path=str(path))

        page.route("http://overlay.test/**", serve)
        page.goto("http://overlay.test/heartbeat/index.html")
        page.evaluate("""() => {
          renderHeartbeat({heartbeat: {pulse_id: 0}});
          if (document.getAnimations().length < 5) throw Error('Missing idle motion');
          renderHeartbeat({theme: {accent: '#aa44ff'}, heartbeat: {pulse_id: 1, kind: 'journal'}});
          if (!document.querySelector('.lens-optics').getAnimations().length) throw Error('Missing activity focus');
          renderHeartbeat({heartbeat: {pulse_id: 2, stalled: true}});
          if (document.querySelector('.lens-optics').getAnimations().length) throw Error('Stalled activity still playing');
          const core = document.querySelector('.signal-core');
          if (Number(getComputedStyle(core).opacity) < .9) throw Error('Quiet lens is dimmed');
          if (!document.querySelector('.lens-emitter').getAnimations().length) throw Error('Quiet lens stopped breathing');
          if (document.querySelector('.orbital-satellite').getAnimations()[0].playState !== 'paused') throw Error('Stalled feed still orbiting');
          renderHeartbeat({heartbeat: {pulse_id: 3}});
        }""")
        page.emulate_media(reduced_motion="reduce")
        page.evaluate("""() => {
          renderHeartbeat({heartbeat: {pulse_id: 4, kind: 'journal'}});
          if (document.getAnimations().length) throw Error('Reduced motion still animating');
        }""")
        page.emulate_media(reduced_motion="no-preference")
        page.goto("http://overlay.test/navigation_hud/index.html")
        page.evaluate("""() => {
          for (const count of [0, 1, 5, 10, 100, 150, 1000, 5]) {
            const hops = Array.from({length: count}, (_, index) => ({
              name: `System ${index}`, position: 0, completed: index < 2,
              current: index === 2, next: index === 3, scoopable: index % 2 === 0,
            }));
            renderRoute({active: count > 0, hops});
            const host = document.getElementById('route-pips');
            if (host.children.length !== count) throw Error(`Lost waypoints: ${count}`);
            const bounds = host.getBoundingClientRect();
            for (const node of host.children) {
              const box = node.getBoundingClientRect();
              if (box.width <= 0 || box.right > bounds.right + 1) throw Error('Clipped waypoint');
            }
            const first = host.firstElementChild;
            renderRoute({active: count > 0, hops, leg_distance: '12 LY'});
            if (host.firstElementChild !== first) throw Error('Rebuilt unchanged route nodes');
          }
          if (!document.querySelector('.route-segment.next > b').getAnimations().length) throw Error('Missing next-stop animation');
          document.getElementById('hud').classList.add('reduced-motion');
          if (document.querySelector('.route-segment.next > b').getAnimations().length) throw Error('Reduced route motion');
        }""")
        assert not errors, errors
        browser.close()
    print("PASS: lens idle/activity/stalled/reduced motion; 0–1000 waypoints, bounds, node reuse and route animation")


if __name__ == "__main__":
    run()
