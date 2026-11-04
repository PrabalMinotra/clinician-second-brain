"""Local extractive record queries: every returned clinical word is a literal record excerpt.

This is retrieval, not an LLM, diagnostic system or clinical recommendation engine.
No query text is persisted or transmitted to external services.
"""
import math,re
from .documents import FIELDS
from .privacy import redact

FIELD_TERMS={
 'age':r'\bage\b|\bold\b',
 'sex':r'\bsex\b|\bgender\b',
 'diagnosis':r'\bdiagnos(?:is|es|ed)\b|\bhistology\b',
 'stage':r'\bstag(?:e|ing)\b|\btnm\b',
 'site':r'\bsite\b|\blocation\b|\bprimary\b',
 'pathology':r'\bpathology\b|\bbiopsy\b|\bhistopathology\b|\bdifferentiated\b',
 'imaging':r'\bimaging\b|\bscans?\b|\bmri\b|\bct\b|\bradiology\b|\bnodes?\b|\bchest\b',
 'allergies':r'\ballerg(?:y|ies|ic)\b',
 'medications':r'\bmedication\w*\b|\bmedicines?\b|\bdrugs?\b',
 'comorbidities':r'\bcomorbid\w*\b|\bother conditions\b|\bmedical history\b',
 'prior_treatment':r'\bprior treatment\b|\bprevious treatment\b|\breceived\b|\bcompleted\b|\bundergone\b|\bperformed\b|\btreatment history\b',
 'performance_status':r'\bperformance\b|\becog\b|\bkarnofsky\b',
 'mdt_plan':r'\bplan(?:ned)?\b|\bmdt\b|\bconsensus\b|\btumou?r.board\b',
 'follow_up':r'\bfollow.up\b|\bappointments?\b|\bnext visit\b|\bfollowup\b',
}
CATEGORIES={'imaging':'Imaging report','pathology':'Pathology','medications':'Medication list','prior_treatment':'Treatment record','follow_up':'Follow-up'}
STOP=set('a an the what which who when where why how is are was were has have had do does did this that these those it its for from with and or to of in on at by me show tell please patient patients record records recorded documented notes note about any all their his her can list find summary summarise summarize history latest recent'.split())
# These patterns affect only the response mode. Even unrecognised requests can only
# retrieve literal excerpts, so safety does not rely on this lexicon being complete.
INFERENCE=re.compile(r'\b(?:recommend\w*|should|suggest\w*|predict\w*|prognos\w*|survival|diagnose|interpret\w*|infer\w*|restag\w*|calculate|prescrib\w*|best treatment|optimal|differential|likely|probab\w*|chance|what dose|which therapy|is this cancer|does .{0,60}mean|why .{0,60}(?:chosen|treatment|plan)|would you|can .{0,30}(?:take|tolerate)|what stage is)\b',re.I)

def tokens(text):return [w for w in re.findall(r'[a-z0-9]+',text.lower()) if len(w)>1 and w not in STOP]
def unknown(text):return not text.strip() or bool(re.match(r'(?i)\s*(?:not recorded|not documented|unknown|\[missing:)',text))
def excerpt(text,terms,limit=1400):
    if len(text)<=limit:return text,0,len(text)
    candidates=[m.start() for t in terms for m in re.finditer(r'(?i)\b'+re.escape(t)+r'\b',text)]
    start=max(0,min(candidates,default=0)-200)
    if start:
        boundary=text.find('\n',start,min(len(text),start+200))
        if boundary!=-1:start=boundary+1
    end=min(len(text),start+limit)
    if end<len(text):
        boundary=max(text.rfind('\n',start,end),text.rfind('. ',start,end))
        if boundary>start+limit//2:end=boundary+1
    return text[start:end],start,end

