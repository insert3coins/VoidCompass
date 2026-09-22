"""Headless startup presentation checks, without screenshots or a running backend."""
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parents[1] / "web"
SOURCE = (WEB / "dashboard/app.js").read_text(encoding="utf-8")
RENDER = SOURCE[SOURCE.index("function renderBoot(state)"):SOURCE.index("function renderCommissioning(onboarding)")]


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_init_script("""window.bootDraws = 0;
          window.bootActivityCount = 0;
          const animate = Element.prototype.animate;
          Element.prototype.animate = function(...args) {
            if (this.classList.contains('boot-optic-lens')) window.bootActivityCount++;
            return animate.apply(this, args);
          };
          const clear = CanvasRenderingContext2D.prototype.clearRect;
          CanvasRenderingContext2D.prototype.clearRect = function(...args) {
            if (this.canvas.id === 'boot-starfield') window.bootDraws++;
            return clear.apply(this, args);
          };
        """)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path == WEB / "dashboard/app.js":
                route.fulfill(content_type="application/javascript", body="""
                  let model = {}, bootHideTimer = 0, bootStageTransitionTimer = 0, lastBootStage = '';
                  const byId = id => document.getElementById(id);
                  const number = value => Number(value) || 0;
                  const text = (id, value, fallback = '') => byId(id).textContent = value || fallback;
                  const percentWidth = (id, value) => byId(id).style.width = `${value}%`;
                  const renderCommissioning = () => {};
                """ + RENDER + "\nwindow.bootTest = state => { model = state; renderBoot(state); };")
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")

        page.route("http://boot.test/**", serve)
        page.goto("http://boot.test/dashboard/index.html")
        page.wait_for_function("window.bootDraws > 2")
        page.wait_for_function("window.bootActivityCount > 0")
        page.evaluate("""() => {
          const sky = document.getElementById('boot-starfield');
          const pixels = sky.getContext('2d').getImageData(0,0,sky.width,sky.height).data;
          if (!pixels.some((value,index) => index % 4 === 3 && value > 0)) throw Error('Starfield is empty');
        }""")
        for width, height in [(1440, 900), (1024, 768), (800, 600), (480, 740), (960, 480)]:
            page.set_viewport_size({"width": width, "height": height})
            for progress, stage in [(0, "profile"), (.2, "survey"), (.65, "journal"), (.8, "cockpit"), (1, "handoff")]:
                page.evaluate("""({progress, stage}) => {
                  bootTest({boot: {active: true, progress, status: 'INITIALISING FLIGHT COMPUTER', detail: 'Preparing the local exploration archive'}});
                  const loader = document.getElementById('boot-loader');
                  if (loader.dataset.bootStage !== stage) throw Error('Wrong stage');
                  if (loader.style.getPropertyValue('--boot-progress') !== String(Math.round(progress * 100))) throw Error('Ring disagrees with progress');
                  if (stage !== 'handoff' && !document.querySelector(`.boot-sequence > [data-boot-stage="${stage}"]`).classList.contains('active')) throw Error('Missing active stage');
                  for (const selector of ['.boot-instrument','.boot-copy','.boot-sequence']) {
                    const box = document.querySelector(selector).getBoundingClientRect();
                    if (box.width <= 0 || box.left < 0 || box.right > innerWidth + 1) throw Error(`Layout clipped: ${selector}`);
                  }
                  if (document.body.classList.contains('ready')) throw Error('Premature handoff');
                }""", {"progress": progress, "stage": stage})
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_timeout(100)
        still_draws = page.evaluate("window.bootDraws")
        still_activity = page.evaluate("window.bootActivityCount")
        page.wait_for_timeout(150)
        assert page.evaluate("window.bootDraws") == still_draws, "Reduced-motion sky still drawing"
        page.evaluate("""() => {
          if (document.querySelector('.boot-instrument').getAnimations({subtree:true}).length) throw Error('Reduced motion animating');
          bootTest({onboarding: {active:true}, boot: {active:true}});
          if (!document.getElementById('boot-loader').hidden || document.getElementById('commissioning').hidden) throw Error('Commissioning visibility changed');
        }""")
        page.emulate_media(reduced_motion="no-preference")
        page.evaluate("""() => {
          bootTest({boot: {active:false, progress:1}});
          if (!document.body.classList.contains('ready')) throw Error('Missing handoff');
        }""")
        page.wait_for_function("document.getElementById('boot').hidden")
        ended_draws = page.evaluate("window.bootDraws")
        page.wait_for_timeout(150)
        assert page.evaluate("window.bootDraws") == ended_draws, "Starfield still drawing after handoff"
        page.emulate_media(reduced_motion="reduce")
        page.clock.install()
        page.evaluate("bootTest({boot:{active:true,progress:0}})")
        page.wait_for_function("document.getElementById('boot-fact').textContent.length > 0")
        ids = {page.locator('#boot-fact').get_attribute('data-fact-id')}
        for _ in range(9):
            page.clock.run_for(9000)
            ids.add(page.locator('#boot-fact').get_attribute('data-fact-id'))
        assert page.evaluate("window.bootActivityCount") == still_activity, "Reduced motion triggered decorative activity"
        assert len(ids) == 10, "Fact deck repeated before all ten entries appeared"
        assert page.locator('#boot-fact-previous').is_visible(), "Missing previous chat bubble"
        page.evaluate("bootTest({boot:{active:false,progress:1}})")
        final_fact = page.locator('#boot-fact').text_content()
        page.emulate_media(reduced_motion="no-preference")
        final_activity = page.evaluate("window.bootActivityCount")
        page.clock.run_for(20000)
        assert page.evaluate("window.bootActivityCount") == final_activity, "Decorative activity continued after handoff"
        assert page.locator('#boot-fact').text_content() == final_fact, "Facts continued after startup"
        assert not errors, errors
        browser.close()
    print("PASS: boot stages, progress ring, 5 viewport sizes, starfield rendering, reduced-motion freeze, commissioning and stopped animation after handoff")


if __name__ == "__main__":
    run()
