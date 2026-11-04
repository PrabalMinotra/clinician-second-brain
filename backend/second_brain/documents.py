"""Deterministic administrative drafting. No inferred clinical facts or advice."""
import hashlib,json,re
TYPES={'referral':'Referral letter','patient_handout':'Patient information sheet','mdt_note':'Tumour-board note'}
FIELDS={'age':'Age at encounter','sex':'Recorded sex','diagnosis':'Recorded diagnosis','stage':'Clinician-recorded stage','site':'Site','pathology':'Pathology','imaging':'Imaging','allergies':'Allergies','medications':'Current medicines','comorbidities':'Other conditions','prior_treatment':'Prior treatment','performance_status':'Performance status','mdt_plan':'Clinician-recorded MDT plan','follow_up':'Follow-up arrangements'}

def digest(payload): return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def make_draft(case_id,case_data,kind,sources,template=None):
    facts=case_data['facts']; paragraphs=[]
    def add(title,text,refs=[],clinical=True):
        paragraphs.append({'id':f'p{len(paragraphs)+1}','title':title,'text':text,'original':text,'source_ids':refs,'citation_status':'case_fact' if clinical else 'not_applicable','review_status':'pending'})
    ref='snapshot:'+str(case_id)
    if template:
        for key in template.fields:
            value = facts.get(key, '').strip()
            if not value or value.lower().startswith('not recorded'):
                value = f'[MISSING: {FIELDS[key]}]'
            add(FIELDS[key], value, [ref])
    elif kind=='referral':
        add('Purpose','Referral for review of the documented oncology history and clinician-recorded MDT plan.',[],False)
        for key in ['age','sex','diagnosis','site','stage','pathology','imaging','prior_treatment','allergies','medications','comorbidities','performance_status','mdt_plan','follow_up']:
            add(FIELDS[key],facts.get(key) or f'[MISSING: {FIELDS[key]}]',[ref])
    elif kind=='patient_handout':
        add('About this sheet','This sheet records what your care team has written. Please ask your care team to explain any words or details you do not understand.',[],False)
        for key,title in [('diagnosis','What your care team recorded'),('mdt_plan','The plan written by your care team'),('medications','Your listed medicines'),('allergies','Your listed allergies'),('follow_up','Your next visit')]:
            add(title,facts.get(key) or '[MISSING: '+FIELDS[key]+']',[ref])
        add('Before you leave','Ask your care team: Who can I contact? When is my next visit? Can you explain the plan in simple words?',[],False)
    else:
        add('Meeting record',f"Meeting date: {case_data.get('meeting_date') or '[MISSING: meeting date]'}. Attendees: {case_data.get('attendees') or '[MISSING: attendees]' }.",[ref])
        for key in ['age','sex','diagnosis','stage','site','pathology','imaging','prior_treatment','comorbidities','allergies','medications','performance_status','mdt_plan','follow_up']:
            add(FIELDS[key],facts.get(key) or f'[MISSING: {FIELDS[key]}]',[ref])
    # Longitudinal source excerpts are copied exactly, never interpreted.
    for source in sources:
        add('Reviewed history · '+source['title'],source['text'],[source['id']])
    return {**({'template_title': template.title, 'required_fields': template.fields} if template else {}), 'paragraphs':paragraphs,'case_snapshot':case_data,'case_revision':case_data.get('revision',1),'engine':'Deterministic templates · no LLM','type':kind,'missing':[label for key,label in FIELDS.items() if not facts.get(key)],'references':{ref:{'title':'Frozen clinician-confirmed case facts','text':json.dumps(case_data,indent=2)},**{s['id']:{'title':s['title'],'text':s['text']} for s in sources}}}

def readability(paragraphs):
    text=' '.join(p['text'] for p in paragraphs)
    words=re.findall(r"[A-Za-z]+",text)
    sentences=max(1,len(re.findall(r'[.!?]+',text)))
    syllables=sum(max(1,len(re.findall(r'[aeiouy]+',w.lower()))-int(w.lower().endswith('e'))) for w in words)
    grade=round(max(0,.39*len(words)/sentences+11.8*syllables/max(1,len(words))-15.59),1)
    return {'grade':grade,'method':'Approximate English Flesch–Kincaid proxy; clinical terms copied unchanged','target':6,'words':len(words),'validated':False}
