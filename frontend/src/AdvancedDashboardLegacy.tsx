import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, AlertTriangle, Bot, CheckCircle, Database, GitBranch, Pause, Play, RefreshCw, Send, ServerCog, ShieldCheck, Workflow, XCircle, Zap, Eye, RotateCcw, Gauge} from 'lucide-react';
import {BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid, AreaChart, Area} from 'recharts';
import {API_BASE, apiGet, apiPost} from './lib/api';
import './styles.css';

type AnyObj = Record<string, any>;
type Summary = {orders_count:number; incident_count:number; healed_count:number; manual_review_count:number; failed_count:number; unresolved_count:number; dlq_count:number; total_seen?:number; healing_rate?:number; clean_insert_rate?:number; risk_score?:number;};
type Incident = {incident_id:number; event_id?:string; error_type:string; error_message:string; original_payload:any; healed_payload?:any; healing_action?:string; risk_level?:string; status:string; created_at?:string; agent_trace?:AnyObj[]; rag_evidence?:AnyObj[];};
type Order = {event_id:string; customer_id:string; amount:number; currency:string; status:string; schema_version?:number; created_at:string;};
type Journey = {journey_id:number; event_id?:string; stage:string; component:string; status:string; reason?:string; action?:string; risk_level?:string; payload?:any; metadata?:any; created_at?:string;};
type ComponentHealth = {component:string; status:string; problem_type?:string; reason?:string; detected_state?:any; risk_level?:string; suggested_action?:string; requires_human_approval?:boolean;};

const tabs = ['Overview','System Design','Failure Simulator','Live Journey','Reason Act Verify','Producer Controls','Pressure Test','PostgreSQL Records','Human Approval','DLQ Replay','RAG Evidence','Schema Evolution','Pipeline Step Healing','Metrics'];
const scenarios = ['valid_order','amount_string','missing_currency','bad_status','negative_amount','missing_customer','missing_event_id','schema_v2_order','unsupported_schema'];
const COLORS = ['#22c55e','#38bdf8','#f59e0b','#ef4444','#a78bfa','#ec4899'];

function JsonBlock({data}:{data:any}) { return <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>; }
function Stat({title,value,icon,color}:{title:string;value:any;icon:React.ReactNode;color?:string}) { return <div className={`stat-card ${color||''}`}><div className="stat-icon">{icon}</div><div><div className="stat-title">{title}</div><div className="stat-value">{value ?? 0}</div></div></div>; }

