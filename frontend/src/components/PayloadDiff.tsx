import {JsonBlock} from './JsonBlock';

function changedFields(original:any, healed:any){
  const keys = Array.from(new Set([...Object.keys(original||{}), ...Object.keys(healed||{})]));
  return keys.map(k=>({field:k, original:original?.[k], healed:healed?.[k], changed:JSON.stringify(original?.[k])!==JSON.stringify(healed?.[k])}));
}

export function PayloadDiff({original, healed}:{original:any; healed:any}){
  if(!healed) return <div className="two-col"><JsonBlock data={original}/><JsonBlock data={{proposed:'none'}}/></div>;
  return <div><div className="table-wrap"><table><thead><tr><th>field</th><th>original</th><th>healed</th><th>change</th></tr></thead><tbody>{changedFields(original, healed).map(row=><tr key={row.field} className={row.changed?'changed-row':''}><td>{row.field}</td><td>{JSON.stringify(row.original)}</td><td>{JSON.stringify(row.healed)}</td><td>{row.changed?'changed':'same'}</td></tr>)}</tbody></table></div><div className="two-col"><JsonBlock data={original}/><JsonBlock data={healed}/></div></div>
}
