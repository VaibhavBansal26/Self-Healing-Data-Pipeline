import {Activity, CheckCircle2, Clock, Loader2, ShieldAlert, Wrench, Zap, History} from 'lucide-react';
import {JsonBlock} from './JsonBlock';

function metaOf(row:any){
  const m=row?.metadata;
  if(!m) return {};
  if(typeof m === 'string'){
    try { return JSON.parse(m); } catch { return {raw:m}; }
  }
  return m;
}

function stepLabel(row:any){
  const stage=row?.stage || 'background';
  const status=row?.status || 'info';
  if(stage === 'detect' && status === 'started') return 'Checking pipeline health';
  if(stage === 'detect' && status === 'unhealthy_detected') return 'Issue detected';
  if(stage === 'plan' && status === 'agent_active') return 'Agent planning recovery';
  if(stage === 'visible_delay') return 'Keeping healing visible';
  if(stage === 'heal' && status === 'started') return 'Running safe recovery';
  if(stage === 'heal' && status === 'completed') return 'Recovery command completed';
  if(stage === 'verify' && status === 'recovered') return 'Recovery verified';
  if(stage === 'verify' && status === 'needs_attention') return 'Needs attention';
  if(stage === 'ui_latch' && status === 'recently_recovered') return 'Recently auto-healed';
  if(stage === 'sleep') return 'Agent sleeping';
  return `${stage}: ${status}`;
}

function stateCopy(state:string){
  if(String(state).includes('healing')) return 'Agent is actively detecting, planning, healing, or verifying a pipeline issue.';
  if(String(state).includes('recently_recovered') || String(state).includes('recovered')) return 'Agent recently completed an automatic recovery. The live pipeline may already be green again.';
  if(String(state).includes('attention')) return 'Agent tried to heal but some stages still need attention or approval.';
  if(String(state).includes('sleep')) return 'Agent is sleeping because all monitored stages are healthy.';
  return 'Background auto-healer is monitoring the pipeline.';
}

export function BackgroundActivityPanel({autoHealer,traces}:{autoHealer:any; traces?:any[]}){
  const cycleRows = autoHealer?.current_cycle_events || [];
  const rows = cycleRows.length ? cycleRows : (autoHealer?.recent_activity?.length ? autoHealer.recent_activity : (traces || []).filter((t:any)=>t.trace_name === 'auto_healer').slice(0,12));
  const state = autoHealer?.state || 'waiting';
  const active = ['healing','unhealthy_detected','started','needs_attention','visible'].some(x=>String(state).includes(x));
  const recovered = ['recently_recovered','recovered'].some(x=>String(state).includes(x));
  const healthy = ['sleeping','healthy'].some(x=>String(state).includes(x));
  const bannerClass = active ? 'active' : recovered ? 'recovered' : healthy ? 'healthy' : 'waiting';
  return <div className={`background-panel ${bannerClass}`}>
    <div className="background-head">
      <div className="background-title">
        <span className="background-orb">{active ? <Loader2 className="spin"/> : recovered ? <Zap/> : healthy ? <CheckCircle2/> : <Activity/>}</span>
        <div>
          <b>{active ? 'Agent is healing now' : recovered ? 'Agent just healed something' : 'Background auto-healer'}</b>
          <p>{autoHealer?.latest_message || stateCopy(state)}</p>
          <small>{stateCopy(state)}</small>
        </div>
      </div>
      <div className="background-state">
        <span>{autoHealer?.enabled ? 'Auto-heal enabled' : 'Auto-heal disabled'}</span>
        <strong>{state}</strong>
      </div>
    </div>

    <div className="background-flow">
      <div className={active ? 'pulse-step' : ''}><Clock size={16}/><b>Detect</b><span>Poll /pipeline/health</span></div>
      <div className={active ? 'pulse-step' : ''}><Activity size={16}/><b>Plan</b><span>Policy + memory + MCP</span></div>
      <div className={active ? 'pulse-step' : ''}><Wrench size={16}/><b>Heal safe</b><span>Auto-run allowlisted action</span></div>
      <div className={active || recovered ? 'pulse-step' : ''}><CheckCircle2 size={16}/><b>Verify</b><span>Recheck stage health</span></div>
      <div><ShieldAlert size={16}/><b>Escalate</b><span>Risky actions need approval</span></div>
    </div>

    <div className="background-mini-note">
      <History size={15}/> Fast recoveries can finish in seconds. This panel keeps recent recovery history visible even when the live map is already green again.
    </div>

    <div className="background-timeline">
      {rows.length === 0 && <div className="empty-state small"><Activity/> Waiting for the auto-healer to write its first background event. Check docker compose logs -f auto-healer.</div>}
      {rows.slice(0,12).map((row:any,idx:number)=>{
        const meta=metaOf(row);
        return <div className={`background-event ${row.status || ''}`} key={row.trace_id || idx}>
          <span>{idx+1}</span>
          <div>
            <b>{stepLabel(row)}</b>
            <p>{meta.message || meta.state || meta.summary?.join?.(', ') || meta.initial_unhealthy_summary?.join?.(', ') || row.stage}</p>
            <small>{row.created_at || 'live'} · {row.status}</small>
          </div>
          {idx===0 && <details><summary>details</summary><JsonBlock data={row}/></details>}
        </div>
      })}
    </div>
  </div>;
}
