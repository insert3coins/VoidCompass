"""Capture the real shared Hatchling models as Discord cards and cutouts."""
from __future__ import annotations

import argparse
import base64
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
PETS = [
    ('thargoid-larva', 'Thargoid larva', 'A little light from the black.', 'larva', '', 'juvenile'),
    ('remlok-bot', 'Remlok companion bot', 'Small chassis. An enormous personality.', 'bot', '', 'juvenile'),
    ('bacterium', 'Bacterium', 'A whole tiny world, aboard your ship.', 'sample', 'bacterium', 'juvenile'),
    ('tubus', 'Tubus', 'Growing toward the next discovery.', 'sample', 'tubus', 'juvenile'),
    ('fungoida', 'Fungoida', 'A little more life in the black.', 'sample', 'fungoida', 'juvenile'),
    ('thargoid-scout', 'Scout foundling', 'The first unfurling.', 'thargoid', '', 'hatchling'),
    ('thargoid-thargon', 'Thargon foundling', 'Growing into its own strange self.', 'thargoid', '', 'juvenile'),
    ('thargoid-orthrus', 'Orthrus foundling', 'A familiar traveller. An extraordinary form.', 'thargoid', '', 'adult'),
]
OUTFITS = [
    ('visor', 'Scanner visor', 1), ('helmet', 'Mining helmet', 0),
    ('charm', 'Guardian charm', 5), ('scarf', "Explorer’s scarf", 3), ('bowtie', 'Bow tie', 4),
]
SHELL = '''<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#050b12;color:#d8e5ed;font-family:Arial,sans-serif}
.card{position:relative;width:1080px;height:1080px;overflow:hidden;background:radial-gradient(ellipse at 50% 51%,#193139 0,#0b1822 40%,#04090f 78%)}
.card:before{content:"";position:absolute;inset:29px;border:1px solid #c46d2c66;clip-path:polygon(0 0,35% 0,35% 1%,65% 1%,65% 0,100% 0,100% 100%,65% 100%,65% 99%,35% 99%,35% 100%,0 100%)}
header{position:absolute;inset:58px 65px auto;display:flex;align-items:center;justify-content:space-between;font:700 18px Consolas,monospace;letter-spacing:4px;color:#ed9b55}header span{color:#81969f;font-size:13px;letter-spacing:2px}
.stars{position:absolute;inset:90px 45px 150px;background-image:radial-gradient(#9bb9c6 1px,transparent 2px),radial-gradient(#e0edee 1px,transparent 2px);background-size:109px 97px,181px 157px;opacity:.2;mask-image:linear-gradient(transparent,#000 20%,#000 75%,transparent)}
.platform{position:absolute;left:170px;right:170px;top:790px;height:125px;border-radius:50%;border:1px solid #7aaca755;background:radial-gradient(ellipse,#71bea618,transparent 70%);box-shadow:0 0 40px #89e9cf08,inset 0 0 28px #b6f1d608}
canvas{position:absolute;inset:0;width:1080px;height:1080px}
footer{position:absolute;inset:auto 65px 61px}footer small{color:#ed9b55;font:700 12px Consolas,monospace;letter-spacing:4px}h1{margin:13px 0 10px;font-size:48px;font-weight:500;letter-spacing:1px}p{margin:0;color:#8fa5ae;font-size:20px}aside{position:absolute;bottom:58px;right:65px;color:#637d88;font:12px Consolas,monospace;letter-spacing:2px}
</style><main class="card"><div class="stars"></div><header>VOID COMPASS<span>SHIPBOARD COMPANIONS / 5.6.8</span></header><div class="platform"></div><canvas id="pet" width="1080" height="1080"></canvas><footer><small id="family"></small><h1 id="name"></h1><p id="line"></p></footer><aside>FOUND. LOVED. ABOARD.</aside></main>
<script src="/assets/hatchling-art.js"></script><script type="module">
import '/assets/hatchling-3d.js';
window.paintPortrait = ({pet,name,line,family}) => {
  document.querySelector('#name').textContent=name;document.querySelector('#line').textContent=line;document.querySelector('#family').textContent=family;
  const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,1080,1080);
  const size=pet.species==='thargoid'&&pet.stage==='adult'?440:500;
  const ok=Hatchling3D.draw(ctx,pet,{x:540,y:600,size,t:2.25,look:[.6,.08],aura:false,shadow:true,resolution:1536});
  if(!ok)throw Error('Native Hatchling renderer failed');return canvas.toDataURL('image/png');
};
</script>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'exports/hatchlings-5.6.8')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    entries = []
    for slug, name, line, species, kind, stage in PETS:
        entries.append((slug, {'pet': {'species': species, 'kind': kind, 'stage': stage, 'needs': {'mood': 88}, 'mood_word': 'HAPPY'},
                              'name': name, 'line': line, 'family': 'COMPANION BAY / ' + ('THARGOID FOUNDLING' if species == 'thargoid' else 'HATCHLINGS')}))
    for outfit, label, index in OUTFITS:
        slug, original = entries[index]
        data = {**original, 'pet': {**original['pet'], 'outfit': outfit}, 'name': label, 'family': 'EARNED OUTFITS / ' + original['name'].upper(), 'line': original['line']}
        entries.append((f'outfit-{outfit}', data))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1080, 'height': 1080}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def serve(route):
            path = urlsplit(route.request.url).path
            if path == '/':
                route.fulfill(content_type='text/html', body=SHELL)
            else:
                target = (WEB / path.lstrip('/')).resolve()
                if target.is_relative_to(WEB) and target.is_file():
                    route.fulfill(path=str(target))
                else:
                    route.fulfill(status=404, body='')
        page.route('http://showcase.test/**', serve)
        page.goto('http://showcase.test/')
        page.wait_for_function("typeof paintPortrait === 'function'")
        for slug, data in entries:
            cutout = page.evaluate('paintPortrait', data)
            (output / f'{slug}-transparent.png').write_bytes(base64.b64decode(cutout.split(',', 1)[1]))
            page.screenshot(path=str(output / f'{slug}.png'))
            print(f'Captured {slug}', flush=True)
        for name, selected in [('crew-gallery', entries[:8]), ('outfit-gallery', entries[8:])]:
            pictures = ''.join(f'<img src="data:image/png;base64,{base64.b64encode((output / (slug + ".png")).read_bytes()).decode()}">' for slug, _ in selected)
            page.set_viewport_size({'width': 1920, 'height': 1080})
            layout = 'repeat(4,1fr)' if name == 'crew-gallery' else 'repeat(6,1fr)'
            extra = '' if name == 'crew-gallery' else 'img{grid-column:span 2}img:nth-child(4){grid-column:2/span 2}img:nth-child(5){grid-column:4/span 2}'
            page.set_content('<style>body{margin:0;background:#030910}main{display:grid;grid-template-columns:'+layout+';gap:0}img{width:100%;display:block}'+extra+'</style><main>'+pictures+'</main>')
            page.locator('main').screenshot(path=str(output / f'{name}.png'))
        browser.close()
        if errors:
            raise RuntimeError(errors)
    (output / 'README.txt').write_text('Void Compass Hatchling showcase / 5.6.8\n\nEight companion cards, five outfit cards, two galleries, and transparent PNG cutouts.\nAll images captured from the app\'s shared Three.js renderer.\n\nRecreate: .venv\\Scripts\\python.exe tools\\hatchling_showcase.py\n', encoding='utf-8')
    archive_path = output.parent / f'{output.name}.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(output.iterdir()):
            if file.suffix == '.png' or file.name == 'README.txt':
                archive.write(file, file.name)
    print(archive_path)


if __name__ == '__main__':
    main()
