import {useMemo, useState} from 'react';
import {CheckCircle2, Loader2, ShieldCheck} from 'lucide-react';
import {apiPost} from '../lib/api';
import {Panel} from '../components/Panel';
import {PayloadDiff} from '../components/PayloadDiff';
import {RiskBadge} from '../components/RiskBadge';
import type {Incident} from '../types/pipeline';

export function HumanApproval({incidents,onChanged}:{incidents:Incident[]; onChanged:()=>void | Promise<void>}){
  const [busyId,setBusyId]=useState<number|null>(null);
  const [localDecisions,setLocalDecisions]=useState<Record<number,string>>({});
  const [lastMessage,setLastMessage]=useState('');

  async function approveIncident(id:number,status:string){
    setBusyId(id);
    setLastMessage('Submitting operator decision…');
    try{
      const res = await apiPost(`/incidents/${id}/status`,{status, reviewer_notes:'Reviewed from React dashboard'});
      setLocalDecisions(prev=>({...prev,[id]:status}));
      setLastMessage(`Decision saved: ${status}. The item was removed from the active approval queue.`);
      await onChanged();
      return res;
    } finally {
      setBusyId(null);
    }
  }

  async function replayPayload(payload:any, id:number){
    setBusyId(id);
    setLastMessage('Replaying approved healed payload…');
    try{
      const res = await apiPost('/dlq/replay',{payload, reviewer:'dashboard', reviewer_notes:'replayed from manual approval tab'});
      setLastMessage('Replay request submitted. Check DLQ Replay audit for the result.');
      await onChanged();
      return res;
    } finally {
      setBusyId(null);
    }
  }

  const queue=useMemo(()=>incidents.filter(i=>i.status==='manual_review' && !localDecisions[i.incident_id]),[incidents,localDecisions]);
  const reviewed=useMemo(()=>incidents.filter(i=>localDecisions[i.incident_id] || i.status==='approved_for_replay' || i.status==='closed' || i.status==='failed').slice(0,8),[incidents,localDecisions]);

  return <Panel icon={<ShieldCheck/>} title="Human approval queue" desc="High risk AI repairs require operator approval. After approval/rejection, the item is removed from the active queue and shown in recent decisions.">
    {lastMessage && <div className="operator-toast success"><b>Approval update</b><span>{lastMessage}</span></div>}
    {queue.length===0 && <div className="empty-state"><CheckCircle2/> No active manual review items right now.</div>}
    {queue.map(i=><div className="trace-card" key={i.incident_id}>
      <h3>{i.event_id || 'unknown'} <RiskBadge risk={i.risk_level} status={i.status}/></h3>
      <p>{i.error_message}</p>
      <div className="button-row">
        <button disabled={busyId===i.incident_id} onClick={()=>approveIncident(i.incident_id,'approved_for_replay')}>{busyId===i.incident_id ? <Loader2 className="spin" size={14}/> : null} Approve for replay</button>
        <button disabled={busyId===i.incident_id} onClick={()=>approveIncident(i.incident_id,'failed')}>Reject</button>
        <button disabled={busyId===i.incident_id} onClick={()=>approveIncident(i.incident_id,'closed')}>Close</button>
        {i.healed_payload&&<button disabled={busyId===i.incident_id} onClick={()=>replayPayload(i.healed_payload,i.incident_id)}>Replay healed payload</button>}
      </div>
      <PayloadDiff original={i.original_payload} healed={i.healed_payload}/>
    </div>)}
    {reviewed.length>0 && <details className="compact-details" open={false}><summary>Recent approval decisions</summary><div className="approval-history">{reviewed.map(i=><div className="mini-row" key={i.incident_id}><b>{i.event_id || i.incident_id}</b><span>{localDecisions[i.incident_id] || i.status}</span></div>)}</div></details>}
  </Panel>;
}
