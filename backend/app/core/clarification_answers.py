"""Conservative mappings for explicit answers, never infer a missing expectation.
Relative periods are valid definitions; identifying the actual filing is retrieval work.
"""
import re

REVENUE={'รายได้รวมทั้งหมด','รายได้รวม','รายได้บริษัทเพิ่มขึ้น','total revenue','company revenue','consolidated revenue'}
COMPARISONS={'ไตรมาสก่อนหน้าทันที (qoq)':'ไตรมาสก่อนหน้าทันที (QoQ)',
 'ไตรมาสเดียวกันของปีก่อน (yoy)':'ไตรมาสเดียวกันของปีก่อน (YoY)',
 'ไตรมาสเดียวกันของปีก่อน':'ไตรมาสเดียวกันของปีก่อน (YoY)',
 'previous quarter':'previous quarter (QoQ)','same quarter last year':'same quarter last year (YoY)'}

def relative_period(answer):
    value=answer.strip()
    return bool(re.fullmatch(r'ไตรมาสล่าสุดที่(?:เผยแพร่แล้ว|มีงบการเงินเผยแพร่แล้ว|(?:[A-Za-z. ]+ )?เพิ่งประกาศไป(?:แล้ว)?)',value) or
                value.lower() in {'latest published quarter','latest reported quarter'})

def explicit_growth_preview(payload,company,original=""):
    """Only a single, fully answered standard revenue-growth choice flow.
    Unsupported/free-form/multi-claim cases continue through the existing LLM.
    Every answer must be accounted for; no dropping an extra business expectation.
    """
    if re.search(r'กำไร|หนี้|แข่งขัน|services|aws|azure|margin|debt|profit|และ| and ',original,re.I):return None
    answers=payload.get('answers',[])
    if len(payload.get('claims',[]))>1:return None
    scope=period=comparison=expectation=None
    for item in answers:
        value=item['answer'].strip();lower=value.lower()
        if lower in REVENUE:scope=value
        elif lower in COMPARISONS:comparison=COMPARISONS[lower]
        elif relative_period(value):
            # Preserve the selected option's meaning, including a purchase-date anchor if present.
            selected=next((o for o in item['question'].get('options',[]) if o['label']==value),None)
            period=value+((' — '+selected['explanation']) if selected else '')
        elif value in ('ไตรมาสถัดไป 1 ไตรมาส','next quarter'):
            period=value
        elif re.fullmatch(r'(?:เติบโต(?:ขึ้นเล็กน้อย|ปานกลาง|สูง)?\s*)?\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?\s*%',value):
            expectation=value
        elif value in ('ขอแค่เพิ่มขึ้นจากปีก่อนก็พอ','รายได้เพิ่มขึ้นจากปีก่อน','รายได้ไม่ลดลงจากปีก่อน','เพิ่มขึ้นจากไตรมาสก่อน','รายได้เพิ่มขึ้น','รายได้ไม่ลดลง'):
            expectation=value
        else:return None
    if not all((scope,period,comparison,expectation)):return None
    # A YoY phrase may not silently be reinterpreted as QoQ.
    if 'ปีก่อน' in expectation and 'QoQ' in comparison:return None
    claim={'claim_id':'C1','expectation':expectation,'scope':f'{company}: {scope}',
           'timeframe':period,'comparison_basis':comparison,
           'checkable_question':f'{scope}ของ {company} ใน {period} เป็นไปตามความคาดหวัง “{expectation}” เมื่อเทียบกับ {comparison} หรือไม่?',
           'evidence_standard':'รายได้รวมจากงบ 10-Q/10-K ของบริษัทเดียวกัน ในงวดที่เลือกและงวดเปรียบเทียบ ใช้หน่วยและขอบเขตบัญชีเดียวกัน',
           'evidence_queries':['consolidated revenue net sales quarterly comparison'],
           'ambiguities':[], 'limitations':['ยังไม่ใช่ผลตรวจสอบงบ ต้องระบุงวดจริงจากวันที่อ้างอิงและตรวจหลักฐานหลังยืนยัน']}
    return {'understood':f'{company}: {scope} · {period} · เทียบ {comparison} · ความคาดหวัง: {expectation}',
            'claims':[claim],'question':None,'missing':[],'explanation':'สรุปจากคำตอบที่คุณเลือก โปรดตรวจความหมายก่อนยืนยัน ชื่อไตรมาสจริงจะตรวจจากเอกสารในขั้นตรวจหลักฐาน',
            'limit_reached':False,'resolution_method':'explicit-answer-mapping-v1'}
