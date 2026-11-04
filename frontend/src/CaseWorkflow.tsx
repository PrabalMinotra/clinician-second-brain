import {useEffect, useState, type FormEvent} from 'react';
import {api} from './api';

type Review = {id:number; case_alias:string; revision:number; reviewer:string; status:string; stale:boolean};
type Template = {id:number; title:string; fields:string[]};
type Changes = {approved_at:string; fields:string[]; added:string[]; changed:string[]; removed:string[]; stale_drafts:number};
type Workflow = {
 fields:Record<string,string>; readiness:Record<string,string>; pending_sources:number;
 differences:{field:string; case_value:string; source:{id:string;title:string;text:string;date:string}}[];
 record_differences:{label:string;date:string;sources:{id:string;title:string;value:string}[]}[];
 changes:Changes|null; reviews:Review[];
};
type Excerpt = {title:string; text:string};
type Comparison = {topic:string; sources:Excerpt[]; finding:string; review_question:string};
type Evidence = {model:string; mode:string; comparisons:Comparison[]};
const displayStatus:Record<string,string> = {
 confirmed:'Confirmed', missing:'Missing', needs_review:'Needs review',
 pending:'Pending', reviewed:'Reviewed', changes_requested:'Changes requested', cancelled:'Cancelled',
 possible_conflict:'Possible conflict', consistent:'Consistent', insufficient_evidence:'Insufficient evidence',
};
const status = (value:string) => displayStatus[value] || value;
const defaults:Record<string,string[]> = {
 referral:['age','sex','diagnosis','site','stage','pathology','imaging','prior_treatment','allergies','medications','comorbidities','performance_status','mdt_plan','follow_up'],
 handout:['diagnosis','mdt_plan','medications','allergies','follow_up'],
 board:['age','sex','diagnosis','stage','site','pathology','imaging','prior_treatment','comorbidities','allergies','medications','performance_status','mdt_plan','follow_up'],
};

export function EvidenceLab(){
 const [result,setResult]=useState<Evidence|null>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 async function compare(){
  setBusy(true);setError('');
  try{setResult(await api('/evidence-lab/'));}catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 return <section className="panel workflow-panel">
  <h2>AI Evidence Reviewer</h2>
  <p>Compare bundled fictional documentation with a natural language inference model. Results were generated offline. This lab does not read your case, uploads or CARE records.</p>
  <button className="btn primary" onClick={compare} disabled={busy}>{busy?'Loading…':'Compare evidence'}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<><p className="muted">Model: {result.model}. Findings are prompts for human review.</p>
   {result.comparisons.map(pair=><article className="workflow-card" key={pair.topic}>
    <h3>{pair.topic} <span className="pill neutral">{status(pair.finding)}</span></h3>
    <div className="workflow-compare">{pair.sources.map(source=><blockquote key={source.title}><strong>{source.title}</strong><p>{source.text}</p></blockquote>)}</div>
    <p><strong>Review question.</strong> {pair.review_question}</p>
   </article>)}
  </>}
 </section>;
}

