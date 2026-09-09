const {chromium} = require('./nav-preview-tools/node_modules/playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:1100}});
    await page.setContent('<main style="padding:24px;height:100vh;overflow:auto"><h1>Planet materials</h1><div id="planet-materials-workspace"></div></main>');
    await page.addStyleTag({path:'web/dashboard/styles.css'});
    const app = fs.readFileSync('web/dashboard/app.js','utf8');
    const constants = ['byId','number','escapeHtml','numeric'].map(name => app.split('\n').find(line => line.startsWith(`const ${name} =`))).join('\n');
    const helpers = app.slice(app.indexOf('function workspaceCard('), app.indexOf('function workspaceTable('));
    const renderer = app.slice(app.indexOf('function renderPlanetMaterialsWorkspace('), app.indexOf('function renderExploreWorkspace('));
    await page.addScriptTag({content: constants + '\n' + helpers + '\nlet workspaceFingerprints={}; let calls=[]; const showToast=()=>{}; const command=async(action,payload)=>{calls.push({action,payload}); return true};\n' + renderer});
    await page.evaluate(() => renderPlanetMaterialsWorkspace({profile_key:'test',system:'Sol',body:'Moon',current_position:{system:'Sol',body:'Moon',latitude:0,longitude:-180},mining_catalogue:['Diamond','Ruby','Sapphire','Bastnasite'],new_mining_materials:['Diamond','Ruby','Sapphire','Bastnasite'],bodies:[{system:'Sol',body:'Moon',class:'Rocky body',volcanism:'Silicate magma',temperature:320,gravity:0.16,materials:[{name:'Iron',percent:18.2},{name:'Yttrium',percent:1.1}]}],sites:[{id:1,system:'Sol',body:'Moon',name:'Western deposit',latitude:0,longitude:-180,materials:'Diamond, Osmium',notes:'Dense deposits'}],resources:{bodies:[{body:'Moon',class:'Rocky body',landable:true,mining_locations:3,materials:[{name:'Iron',percent:18.2},{name:'Yttrium',percent:1.1,rare:true}]}]}}));
    const form = page.locator('form').first();
    await page.evaluate(() => {
      const root=document.querySelector('#planet-materials-workspace');
      root.currentPosition.body_details={system:'Sol',body:'Moon',class:'Rocky body',materials:[{name:'Iron',percent:18.2}]};
    });
    await form.locator('[data-current-coordinates]').click();
    assert.equal(JSON.parse(await form.locator('[name="body_details"]').inputValue()).materials[0].percent,18.2);
    assert.equal(await form.locator('[name="latitude"]').inputValue(),'0');
    assert.equal(await form.locator('[name="longitude"]').inputValue(),'-180');
    await form.locator('[data-material-choice]').selectOption('Bastnasite');
    await form.locator('[data-material-choice]').selectOption('Bastnasite');
    assert.equal(await form.locator('[name="materials"]').inputValue(),'Bastnasite');
    await page.evaluate(() => updatePlanetMaterialsLive(document.querySelector('#planet-materials-workspace'),{current_position:{system:'Sol',body:'Moon',latitude:12,longitude:34,body_details:{system:'Sol',body:'Moon'}}}));
    await form.locator('[data-current-coordinates]').click();
    assert.equal(await form.locator('[name="latitude"]').inputValue(),'12');
    assert.equal(await form.locator('[name="materials"]').inputValue(),'Bastnasite');
    await page.evaluate(() => updatePlanetMaterialsLive(document.querySelector('#planet-materials-workspace'),{current_position:null}));
    assert.equal(await form.locator('[data-current-coordinates]').isDisabled(),true);
    await page.locator('[data-atlas-view="heat"]').click();
    assert.equal(await page.locator('[data-atlas-panel="heat"]').isVisible(),true);
    await page.locator('[data-atlas-view="material"]').click();
    assert.equal(await page.locator('[data-atlas-panel="material"]').isVisible(),true);
    await page.locator('[data-atlas-view="body"]').click();
    for (const [name,value] of Object.entries({body:'Moon',name:'East ridge',latitude:'-45.5',longitude:'120.25',materials:'Ruby, Sapphire'})) await form.locator(`[name="${name}"]`).fill(value);
    await form.locator('[type="submit"]').click();
    const saved = await page.evaluate(()=>calls[0]);
    assert.equal(saved.payload.latitude,'-45.5');
    assert.equal(saved.payload.longitude,'120.25');
    assert.equal(saved.payload.profile_key,'test');
    assert.equal(saved.action,'workspace');
    await page.locator('summary').click();
    await page.locator('form').nth(1).locator('[name="longitude"]').fill('90');
    await page.locator('form').nth(1).locator('[type="submit"]').click();
    assert.equal(await page.evaluate(()=>calls[1].payload.id),'1');
    assert.equal(await page.evaluate(()=>calls[1].payload.longitude),'90');
    await page.locator('#planet-site-filter').fill('absent');
    assert.equal(await page.locator('#planet-site-list details:visible').count(),0);
    await page.locator('#planet-site-filter').fill('osmium');
    assert.equal(await page.locator('#planet-site-list details:visible').count(),1);
    await page.evaluate(()=>document.querySelector('main').scrollTop=0);
    await page.screenshot({path:'tests/planet-materials-preview.png',fullPage:true});
    page.on('dialog', dialog=>dialog.accept());
    await page.locator('[data-site-delete]').click();
    assert.equal(await page.evaluate(()=>calls[2].payload.operation),'delete_site');
    for (const width of [800,1280]) {
      await page.setViewportSize({width,height:1100});
      assert.equal(await page.evaluate(()=>document.querySelector('main').scrollWidth <= innerWidth),true);
    }
    console.log('Planet materials browser checks passed: add, edit, delete, filter, coordinates, profile identity and responsive width.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
