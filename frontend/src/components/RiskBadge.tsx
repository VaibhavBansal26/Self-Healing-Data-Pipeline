export function RiskBadge({risk,status}:{risk?:string;status?:string}){const label=risk||status||'unknown'; return <span className={`pill ${status||risk||''}`}>{label}</span>}
