import {Bot} from 'lucide-react';
import {Panel} from '../components/Panel';
import {PayloadDiff} from '../components/PayloadDiff';
import {RiskBadge} from '../components/RiskBadge';
import type {Incident} from '../types/pipeline';

export function ReasonActVerify({incidents}:{incidents:Incident[]}){
  return <Panel icon={<Bot/>} title="Reason → Act → Verify" desc="Agent trace showing retrieval, reasoning, safe action, verification, and final route.">{incidents.slice(0,30).map(i=><div className="trace-card" key={i.incident_id}><h3>{i.event_id || 'unknown'} <RiskBadge risk={i.risk_level} status={i.status}/></h3><div className="two-col"><div><b>Problem</b><p>{i.error_message}</p><b>Action</b><p>{i.healing_action || 'none'}</p><b>Risk</b><p>{i.risk_level || 'unknown'}</p></div><div><b>Trace</b><ol>{(i.agent_trace && i.agent_trace.length? i.agent_trace : [{step:'Detect',reason:i.error_message},{step:'Reason',reason:`Selected ${i.healing_action}`},{step:'Verify',reason:i.status}]).map((s:any,idx:number)=><li key={idx}><b>{s.step}</b>: {s.reason || s.detail || s.act}</li>)}</ol></div></div><PayloadDiff original={i.original_payload} healed={i.healed_payload}/></div>)}</Panel>;
}
