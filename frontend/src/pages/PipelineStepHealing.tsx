import {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, HeartPulse, Loader2, PlayCircle, RotateCw, ShieldCheck, Sparkles, Wrench, Zap} from 'lucide-react';
import {Panel} from '../components/Panel';
import {DataTable} from '../components/DataTable';
import {JsonBlock} from '../components/JsonBlock';
import {apiGet, apiPost} from '../lib/api';
import {AutoHealerTerminal} from '../components/AutoHealerTerminal';

type Props = {
  health:any;
  pipelineIncidents:any[];
  onChanged:()=>void;
  autoHealer?: any;
  traces?: any[];
};

const statusIcon = (status:string) => status === 'healthy' ? <CheckCircle2 size={18}/> : <AlertTriangle size={18}/>;

function summarizeResult(result:any){
  if(!result) return null;
  const healed = result?.healed || result?.recovered || result?.status === 'recovered' || result?.status === 'healed';
  const attempted = result?.actions?.length || result?.results?.length || result?.action || result?.message;
  return {
    title: healed ? 'Safe healing completed' : attempted ? 'Healing action finished' : 'Action completed',
    message: result?.human_update || result?.message || result?.status || 'The agent finished the requested action and refreshed pipeline state.',
    status: healed ? 'success' : 'info'
  };
}

