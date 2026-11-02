// Isolated synthetic financial/LLM test server only. Never run against production.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs');const out='reports/renovation';fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});try{
 const ctx=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const page=await ctx.newPage();page.setDefaultTimeout(20000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{const u=new URL(route.request().url());await route.continue({url:'http://127.0.0.1:8013'+u.pathname+u.search})});
 await ctx.addInitScript(()=>localStorage.setItem('lang','th'));
 await page.goto('http://127.0.0.1:8013/login');await page.getByLabel('อีเมล',{exact:true}).waitFor();await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:out+'/01-login.png',fullPage:true});
 const email=`renovation-${Date.now()}@example.com`,password='Renovation!123';
 await page.getByRole('tab',{name:'สมัครสมาชิก',exact:true}).click();await page.locator('#register-full-name').fill('ส้ม · UI Test');await page.locator('#register-email').fill(email);await page.locator('#register-password').fill(password);await page.getByRole('button',{name:'สร้างบัญชี',exact:true}).click();await page.waitForURL('http://127.0.0.1:8013/');
 const token=await page.evaluate(()=>localStorage.getItem('iar_access_token'));
 const api=async(path,data)=>{const r=await ctx.request.post('http://127.0.0.1:8013/api'+path,{headers:{Authorization:'Bearer '+token},data});if(!r.ok())throw Error(path+': '+await r.text());return r.json()};
 const reasonKey=`ui_${Date.now()}`;await api('/reasons',{reason_key:reasonKey,ticker:'AAPL',description:'รายได้ไม่ลดลงจากงวดเดียวกันปีก่อน',original_text:'Synthetic renovation test',rule_definition:{version:1,preset:'revenue_non_decreasing',evaluation_period:'quarterly'}});
 await api('/positions',{ticker:'AAPL',quantity:2,purchase_price:100,purchase_date:'2025-06-01',reason_keys:[reasonKey]});
 console.log('PASS registration and fixture purchase setup');
 for(const [name,path] of [['02-dashboard','/'],['03-portfolio','/portfolio'],['04-companies','/companies'],['05-company-detail','/companies?ticker=AAPL'],['06-watchlist','/watchlist'],['07-screener','/screener'],['08-agent','/agent'],['09-reports','/reports'],['10-settings','/user']]){
   await page.goto('http://127.0.0.1:8013'+path);await page.locator('main').waitFor();await page.waitForTimeout(900);
   if(await page.locator('main').evaluate(e=>e.scrollWidth>e.clientWidth+2))throw Error('Desktop overflow '+path);
   await page.screenshot({path:out+'/'+name+'.png',fullPage:true});console.log('PASS desktop route '+path);
 }
 await page.goto('http://127.0.0.1:8013/companies');const star=page.getByRole('button',{name:'เพิ่มรายการโปรด'});if(await star.count()){await star.first().click()}
 await page.goto('http://127.0.0.1:8013/reports');await page.getByRole('button',{name:'ดาวน์โหลด JSON'}).waitFor();const dl=page.waitForEvent('download');await page.getByRole('button',{name:'ดาวน์โหลด JSON'}).click();const download=await dl;const file=out+'/report-export.json';await download.saveAs(file);const data=JSON.parse(fs.readFileSync(file));if(data.company_report.ticker!=='AAPL')throw Error('Export ticker mismatch');console.log('PASS JSON export');
 await page.goto('http://127.0.0.1:8013/screener');await page.getByRole('button',{name:'เพิ่มเหตุผล',exact:true}).click();await page.waitForTimeout(250);await page.screenshot({path:out+'/11-reason-builder.png',fullPage:true});await page.getByRole('button',{name:'เขียนเหตุผลด้วยตัวเอง',exact:true}).click();await page.screenshot({path:out+'/12-natural-thesis.png',fullPage:true});await page.keyboard.press('Escape');
 await page.goto('http://127.0.0.1:8013/portfolio');await page.getByRole('button',{name:'บันทึกการซื้อ',exact:true}).first().click();
 await page.locator('#purchase-company').click();await page.getByRole('button',{name:'AAPL — Apple Inc.',exact:true}).click();
 await page.locator('#purchase-quantity').fill('1');await page.locator('#purchase-price').fill('123');await page.screenshot({path:out+'/13-purchase-details.png',fullPage:true});
 await page.getByRole('button',{name:'ถัดไป',exact:true}).click();await page.getByRole('button',{name:'เพิ่มเหตุผลใหม่',exact:true}).click();
 await page.getByRole('checkbox',{name:'ยืนยันว่ากฎนี้ตรงกับความคาดหวังของฉัน'}).check();const created=page.waitForResponse(r=>r.url().endsWith('/api/reasons')&&r.request().method()==='POST');await page.getByRole('button',{name:'บันทึกเหตุผล',exact:true}).click();if(!(await created).ok())throw Error('Inline reason creation failed');
 await page.getByRole('button',{name:'ถัดไป',exact:true}).click();await page.waitForTimeout(250);await page.screenshot({path:out+'/14-purchase-confirm.png',fullPage:true});
 const before=await ctx.request.get('http://127.0.0.1:8013/api/positions',{headers:{Authorization:'Bearer '+token}});if((await before.json()).length!==1)throw Error('Purchase submitted before confirmation');
 const bought=page.waitForResponse(r=>r.url().endsWith('/api/positions')&&r.request().method()==='POST');await page.getByRole('button',{name:'บันทึกการซื้อ',exact:true}).last().click();if(!(await bought).ok())throw Error('Wizard failed');console.log('PASS inline reason creation, selected reason key and explicit purchase confirmation');
 await page.goto('http://127.0.0.1:8013/reports');await page.getByRole('button',{name:'ดาวน์โหลด JSON'}).waitFor();await page.emulateMedia({media:'print'});await page.pdf({path:out+'/report-print.pdf',format:'A4',printBackground:true});await page.emulateMedia({media:'screen'});console.log('PASS printable report rendering');
 await page.evaluate(()=>{localStorage.setItem('reasoncheck.theme.v2','dark');localStorage.setItem('lang','en')});await page.goto('http://127.0.0.1:8013/companies');await page.waitForTimeout(500);if(await page.locator('html').getAttribute('data-theme')!=='dark')throw Error('Dark theme failed');await page.screenshot({path:out+'/15-dark-theme.png',fullPage:true});await page.evaluate(()=>localStorage.setItem('reasoncheck.theme.v2','light'));console.log('PASS persisted dark theme');
 await page.setViewportSize({width:390,height:844});
 for(const path of ['/','/portfolio','/companies','/screener','/agent','/reports','/user']){
   await page.goto('http://127.0.0.1:8013'+path);await page.locator('main').waitFor();await page.waitForTimeout(400);
   if(await page.locator('main').evaluate(e=>e.scrollWidth>e.clientWidth+2))throw Error('Mobile overflow '+path);
   await page.screenshot({path:out+'/mobile-'+(path.slice(1)||'dashboard')+'.png',fullPage:true});
 }
 await page.getByRole('button',{name:'เปิดเมนู',exact:true}).click();await page.locator('aside').getByRole('link',{name:'พอร์ต',exact:true}).click();await page.waitForURL('**/portfolio');console.log('PASS mobile routes, overflow checks and drawer navigation');
 if(errors.length)throw Error('Browser runtime errors: '+errors.join(';'));
 console.log('PASS no browser runtime errors; screenshots use synthetic data, not research evidence');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
