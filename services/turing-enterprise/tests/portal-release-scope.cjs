/* Browser transport fixtures only: no real SSO, TURING execution or actuation. */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH,headless:true,args:['--no-sandbox']});
 const root=path.resolve(__dirname,'../src/hyba_turing_service/static');
 const out=process.env.TURING_PREVIEW_DIR;fs.mkdirSync(out,{recursive:true});
 const summary=[];const axe=process.env.AXE_CORE_PATH;
 for(const width of [1280,390]){
  const page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true});
  const errors=[],queries=[];let cancels=0,delayInspection=false,held=null;
  page.on('pageerror',e=>errors.push(e.message));
  const report={job:'first',state:'completed',report:{verdict:'PASS',certificate:{fixture:true},payload:{amplitudes:['fixture-not-computation']}}};
  await page.route('https://turing.test/**',async route=>{
   const u=new URL(route.request().url()),p=u.pathname;let data;
   if(p.startsWith('/assets/'))return route.fulfill({path:path.join(root,path.basename(p))});
   if(p==='/workspace')return route.fulfill({path:path.join(root,'portal.html'),contentType:'text/html'});
   if(p==='/api/session')data={subject:'fixture-user',memberships:[{tenant:'a',role:'analyst'},{tenant:'b',role:'analyst'}],csrf:'fixture'};
   else if(p.endsWith('/overview'))data={allocated:2,available:1,in_flight:1,consumed:0};
   else if(p.endsWith('/cancel')){cancels++;data={state:'cancelled'};}
   else if(p.endsWith('/jobs/first')){
    if(delayInspection){held=route;return;}
    data=report;
   }else if(p.endsWith('/jobs')){
    queries.push({tenant:p.split('/')[3],params:Object.fromEntries(u.searchParams)});
    const second=u.searchParams.get('after')==='first',b=p.includes('/b/');
    data={jobs:[{job:b?'tenant-b':second?'second':'first',state:'admitted',project:'p'}],next_cursor:second||b?null:'first'};
   }else data={};
   await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('https://turing.test/workspace');
  await page.getByRole('button',{name:'Next page',exact:true}).waitFor();
  await page.getByRole('button',{name:'Next page',exact:true}).click();
  await page.getByRole('cell',{name:'second',exact:true}).waitFor();assert.equal(queries.at(-1).params.after,'first');
  assert.equal(await page.getByRole('button',{name:'Next page',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Previous page',exact:true}).click();
  await page.getByRole('cell',{name:'first',exact:true}).waitFor();assert.equal(queries.at(-1).params.after,'');
  await page.getByLabel('Search job identifier',{exact:true}).fill('FiR');
  await page.getByLabel('State (admitted, running, completed, failed, cancelled, unknown)',{exact:true}).fill('admitted');
  await page.getByLabel('Project identifier filter',{exact:true}).fill('p');
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  await page.waitForTimeout(100);assert.equal(queries.at(-1).params.q,'FiR');assert.equal(queries.at(-1).params.project,'p');assert.equal(queries.at(-1).params.state,'admitted');assert.equal(queries.at(-1).params.after,'');
  page.once('dialog',d=>d.dismiss());await page.getByRole('button',{name:'Request cancellation',exact:true}).click();assert.equal(cancels,0);
  page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Request cancellation',exact:true}).click();
  await page.waitForTimeout(100);assert.equal(cancels,1);
  await page.getByRole('button',{name:'Inspect result',exact:true}).click();
  await page.getByRole('button',{name:'Export returned report JSON',exact:true}).waitFor();
  const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export returned report JSON',exact:true}).click();
  const download=await downloadPromise;assert.deepEqual(JSON.parse(fs.readFileSync(await download.path(),'utf8')),report);
  await page.getByRole('button',{name:'Refresh',exact:true}).click();await page.getByRole('button',{name:'Inspect result',exact:true}).waitFor();
  delayInspection=true;await page.getByRole('button',{name:'Inspect result',exact:true}).click();
  await page.waitForFunction(()=>true);for(let i=0;!held&&i<20;i++)await page.waitForTimeout(10);assert.ok(held);
  await page.locator('#tenant').selectOption('b');await page.getByRole('cell',{name:'tenant-b',exact:true}).waitFor();
  await held.fulfill({contentType:'application/json',body:JSON.stringify(report)});await page.waitForTimeout(100);
  assert.equal(await page.getByRole('button',{name:'Export returned report JSON',exact:true}).count(),0);
  assert.equal(queries.at(-1).params.q,'');assert.equal(queries.at(-1).params.after,'');
  assert.equal(await page.locator('#data').innerText().then(x=>x.includes('tenant-b')),true);
  let violations=[];
  if(axe){await page.addScriptTag({path:axe});const result=await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}));violations=result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}));}
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  const result={width,fixture:true,interactionGroups:['history-cursors','server-filter-query','cancel-confirmation','unchanged-export','stale-tenant-inspection','tenant-filter-reset'],errors,overflow,axeRun:!!axe,violations};summary.push(result);
  fs.writeFileSync(path.join(out,'release-scope-qa.json'),JSON.stringify(summary,null,2));
  assert.deepEqual(errors,[]);assert.equal(overflow,false);assert.deepEqual(violations,[]);
  await page.close();
 }
 await browser.close();console.log('2 viewport fixture workflows passed; 12 interaction groups; automated axe scans only.');process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
