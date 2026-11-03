import {Bar, BarChart, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid} from 'recharts';

function colorFor(color:string){
  if(color === 'green') return '#22c55e';
  if(color === 'yellow') return '#f59e0b';
  if(color === 'red') return '#ef4444';
  if(color === 'blue') return '#2563eb';
  return '#94a3b8';
}

export function DynamicHealthCharts({data}:{data:any}){
  const stages = data.health?.stage_map || [];
  const statusCounts = ['green','yellow','red'].map(color => ({
    status: color === 'green' ? 'Healthy' : color === 'yellow' ? 'Healing / degraded' : 'Down / blocked',
    value: stages.filter((s:any)=>s.color===color).length,
    color
  }));
  const outcome = data.summary ? [
    {name:'Clean orders', value:data.summary.orders_count || 0},
    {name:'Healed', value:data.summary.healed_count || 0},
    {name:'Manual review', value:data.summary.manual_review_count || 0},
    {name:'Failed', value:data.summary.failed_count || 0},
    {name:'DLQ', value:data.summary.dlq_count || 0},
  ] : [];
  const traceRows = (data.traces || []).slice(0,12).reverse().map((t:any, idx:number)=>({
    step: idx + 1,
    events: idx + 1,
    status: t.status || t.event_type || 'trace'
  }));
  const recovery = [
    {name:'Approvals', value:(data.approvals || []).length},
    {name:'Alerts', value:(data.alerts || []).length},
    {name:'Traces', value:(data.traces || []).length},
    {name:'Incidents', value:(data.pipelineIncidents || []).length},
  ];
  return <div className="dynamic-chart-grid">
    <div className="chart-card polished">
      <h3>Pipeline stage status</h3>
      <p>Live distribution of green, yellow, and red pipeline stages.</p>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Tooltip/>
          <Pie data={statusCounts} dataKey="value" nameKey="status" innerRadius={55} outerRadius={86} paddingAngle={4}>
            {statusCounts.map((row)=><Cell key={row.status} fill={colorFor(row.color)}/>) }
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
    <div className="chart-card polished">
      <h3>Record healing outcomes</h3>
      <p>Shows how events are flowing through clean insert, healing, human review, failure, and DLQ paths.</p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={outcome}>
          <CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name" tick={{fontSize:11}}/><YAxis allowDecimals={false}/><Tooltip/>
          <Bar dataKey="value" radius={[10,10,0,0]} fill="#2563eb"/>
        </BarChart>
      </ResponsiveContainer>
    </div>
    <div className="chart-card polished">
      <h3>Agent trace activity</h3>
      <p>Timeline proxy for detect, plan, act, verify, and memory-update events.</p>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={traceRows}>
          <CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="step"/><YAxis allowDecimals={false}/><Tooltip/>
          <Line type="monotone" dataKey="events" stroke="#0ea5e9" strokeWidth={3} dot={{r:4}}/>
        </LineChart>
      </ResponsiveContainer>
    </div>
    <div className="chart-card polished">
      <h3>Recovery control signals</h3>
      <p>Operational control-plane indicators used by the pipeline healing agent.</p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={recovery} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" allowDecimals={false}/><YAxis dataKey="name" type="category" width={92}/><Tooltip/>
          <Bar dataKey="value" radius={[0,10,10,0]} fill="#14b8a6"/>
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>;
}
