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
        page.evaluate("""() => {
          const expect = (ok, message) => { if (!ok) throw Error(message); };
          dom.hud.classList.remove('reduced-motion');
          routeMemory = null;
          lastRouteSignature = '';
          clearTimeout(routeFeedbackTimer);
          dom['route-feedback'].textContent = '';
          const route = {active: true, source: 'game', target: 'Beta',
            next_star: {star_class: 'K', scoopable: true}, fuel_endurance_jumps: 1,
            hops: [{name: 'Beta', next: true}, {name: 'Gamma'}]};
          renderRoute(route, 'Alpha');
          expect(!dom['route-feedback'].textContent, 'Startup announced a replot');
          expect(dom['route-star'].textContent === 'K · SCOOPABLE', 'Missing next-star facts');
          expect(dom['route-fuel'].classList.contains('fuel-caution'), 'Missing fuel caution');
          expect(dom['route-title'].textContent === 'JUMP 1 / 2', 'Incorrect jump count');
          renderRoute({...route, leg_distance: '20 LY'}, 'Alpha');
          expect(!dom['route-feedback'].textContent, 'Distance update announced a replot');
          renderRoute({...route, target: 'Delta', hops: [{name: 'Delta', next: true}]}, 'Alpha');
          expect(dom['route-feedback'].textContent === 'ROUTE UPDATED', 'Missing replot notice');
          expect(dom['route-block'].classList.contains('route-notice')
            && dom['route-block'].dataset.notice === 'updated', 'Missing replot confirmation');
          renderRoute({}, 'Alpha');
          expect(dom['route-feedback'].textContent === 'ROUTE CLEARED', 'Missing clear notice');
          renderRoute(route, 'Alpha');
          renderRoute({...route, target: 'Gamma', fuel_endurance_jumps: null,
            next_star: {}, hops: [{name: 'Beta', completed: true, current: true}, {name: 'Gamma', next: true}]}, 'Beta');
          expect(dom['route-feedback'].textContent === 'ARRIVED · Beta', 'Missing arrival');
          expect(dom['route-block'].dataset.notice === 'arrived', 'Missing arrival confirmation');
          expect(dom['route-title'].textContent === 'JUMP 2 / 2', 'Arrival progress wrong');
          expect(dom['route-progress'].style.width === '50%', 'Rail progress not aligned');
          expect(dom['route-fuel'].textContent === 'FUEL RANGE UNKNOWN', 'Unknown fuel presented as verified');
          expect(dom['route-star'].textContent === 'STAR UNKNOWN', 'Unknown star presented as verified');
        }""")
        page.evaluate("""() => {
          renderRoute({active: true, source: 'game', next_star: {star_class: 'G', scoopable: true},
            hops: [
              {name: 'Yellow', star_class: 'G', next: true, scoopable: true},
              {name: 'Neutron', star_class: 'N', scoopable: false},
              {name: 'Black hole', star_class: 'BH', scoopable: false},
              {name: 'Unknown', star_class: '', scoopable: null},
            ]}, 'Alpha');
          if (!dom['route-star-orb'].classList.contains('star-g')) throw Error('Next star visual has wrong class');
          if (!dom['route-star-orb'].querySelector('i').getAnimations().length) throw Error('Known star visual is static');
          const markers = [...dom['route-pips'].children];
          if (!markers[0].classList.contains('star-g') || !markers[1].classList.contains('star-neutron')
              || !markers[2].classList.contains('star-blackhole')
              || !markers[3].classList.contains('star-unknown') || markers[3].classList.contains('unscoopable'))
            throw Error('Route star markers misclassified');
          renderRoute({active: true, source: 'waypoints', hops: [{name: 'Unknown', next: true}]}, 'Alpha');
          if (!dom['route-star-orb'].classList.contains('star-unknown')) throw Error('Unknown destination displayed as a star');
        }""")
        for layout, width, height in [("standard", 500, 326), ("expanded", 620, 342)]:
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("""layout => {
              render({schema: 1, layout, effects: {reduced_motion: true},
                state: {motion: 'flight', label: 'FLIGHT', vehicle: {ship_symbol: 'anaconda'}},
                context: {surface: true, primary: 'SURFACE · TEST'}, system: {name: 'Beta', star_class: 'K'},
                route: {active: true, source: 'game', next_star: {star_class: 'G', scoopable: true},
                  hops: [{name: 'Gamma', star_class: 'G', next: true}]}});
              if (!dom.hud.classList.contains('surface-focus')) throw Error('Missing surface emphasis');
              if (dom['vehicle-display'].hidden || !dom['vehicle-image'].src.endsWith('/ship-art/Anaconda.png'))
                throw Error('Ship art missing from redesigned HUD');
              if (!dom['current-star-orb'].classList.contains('star-k')
                  || dom['current-star-label'].textContent !== 'STAR K') throw Error('Current star visual missing');
              const route = document.querySelector('.route-block').getBoundingClientRect();
              const survey = dom['survey-block'].getBoundingClientRect();
              const footer = document.querySelector('.context-rail').getBoundingClientRect();
              if (route.bottom > survey.top || survey.bottom > footer.top) throw Error('HUD sections overlap');
              const orb = dom['route-star-orb'].getBoundingClientRect();
              const target = document.querySelector('.route-target').getBoundingClientRect();
              if (orb.left < target.left || orb.right > target.right || orb.bottom > target.bottom)
                throw Error('Star visual escapes next-system panel');
              const status = document.querySelector('.route-status').getBoundingClientRect();
              if (status.bottom > route.bottom) throw Error('Status row exceeds route block');
            }""", layout)
        page.emulate_media(reduced_motion="reduce")
        page.evaluate("""() => {
          render({schema: 1, layout: 'standard', effects: {reduced_motion: false},
            state: {motion: 'flight', label: 'FLIGHT', vehicle: {ship_symbol: 'anaconda'}},
            system: {name: 'Beta'}});
          if (!dom.hud.classList.contains('reduced-motion')) throw Error('OS reduced-motion preference ignored');
          const running = document.getAnimations();
          if (running.length) throw Error('HUD still animates with OS reduced motion: '
            + running.map(animation => `${animation.effect?.target?.className || animation.effect?.target?.id}:${animation.playState}`).join(', '));
        }""")
        assert not errors, errors
        browser.close()
    print("PASS: lens animation; 0-1000 waypoints; stellar visuals; route updates/arrival/clear; ship art; both HUD layouts; OS reduced motion")


if __name__ == "__main__":
    run()
