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
