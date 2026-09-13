# Third-Party Notices


## EDSY ship and module data

The v5.4.6 Build Planner bundles a normalized snapshot of the Elite Dangerous
ship, module, Engineering blueprint, experimental-effect and material database
maintained by [EDSY](https://github.com/taleden/EDSY), pinned at commit
`9cd829062217036184ea9ec79ee30934d235aca8`.

VoidCompass contains its own offline calculation, storage and interface code;
it does not include EDSY's application source. EDSY is distributed under the
Creative Commons Attribution-NonCommercial 4.0 International licence. The database
is separately attributed and is used by this unofficial, non-commercial fan
project. Elite Dangerous names and game data remain the property of Frontier
Developments plc.

Copyright © 2015-2025 taleden. Licence:
<https://creativecommons.org/licenses/by-nc/4.0/>

## Elite Dangerous Character Portraits

`assets/images/people/powerplay` includes official, non-fanmade Elite Dangerous
Powerplay character artwork. Nine portraits were sourced from
[Venefilyn/EDAssets](https://github.com/Venefilyn/EDAssets), pinned at commit
`5a9b2f82796fc65abace9439aea000155f1e6eb3`. The current Powerplay 2.0
portraits missing from that collection (Jerome Archer, Nakato Kaine and Yuri
Grom) were sourced from the Elite Dangerous Wiki's Frontier artwork archive.

`assets/images/people/engineers` includes the in-game Engineer portraits maintained
by [EDDiscovery](https://github.com/EDDiscovery/EDDiscovery), pinned at commit
`758d69d4ecee70974c24f5e69c142994b565cfd9`.

The EDAssets repository is MIT-licensed and EDDiscovery is Apache-2.0-licensed.
The character designs and original game artwork remain the property of
Frontier Developments plc and are used here by an unofficial fan project.

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
