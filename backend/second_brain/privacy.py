"""Conservative identifier screening; never a guarantee of anonymisation."""
import re
RULES=[
 ('email',r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'),
 ('identifier',r'\b(?:MRN|UHID|ABHA|Aadhaar|Patient\s*ID)\s*[:#=-]?\s*[A-Z0-9][A-Z0-9 -]{3,30}'),
 ('phone',r'(?<!\w)(?:\+91[ -]?)?[6-9]\d{9}(?!\w)'),
 ('identifier',r'\b\d{4}[ -]\d{4}[ -]\d{4}\b'),
 ('identifier',r'\b\d{14}\b'),
 ('name',r'(?im)^\s*(?:Patient\s*name|Name)\s*[:=-][^\n]+'),
 ('address',r'(?im)^\s*(?:Address|Residence)\s*[:=-][^\n]+'),
 ('dob',r'(?im)^\s*(?:DOB|Date of birth)\s*[:=-][^\n]+'),
]
def redact(text):
    counts={}
    for label,pattern in RULES:
        text,n=re.subn(pattern,'['+label.upper()+' REMOVED]',text,flags=re.I)
        if n: counts[label]=counts.get(label,0)+n
    return text,counts
