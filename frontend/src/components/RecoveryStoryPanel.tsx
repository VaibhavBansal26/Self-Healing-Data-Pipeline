import {Activity, Bot, CheckCircle2, Clock3, ShieldAlert, Wrench} from 'lucide-react';

function meta(row:any){
  const raw = row?.metadata || {};
  if(typeof raw === 'string'){
    try{return JSON.parse(raw);}catch{return {message:raw};}
  }
  return raw;
}

function summarizeIssue(row:any){
  const m = meta(row);
  const list = m.initial_unhealthy_summary || m.summary || m.unhealthy || m.actions || [];
  if(Array.isArray(list) && list.length) return list.map(String).join('  •  ');
  return m.message || `${row?.stage || 'agent'} ${row?.status || ''}`.trim();
}

function findLatest(rows:any[], statuses:string[]){
  return rows.find((r:any)=>statuses.includes(String(r.status)) || statuses.includes(String(r.stage)));
}

export function RecoveryStoryPanel({autoHealer, health}:{autoHealer:any; health:any}){
  const rows = autoHealer?.current_cycle_events?.length ? autoHealer.current_cycle_events : (autoHealer?.recent_activity || []);
  const unhealthy = (health?.components || []).filter((c:any)=>c.status !== 'healthy');
  const state = String(autoHealer?.state || 'waiting');
  const active = state.includes('healing') || state.includes('visible') || state.includes('attention');
  const recovered = state.includes('recent') || state.includes('recovered');

  const detected = findLatest(rows, ['unhealthy_detected','detect']);
  const planned = findLatest(rows, ['agent_active','plan']);
  const healed = findLatest(rows, ['completed','heal']);
  const verified = findLatest(rows, ['recovered','verify','recently_recovered']);
  const focus = detected || verified || rows[0];

  const steps = [
    {key:'detect', label:'Detect', icon:Activity, done:!!detected || active || recovered, text: detected ? summarizeIssue(detected) : unhealthy.length ? `${unhealthy.length} active stage issue(s)` : 'No active failures'},
    {key:'plan', label:'Plan', icon:Bot, done:!!planned || active || recovered, text: planned ? summarizeIssue(planned) : 'Agent checks policy, memory, MCP tools'},
    {key:'heal', label:'Heal safe', icon:Wrench, done:!!healed || recovered, working: active && !healed, text: healed ? summarizeIssue(healed) : 'Safe actions auto-run; risky actions wait'},
    {key:'verify', label:'Verify', icon:CheckCircle2, done:!!verified || recovered, text: verified ? summarizeIssue(verified) : 'Health check confirms recovery'},
  ];

  return <section className={`recovery-story ${active ? 'active' : recovered ? 'recovered' : unhealthy.length ? 'attention' : 'idle'}`}>
    <div className="story-header">
      <div>
        <span className="eyebrow">Background recovery story</span>
        <h2>{active ? 'Agent is working now' : recovered ? 'Agent recently recovered the pipeline' : unhealthy.length ? 'Agent found issues that need action' : 'Pipeline is stable'}</h2>
        <p>{autoHealer?.latest_message || (unhealthy.length ? 'One or more stages are unhealthy.' : 'No recovery cycle is active right now.')}</p>
      </div>
      <div className="story-status">
        {active ? <Wrench className="spin-slow" size={22}/> : unhealthy.length ? <ShieldAlert size={22}/> : <CheckCircle2 size={22}/>}<b>{active ? 'Healing' : recovered ? 'Recovered' : unhealthy.length ? 'Needs action' : 'Sleeping'}</b>
      </div>
    </div>
    <div className="story-focus">
      <Clock3 size={16}/>
      <span>{focus ? summarizeIssue(focus) : 'No incident has been observed in the current hold window.'}</span>
    </div>
    <div className="story-steps">
      {steps.map((s, idx)=>{ const Icon=s.icon; return <div className={`story-step ${s.done ? 'done' : ''} ${s.working ? 'working' : ''}`} key={s.key}>
        <div className="step-dot"><Icon size={16}/></div>
        <b>{s.label}</b>
        <small>{s.text}</small>
        {idx < steps.length-1 && <i/>}
      </div>;})}
    </div>
  </section>;
}
