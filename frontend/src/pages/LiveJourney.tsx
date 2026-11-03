import {Activity} from 'lucide-react';
import {Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts';
import {Panel} from '../components/Panel';
import {DataTable} from '../components/DataTable';
import type {Journey} from '../types/pipeline';

export function LiveJourney({journey}:{journey:Journey[]}){
  const timeline=[...journey].reverse().slice(-80).map((j,idx)=>({idx, stage:j.stage, count:idx+1}));
  return <Panel icon={<Activity/>} title="Live event journey" desc="Trace events across producer, Kafka, validation, agent, human review, DLQ, and PostgreSQL."><div className="chart-card"><ResponsiveContainer width="100%" height={220}><AreaChart data={timeline}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="idx"/><YAxis/><Tooltip/><Area dataKey="count" stroke="#38bdf8" fill="#1d4ed8"/></AreaChart></ResponsiveContainer></div><DataTable rows={journey} cols={['created_at','event_id','stage','component','status','action','risk_level','reason']}/></Panel>;
}