export function PipelineStepHealing({health,pipelineIncidents,onChanged,autoHealer,traces}:Props){
  const [result,setResult]=useState<any>(null);
  const [scenarios,setScenarios]=useState<any[]>([]);
  const [busyAction,setBusyAction]=useState('');
  const [busyLabel,setBusyLabel]=useState('');

  useEffect(()=>{ apiGet<any>('/failure-simulator/scenarios').then(r=>setScenarios(r.scenarios || [])).catch(()=>setScenarios([])); },[]);

  async function runWithStatus(label:string, fn:()=>Promise<any>){
    setBusyAction(label); setBusyLabel(label); setResult({pending:true, label});
    try {
      const r = await fn();
      setResult(r);
      await onChanged();
    } catch(e:any){
      setResult({error:true, message:e.message || String(e)});
    } finally {
      setBusyAction(''); setBusyLabel('');
    }
  }
  async function healSafe(){
    await runWithStatus('Agent is healing safe issues automatically…', ()=>apiPost('/pipeline/heal'));
  }
  async function healComponent(component:string, approve=false){
    await runWithStatus(`Agent is checking ${component} and applying a safe recovery…`, ()=>apiPost('/pipeline/heal/component',{component, approve_risky:approve}));
  }
  async function runScenario(id:string){
    await runWithStatus('Failure simulator is creating a pipeline issue…', ()=>apiPost('/failure-simulator/run',{scenario:id}));
  }

  const components = health?.components || [];
  const unhealthy = components.filter((c:any)=>c.status !== 'healthy');
  const summary = summarizeResult(result);
  const autoState = useMemo(()=>{
    const unhealthyCount = health?.unhealthy_count ?? unhealthy.length;
    if(busyAction) return {className:'active', title:'Agent is working', msg:busyLabel || 'Detecting, healing, and verifying the pipeline.'};
    if(unhealthyCount > 0) return {className:'warn', title:'Issues detected', msg:'Click Auto heal safe issues. Safe allowlisted actions run automatically; risky actions stay in Human Approval.'};
    return {className:'ok', title:'All safe stages verified', msg:'No automatic recovery is needed. Stop a service or run a simulator scenario to test healing.'};
  },[busyAction,busyLabel,health,unhealthy.length]);

  return <div>
    <AutoHealerTerminal autoHealer={autoHealer} traces={traces}/>

    <Panel icon={<HeartPulse/>} title="Pipeline self-healing control plane" desc="This is pipeline level healing: Kafka, consumer, PostgreSQL, Redis, OpenAI, Airflow, MCP context, memory, action, and verification.">
      <div className={`heal-status-banner ${autoState.className}`}>
        <div className="heal-status-icon">{busyAction ? <Loader2 className="spin"/> : autoState.className==='ok' ? <CheckCircle2/> : <Zap/>}</div>
        <div>
          <b>{autoState.title}</b>
          <p>{autoState.msg}</p>
        </div>
      </div>
      <div className="heal-steps">
        <span className={busyAction?'active':''}>1 Detect</span>
        <span className={busyAction?'active':''}>2 Plan</span>
        <span className={busyAction?'active':''}>3 Heal safe</span>
        <span className={busyAction?'active':''}>4 Verify</span>
        <span className={busyAction?'active':''}>5 Store memory</span>
      </div>
      <div className="button-row sticky-actions">
        <button onClick={onChanged} disabled={!!busyAction}><RotateCw size={16}/> Run health check</button>
        <button className={`heal-button ${busyAction==='Agent is healing safe issues automatically…'?'working':''}`} onClick={healSafe} disabled={!!busyAction}>
          {busyAction==='Agent is healing safe issues automatically…' ? <Loader2 className="spin" size={16}/> : <Wrench size={16}/>} {busyAction==='Agent is healing safe issues automatically…' ? 'Healing in progress…' : 'Auto heal safe issues'}
        </button>
      </div>
      {summary && <div className={`operator-toast ${summary.status}`}>
        <b>{summary.title}</b><span>{summary.message}</span>
        {result && !result.pending && <details><summary>Technical response</summary><JsonBlock data={result}/></details>}
      </div>}
      <div className="explain light-explain">
        <b>Automatic does not mean reckless.</b> The agent auto-executes safe allowlisted actions such as restarting the consumer, restarting Airflow, creating a missing Kafka topic, or running reconciliation. It asks only when the action is risky, destructive, changes business data, or cannot be verified.
      </div>
    </Panel>

    <Panel icon={<Sparkles/>} title="Agent decision layer" desc="The cards below stay compact. They show what each component is doing, what the agent plans, and whether action is automatic or approval-gated.">
      {unhealthy.length === 0 && <div className="empty-state"><CheckCircle2/> All monitored pipeline components are currently healthy. Use the failure simulator below to test self healing.</div>}
      <div className="component-grid compact-components">
        {components.map((c:any)=><div className={`component-card compact ${c.status}`} key={`${c.component}-${c.problem_type}`}>
          <div className="component-head"><div>{statusIcon(c.status)}<b>{c.component}</b></div><span className={`pill ${c.status}`}>{c.status}</span></div>
          <p>{c.reason}</p>
          <div className="mini-grid"><span>Problem</span><b>{c.problem_type}</b><span>Action</span><b>{c.suggested_action}</b><span>Mode</span><b>{c.requires_human_approval ? 'approval' : c.status==='healthy' ? 'none' : 'auto if safe'}</b></div>
          {c.status !== 'healthy' && <div className="button-row compact"><button disabled={!!busyAction} onClick={()=>healComponent(c.component,false)}>{busyAction===`Agent is checking ${c.component} and applying a safe recovery…` ? <Loader2 className="spin" size={14}/> : <PlayCircle size={14}/>} Heal safe</button>{c.requires_human_approval && <button disabled={!!busyAction} onClick={()=>healComponent(c.component,true)} className="secondary">Approve risky action</button>}</div>}
          {c.agent_plan && <details className="compact-details"><summary>Plan, memory, MCP context</summary><JsonBlock data={c.agent_plan}/></details>}
        </div>)}
      </div>
    </Panel>

    <Panel icon={<AlertTriangle/>} title="Failure simulator" desc="Use these scenarios to prove pipeline self healing beyond record level validation.">
      <div className="scenario-grid compact-scenarios">{scenarios.map((s:any)=><button className="scenario clean" key={s.id} onClick={()=>runScenario(s.id)} disabled={!!busyAction}><b>{s.label}</b><small>{s.description}</small></button>)}</div>
    </Panel>

    <Panel icon={<ShieldCheck/>} title="Pipeline healing memory" desc="Every recovery action is logged. Future agent decisions use this previous outcome memory to avoid repeating bad actions.">
      <DataTable rows={pipelineIncidents} cols={['created_at','component','problem_type','recovery_action','risk_level','status','requires_human_approval']}/>
    </Panel>
  </div>;
}
