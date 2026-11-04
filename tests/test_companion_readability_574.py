"""The three holograms need an instrument silhouette over game scenery."""
from io import BytesIO
import math
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from tests import test_watcher_three_568 as three
from tests.test_heartbeat_orb import snapshot

ARTIFACTS = Path(tempfile.gettempdir()) / "voidcompass-companion-contrast"
ARTIFACTS.mkdir(exist_ok=True)


class CompanionReadabilityTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def ready(self):
        page = self.open_page("heartbeat/index.html", reduced=True)
        page.wait_for_function("Boolean(window.AsterCompanion && window.CrewCompanion && window.renderHeartbeat)")
        page.route("http://watcher3d.test/api/live*", lambda route: route.fulfill(content_type="application/json", body="{}"))
        return page

    def render(self, page, identity, size):
        page.set_viewport_size({"width": size, "height": size})
        data = snapshot(crt=False, reduced=True)
        data["heartbeat"]["orb"].update(identity=identity, size=size, motion=False, focus_movement="off",
                                         accent="brass" if identity == "meridian" else "cyan")
        page.evaluate("data => renderHeartbeat(data)", data)
        name = "AsterCompanion" if identity == "aster" else "CrewCompanion"
        page.wait_for_function(f'{name}.inspect(document.getElementById("orb"))?.frames > 0')

    def capture(self, page, name):
        return Image.open(BytesIO(page.screenshot(path=str(ARTIFACTS / name), omit_background=True))).convert("RGBA")

    def test_bezel_has_dark_and_light_contrast_at_small_sizes(self):
        page = self.ready()
        for identity in ("aster", "axiom", "meridian"):
            for size in (54, 96):
                self.render(page, identity, size)
                for background in ("#ffffff", "#070b10"):
                    page.evaluate("colour => document.body.style.background = colour", background)
                    pixels = self.capture(page, f'{identity}-{size}-{background[1:]}.png')
                    samples = []
                    # A small circle is antialiased across pixels: measure the
                    # darkest/lightest part of each radial profile, rather than
                    # assuming a chosen pixel lands exactly on one thin bevel.
                    for index in range(48):
                        angle = index / 48 * math.tau
                        profile = []
                        for radius in (.85, .88, .90, .925, .95, .975, .99):
                            x = int(size / 2 + math.cos(angle) * radius * size / 2)
                            y = int(size / 2 + math.sin(angle) * radius * size / 2)
                            rgb = pixels.getpixel((x, y))[:3]
                            profile.append(sum(rgb) / 3)
                        samples.append(min(profile) if background == "#ffffff" else max(profile))
                    if background == "#ffffff":
                        self.assertGreater(sum(value < 180 for value in samples), 40,
                                           f"{identity} needs a dark silhouette over bright scenery at {size}px")
                    else:
                        self.assertGreater(sum(value > 90 for value in samples), 40,
                                           f"{identity} needs a visible lit rim over dark scenery at {size}px")

    def test_lattice_gaps_and_outer_transparency_are_preserved(self):
        page = self.ready()
        for identity in ("aster", "axiom", "meridian"):
            self.render(page, identity, 192)
            pixels = self.capture(page, f"{identity}-transparent.png")
            for point in ((0, 0), (191, 0), (0, 191), (191, 191)):
                self.assertEqual(pixels.getpixel(point)[3], 0)
            if identity in ("aster", "axiom"):
                radius=.27 if identity=="aster" else .40
                gap=[(round(96+math.cos(i/48*math.tau)*radius/2.32*192),
                      round(96+math.sin(i/48*math.tau)*radius/2.32*192)) for i in range(48)]
                self.assertGreater(sum(pixels.getpixel(point)[3]<16 for point in gap),24,
                                   "most of the gap around the central lattice stays transparent")
            else:
                self.assertGreater(pixels.getpixel((96, 96))[3], 100, "the portrait has dark glass behind it")
            self.assertGreater(pixels.getpixel((170, 96))[3], 140, "a translucent recess supports the detail")

    def test_frame_uses_the_selected_accent_and_stays_when_motion_is_off(self):
        page = self.ready()
        for identity in ("aster", "axiom", "meridian"):
            self.render(page, identity, 96)
            page.evaluate('''identity => {
                const display = identity === "aster" ? AsterCompanion : CrewCompanion;
                window.repaintFrame = accent => display.update(document.getElementById("orb"),
                    {orb:{identity,accent,motion:false,focus_movement:"off"}}, {}, {reducedMotion:true});
                repaintFrame("brass");
            }''', identity)
            page.wait_for_timeout(100)
            brass = self.capture(page, f"{identity}-brass.png")
            page.evaluate('repaintFrame("cyan")')
            page.wait_for_timeout(100)
            cyan = self.capture(page, f"{identity}-cyan.png")
            brass_gain = cyan_gain = 0
            for index in range(48):
                angle = index / 48 * math.tau
                x = int(48 + math.cos(angle) * .95 * 48)
                y = int(48 + math.sin(angle) * .95 * 48)
                b, c = brass.getpixel((x,y)), cyan.getpixel((x,y))
                brass_gain += b[0] - c[0]
                cyan_gain += c[1] - b[1]
            self.assertGreater(brass_gain, 40)
            self.assertGreater(cyan_gain, 40)
