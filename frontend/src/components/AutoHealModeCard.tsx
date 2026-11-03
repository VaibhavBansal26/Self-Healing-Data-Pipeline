import {CheckCircle2, ShieldAlert, Wrench, Zap, AlertTriangle} from 'lucide-react';

function dockerRuntimeState(health:any){
  const stages = health?.stage_map || [];
  const reasons = stages.map((s:any)=>String(s.reason || '')).join(' ').toLowerCase();
  const components = health?.components || [];
  const dockerStates = JSON.stringify(components.map((c:any)=>c.detected_state || {})).toLowerCase();
  if (reasons.includes('docker_socket_unavailable') || dockerStates.includes('docker_socket_unavailable')) return 'disconnected';
  if (dockerStates.includes('container_running') || dockerStates.includes('docker_state')) return 'connected';
  return 'unknown';
}

export function AutoHealModeCard({health}:{health:any}){
  const dockerState = dockerRuntimeState(health);
  const unhealthy = health?.unhealthy_count || 0;
  const agent = health?.agent_status || {};
  const hasApproval = (health?.components || []).some((c:any)=>c.requires_human_approval);
  const autoHealPossible = dockerState === 'connected' && !hasApproval;
  const statusClass = dockerState === 'connected' ? 'green' : dockerState === 'disconnected' ? 'yellow' : 'blue';
  return <div className={`autoheal-card ${statusClass}`}>
    <div className="autoheal-main">
      <div className="autoheal-icon">{dockerState === 'connected' ? <Zap/> : <AlertTriangle/>}</div>
      <div>
        <span className="eyebrow">Auto-heal control</span>
        <h2>{autoHealPossible ? 'Safe auto-healing is ready' : 'Safe healing needs verification'}</h2>
        <p>{dockerState === 'connected'
          ? 'The control plane can inspect Docker runtime state. Low-risk, allowlisted recoveries can run automatically and then verify the stage again.'
          : 'Docker runtime access is not verified. The agent can detect symptoms and recommend actions, but it will avoid blind recovery until it can verify containers.'}</p>
      </div>
    </div>
    <div className="autoheal-grid">
      <div><CheckCircle2 size={16}/><b>Runtime access</b><span>{dockerState}</span></div>
      <div><Wrench size={16}/><b>Unhealthy stages</b><span>{unhealthy}</span></div>
      <div><ShieldAlert size={16}/><b>Risky actions</b><span>{hasApproval ? 'approval required' : 'none pending'}</span></div>
      <div><Zap size={16}/><b>Agent state</b><span>{agent.state || 'unknown'}</span></div>
    </div>
    <div className="autoheal-policy">
      <b>How automatic healing works</b>
      <p>Safe actions such as restarting the consumer, restarting Airflow, creating a missing Kafka topic, or running reconciliation are auto-executed only when the action is allowlisted and the platform can verify the result. Risky actions such as replaying DLQ records, changing financial payloads, or historically failed recoveries are routed to human approval.</p>
    </div>
  </div>;
}
