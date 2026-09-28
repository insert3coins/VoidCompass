"""Headless startup presentation checks, without screenshots or a running backend."""
from pathlib import Path
import re
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parents[1] / "web"
SOURCE = (WEB / "dashboard/app.js").read_text(encoding="utf-8")
MILESTONES = SOURCE[SOURCE.index("function postBootMilestone(action)"):SOURCE.index("function reportClientError(")]
RENDER = SOURCE[SOURCE.index("function renderBoot(state)"):SOURCE.index("function renderCommissioning(onboarding)")]
STATE_RENDER = SOURCE[SOURCE.index("function renderState(state)"):SOURCE.index("function aboutMatrixNodes(")]
SCENE = (WEB / "dashboard/boot-scene.js").read_text(encoding="utf-8")
FACT_INTERVAL_MS = int(re.search(r"const FACT_INTERVAL_MS = (\d+);", SCENE).group(1))


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_init_script("""window.bootDraws = 0;
          const clear = CanvasRenderingContext2D.prototype.clearRect;
          CanvasRenderingContext2D.prototype.clearRect = function(...args) {
            if (this.canvas.id === 'boot-drift') window.bootDraws++;
            return clear.apply(this, args);
          };
        """)
        errors = []
        signals = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            request_path = urlsplit(route.request.url).path
            if request_path == "/api/command":
                signals.append(route.request.post_data_json["action"])
                route.fulfill(status=202, content_type="application/json",
                              body='{"accepted":true}')
                return
            path = WEB / request_path.lstrip("/")
            if path == WEB / "dashboard/app.js":
                route.fulfill(content_type="application/javascript", body="""
                  let model = {}, bootHideTimer = 0, bootStageTransitionTimer = 0, lastBootStage = '';
                  const BOOT_READY_HOLD_MS = 5000;
                  let bootReadyAt = 0, bootHoldComplete = false, bootHoldTimer = 0;
                  let bootActive = true, bootReleaseStarted = false, currentPage = 'overview';
                  let bootPresentedRequested = false, bootHandoffRequested = false;
                  window.deckHydrations = 0;
                  const byId = id => document.getElementById(id);
                  const apiUrl = path => path;
                  const number = value => Number(value) || 0;
                  const text = (id, value, fallback = '') => byId(id).textContent = value || fallback;
                  const percentWidth = (id, value) => byId(id).style.width = `${value}%`;
                  const renderCommissioning = () => {};
                  const applyTheme = () => {};
                  const startAboutMatrix = () => {};
                  const renderDashboard = () => { window.deckHydrations++; };
                  // The music player (music.js) is not part of the boot.
                  let musicDeck = {update() {}, showPage() {}};
                """ + MILESTONES + RENDER + STATE_RENDER + "\nwindow.bootTest = state => { model = state; renderBoot(state); };"
                    + "\nwindow.bootStateTest = state => renderState(state);")
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")

        page.route("http://boot.test/**", serve)
        page.goto("http://boot.test/dashboard/index.html")
        page.wait_for_function("window.bootDraws > 2")
        page.wait_for_function("bootScene.state().orb && bootScene.state().orb.frames > 2")
        page.evaluate("""() => {
          for (const id of ['boot-sky', 'boot-drift', 'boot-orb']) {
            const canvas = document.getElementById(id);
            const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
            if (!pixels.some((value, index) => index % 4 === 3 && value > 0)) throw Error(`${id} is empty`);
          }
          if (document.querySelectorAll('#boot-ring-stages > g').length !== 4) throw Error('Ring is missing stage markers');
        }""")
        for width, height in [(1440, 900), (1024, 768), (800, 600), (480, 740), (960, 480)]:
            page.set_viewport_size({"width": width, "height": height})
            for progress, stage in [(0, "profile"), (.5, "survey"), (.8, "journal"), (.9, "cockpit"), (1, "handoff")]:
                page.evaluate("""({progress, stage}) => {
                  bootTest({app: {version: '9.9.9'}, boot: {active: true, progress, status: 'INITIALISING FLIGHT COMPUTER', detail: 'Preparing the local exploration archive'}});
                  const loader = document.getElementById('boot-loader');
                  if (loader.dataset.bootStage !== stage) throw Error(`Wrong stage at ${progress}: ${loader.dataset.bootStage}`);
                  if (loader.style.getPropertyValue('--boot-progress') !== String(Math.round(progress * 100))) throw Error('Ring disagrees with progress');
                  if (stage !== 'handoff') {
                    if (!document.querySelector(`.boot-sequence > [data-boot-stage="${stage}"]`).classList.contains('active')) throw Error('Missing active stage');
                    if (!document.querySelector(`#boot-ring-stages > [data-ring-stage="${stage}"]`).classList.contains('active')) throw Error('Ring marker not active');
                  }
                  for (const selector of ['.boot-instrument', '.boot-copy', '.boot-sequence', '.boot-transmission']) {
                    const box = document.querySelector(selector).getBoundingClientRect();
                    if (box.width <= 0 || box.left < 0 || box.right > innerWidth + 1) throw Error(`Layout clipped: ${selector}`);
                  }
                  if (document.documentElement.scrollWidth > innerWidth + 1) throw Error('Boot scrolls sideways');
                  if (document.body.classList.contains('ready')) throw Error('Premature handoff');
                }""", {"progress": progress, "stage": stage})
        page.wait_for_timeout(100)
        assert "boot_presented" in signals, "Browser never acknowledged its first boot frame"
        page.evaluate("""() => {
          // The version, and no release notes: the log has the room.
          if (!document.getElementById('boot-version-line').textContent.startsWith('V9.9.9')) throw Error('Version missing');
          if (document.querySelector('#boot-release, .boot-release')) throw Error('Release notes are back on the boot screen');
          bootTest({app: {version: '9.9.9'}, boot: {active: true, progress: .2, status: 'BUILDING DASHBOARD CORE', detail: 'Loading profile', events: 0}});
          bootTest({boot: {active: true, progress: .8, status: 'RESTORING RECENT JOURNAL', detail: 'Reduced 400 events', events: 400}});
          const state = bootScene.state();
          if (!state.log.includes('BUILDING DASHBOARD CORE') || state.log.at(-1) !== 'RESTORING RECENT JOURNAL') throw Error('Log missed a status');
          if (!state.orb.motes) throw Error('Restored journal events never reached the watcher');
          if (!document.getElementById('boot-events').textContent.includes('400')) throw Error('Event count missing');
          bootTest({boot: {active: true, progress: .81, status: 'RESTORING RECENT JOURNAL', detail: 'Reduced 500 events', events: 500}});
          if (bootScene.state().log.filter(line => line === 'RESTORING RECENT JOURNAL').length !== 1) throw Error('A repeated status filled the log');
        }""")
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_timeout(100)
        still_draws = page.evaluate("window.bootDraws")
        still_frames = page.evaluate("bootScene.state().orb.frames")
        page.wait_for_timeout(200)
        assert page.evaluate("window.bootDraws") == still_draws, "Reduced-motion sky still drawing"
        assert page.evaluate("bootScene.state().orb.frames") == still_frames, "Reduced-motion watcher still animating"
        page.evaluate("""() => {
          if (document.querySelector('.boot-instrument').getAnimations({subtree: true}).length) throw Error('Reduced motion animating');
          bootTest({onboarding: {active: true}, boot: {active: true}});
          if (!document.getElementById('boot-loader').hidden || document.getElementById('commissioning').hidden) throw Error('Commissioning visibility changed');
        }""")
        page.emulate_media(reduced_motion="no-preference")
        page.evaluate("""() => {
          bootTest({boot: {active: false, progress: 1}});
          if (document.body.classList.contains('ready')) throw Error('Boot screen vanished immediately');
          if (document.getElementById('boot-status').textContent !== 'FLIGHT DECK READY') throw Error('Hold lost its status');
        }""")
        # The hold counts down from 4 and jumps just before the deck appears.
        page.wait_for_function("bootScene.state().counting && bootScene.state().count === '4'", timeout=2500)
        page.wait_for_function("bootScene.state().jumped", timeout=5500)
        assert not page.evaluate("document.body.classList.contains('ready')"), "The jump came after the deck appeared"
        assert page.evaluate("document.getElementById('boot').classList.contains('jumping')"), "No jump class"
        page.wait_for_function("document.body.classList.contains('ready')", timeout=2000)
        page.wait_for_function("bootScene.state().warp > .3", timeout=2000)
        page.wait_for_function("document.getElementById('boot').hidden")
        page.wait_for_timeout(100)
        assert "boot_handoff_complete" in signals, "Browser never acknowledged dashboard reveal"
        ended_draws = page.evaluate("window.bootDraws")
        ended_frames = page.evaluate("bootScene.state().orb.frames")
        page.wait_for_timeout(200)
        assert page.evaluate("window.bootDraws") == ended_draws, "Sky still drawing after handoff"
        assert page.evaluate("bootScene.state().orb.frames") == ended_frames, "Watcher still animating after handoff"
        page.emulate_media(reduced_motion="reduce")
        page.clock.install()
        page.evaluate("""() => {
          document.getElementById('boot').hidden = false;
          document.body.classList.remove('ready');
          bootHoldComplete = false;
          bootTest({boot: {active: true, progress: 0}});
          if (document.getElementById('boot').classList.contains('jumping')) throw Error('Jump survived a restarted boot');
        }""")
        page.wait_for_function("document.getElementById('boot-fact').textContent.length > 0")
        fact_count = page.evaluate("import('/dashboard/boot-facts.js').then(module => module.BOOT_FACTS.length)")
        ids = {page.locator('#boot-fact').get_attribute('data-fact-id')}
        # Resume from an arbitrary point in the current shuffle and cover a full new deck.
        for _ in range(fact_count * 2):
            page.clock.run_for(FACT_INTERVAL_MS)
            ids.add(page.locator('#boot-fact').get_attribute('data-fact-id'))
        assert len(ids) == fact_count, "Fact deck did not cover every entry"
        page.evaluate("bootTest({boot:{active:false,progress:1}})")
        assert not page.evaluate("document.body.classList.contains('ready')"), "Handoff skipped minimum display"
        page.clock.run_for(4900)
        assert not page.evaluate("document.body.classList.contains('ready')"), "Handoff happened before 5 seconds"
        assert page.evaluate("bootScene.state().jumped"), "Reduced motion skipped the handoff countdown"
        assert not page.evaluate("document.getElementById('boot').classList.contains('jumping')"), "Reduced motion played the jump"
        page.clock.run_for(150)
        assert page.evaluate("document.body.classList.contains('ready')"), "Handoff did not finish"
        final_fact = page.locator('#boot-fact').text_content()
        page.emulate_media(reduced_motion="no-preference")
        page.clock.run_for(20000)
        assert page.evaluate("document.body.classList.contains('ready')"), "Repeated render restarted minimum hold"
        assert page.locator('#boot-fact').text_content() == final_fact, "Facts continued after startup"
        page.evaluate("""() => {
          bootActive = true;
          bootReleaseStarted = false;
          bootHoldComplete = false;
          bootReadyAt = 0;
          document.body.classList.remove('ready');
          document.getElementById('boot').hidden = false;
          window.deckHydrations = 0;
          bootStateTest({boot: {active: true, progress: .8}});
          bootStateTest({boot: {active: false, progress: 1}});
          if (window.deckHydrations !== 1) throw Error('Dashboard was not hydrated behind the boot curtain');
          if (document.body.classList.contains('ready')) throw Error('Deck revealed before hold finished');
          if (bootStateTest({boot: {active: true, progress: .8}}) !== false)
            throw Error('A stale active snapshot reopened boot');
        }""")
        page.clock.run_for(4900)
        assert not page.evaluate("document.body.classList.contains('ready')"), "Stale snapshot shortened boot hold"
        page.clock.run_for(150)
        assert page.evaluate("document.body.classList.contains('ready')"), "Browser did not own the final handoff"
        page.clock.run_for(721)
        assert page.evaluate("document.getElementById('boot').hidden"), "Boot curtain was not dismissed"
        page.evaluate("""() => {
          bootStateTest({boot: {active: true, progress: .8}});
          if (!document.body.classList.contains('ready') || !document.getElementById('boot').hidden)
            throw Error('A late snapshot flashed the boot curtain after handoff');
        }""")
        assert not errors, errors
        browser.close()
    print("PASS: boot stages and ring, 5 viewport sizes, sky and watcher, log and version, reduced motion, "
          "commissioning, countdown and jump, single hydrated handoff and stale-snapshot rejection")


if __name__ == "__main__":
    run()
