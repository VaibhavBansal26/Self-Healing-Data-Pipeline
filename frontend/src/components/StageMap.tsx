import {Bot, CheckCircle2, Clock3, Database, GitBranch, PauseCircle, ShieldCheck, Wrench, AlertTriangle, RadioTower, Activity, Workflow} from 'lucide-react';
import {JsonBlock} from './JsonBlock';

const iconFor = (id:string) => {
  const map: Record<string, any> = {
    gateway: RadioTower,
    kafka: GitBranch,
    consumer: Activity,
    rules: Wrench,
    rag: Workflow,
    agent: Bot,
    mcp: Workflow,
    approval: ShieldCheck,
    postgres: Database,
    dlq: GitBranch,
    airflow: Clock3,
    observability: Activity,
  };
  return map[id] || Activity;
};

function statusLabel(color:string){
  if(color === 'green') return 'Working fine';
  if(color === 'yellow') return 'Self healing / degraded';
  return 'Down / needs action';
}

function agentLabel(state:string){
  if(state === 'sleeping') return 'Agent sleeping';
  if(state === 'waiting_for_human') return 'Waiting for approval';
  return 'Agent detecting and planning';
}

export function StageMap({health,autoHealer}:{health:any; autoHealer?:any}){
  const stages = health?.stage_map || [];
  const agent = health?.agent_status || {state:'sleeping', headline:'Agent status unavailable', human_updates:[]};
  const recent = String(autoHealer?.state || '').includes('recently_recovered') || String(autoHealer?.state || '').includes('recovered');
  const active = String(autoHealer?.state || '').includes('healing') || String(autoHealer?.state || '').includes('visible');
  return <div className="stage-map-wrap">
    <div className={`agent-banner ${active ? 'blue' : recent ? 'green recovered' : agent.badge_color || 'green'}`}>
      <div className="agent-orb"><Bot size={24}/></div>
      <div>
        <div className="agent-status-line"><b>Pipeline Agent:</b> {active ? 'healing now' : recent ? 'recently recovered' : agent.state || 'unknown'}</div>
        <p>{active || recent ? autoHealer?.latest_message : agent.headline}</p>
        <div className="agent-updates">
          {(agent.human_updates || []).slice(0,3).map((u:string,idx:number)=><span key={idx}>{u}</span>)}
        </div>
      </div>
    </div>

    <div className="stage-legend">
      <span><i className="dot green"/> Green means working fine</span>
      <span><i className="dot yellow"/> Yellow means self healing or degraded</span>
      <span><i className="dot red"/> Red means down or blocked</span>
      <span><i className="dot blue"/> Blue agent badge means active</span>
    </div>

    <div className="stage-map">
      {stages.map((s:any,idx:number)=>{
        const Icon = iconFor(s.id);
        const agentActive = s.agent_active || s.agent_state !== 'sleeping';
        return <div className="stage-node-row" key={s.id}>
          <div className={`stage-node ${s.color}`}>
            <div className="stage-node-head">
              <div className="stage-title"><Icon size={18}/><b>{s.label}</b></div>
              <span className={`stage-pill ${s.color}`}>{statusLabel(s.color)}</span>
            </div>
            <p>{s.description}</p>
            <div className="stage-meta">
              <span>Component: <b>{s.component}</b></span>
              <span>Problem: <b>{s.problem_type || 'none'}</b></span>
              <span>Action: <b>{s.suggested_action || 'none'}</b></span>
            </div>
            <div className="stage-reason"><b>Agent update:</b> {s.reason}</div>
            {s.agent_plan && <details><summary>Agent plan, memory, MCP context</summary><JsonBlock data={s.agent_plan}/></details>}
          </div>
          <div className={`stage-agent ${agentActive ? 'active' : 'sleep'}`}>
            {agentActive ? <AlertTriangle size={15}/> : <CheckCircle2 size={15}/>} {agentLabel(s.agent_state)}
          </div>
          {idx < stages.length - 1 && <div className="stage-connector"/>}
        </div>;
      })}
    </div>
  </div>;
}
