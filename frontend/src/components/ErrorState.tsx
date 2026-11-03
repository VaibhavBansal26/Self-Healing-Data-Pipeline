import {AlertTriangle, RefreshCw} from 'lucide-react';

export function ErrorState({message,onRetry}:{message:string; onRetry?:()=>void}){
  return <div className="error-state">
    <AlertTriangle size={20}/>
    <div><strong>Something did not load</strong><p>{message}</p></div>
    {onRetry && <button className="action-button" onClick={onRetry}><RefreshCw size={14}/> Retry</button>}
  </div>;
}
