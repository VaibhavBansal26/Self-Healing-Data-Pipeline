import {Bot, BrainCircuit, Database, GitBranch, RadioTower, ServerCog, Workflow, Activity, Search, Logs, PlugZap, Network} from 'lucide-react';
import {Panel} from './Panel';
import {DataTable} from './DataTable';
import {JsonBlock} from './JsonBlock';
import {AIOpsCharts} from './AIOpsCharts';

function iconForAgent(agent:string){
  if(agent?.toLowerCase().includes('kafka')) return <GitBranch size={20}/>;
  if(agent?.toLowerCase().includes('database')) return <Database size={20}/>;
  if(agent?.toLowerCase().includes('redis')) return <ServerCog size={20}/>;
  if(agent?.toLowerCase().includes('airflow')) return <Workflow size={20}/>;
  if(agent?.toLowerCase().includes('recovery')) return <Bot size={20}/>;
  return <Activity size={20}/>;
}
function statusClass(s:string){
  const v=(s||'').toLowerCase();
  if(v.includes('active')) return 'blue';
  if(v.includes('degraded') || v.includes('pending')) return 'yellow';
  if(v.includes('down') || v.includes('failed')) return 'red';
  return 'green';
}

export function AIOpsVisuals({ops}:{ops:any}){
  const logs=ops?.logs?.rows || [];
  const memories=ops?.vector_memory?.rows || [];
  const ragNodes=ops?.rag_flow?.nodes || [];
  const agents=ops?.mcp_mesh?.agents || [];
  const collaboration=ops?.mcp_mesh?.collaboration_timeline || [];
  const toolTraces=ops?.tool_traces?.rows || [];
  return <div>
    <Panel icon={<Network/>} title="AI Operations Observatory" desc="A visual layer for logs, RAG memory, MCP agents, tool calls, and agent collaboration. This proves how the self-healing platform reasons, acts, verifies, and remembers.">
      <div className="explain light-explain">Health checks tell the platform what is broken. The AI operations layer explains why, retrieves previous similar incidents, selects the right MCP tool, plans a safe recovery, verifies the result, and stores the outcome for future decisions.</div>
      <AIOpsCharts ops={ops}/>
    </Panel>

    <Panel icon={<PlugZap/>} title="MCP Agent Mesh" desc="The coordinator agent delegates to component-specific MCP operational agents. Each card shows tools, status, latency, success rate, and last result.">
      <div className="mcp-agent-grid">
        {agents.map((a:any)=><div key={a.agent} className={`mcp-agent-card ${statusClass(a.status)}`}>
          <div className="mcp-agent-head"><div>{iconForAgent(a.agent)}<b>{a.agent}</b></div><span>{a.status}</span></div>
          <p>{a.last_result}</p>
          <div className="mcp-agent-metrics"><span>Latency <b>{a.latency_ms} ms</b></span><span>Success <b>{Math.round((a.success_rate||0)*100)}%</b></span></div>
          <div className="tool-chip-row">{(a.tools||[]).map((t:string)=><em key={t}>{t}</em>)}</div>
        </div>)}
      </div>
    </Panel>

    <Panel icon={<BrainCircuit/>} title="RAG + Vector Memory Explorer" desc="Shows the previous incidents retrieved from vector memory and whether those memories were used as evidence by the agent.">
      <div className="cards-grid">
        <div className="stat-card purple"><div><div className="stat-title">Precision@1</div><div className="stat-value">{Math.round((ops?.vector_memory?.metrics?.precision_at_1||0)*100)}%</div></div></div>
        <div className="stat-card green"><div><div className="stat-title">Hit@K</div><div className="stat-value">{Math.round((ops?.vector_memory?.metrics?.hit_rate_at_k||0)*100)}%</div></div></div>
        <div className="stat-card blue"><div><div className="stat-title">Memory rows</div><div className="stat-value">{ops?.vector_memory?.metrics?.memory_rows || 0}</div></div></div>
      </div>
      <DataTable rows={memories} cols={['query','memory_id','rank','similarity_score','expected_memory','used_by_agent','previous_action','previous_outcome']}/>
    </Panel>

    <Panel icon={<Search/>} title="RAG Decision Flow" desc="Connected decision path showing where vector memory participates in recovery planning.">
      <div className="rag-flow-map">
        {ragNodes.map((n:any,idx:number)=><div className={`rag-node ${n.status}`} key={n.id}>
          <div><b>{idx+1}. {n.label}</b><span>{n.status}</span></div><p>{n.detail}</p>{idx < ragNodes.length-1 && <strong>↓</strong>}
        </div>)}
      </div>
    </Panel>

    <Panel icon={<Logs/>} title="Logs and Diagnosis" desc="Raw logs are classified into stage, failure type, severity, recommended action, and human-spoken agent update.">
      <DataTable rows={logs} cols={['timestamp','source','stage','severity','problem_type','recommended_action','agent_update','raw_log']}/>
    </Panel>

    <Panel icon={<RadioTower/>} title="MCP Tool Call Trace Viewer" desc="Step-by-step operational tool calls used by the platform during detection, recovery, and verification.">
      <DataTable rows={toolTraces} cols={['step','timestamp','component','tool','input','output','latency_ms']}/>
    </Panel>

    <Panel icon={<Bot/>} title="Agent Collaboration Timeline" desc="Shows how the coordinator, observability, vector memory, component MCP agents, recovery agent, and verifier work together.">
      <div className="collab-timeline">
        {collaboration.map((c:any)=><div className={`collab-item ${statusClass(c.status)}`} key={c.step}><span>{c.step}</span><div><b>{c.agent}</b><p>{c.action}</p></div><em>{c.status}</em></div>)}
      </div>
    </Panel>

    <Panel icon={<Activity/>} title="Raw AI Ops Observatory payload" desc="Complete JSON payload backing the observability visualizations for debugging and extension.">
      <JsonBlock data={ops}/>
    </Panel>
  </div>;
}
