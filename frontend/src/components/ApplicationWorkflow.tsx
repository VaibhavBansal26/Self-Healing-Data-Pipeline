import {Activity, Bot, CheckCircle2, Database, GitBranch, ShieldCheck, Wrench, Workflow, RadioTower, Search, ServerCog, BarChart3} from 'lucide-react';

function iconFor(id:string){
  const map:Record<string, any>={gateway:RadioTower,kafka:GitBranch,consumer:Activity,rules:Wrench,rag:Search,agent:Bot,mcp:ServerCog,approval:ShieldCheck,postgres:Database,dlq:GitBranch,airflow:Workflow,observability:BarChart3};
  return map[id] || Activity;
}
function label(color:string){ return color==='green'?'healthy':color==='yellow'?'healing':color==='red'?'down':'unknown'; }
function copyFor(stage:any){
  const reason = String(stage?.reason || 'healthy');
  if(reason.length > 92) return reason.slice(0, 92) + '…';
  return reason;
}

const rows = [
  ['gateway','kafka','consumer','rules'],
  ['rag','agent','mcp','approval'],
  ['postgres','dlq','airflow','observability'],
];

export function ApplicationWorkflow({health,autoHealer}:{health:any; autoHealer?:any}){
  const stages = health?.stage_map || [];
  const byId:Record<string, any> = Object.fromEntries(stages.map((s:any)=>[s.id,s]));
  const recent = String(autoHealer?.state || '').includes('recently_recovered') || String(autoHealer?.state || '').includes('recovered');
  const active = String(autoHealer?.state || '').includes('healing') || String(autoHealer?.state || '').includes('visible');
  return <div className="workflow-card compact-workflow">
    <div className="workflow-head">
      <div>
        <span className="eyebrow">Application workflow</span>
        <h2>Live connected pipeline map</h2>
        <p>This compact graph shows the whole application flow. Click into Pipeline Step Healing or AI Engineering for deeper logs, RAG evidence, MCP tools, and agent timeline.</p>
      </div>
      <div className="workflow-legend"><span><i className="dot green"/> healthy</span><span><i className="dot yellow"/> self-healing</span><span><i className="dot red"/> down</span></div>
    </div>
    {(active || recent) && <div className={`workflow-live-banner ${active ? 'active' : 'recovered'}`}>
      <b>{active ? 'Agent is healing in the background' : 'Agent recently completed recovery'}</b>
      <span>{autoHealer?.latest_message}</span>
    </div>}
    <div className="compact-dag">
      {rows.map((row, rIdx)=><div className="compact-dag-row" key={row.join('-')}>
        {row.map((id, idx)=>{
          const s = byId[id]; if(!s) return null;
          const Icon = iconFor(id);
          return <div className="compact-node-wrap" key={id}>
            <div className={`compact-node ${s.color || 'gray'}`}>
              <div className="compact-node-top"><Icon size={18}/><b>{s.label}</b><span>{label(s.color)}</span></div>
              <p>{copyFor(s)}</p>
              <div className="compact-node-meta"><em>Action</em><strong>{s.suggested_action || 'none'}</strong></div>
              <small className={s.agent_active ? 'agent-on' : 'agent-off'}>{s.agent_active ? 'Agent active' : 'Agent sleeping'}</small>
            </div>
            {idx < row.length-1 && <div className={`compact-arrow ${s.color}`}>→</div>}
          </div>;
        })}
        {rIdx < rows.length-1 && <div className="row-down-arrow">↓</div>}
      </div>)}
    </div>
    <div className="workflow-note"><CheckCircle2 size={16}/> Green means verified. Yellow means degraded/self-healing. Red means blocked/down. Blue agent chips mean the agent is actively diagnosing or planning.</div>
  </div>;
}