def answer(question,case_id,revision,case_data,sources):
    clean,removed=redact(question)
    accepted=[s for s in sources if s['status']=='accepted' and s.get('privacy_reviewed') is True]
    pending=sum(s['status']=='pending' for s in sources)
    base={'case_id':str(case_id),'case_revision':revision,'engine':'Local extractive record search · no LLM','question':clean,'query_identifiers_screened':sum(removed.values()),'excluded_pending':pending,'items':[],'not_recorded':[],'has_more':False,'warnings':['Answers contain recorded excerpts, not independent clinical conclusions. A plan is not evidence that treatment occurred.','Only supplied, clinician-confirmed facts and accepted privacy-reviewed sources are searched. The patient history may be incomplete.']}
    if INFERENCE.search(clean):
        return {**base,'status':'outside_scope','answer':'I can retrieve recorded history, reports and the clinician-written plan. I cannot interpret an image, diagnose, infer a stage, recommend treatment or predict an outcome. Ask what is documented in the record instead.'}
    lower=clean.lower();terms=tokens(clean)
    summary=bool(re.search(r'\b(?:summari[sz]e|summary|overview|timeline)\b|\bfull history\b',lower))
    wanted=[key for key,pattern in FIELD_TERMS.items() if re.search(pattern,lower)]
    # A completed-treatment question must not be answered with a planned procedure.
    completed='prior_treatment' in wanted
    if completed and not re.search(r'\b(?:plan|planned|mdt)\b',lower):wanted=[k for k in wanted if k!='mdt_plan']
    facts=case_data.get('facts',{}) if case_data.get('confirmed') is True else {}
    items=[]
    for key,label in FIELDS.items():
        value=facts.get(key,'')
        if summary or key in wanted or (not wanted and set(terms)&set(tokens(label+' '+value))):
            if unknown(value):base['not_recorded'].append(label)
            if value.strip():
                text,start,end=excerpt(value,terms)
                items.append({'source_id':'case:'+str(case_id)+':'+str(revision),'kind':'case_fact','field':key,'title':label,'date':None,'text':text,'excerpt_start':start,'excerpt_end':end,'source_length':len(value),'is_unknown':unknown(value),'score':100 if key in wanted else 20})
    paragraphs=[]
    for source in accepted:
        chunks=[x.strip() for x in re.split(r'\n\s*\n',source['text']) if x.strip()]
        # Short documents remain one extract, retaining qualifiers and negation.
        if len(source['text'])<=1400:chunks=[source['text']]
        for chunk in chunks:
            paragraphs.append((source,chunk,set(tokens(chunk+' '+source['title']+' '+source['category']))))
    doc_count=max(1,len(paragraphs));document_frequency={t:sum(t in words for _,_,words in paragraphs) for t in set(terms)}
    for source,chunk,words in paragraphs:
        common=set(terms)&words
        score=sum(math.log(1+(doc_count-document_frequency[t]+.5)/(document_frequency[t]+.5)) for t in common)
        matching_category=any(source['category']==CATEGORIES.get(key) for key in wanted)
        if matching_category:score+=2
        if summary:score+=1
        if not common and not matching_category and not summary:continue
        # A planning-only passage is not a response to a question about treatment received.
        if completed and not re.search(r'\b(?:plan|planned|mdt)\b',lower) and source['category']!='Treatment record':
            if re.search(r'\bplan(?:ned)?\b',chunk,re.I):continue
        text,start,end=excerpt(chunk,terms)
        items.append({'source_id':source['id'],'kind':'source','field':None,'title':source['title'],'category':source['category'],'date':source['date'],'text':text,'excerpt_start':start,'excerpt_end':end,'source_length':len(chunk),'is_unknown':False,'score':score})
    # Case fields first, then relevance and source date. One excerpt per source.
    items.sort(key=lambda i:(i['kind']=='case_fact',i['score'],i['date'] or ''),reverse=True)
    seen=set();unique=[]
    for item in items:
        key=(item['source_id'],item.get('field'))
        if key in seen:continue
        seen.add(key);item.pop('score');unique.append(item)
    base['has_more']=len(unique)>12;base['items']=unique[:12]
    base['returned_count']=len(base['items'])
    base['accepted_sources_searched']=len(accepted)
    if not base['items']:
        return {**base,'status':'not_found','answer':'I could not find a matching statement in the confirmed case facts or reviewed history. This does not establish that the information or condition is absent. Try a specific record term or add and review the missing source.'}
    if all(i['is_unknown'] for i in base['items']):
        return {**base,'status':'not_recorded','answer':'The confirmed case field says this information is not recorded. No matching reviewed source supplies the missing detail. Do not infer a normal finding or an absence of treatment.'}
    return {**base,'status':'records_found','answer':'These are the matching recorded facts and source excerpts. Compare the dates and original wording; no clinical interpretation or reconciliation has been performed.'}
