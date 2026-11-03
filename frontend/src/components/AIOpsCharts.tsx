import {Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts';

function colorFor(name:string){
  const n=(name||'').toLowerCase();
  if(n.includes('down') || n.includes('critical')) return '#ef4444';
  if(n.includes('self') || n.includes('high') || n.includes('medium')) return '#f59e0b';
  if(n.includes('healthy') || n.includes('hits')) return '#22c55e';
  return '#2563eb';
}

export function AIOpsCharts({ops}:{ops:any}){
  const charts=ops?.charts || {};
  const stageHealth=charts.stage_health || [];
  const mcpSuccess=charts.mcp_success || [];
  const ragScores=charts.rag_scores || [];
  const logSeverity=charts.log_severity || [];
  const cache=charts.cache || [];
  return <div className="aiops-chart-grid">
    <div className="chart-card polished"><h3>Stage health split</h3><p>Shows how many workflow nodes are healthy, self-healing, or down.</p><ResponsiveContainer width="100%" height={230}><PieChart><Tooltip/><Pie data={stageHealth} dataKey="value" nameKey="name" innerRadius={52} outerRadius={84} paddingAngle={4}>{stageHealth.map((r:any)=><Cell key={r.name} fill={colorFor(r.name)}/>)}</Pie></PieChart></ResponsiveContainer></div>
    <div className="chart-card polished"><h3>MCP agent success rate</h3><p>Component-specific MCP agents and their recent tool reliability.</p><ResponsiveContainer width="100%" height={230}><BarChart data={mcpSuccess} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" domain={[0,100]}/><YAxis dataKey="agent" type="category" width={92}/><Tooltip/><Bar dataKey="success_rate" radius={[0,10,10,0]} fill="#14b8a6"/></BarChart></ResponsiveContainer></div>
    <div className="chart-card polished"><h3>RAG memory similarity</h3><p>Top retrieved memories used as evidence before recovery planning.</p><ResponsiveContainer width="100%" height={230}><BarChart data={ragScores}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="memory" tick={{fontSize:10}}/><YAxis/><Tooltip/><Bar dataKey="score" radius={[10,10,0,0]} fill="#8b5cf6"/></BarChart></ResponsiveContainer></div>
    <div className="chart-card polished"><h3>Log severity distribution</h3><p>Classified operational logs grouped by severity.</p><ResponsiveContainer width="100%" height={230}><BarChart data={logSeverity}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="severity"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" radius={[10,10,0,0]} fill="#f97316"/></BarChart></ResponsiveContainer></div>
    <div className="chart-card polished"><h3>Semantic cache activity</h3><p>Repeated incident decisions reused to reduce latency and LLM cost.</p><ResponsiveContainer width="100%" height={230}><BarChart data={cache}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" radius={[10,10,0,0]} fill="#2563eb"/></BarChart></ResponsiveContainer></div>
    <div className="chart-card polished"><h3>MCP latency profile</h3><p>Latency by MCP operational agent in milliseconds.</p><ResponsiveContainer width="100%" height={230}><LineChart data={mcpSuccess}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="agent" tick={{fontSize:10}}/><YAxis/><Tooltip/><Line type="monotone" dataKey="latency_ms" stroke="#0ea5e9" strokeWidth={3} dot={{r:4}}/></LineChart></ResponsiveContainer></div>
  </div>;
}