export function CaseWorkflow({caseId,revision,onFacts,onIntake,onDrafts}:{caseId:string;revision:number;onFacts:()=>void;onIntake:()=>void;onDrafts:()=>void}){
 const [workflow,setWorkflow]=useState<Workflow|null>(null);
 const [templates,setTemplates]=useState<Template[]>([]);
 const [selected,setSelected]=useState('referral');
 const [reviewer,setReviewer]=useState('');
 const [title,setTitle]=useState('');
 const [fields,setFields]=useState<string[]>([]);
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [busy,setBusy]=useState(false);
 const base='/cases/'+caseId;
 useEffect(()=>{
  let active=true;
  setWorkflow(null);setError('');setNotice('');
  Promise.all([api(base+'/workflow/'),api('/templates/')]).then(([w,t])=>{
   if(active){setWorkflow(w);setTemplates(t.templates);}
  }).catch(e=>{if(active)setError(e.message);});
  return ()=>{active=false;};
 },[base,revision]);
 async function run(action:()=>Promise<void>){
  setBusy(true);setError('');setNotice('');
  try{await action();}catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 async function saveTemplate(e:FormEvent){
  e.preventDefault();
  await run(async()=>{
   const created=await api('/templates/','POST',{title,fields});
   setTemplates(previous=>[...previous,created]);setSelected(String(created.id));setTitle('');setFields([]);
   setNotice('Template saved.');
  });
 }
 const custom=templates.find(t=>String(t.id)===selected);
 const checklist=custom?.fields||defaults[selected]||defaults.referral;
 const changes=workflow?.changes;
 return <section className="panel workflow-panel">
  <h2>Case readiness and handoff</h2>
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {!workflow&&!error&&<p>Loading case checks…</p>}
  {workflow&&<>
   <article className="workflow-card">
    <h3>Document readiness</h3>
    <label>Checklist <select value={selected} onChange={e=>setSelected(e.target.value)}>
     <option value="referral">Referral letter</option><option value="handout">Patient information sheet</option><option value="board">Tumour-board note</option>
     {templates.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}
    </select></label>
    {workflow.pending_sources>0&&<p>{workflow.pending_sources} pending source(s). <button className="text-btn" onClick={onIntake}>Open intake review</button></p>}
    <ul className="workflow-checklist">{checklist.map(key=><li key={key}>{workflow.fields[key]} <span className="pill neutral">{status(workflow.readiness[key])}</span></li>)}</ul>
    <button className="btn secondary" onClick={onFacts}>Review case facts</button>
    {custom&&<button className="btn primary" disabled={busy} onClick={()=>run(async()=>{
     await api(base+'/generate/','POST',{revision,template_id:custom.id});onDrafts();
    })}>Draft from this template</button>}
   </article>
   <article className="workflow-card">
    <h3>Record differences</h3>
    <p>Compares recorded stage wording with the case field and checks explicitly labeled stage, treatment status and dates across same-day sources. Review the excerpts before reconciling a difference.</p>
    {workflow.differences.length===0&&workflow.record_differences.length===0&&<p className="muted">No differences detected by these checks.</p>}
    {workflow.record_differences.map(group=><div key={group.label+group.date}>
     <h4>{group.label} · {group.date}</h4>
     <div className="workflow-compare">{group.sources.map((source,index)=><blockquote key={source.id+index}><strong>{source.title}</strong><p>{source.value}</p></blockquote>)}</div>
    </div>)}
    {workflow.differences.map((d,i)=><div className="workflow-compare" key={d.source.id+':'+i}>
     <blockquote><strong>Case field</strong><p>{d.case_value}</p></blockquote>
     <blockquote><strong>{d.source.title} · {d.source.date}</strong><p>{d.source.text}</p></blockquote>
    </div>)}
   </article>
   <article className="workflow-card">
    <h3>Changes since the last approved draft</h3>
    {changes?<><p>Approved {new Date(changes.approved_at).toLocaleString()}. {changes.stale_drafts} draft(s) use an earlier case revision.</p>
     <ul>{[['Changed facts',changes.fields],['Added records',changes.added],['Updated records',changes.changed],['Removed records',changes.removed]].map(([label,items])=><li key={String(label)}><strong>{label}</strong> · {(items as string[]).join(', ')||'None'}</li>)}</ul>
    </>:<p className="muted">Approve a draft to establish a comparison baseline.</p>}
   </article>
   <article className="workflow-card">
    <h3>Assign case review</h3>
    <p>Another clinician can read the confirmed fields and accepted sources for this revision. Document approval stays with the case owner.</p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
     await api(base+'/assign-review/','POST',{revision,reviewer});
     setWorkflow(await api(base+'/workflow/'));setReviewer('');setNotice('Case review assigned.');
    });}}>
     <label>Reviewer username <input required maxLength={150} value={reviewer} onChange={e=>setReviewer(e.target.value)}/></label>
     <button className="btn secondary" disabled={busy}>Assign revision {revision}</button>
    </form>
    {workflow.reviews.length>0&&<ul>{workflow.reviews.map(r=><li key={r.id}>{r.reviewer} · revision {r.revision} · {r.stale&&r.status==='pending'?'Outdated':status(r.status)}</li>)}</ul>}
   </article>
   <article className="workflow-card">
    <h3>Save a reusable template</h3>
    <p>Selected fields become required draft sections. Saved templates are available across your cases.</p>
    <form onSubmit={saveTemplate}>
     <label>Template name <input required maxLength={80} value={title} onChange={e=>setTitle(e.target.value)}/></label>
     <fieldset><legend>Required sections</legend><div className="workflow-checklist">
      {Object.entries(workflow.fields).map(([key,label])=><label className="checkbox" key={key}><input type="checkbox" checked={fields.includes(key)} onChange={e=>setFields(e.target.checked?[...fields,key]:fields.filter(f=>f!==key))}/>{label}</label>)}
     </div></fieldset>
     <button className="btn secondary" disabled={busy||!fields.length}>Save template</button>
    </form>
   </article>
  </>}
 </section>;
}

type AssignedCase = Review & {facts:Record<string,string>;sources:(Excerpt&{date:string})[]};
export function ReviewQueue(){
 const [queue,setQueue]=useState<Review[]>([]);
 const [selected,setSelected]=useState<AssignedCase|null>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(true);
 useEffect(()=>{api('/reviews/').then(r=>setQueue(r.reviews)).catch(e=>setError(e.message)).finally(()=>setBusy(false));},[]);
 async function run(action:()=>Promise<void>){
  setBusy(true);setError('');
  try{await action();}catch(e){setError((e as Error).message);setSelected(null);}finally{setBusy(false);}
 }
 return <section className="panel workflow-panel">
  <h2>My review queue</h2>
  <p>Read a case assigned to you and record a review outcome. This does not approve documents.</p>
  {error&&<p role="alert">{error}</p>}
  {!queue.length&&!busy&&<p>No reviews assigned to you.</p>}
  {queue.map(item=><div className="workflow-card" key={item.id}><strong>{item.case_alias}</strong> · Revision {item.revision} · {item.stale&&item.status==='pending'?'Outdated':status(item.status)}
   {item.status==='pending'&&!item.stale&&<button className="text-btn" disabled={busy} onClick={()=>run(async()=>setSelected(await api('/reviews/'+item.id+'/')))}>Open review</button>}
  </div>)}
  {selected&&<article className="workflow-card">
   <h3>Review {selected.case_alias}</h3>
   <dl>{Object.entries(selected.facts).map(([key,value])=><div key={key}><dt><strong>{key}</strong></dt><dd>{value||'Not recorded'}</dd></div>)}</dl>
   {selected.sources.map((s,i)=><details key={i}><summary>{s.title} · {s.date}</summary><p>{s.text}</p></details>)}
   {['reviewed','changes_requested'].map(outcome=><button className="btn secondary" disabled={busy} key={outcome} onClick={()=>run(async()=>{
    const updated=await api('/reviews/'+selected.id+'/','PATCH',{status:outcome});
    setQueue(queue.map(item=>item.id===updated.id?updated:item));setSelected(null);
   })}>{status(outcome)}</button>)}
  </article>}
 </section>;
}
