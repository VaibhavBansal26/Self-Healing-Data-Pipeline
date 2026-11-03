import {Activity, AlertTriangle, CheckCircle2, Clock, Database, GitBranch, RadioTower, RefreshCw, ShieldCheck, Workflow, Zap} from 'lucide-react';
import {JsonBlock} from './JsonBlock';

function iconFor(id:string){
  if(id.includes('kafka')) return RadioTower;
  if(id.includes('postgres')) return Database;
  if(id.includes('dlq')) return GitBranch;
  if(id.includes('approval')) return ShieldCheck;
  if(id.includes('airflow')) return Workflow;
  if(id.includes('agent')) return Zap;
  return Activity;
}
function label(color:string){
  if(color==='green') return 'Healthy';
  if(color==='yellow') return 'Healing';
  if(color==='red') return 'Down';
  return 'Unknown';
}
function shortReason(reason?:string){
  const text = String(reason || 'Healthy');
  return text.length > 72 ? text.slice(0,72) + '…' : text;
}

export function FailurePipelineVisualization({health, metrics, approvals, alerts, traces}:{health:any; metrics?:any; approvals?:any[]; alerts?:any[]; traces?:any[]}){
  const stages = health?.stage_map || [];
  const agent = health?.agent_status || {};
  const active = stages.filter((s:any)=>s.color!=='green');
  const isActive = agent?.is_active || active.length > 0;
  const current = active[0];
  return <div className="failure-visual-wrap compact-failure-visual">
    <div className="failure-visual-head compact-head">
      <div>
        <span className="eyebrow">Live failure visualization</span>
        <h2>What is happening right now?</h2>
        <p>This view keeps the pipeline compact. Green means verified, yellow means degraded or healing, and red means blocked. The agent message below explains the current action in plain English.</p>
      </div>
      <div className={`agent-mode-card compact-agent-card ${isActive ? 'blue' : (agent.badge_color || 'green')}`}>
        <b>Pipeline agent</b>
        <strong>{isActive ? 'Working on it' : 'Sleeping'}</strong>
        <span>{agent.headline || (isActive ? 'I found an issue and I am planning the safest recovery.' : 'All stages are healthy.')}</span>
      </div>
    </div>

    <div className="agent-notification-row">
      <div className={`live-agent-notice ${isActive ? 'active' : 'idle'}`}>
        <span className="notice-pulse" />
        <div>
          <b>{isActive ? 'Agent is diagnosing / healing' : 'Agent is idle'}</b>
          <p>{current ? `I am checking ${current.label}: ${shortReason(current.reason)}` : 'No pipeline failures are active right now.'}</p>
        </div>
      </div>
      <div className="mini-policy-note">
        <b>Automatic means:</b> safe allowlisted actions run without approval. Risky actions wait for a human.
      </div>
    </div>

    <div className="stage-strip">
      {stages.map((s:any, idx:number)=>{
        const Icon = iconFor(s.id || s.component);
        const agentActive = s.agent_active || s.agent_state !== 'sleeping';
        return <div className={`stage-chip-card ${s.color || 'green'}`} key={s.id || idx} title={s.reason}>
          <div className="stage-chip-top"><Icon size={16}/><b>{s.label}</b><span>{label(s.color)}</span></div>
          <p>{shortReason(s.reason)}</p>
          <small>{agentActive ? 'Agent active' : 'Verified'}</small>
        </div>;
      })}
    </div>

    <div className="agent-timeline-grid compact-agent-grid">
      <div className="agent-log-card">
        <h3><Clock size={17}/> Agent updates</h3>
        {(agent.human_updates || []).slice(0,5).map((u:string,idx:number)=><div className="agent-speech" key={idx}>{u}</div>)}
        {!(agent.human_updates || []).length && <div className="agent-speech">I have no active updates yet.</div>}
      </div>
      <div className="agent-log-card">
        <h3><RefreshCw size={17}/> Recovery signals</h3>
        <div className="signal-grid">
          <div><span>Pending approvals</span><b>{approvals?.length || 0}</b></div>
          <div><span>Recent alerts</span><b>{alerts?.length || 0}</b></div>
          <div><span>Trace events</span><b>{traces?.length || 0}</b></div>
          <div><span>Unhealthy stages</span><b>{active.length}</b></div>
        </div>
        <details className="compact-details"><summary>Show raw recovery metrics</summary><JsonBlock data={{pipeline_healing_metrics: metrics, recent_alerts: alerts?.slice?.(0,3) || [], recent_traces: traces?.slice?.(0,3) || []}}/></details>
      </div>
      <div className="agent-log-card wide">
        <h3><AlertTriangle size={17}/> Active focus</h3>
        {active.length ? active.slice(0,4).map((s:any)=><div className={`failure-focus compact ${s.color}`} key={s.id}>
          <b>{s.label}</b><span>{s.problem_type}</span><p>{s.reason}</p>
          {s.agent_plan && <details><summary>Agent plan</summary><JsonBlock data={s.agent_plan}/></details>}
        </div>) : <div className="empty-state"><CheckCircle2/> No active pipeline stage failures. The agent is sleeping.</div>}
      </div>
    </div>
  </div>;
}
