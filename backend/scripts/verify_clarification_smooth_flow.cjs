// Real browser + test DB. Deliberately delay/drop POST responses; never use live AI.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base='http://127.0.0.1:8015';
(async()=>{const browser=await chromium.launch({headless:true});try{
 for(const mode of ['delayed-response','lost-response','resume-processing']){
  const context=await browser.newContext({viewport:{width:1440,height:1100}});const page=await context.newPage();
  const reg=await context.request.post(base+'/api/auth/register',{data:{email:`smooth-${mode}-${Date.now()}@example.com`,password:'SmoothFlowTest!123',full_name:'Synthetic flow test'}});
  if(!reg.ok())throw Error(await reg.text());const token=(await reg.json()).access_token;
  await context.addInitScript(t=>{localStorage.setItem('iar_access_token',t);localStorage.setItem('lang','th')},token);
  const open=async()=>{await page.goto(base+'/screener');await page.getByRole('button',{name:'เพิ่มเหตุผล',exact:true}).click();await page.getByRole('button',{name:'เขียนเหตุผลด้วยตัวเอง',exact:true}).click()};
  await open();await page.getByLabel('Original thesis',{exact:true}).fill('ซื้อ Apple เพราะคิดว่าน่าจะเติบโตดี');
  await page.getByRole('button',{name:'ช่วยทำให้เหตุผลชัดเจน',exact:true}).click();await page.getByLabel('Clarification answer').waitFor();
  let submitted=0,reads=0,draftId;
  page.on('request',r=>{if(r.url().includes('/theses/clarifications/')){if(r.method()==='GET')reads++;else if(r.postDataJSON()?.action==='answer'){submitted++;draftId=r.url().split('/').pop()}}});
  if(mode!=='resume-processing')await page.route('**/api/theses/clarifications/*',async route=>{
   const r=route.request();if(r.method()!=='POST'||r.postDataJSON()?.action!=='answer')return route.continue();
   const response=await route.fetch();
   if(mode==='lost-response')return route.abort('failed');
   await new Promise(resolve=>setTimeout(resolve,20000));
   try{await route.fulfill({response})}catch{/* poll already delivered the result and cancelled POST */}
  });
  await page.getByLabel('Clarification answer').fill('รายได้รวมเพิ่มจากไตรมาสเดียวกันปีก่อน ตรวจเป็นรายไตรมาส');
  const started=Date.now();await page.getByRole('button',{name:'ส่งคำตอบ',exact:true}).click();
  await page.getByText('กำลังอ่านคำตอบของคุณ',{exact:true}).waitFor();
  if(mode==='delayed-response')await page.screenshot({path:'reports/clarification_validation/03-sending-answer.png',fullPage:true});
  if(mode==='resume-processing'){
   // Wait for durable acceptance before closing the form, then reopen without a reload.
   let accepted=false;
   for(let i=0;i<12;i++){
    const r=await context.request.get(base+'/api/theses/clarifications/'+draftId,{headers:{Authorization:'Bearer '+token}});
    if((await r.json()).state==='PROCESSING'){accepted=true;break}
    await new Promise(resolve=>setTimeout(resolve,100));
   }
   if(!accepted)throw Error('Did not observe processing state');
   await page.goto(base+'/companies');await open();
  }
  await page.getByRole('button',{name:'ยืนยันและบันทึกเหตุผล',exact:true}).waitFor({timeout:14000});
  const elapsed=Date.now()-started;
  if(submitted!==1)throw Error('Paid answer resubmitted: '+submitted);
  if(!reads)throw Error('Did not poll saved result');
  if(mode==='delayed-response'&&elapsed>=20000)throw Error('Still waited on stalled POST');
  if(await page.getByRole('button',{name:'ยืนยันและบันทึกเหตุผล',exact:true}).isEnabled())throw Error('Confirmation bypass');
  if(await page.getByText('กำลังอ่านคำตอบของคุณ',{exact:true}).count())throw Error('Loading never cleared');
  console.log(`PASS ${mode}: next step in ${elapsed}ms; answer POSTs=${submitted}; status reads=${reads}; no refresh needed`);
  await context.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
