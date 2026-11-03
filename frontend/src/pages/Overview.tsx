import {AlertTriangle, Bot, Database, GitBranch, ShieldCheck, XCircle} from 'lucide-react';
import {StatCard} from '../components/StatCard';
import {ApplicationWorkflow} from '../components/ApplicationWorkflow';
import {RecoveryStoryPanel} from '../components/RecoveryStoryPanel';
import {AutoHealerTerminal} from '../components/AutoHealerTerminal';
import {AutoHealModeCard} from '../components/AutoHealModeCard';
import {DynamicHealthCharts} from '../components/DynamicHealthCharts';
import type {PipelineData} from '../types/pipeline';

export function Overview({data}:{data:PipelineData}){
  const s=data.summary;
  return <div className="page-stack overview-clean">
    <AutoHealModeCard health={data.health}/>
    <RecoveryStoryPanel autoHealer={data.autoHealer} health={data.health}/>
    <AutoHealerTerminal autoHealer={data.autoHealer} traces={data.traces} compact/>
    <ApplicationWorkflow health={data.health} autoHealer={data.autoHealer}/>
    <div className="cards-grid compact-stats">
      <StatCard title="Clean Orders" value={s?.orders_count} icon={<Database/>} color="green"/>
      <StatCard title="Incidents" value={s?.incident_count} icon={<AlertTriangle/>} color="yellow"/>
      <StatCard title="Agent Healed" value={s?.healed_count} icon={<Bot/>} color="blue"/>
      <StatCard title="Human Review" value={s?.manual_review_count} icon={<ShieldCheck/>} color="purple"/>
      <StatCard title="Failed" value={s?.failed_count} icon={<XCircle/>} color="red"/>
      <StatCard title="DLQ" value={s?.dlq_count} icon={<GitBranch/>} color="red"/>
    </div>
    <DynamicHealthCharts data={data}/>
  </div>;
}
