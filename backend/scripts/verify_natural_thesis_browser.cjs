// Run only against natural_browser_fixture (synthetic model/SEC), port 8013.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
const browser=await chromium.launch({headless:true});try{
const context=await browser.newContext({viewport:{width:1440,height:1100}});const page=await context.newPage();
await page.route('**/api/**',async route=>{const u=new URL(route.request().url());await route.continue({url:'http://127.0.0.1:8013'+u.pathname+u.search})});
const auth=await context.request.post('http://127.0.0.1:8013/api/auth/register',{data:{email:`nl-ui-${Date.now()}@example.com`,password:'NaturalTest!123',full_name:'Synthetic Natural UI Test'}});if(!auth.ok())throw Error(await auth.text());
const token=(await auth.json()).access_token;
await context.addInitScript(t=>{localStorage.setItem('iar_access_token',t);localStorage.setItem('lang','th')},token);
await page.goto('http://127.0.0.1:8013/screener');await page.getByRole('button',{name:'เพิ่มเหตุผล',exact:true}).click();
await page.getByRole('button',{name:'เขียนเหตุผลด้วยตัวเอง',exact:true}).click();
await page.getByLabel('Original thesis',{exact:true}).fill('ซื้อ Apple เพราะ Services เติบโตต่อเนื่องและช่วยรักษากำไร');
await page.getByRole('button',{name:'ตีความด้วย AI',exact:true}).click();await page.getByText('C1: Services เติบโต',{exact:true}).waitFor();
await page.screenshot({path:'reports/natural_thesis_validation/01-interpretation.png',fullPage:true});
const save=page.getByRole('button',{name:'ยืนยันและบันทึกเวอร์ชัน',exact:true});if(await save.isEnabled())throw Error('Confirmation bypass');
await page.getByRole('checkbox',{name:'ฉันตรวจและยืนยันความหมายทุก Claim แล้ว',exact:true}).check();
const saved=page.waitForResponse(r=>r.url().endsWith('/api/theses/confirm')&&r.request().method()==='POST');await save.click();const sr=await saved;if(!sr.ok())throw Error(await sr.text());const original=await sr.json();
console.log('PASS natural input, interpretation ambiguity, mandatory confirmation, v1 save');
const row=page.getByRole('row').filter({hasText:'ซื้อ Apple เพราะ Services เติบโตต่อเนื่องและช่วยรักษากำไร'});await row.getByRole('button',{name:'Evidence',exact:true}).click();
await page.getByLabel('Period start',{exact:true}).fill('2025-01-01');await page.getByLabel('Period end',{exact:true}).fill('2025-03-31');await page.getByLabel('Evaluation date',{exact:true}).fill('2025-06-01');
await page.getByRole('checkbox',{name:/ยอมรับค่า LLM/}).check();const investigation=page.waitForResponse(r=>r.url().includes('/investigate')&&r.request().method()==='POST');
await page.getByRole('button',{name:'ตรวจหลักฐาน / ตรวจซ้ำ',exact:true}).click();const ir=await investigation;if(!ir.ok())throw Error(await ir.text());const result=await ir.json();
if(result.rule_status!=='NOT_EVALUATED'||result.evidence_status!=='INSUFFICIENT')throw Error('Ambiguity status incorrect');
await page.getByText('What We Know — รู้อะไรแล้ว',{exact:true}).waitFor();await page.screenshot({path:'reports/natural_thesis_validation/02-evidence.png',fullPage:true});
console.log('PASS adaptive investigation, exact citation display, three-part output; ambiguity remains INSUFFICIENT');
await page.goto('http://127.0.0.1:8013/?ticker=AAPL');await page.locator('#purchase-quantity').fill('1');await page.locator('#purchase-price').fill('100');await page.getByRole('button',{name:'ถัดไป',exact:true}).click();await page.getByRole('checkbox',{name:/ซื้อ Apple เพราะ Services เติบโตต่อเนื่องและช่วยรักษากำไร/}).check();
await page.getByRole('button',{name:'ถัดไป',exact:true}).click();
const purchase=page.waitForResponse(r=>r.url().endsWith('/api/positions')&&r.request().method()==='POST');await page.getByRole('button',{name:'บันทึกการซื้อ',exact:true}).click();if(!(await purchase).ok())throw Error('Purchase failed');
await page.goto('http://127.0.0.1:8013/screener');await page.getByRole('row').filter({hasText:'ซื้อ Apple เพราะ Services เติบโตต่อเนื่องและช่วยรักษากำไร'}).getByRole('button',{name:'แก้ไข',exact:true}).click();
await page.getByLabel('Original thesis',{exact:true}).fill('ซื้อ Apple เพราะเชื่อว่าธุรกิจ Services จะยังเติบโต');await page.getByRole('button',{name:'ตีความด้วย AI',exact:true}).click();await page.getByRole('checkbox',{name:'ฉันตรวจและยืนยันความหมายทุก Claim แล้ว',exact:true}).check();
const edited=page.waitForResponse(r=>r.url().endsWith('/api/theses/confirm')&&r.request().method()==='POST');await page.getByRole('button',{name:'ยืนยันและบันทึกเวอร์ชัน',exact:true}).click();const edit=await (await edited).json();if(edit.rule_definition.version_no!==2)throw Error('Version not appended');
const p=await context.request.get('http://127.0.0.1:8013/api/positions',{headers:{Authorization:'Bearer '+token}});const snapshot=(await p.json())[0].reasons[0].reason_snapshot;if(snapshot.rule_definition.thesis_version_id!==original.rule_definition.thesis_version_id)throw Error('Snapshot changed');
console.log('PASS natural purchase, edited v2, immutable purchase v1 snapshot');
await page.goto('http://127.0.0.1:8013/agent');await page.getByText('Natural-language Thesis · ตรวจหลักฐานเหตุผลเชิงธุรกิจ',{exact:true}).waitFor();await page.screenshot({path:'reports/natural_thesis_validation/03-agent-entry.png',fullPage:true});console.log('PASS Agent page natural evidence entry');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
