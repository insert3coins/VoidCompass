# Third-Party Notices

## three.js

The offline HTML Galactic Atlas bundles three.js 0.185.1 and its OrbitControls
addon from [three.js](https://threejs.org/). They provide the local WebGL 2
renderer and camera controls; Void Compass does not load the library from a CDN.

MIT License

Copyright © 2010-2026 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## ORRERY

The v5.4.2.1 Live System Orrery derives orbital-model and display ideas from
[ORRERY](https://github.com/TerjeRu/orrery). Void Compass uses its own
journal-backed Python model and bundled Canvas renderer rather than distributing
ORRERY's Electron application or Three.js code.

MIT License

Copyright (c) 2026 Terje

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Elite Cartoon Ship Vectors

`Images/ships` includes the 2025 **Elite Cartoon Ship Vectors** collection by
[CMDR Qohen Leth](https://www.reddit.com/user/CMDR_Qohen_Leth/), made from
blueprints by CMDR Arithon and the creator's own tracing. The upstream bundle
contains 45 human spacecraft through the Type-11 Prospector and a Cyclops
illustration in PNG, SVG and PDF forms; Void Compass includes its PNG artwork.

Source and attribution:
[Elite Cartoon Ship Vectors — updated 2025](https://www.reddit.com/r/EliteDangerous/comments/1mnmolv/elite_cartoon_ship_vectors_elite_ships_colouring/)

Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International:
<https://creativecommons.org/licenses/by-nc-sa/4.0/>

This artwork is separately licensed, is not covered by Void Compass' GPL-3.0
software licence, and retains its non-commercial and share-alike restrictions.
The post-2025 and auxiliary-vehicle illustrations identified in
`Images/ships/README.md` are Void Compass additions and are not represented as
part of CMDR Qohen Leth's original bundle.

## pywebview

The Windows HTML command deck and cockpit overlay suite use [pywebview](https://pywebview.flowrl.com/)
to host their bundled, offline HTML/CSS/JavaScript UI in the installed Microsoft
Edge WebView2 runtime. No remote page or CDN is loaded by the overlays.

BSD 3-Clause License

Copyright (c) 2014-2017, Roman Sirokov
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its contributors
  may be used to endorse or promote products derived from this software without
  specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## EDMC-BioScan

`bio_requirements.py` contains a merged copy of the species ruleset modules from
[EDMC-BioScan](https://github.com/Silarn/EDMC-BioScan) (`src/bio_scan/bio_data/rulesets/`),
pinned at commit `5f0d2e445a95681bf2e85223f883d5c552a7726b`. They supply the
published spawn requirements — body type, atmosphere, gravity, temperature,
pressure, volcanism and further context — for 116 organic species across 20
Codex genus identifiers, together with their sample values, and the region,
Guardian-nebula and Sinuous Tuber zone definitions from the same commit's
`bio_data/regions.py`. Its region groups are expressed as Codex region
identifiers 1-42, matching the offline region map below.

EDMC-BioScan is licensed under the GNU General Public License version 2 or
later. VoidCompass exercises that "or later" option and uses the data under the
GNU General Public License version 3, matching this project's own licence. The
complete GPL-3.0 text is in [LICENSE](LICENSE).

Copyright (c) Silarn and the EDMC-BioScan contributors.

The upstream project credits the Canonn Research Group, the community Codex NSP
and Bio requirements spreadsheet, and the Deep Space Network for the underlying
observations. Upstream accuracy caveats are preserved verbatim in the vendored
data so predictions do not claim more confidence than the observations support.


## EliteDangerousRegionMap

VoidCompass includes a compressed copy of `RegionMapData.json` from
[EliteDangerousRegionMap](https://github.com/klightspeed/EliteDangerousRegionMap),
pinned at commit `6c1191a58e1e593966f44f16235ab39d1ad24d84`. It supplies the mapped
boundaries and names of the 42 Elite Dangerous Codex regions.

MIT License

Copyright (c) 2020 Ben Peddell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
