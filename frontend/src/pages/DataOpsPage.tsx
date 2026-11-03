import {Database, GitBranch, Workflow} from 'lucide-react';
import {Panel} from '../components/Panel';
import {DataTable} from '../components/DataTable';
import {JsonBlock} from '../components/JsonBlock';

export function DataOpsPage({data}:{data:any}){
  return <div className="page-stack">
    <Panel icon={<Database/>} title="PostgreSQL records" desc="Clean and healed records inserted into the sink table.">
      <DataTable rows={data.orders} cols={['created_at','event_id','customer_id','amount','currency','status','schema_version']}/>
    </Panel>
    <Panel icon={<GitBranch/>} title="DLQ replay and failed records" desc="Unrecoverable payloads and replay audit history.">
      <div className="two-col"><div><h3>Failed incidents</h3><DataTable rows={(data.incidents || []).filter((i:any)=>i.status==='failed')} cols={['created_at','event_id','healing_action','risk_level','status','error_message']}/></div><div><h3>Replay audit</h3><DataTable rows={data.replayAudit} cols={['created_at','event_id','replay_status','reviewer','failure_reason']}/></div></div>
    </Panel>
    <Panel icon={<Workflow/>} title="Schema evolution" desc="Supported schema contracts and compatibility policy.">
      <JsonBlock data={data.schema}/>
    </Panel>
  </div>;
}
