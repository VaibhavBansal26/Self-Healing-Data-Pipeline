import {Activity, Bot, CheckCircle2, CircleDot, Clock, Loader2, TerminalSquare, Wrench, AlertTriangle} from 'lucide-react';

function parseMeta(row:any){
  const m = row?.metadata;
  if(!m) return {};
  if(typeof m === 'string'){
    try { return JSON.parse(m); } catch { return {message:m}; }
  }
  return m;
}

function eventText(row:any){
  const meta = parseMeta(row);
  if(meta.message) return meta.message;
  if(meta.initial_unhealthy_summary?.length) return `Detected ${meta.initial_unhealthy_summary.join(', ')}`;
  if(meta.remaining?.length) return `Remaining issues: ${meta.remaining.join(', ')}`;
  if(meta.summary?.length) return meta.summary.join(', ');
  if(meta.state) return `Agent state changed to ${meta.state}`;
  return `${row?.stage || 'auto-healer'} ${row?.status || ''}`.trim();
}

function lineKind(row:any){
  const status = String(row?.status || '');
  const stage = String(row?.stage || '');
  if(status.includes('recovered') || status.includes('completed')) return 'success';
  if(status.includes('unhealthy') || status.includes('started') || stage.includes('heal') || stage.includes('plan')) return 'active';
  if(status.includes('attention') || status.includes('failed') || status.includes('error')) return 'danger';
  if(stage.includes('sleep')) return 'sleep';
  return 'info';
}

function titleFor(row:any){
  const stage = String(row?.stage || 'background');
  const status = String(row?.status || 'info');
  if(stage === 'detect' && status === 'unhealthy_detected') return 'Issue detected';
  if(stage === 'plan') return 'Agent planning';
  if(stage === 'visible_delay') return 'Holding visible healing state';
  if(stage === 'heal' && status === 'started') return 'Running safe recovery';
  if(stage === 'heal' && status === 'completed') return 'Recovery command completed';
  if(stage === 'verify' && status === 'recovered') return 'Recovery verified';
  if(stage === 'sleep') return 'Agent sleeping';
  return `${stage}: ${status}`;
}

function stateLabel(state:string){
  const s = String(state || 'waiting');
  if(s.includes('healing') || s.includes('visible')) return 'Healing in progress';
  if(s.includes('recent') || s.includes('recovered')) return 'Recovered recently';
  if(s.includes('sleep')) return 'Sleeping';
  if(s.includes('attention')) return 'Needs attention';
  return s;
}

export function AutoHealerTerminal({autoHealer,traces,compact=false}:{autoHealer:any; traces?:any[]; compact?:boolean}){
  const traceRows = (traces || []).filter((t:any)=>t.trace_name === 'auto_healer');
  const rawRows = autoHealer?.current_cycle_events?.length ? autoHealer.current_cycle_events : (autoHealer?.recent_activity?.length ? autoHealer.recent_activity : traceRows);
  const importantRows = rawRows.filter((r:any)=>String(r?.stage || '') !== 'sleep' && String(r?.status || '') !== 'healthy');
  const rows = importantRows.length ? importantRows : rawRows.slice(0, 1);
  const state = String(autoHealer?.state || 'waiting');
  const active = state.includes('healing') || state.includes('visible') || state.includes('unhealthy') || state.includes('started');
  const recovered = state.includes('recent') || state.includes('recovered');
  const progress = active ? 62 : recovered ? 100 : state.includes('sleep') ? 0 : 15;
  const lastRows = rows.slice(0, compact ? 5 : 10);
  return <section className={`terminal-card ${active ? 'active' : recovered ? 'recovered' : 'idle'}`}>
    <div className="terminal-header">
      <div className="terminal-title"><TerminalSquare size={20}/><div><b>Background Auto-Healer Console</b><span>Live agent activity, safe recovery progress, and recent recovery history</span></div></div>
      <div className="terminal-state">{active ? <Loader2 className="spin" size={16}/> : recovered ? <CheckCircle2 size={16}/> : <Bot size={16}/>}<strong>{stateLabel(state)}</strong></div>
    </div>

    <div className="agent-progress-row">
      <div className={active || recovered ? 'done' : ''}><CircleDot size={15}/><span>Detect</span></div>
      <div className={active || recovered ? 'done' : ''}><Activity size={15}/><span>Plan</span></div>
      <div className={active ? 'working' : recovered ? 'done' : ''}><Wrench size={15}/><span>Heal safe</span></div>
      <div className={recovered ? 'done' : active ? 'working' : ''}><CheckCircle2 size={15}/><span>Verify</span></div>
      <div className={recovered ? 'done' : ''}><Clock size={15}/><span>Remember</span></div>
    </div>
    <div className="progress-track"><span style={{width:`${progress}%`}}/></div>

    <div className="terminal-output" aria-label="Auto-healer terminal output">
      {lastRows.length === 0 && <div className="terminal-line info"><span className="prompt">agent$</span><span>Waiting for background events. Stop consumer or Redis to test self-healing.</span></div>}
      {lastRows.map((row:any,idx:number)=>{
        const kind = lineKind(row);
        return <div className={`terminal-line ${kind}`} key={row.trace_id || idx}>
          <span className="prompt">agent$</span>
          <span className="time">{row.created_at ? new Date(row.created_at).toLocaleTimeString() : 'live'}</span>
          <span className="cmd">{titleFor(row)}</span>
          <span className="msg">{eventText(row)}</span>
        </div>;
      })}
    </div>

    <div className="terminal-help">
      <AlertTriangle size={15}/>
      <span>The live map shows current state; this console keeps the last recovery story visible so fast auto-heals do not disappear.</span>
    </div>
  </section>;
}
