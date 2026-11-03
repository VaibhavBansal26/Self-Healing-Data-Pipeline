import {RefreshCw} from 'lucide-react';
import {usePipelineData} from './api/usePipelineData';
import {Overview} from './pages/Overview';
import {ProducerControls} from './pages/ProducerControls';
import {LiveJourney} from './pages/LiveJourney';
import {ReasonActVerify} from './pages/ReasonActVerify';
import {HumanApproval} from './pages/HumanApproval';
import {Metrics} from './pages/Metrics';
import {AIEngineering} from './pages/AIEngineering';
import {PipelineStepHealing} from './pages/PipelineStepHealing';
import {AutoHealerConsolePage} from './pages/AutoHealerConsolePage';
import {PipelineMapPage} from './pages/PipelineMapPage';
import {DataOpsPage} from './pages/DataOpsPage';

import {SectionInfo} from './components/SectionInfo';
import {ErrorState} from './components/ErrorState';
import {useState} from 'react';

const navGroups = [
  {label:'Operate', tabs:['Overview','Auto-Healer Console','Pipeline Map','Pipeline Step Healing']},
  {label:'Data flow', tabs:['Producer Controls','Live Journey','Reason Act Verify','Human Approval','Data Store']},
  {label:'Observability', tabs:['Metrics','AI Engineering']},
];
const tabs = navGroups.flatMap(g=>g.tabs);

const sectionInfo: Record<string, {purpose:string; shows:string[]; test:string}> = {
  'Overview': {purpose:'The control room for the complete platform. It shows the connected workflow, stage health, agent status, failure visualization, and top-level counts.', shows:['Connected node workflow with green/yellow/red state','Human-spoken agent updates','Charts for stage health, outcomes, traces, and recovery signals'], test:'Stop a stage such as consumer or Redis, then refresh. The affected node should change color and the agent should explain what it detected.'},
  'Producer Controls': {purpose:'Publishes valid, repairable, risky, and broken events into Kafka so you can test how the pipeline behaves.', shows:['Buttons or scenarios for demo events','Record-level healing scenarios','Failures that lead to human approval or DLQ'], test:'Send a demo batch, then check Reason Act Verify, PostgreSQL Records, and DLQ Replay.'},
  'Live Journey': {purpose:'Shows how events move across pipeline stages from API gateway to Kafka, consumer, healing, database, or DLQ.', shows:['Per-event journey rows','Stage, component, status, and reason','Metadata for debugging'], test:'Publish a few events and refresh to watch their path appear in the journey table.'},
  'Reason Act Verify': {purpose:'Explains record-level healing. It shows why a payload failed, what action was taken, and whether validation passed after repair.', shows:['Original and healed payloads','Rules/agent/human/DLQ action','RAG evidence and agent trace when available'], test:'Send amount as a string, missing currency, semantic status, and a broken payload.'},
  'Human Approval': {purpose:'Operator review queue for risky repairs. The system should not invent critical values or replay risky DLQ events without approval.', shows:['Manual review records','Risk score and repair reason','Approve/reject controls'], test:'Send an event missing customer_id or with a risky amount and check that it appears for review.'},
  'Data Store': {purpose:'Data operations section for PostgreSQL sink records, DLQ replay audit, failed events, and schema evolution. This keeps storage views separate from the live control room.', shows:['Inserted records','Failed incidents and replay audit','Schema contract information'], test:'Publish valid and invalid events, then check where they landed.'},
  'Auto-Healer Console': {purpose:'A terminal-style view of the background auto-healer. It shows what the agent is doing right now, what it just healed, and each step in the recovery cycle.', shows:['Terminal log of Detect → Plan → Heal → Verify','Current progress bar and recent recovery latch','Action buttons with button-specific loading state'], test:'Run docker compose stop consumer and watch this page show the recovery cycle.'},
  'Pipeline Map': {purpose:'A clean connected map of the application workflow. Use this page to understand which stage is healthy, healing, or down without crowding other sections.', shows:['Compact connected workflow','Detailed stage cards','Stage health and recovery charts'], test:'Stop Redis or consumer and verify the affected node changes color.'},
  'Pipeline Step Healing': {purpose:'Detailed operational view for pipeline-stage healing. It shows component decisions, recovery memory, and simulator actions.', shows:['Component health','Agent plan and memory evidence','Recovery actions, alerts, traces, approvals'], test:'Run docker compose stop consumer, then watch auto-healer or click Auto heal safe issues.'},
  'Metrics': {purpose:'Operational and AI metrics for reliability, recovery, Kafka lag, pressure tests, and observability.', shows:['Pipeline metrics','Kafka lag','Prometheus-style counters','Load/pressure snapshots'], test:'Run producer/load tests and check that counters and health indicators update.'},
  'AI Engineering': {purpose:'Shows the AI engineering layer: prompt injection defense, semantic cache, retrieval evals, MCP tool-use evals, trajectory, costs, and LangSmith status.', shows:['Agent timeline','Safety/eval scores','Tool selection and memory behavior','Token/cost summaries'], test:'Call semantic cache demo twice, run prompt injection safe-context, and trigger a pipeline failure to generate trajectory events.'}
};

export function App(){
  const [tab,setTab]=useState('Overview');
  const {data,error,loading,refresh}=usePipelineData();
  const info=sectionInfo[tab];
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="logo">SH</div><div><h1>Self Healing Platform</h1><p>Production-style recovery lab</p></div></div>{navGroups.map(g=><div className="nav-group" key={g.label}><span>{g.label}</span>{g.tabs.map(t=><button key={t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t}</button>)}</div>)}</aside><main><div className="topbar"><div><h1>{tab}</h1><p>Kafka → Consumer → Rules → RAG → LangGraph → Human / DLQ / PostgreSQL</p></div><button onClick={refresh}><RefreshCw size={16}/> Refresh</button></div>{info && <SectionInfo title={tab} purpose={info.purpose} shows={info.shows} test={info.test}/>} {loading&&<div className="loading-banner"><span className="button-spinner"/> Loading platform sections...</div>} {error&&<ErrorState message={error} onRetry={refresh}/>}
    {tab==='Overview' && <Overview data={data}/>} 
    {tab==='Auto-Healer Console' && <AutoHealerConsolePage data={data} onChanged={refresh}/>} 
    {tab==='Pipeline Map' && <PipelineMapPage data={data}/>} 
    {tab==='Producer Controls' && <ProducerControls onChanged={refresh}/>} 
    {tab==='Live Journey' && <LiveJourney journey={data.journey}/>} 
    {tab==='Reason Act Verify' && <ReasonActVerify incidents={data.incidents}/>} 
    {tab==='Human Approval' && <HumanApproval incidents={data.incidents} onChanged={refresh}/>} 
    {tab==='Data Store' && <DataOpsPage data={data}/>} 
    {tab==='Pipeline Step Healing' && <PipelineStepHealing health={data.health} pipelineIncidents={data.pipelineIncidents} autoHealer={data.autoHealer} traces={data.traces} onChanged={refresh}/>} 
    {tab==='Metrics' && <Metrics data={data}/>} 
    {tab==='AI Engineering' && <AIEngineering coverage={data.aiCoverage} costs={data.aiCosts} evals={data.aiEvals} langsmith={data.langsmith} promptInjection={data.promptInjection} semanticCache={data.semanticCache} retrievalEval={data.retrievalEval} toolUseEval={data.toolUseEval} trajectory={data.trajectory} aiOps={data.aiOps}/>} 
  </main></div>;
}
