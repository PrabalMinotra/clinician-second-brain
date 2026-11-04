"""Record-quality checks only. Never derive a clinical stage or diagnosis."""
import re
from .documents import FIELDS

def flags(case_data,sources):
    result=[];facts=case_data.get('facts',{})
    for key,label in FIELDS.items():
        value=facts.get(key,'')
        if not value.strip() or value.lower().startswith('not recorded'):
            result.append({'kind':'missing','field':key,'message':label+' is not recorded. Confirm with the clinician; no value inferred.'})
    recorded=facts.get('stage','').strip().upper()
    for source in sources:
        if source['status']!='accepted':continue
        for match in re.finditer(r'(?i)\b(?:recorded\s+stage|stage)\s*[:=]\s*([^\n.;]+)',source['text']):
            literal=match.group(1).strip()
            if recorded and literal.upper()!=recorded:
                result.append({'kind':'wording_difference','field':'stage','source_id':source['id'],'message':f'Stage wording in “{source["title"]}” differs from the confirmed case field. Compare source dates and transcription; no stage has been reconciled automatically.'})
    return result