function App() {
  const [tab,setTab] = useState('Overview');
  const [summary,setSummary] = useState<Summary|null>(null);
  const [orders,setOrders] = useState<Order[]>([]);
  const [incidents,setIncidents] = useState<Incident[]>([]);
  const [journey,setJourney] = useState<Journey[]>([]);
  const [health,setHealth] = useState<any>(null);
  const [pipelineIncidents,setPipelineIncidents] = useState<any[]>([]);
  const [flow,setFlow] = useState<any>(null);
  const [replayAudit,setReplayAudit] = useState<any[]>([]);
  const [schema,setSchema] = useState<any>(null);
  const [rag,setRag] = useState<any[]>([]);
  const [pressure,setPressure] = useState<any>(null);
  const [failureScenarios,setFailureScenarios] = useState<any[]>([]);
  const [message,setMessage] = useState('');
  const [error,setError] = useState('');
  const [customJson,setCustomJson] = useState(JSON.stringify({event_id:'ui_custom_1',customer_id:'cust_ui',amount:'42.50',currency:'usd',status:'PAY',schema_version:1}, null, 2));
  const [transformResult,setTransformResult] = useState<any>(null);
  const [pressureTotal,setPressureTotal] = useState(1000);

  async function refresh() {
    try {
      setError('');
      const [s,o,i,j,h,pi,f,ra,sc,rg,ps,fs] = await Promise.all([
        apiGet<Summary>('/summary'), apiGet<Order[]>('/orders?limit=100'), apiGet<Incident[]>('/incidents?limit=100'),
        apiGet<Journey[]>('/event-journey?limit=300'), apiGet<any>('/pipeline/health'), apiGet<any[]>('/pipeline/incidents?limit=100'),
        apiGet<any>('/flow/live'), apiGet<any[]>('/dlq/replay-audit?limit=100'), apiGet<any>('/schema/evolution'), apiGet<any[]>('/rag/evidence?limit=100'),
        apiGet<any>('/pressure-test/summary'), apiGet<any>('/failure-simulator/scenarios')
      ]);
      setSummary(s); setOrders(o); setIncidents(i); setJourney(j); setHealth(h); setPipelineIncidents(pi); setFlow(f); setReplayAudit(ra); setSchema(sc); setRag(rg); setPressure(ps); setFailureScenarios(fs.scenarios || []);
    } catch(e:any) { setError(e.message || String(e)); }
  }
  useEffect(()=>{ refresh(); const t=setInterval(refresh, 6000); return ()=>clearInterval(t); },[]);

  async function publishDemo(){ const r:any=await apiPost('/events/demo'); setMessage(`Published ${r.published_count} demo events`); setTimeout(refresh,1000); }
  async function publishScenario(sc:string){ const r:any=await apiPost(`/events/test/${sc}`); setMessage(`Published ${sc}: ${r.event_id || r?.payload?.event_id || ''}`); setTimeout(refresh,1000); }
  async function publishCustom(){ const payload=JSON.parse(customJson); const r:any=await apiPost('/events',{payload}); setMessage(`Published custom event ${r.event_id}`); setTimeout(refresh,1000); }
  async function previewTransform(){ const payload=JSON.parse(customJson); setTransformResult(await apiPost('/transform',{payload})); }
  async function pause(paused:boolean){ const r=await apiPost('/consumer/state',{paused}); setMessage(paused?'Consumer paused':'Consumer resumed'); setTimeout(refresh,500); }
  async function pressureRun(){ const r:any=await apiPost(`/events/pressure-test?total=${pressureTotal}`); setMessage(`Pressure test published ${r.published_count} events`); setTimeout(refresh,1500); }
  async function runFailure(sc:string){ const r:any=await apiPost('/failure-simulator/run',{scenario:sc}); setMessage(`Simulated ${sc}`); setTimeout(refresh,1000); }
  async function healSafe(){ const r:any=await apiPost('/pipeline/heal/safe'); setMessage('Safe pipeline healing executed'); setTimeout(refresh,1000); }
  async function approveIncident(id:number,status:string){ const r:any=await apiPost(`/incidents/${id}/status`,{status, reviewer_notes:'Reviewed from dashboard'}); setMessage(`Incident ${id} -> ${status}`); setTimeout(refresh,1000); }
  async function replayPayload(payload:any){ const r:any=await apiPost('/dlq/replay',{payload, reviewer:'dashboard', reviewer_notes:'replayed from DLQ tab'}); setMessage(`Replay submitted`); setTimeout(refresh,1000); }

  const chartData = useMemo(()=> summary ? [
    {name:'Orders', value:summary.orders_count}, {name:'Healed', value:summary.healed_count}, {name:'Manual', value:summary.manual_review_count}, {name:'Failed', value:summary.failed_count}, {name:'DLQ', value:summary.dlq_count}
  ] : [], [summary]);
  const timeline = useMemo(()=> [...journey].reverse().slice(-80).map((j,idx)=>({idx, stage:j.stage, count:idx+1})), [journey]);

  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="logo">SH</div><div><h1>Self Healing Platform</h1><p>Records + pipeline step healing</p></div></div>{tabs.map(t=><button key={t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t}</button>)}</aside><main><div className="topbar"><div><h1>{tab}</h1><p>Kafka → Consumer → Transform → Validate → Agent → PostgreSQL / Human / DLQ</p></div><button onClick={refresh}><RefreshCw size={16}/> Refresh</button></div>{error&&<div className="error">{error}</div>}{message&&<div className="toast">{message}</div>}

  {tab==='Overview' && <><div className="cards-grid"><Stat title="Clean Orders" value={summary?.orders_count} icon={<Database/>} color="green"/><Stat title="Incidents" value={summary?.incident_count} icon={<AlertTriangle/>} color="yellow"/><Stat title="Agent Healed" value={summary?.healed_count} icon={<Bot/>} color="blue"/><Stat title="Human Review" value={summary?.manual_review_count} icon={<ShieldCheck/>} color="purple"/><Stat title="Failed" value={summary?.failed_count} icon={<XCircle/>} color="red"/><Stat title="DLQ" value={summary?.dlq_count} icon={<GitBranch/>} color="red"/></div><div className="charts-grid"><div className="chart-card"><h3>Outcome split</h3><ResponsiveContainer width="100%" height={260}><BarChart data={chartData}><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="value" fill="#38bdf8"/></BarChart></ResponsiveContainer></div><div className="chart-card"><h3>Risk and healing rates</h3><JsonBlock data={{healing_rate:summary?.healing_rate, clean_insert_rate:summary?.clean_insert_rate, risk_score:summary?.risk_score, pressure_summary:pressure}}/></div></div></>}

  {tab==='System Design' && <Panel icon={<Workflow/>} title="Full system design and data journey" desc="Visual map of the whole data flow and every healing route."><div className="pipeline-wrap">{['Producer/API','Kafka raw_orders','Consumer','Transform','Schema Validate','Reason Act Verify Agent','PostgreSQL Orders'].map((n,i)=><React.Fragment key={n}><div className="pipeline-node"><div className="node-title">{n}</div><div className="node-caption">{i===5?'RAG evidence + OpenAI/fallback + guardrails': i===6?'clean and healed records':'live component of pipeline'}</div></div>{i<6&&<div className="arrow">→</div>}</React.Fragment>)}</div><div className="journey-grid"><div className="journey-card"><h3>Agent branch</h3><p>Invalid records move to RAG retrieval, reasoning, safe action selection, verification, and final routing.</p></div><div className="journey-card"><h3>Human branch</h3><p>High risk cases like financial ambiguity or missing customer identity stay pending for approval.</p></div><div className="journey-card"><h3>DLQ branch</h3><p>Unrecoverable or unsafe records are quarantined for later replay, audit, or rejection.</p></div><div className="journey-card"><h3>Pipeline healing</h3><p>Kafka, Redis, Postgres, OpenAI, Airflow, and consumer health are monitored and safely healed.</p></div></div><JsonBlock data={flow}/></Panel>}

  {tab==='Failure Simulator' && <Panel icon={<Zap/>} title="Failure simulator" desc="Break a component or publish failure data, then run safe healing and verify recovery."><div className="button-row"><button onClick={healSafe}><ShieldCheck size={16}/> Run safe pipeline healing</button></div><div className="scenario-grid">{failureScenarios.map((f:any)=><button className="scenario" key={f.id} onClick={()=>runFailure(f.id)}><b>{f.label}</b><br/><span>{f.risk} risk</span></button>)}</div><JsonBlock data={failureScenarios}/></Panel>}

  {tab==='Live Journey' && <Panel icon={<Activity/>} title="Live event journey trace" desc="Every event is traced across producer, Kafka, consumer, validation, agent, human, DLQ, and PostgreSQL."><div className="chart-card"><ResponsiveContainer width="100%" height={220}><AreaChart data={timeline}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="idx"/><YAxis/><Tooltip/><Area dataKey="count" stroke="#38bdf8" fill="#1d4ed8"/></AreaChart></ResponsiveContainer></div><DataTable rows={journey} cols={['created_at','event_id','stage','component','status','action','risk_level','reason']}/></Panel>}

  {tab==='Reason Act Verify' && <Panel icon={<Bot/>} title="Reason → Act → Verify traces" desc="For each incident, see detection, RAG evidence, decision, action, verification, and final route.">{incidents.slice(0,20).map(i=><div className="trace-card" key={i.incident_id}><h3>{i.event_id || 'unknown'} <span className={`pill ${i.status}`}>{i.status}</span></h3><div className="two-col"><div><b>Problem</b><p>{i.error_message}</p><b>Action</b><p>{i.healing_action || 'none'} | risk: {i.risk_level || 'unknown'}</p></div><div><b>Trace</b><ol>{(i.agent_trace && i.agent_trace.length? i.agent_trace : [{step:'Detect',reason:i.error_message},{step:'Reason',reason:`Selected ${i.healing_action}`},{step:'Verify',reason:i.status}]).map((s:any,idx:number)=><li key={idx}><b>{s.step}</b>: {s.reason || s.detail || s.act}</li>)}</ol></div></div></div>)}</Panel>}

  {tab==='Producer Controls' && <Panel icon={<Send/>} title="Producer, consumer and transformation controls" desc="Publish events, pause/resume the consumer, and preview transformations."><div className="button-row"><button onClick={publishDemo}><Send size={16}/> Publish Demo Dataset</button><button onClick={()=>pause(true)}><Pause size={16}/> Pause Consumer</button><button onClick={()=>pause(false)}><Play size={16}/> Resume Consumer</button><button onClick={previewTransform}><Eye size={16}/> Preview Transform</button><button onClick={publishCustom}><Send size={16}/> Publish Custom JSON</button></div><div className="scenario-grid">{scenarios.map(s=><button className="scenario" key={s} onClick={()=>publishScenario(s)}>{s}</button>)}</div><textarea className="code-input" value={customJson} onChange={e=>setCustomJson(e.target.value)}/>{transformResult&&<JsonBlock data={transformResult}/>}</Panel>}

  {tab==='Pressure Test' && <Panel icon={<Gauge/>} title="Pressure test dashboard" desc="Generate many records with clean, healable, human review, and DLQ routes."><div className="button-row"><input value={pressureTotal} type="number" min={1} max={100000} onChange={e=>setPressureTotal(Number(e.target.value))}/><button onClick={pressureRun}><Zap size={16}/> Start pressure test</button></div><JsonBlock data={pressure}/><p>Suggested demo: publish 1,000 records, watch consumer logs, refresh Live Journey, Risk Metrics, Agent Trace, and PostgreSQL Records.</p></Panel>}

  {tab==='PostgreSQL Records' && <Panel icon={<Database/>} title="Inserted PostgreSQL records" desc="These are clean records inserted into the sink table."><DataTable rows={orders} cols={['created_at','event_id','customer_id','amount','currency','status','schema_version']}/><h3>Demo SQL queries</h3><JsonBlock data={{orders:'SELECT event_id, customer_id, amount, currency, status, created_at FROM orders ORDER BY created_at DESC LIMIT 20;', incidents:'SELECT event_id, healing_action, risk_level, confidence, status FROM pipeline_incidents ORDER BY created_at DESC;', event_journey:'SELECT event_id, stage, component, status, reason FROM event_journey ORDER BY created_at DESC LIMIT 100;'}}/></Panel>}

  {tab==='Human Approval' && <Panel icon={<ShieldCheck/>} title="Human approval queue" desc="Risky records are not repaired automatically. Review, approve for replay, reject, or close.">{incidents.filter(i=>i.status==='manual_review').map(i=><div className="trace-card" key={i.incident_id}><h3>{i.event_id} <span className="pill manual_review">manual review</span></h3><p>{i.error_message}</p><div className="button-row"><button onClick={()=>approveIncident(i.incident_id,'approved_for_replay')}>Approve for replay</button><button onClick={()=>approveIncident(i.incident_id,'failed')}>Reject</button><button onClick={()=>approveIncident(i.incident_id,'closed')}>Close</button>{i.healed_payload&&<button onClick={()=>replayPayload(i.healed_payload)}>Replay healed payload</button>}</div><div className="two-col"><JsonBlock data={i.original_payload}/><JsonBlock data={i.healed_payload || {proposed:'none'}}/></div></div>)}</Panel>}

  {tab==='DLQ Replay' && <Panel icon={<RotateCcw/>} title="DLQ replay workflow" desc="Inspect failed records, replay manually fixed payloads, and audit replay attempts."><div className="two-col"><div><h3>Failed incidents</h3>{incidents.filter(i=>i.status==='failed').slice(0,20).map(i=><div className="trace-card" key={i.incident_id}><b>{i.event_id}</b><p>{i.error_message}</p><button onClick={()=>replayPayload(i.original_payload)}>Replay original</button></div>)}</div><div><h3>Replay audit</h3><DataTable rows={replayAudit} cols={['created_at','event_id','replay_status','reviewer','failure_reason']}/></div></div></Panel>}

  {tab==='RAG Evidence' && <Panel icon={<GitBranch/>} title="RAG evidence visibility" desc="Shows retrieved similar incidents used by the agent before it selects an action.">{rag.map((r:any)=><div className="trace-card" key={r.incident_id}><h3>{r.event_id} → {r.agent_action} <span className={`pill ${r.status}`}>{r.status}</span></h3><JsonBlock data={r.rag_evidence}/></div>)}</Panel>}

  {tab==='Schema Evolution' && <Panel icon={<GitBranch/>} title="Schema evolution" desc="Supported schema contracts and normalization policy."><JsonBlock data={schema}/><div className="button-row"><button onClick={()=>publishScenario('schema_v2_order')}>Publish v2 compatible event</button><button onClick={()=>publishScenario('unsupported_schema')}>Publish unsupported schema</button></div></Panel>}

  {tab==='Pipeline Step Healing' && <Panel icon={<ServerCog/>} title="Pipeline step healing" desc="Health checks, safe actions, human approval, and recovery verification for pipeline components."><div className="cards-grid">{(health?.components||[]).map((c:ComponentHealth)=><Stat key={c.component} title={c.component} value={c.status} icon={c.status==='healthy'?<CheckCircle/>:<AlertTriangle/>} color={c.status==='healthy'?'green':'red'}/>)}</div><div className="button-row"><button onClick={healSafe}>Run safe healing</button></div><DataTable rows={pipelineIncidents} cols={['created_at','component','problem_type','reason','recovery_action','risk_level','status','requires_human_approval']}/></Panel>}

  {tab==='Metrics' && <Panel icon={<Activity/>} title="Metrics and risk visualization" desc="Operational metrics and links to Prometheus."><div className="charts-grid"><div className="chart-card"><ResponsiveContainer width="100%" height={260}><PieChart><Pie data={chartData} dataKey="value" nameKey="name" outerRadius={90} label>{chartData.map((_,idx)=><Cell key={idx} fill={COLORS[idx%COLORS.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div><div className="chart-card"><JsonBlock data={{prometheus:'http://localhost:9090', api_metrics:'http://localhost:9108/metrics', consumer_metrics:'http://localhost:9109/metrics', summary}}/></div></div></Panel>}
  </main></div>;
}

function Panel({icon,title,desc,children}:{icon:React.ReactNode;title:string;desc:string;children:React.ReactNode}){return <div className="panel"><div className="panel-head">{icon}<div><h2>{title}</h2><p>{desc}</p></div></div>{children}</div>}
function DataTable({rows,cols}:{rows:any[];cols:string[]}){return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{rows.slice(0,200).map((r,idx)=><tr key={idx}>{cols.map(c=><td key={c}>{typeof r[c]==='object'?JSON.stringify(r[c]):String(r[c] ?? '')}</td>)}</tr>)}</tbody></table></div>}

createRoot(document.getElementById('root')!).render(<App/>);
