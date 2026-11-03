import {EmptyState} from './EmptyState';

function humanize(value:any){
  if(value === null || value === undefined || value === '') return '—';
  if(typeof value === 'boolean') return value ? 'yes' : 'no';
  if(typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function DataTable({rows,cols,emptyTitle='No rows yet',emptyDescription='Run a scenario or refresh the dashboard to populate this table.'}:{rows:any[];cols:string[];emptyTitle?:string;emptyDescription?:string}){
  if(!rows || rows.length===0){
    return <EmptyState title={emptyTitle} description={emptyDescription}/>;
  }
  return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c}>{c.split('_').join(' ')}</th>)}</tr></thead><tbody>{rows.slice(0,200).map((r,idx)=><tr key={idx}>{cols.map(c=><td key={c}>{humanize(r[c])}</td>)}</tr>)}</tbody></table></div>
}
