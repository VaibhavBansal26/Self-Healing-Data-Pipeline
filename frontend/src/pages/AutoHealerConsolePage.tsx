import {Activity, Bot, CheckCircle2, History, PlayCircle, RotateCw, Wrench} from 'lucide-react';
import {AutoHealerTerminal} from '../components/AutoHealerTerminal';
import {Panel} from '../components/Panel';
import {DataTable} from '../components/DataTable';
import {useState} from 'react';
import {apiPost} from '../lib/api';

type Props = {data:any; onChanged:()=>void};

export function AutoHealerConsolePage({data,onChanged}:Props){
  const [busyAction,setBusyAction]=useState<string>('');
  const [message,setMessage]=useState<string>('');
  async function run(action:string, fn:()=>Promise<any>){
    setBusyAction(action);
    setMessage('');
    try{
      const r = await fn();
      setMessage(r?.human_update || r?.message || `${action} completed`);
      await onChanged();
    }catch(e:any){ setMessage(e.message || String(e)); }
    finally{ setBusyAction(''); }
  }
  return <div className="page-stack">
    <AutoHealerTerminal autoHealer={data.autoHealer} traces={data.traces}/>

    <Panel icon={<Bot/>} title="Auto-heal actions" desc="These buttons affect only the selected action. The background worker still monitors continuously and auto-runs safe recovery actions.">
      <div className="action-grid">
        <button className="action-button" disabled={!!busyAction} onClick={()=>onChanged()}><RotateCw size={16}/> Refresh status</button>
        <button className="action-button primary" disabled={!!busyAction} onClick={()=>run('heal-safe',()=>apiPost('/pipeline/heal'))}>{busyAction==='heal-safe' ? <span className="button-spinner"/> : <Wrench size={16}/>} Auto heal safe issues</button>
        <button className="action-button" disabled={!!busyAction} onClick={()=>run('simulate-consumer',()=>apiPost('/failure-simulator/run',{scenario:'pause_consumer'}))}>{busyAction==='simulate-consumer' ? <span className="button-spinner"/> : <PlayCircle size={16}/>} Simulate consumer issue</button>
      </div>
      {message && <div className="inline-result"><CheckCircle2 size={16}/>{message}</div>}
    </Panel>

    <Panel icon={<Activity/>} title="Current stage decisions" desc="Compact list of each component, the current decision, and whether the action is automatic or approval-gated.">
      <DataTable rows={data.health?.components || []} cols={['component','status','problem_type','suggested_action','risk_level','requires_human_approval']}/>
    </Panel>

    <Panel icon={<History/>} title="Recovery history" desc="Past recovery attempts are stored so the agent can use previous decisions as memory.">
      <DataTable rows={data.pipelineIncidents || []} cols={['created_at','component','problem_type','recovery_action','status','risk_level','requires_human_approval']}/>
    </Panel>
  </div>;
}
