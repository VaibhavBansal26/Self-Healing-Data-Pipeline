import {Inbox} from 'lucide-react';

export function EmptyState({title='No data yet', description='Run a demo scenario or refresh once the service is ready.', action}:{title?:string; description?:string; action?:React.ReactNode}){
  return <div className="empty-state">
    <div className="empty-icon"><Inbox size={20}/></div>
    <div><strong>{title}</strong><p>{description}</p>{action}</div>
  </div>;
}
