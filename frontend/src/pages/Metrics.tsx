import {Activity} from 'lucide-react';
import {Cell, Pie, PieChart, ResponsiveContainer, Tooltip} from 'recharts';
import {Panel} from '../components/Panel';
import {JsonBlock} from '../components/JsonBlock';
import type {PipelineData} from '../types/pipeline';

const COLORS=['#22c55e','#38bdf8','#f59e0b','#ef4444','#a78bfa','#ec4899'];
export function Metrics({data}:{data:PipelineData}){
  const s=data.summary;
  const chartData=s?[{name:'Orders',value:s.orders_count},{name:'Healed',value:s.healed_count},{name:'Manual',value:s.manual_review_count},{name:'Failed',value:s.failed_count},{name:'DLQ',value:s.dlq_count}]:[];
  return <Panel icon={<Activity/>} title="Metrics, lag and observability" desc="Prometheus, Grafana, Kafka lag, API metrics, and risk visualization."><div className="charts-grid"><div className="chart-card"><ResponsiveContainer width="100%" height={260}><PieChart><Pie data={chartData} dataKey="value" nameKey="name" outerRadius={90} label>{chartData.map((_,idx)=><Cell key={idx} fill={COLORS[idx%COLORS.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div><div className="chart-card"><JsonBlock data={{prometheus:'http://localhost:9090', grafana:'http://localhost:3001', api_metrics:'http://localhost:9108/metrics', consumer_metrics:'http://localhost:9109/metrics', kafka_lag:data.lag, summary:s}}/></div></div></Panel>;
}
