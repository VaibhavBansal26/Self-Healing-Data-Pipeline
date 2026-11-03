import {GitBranch, Network} from 'lucide-react';
import {ApplicationWorkflow} from '../components/ApplicationWorkflow';
import {StageMap} from '../components/StageMap';
import {DynamicHealthCharts} from '../components/DynamicHealthCharts';
import {Panel} from '../components/Panel';

export function PipelineMapPage({data}:{data:any}){
  return <div className="page-stack">
    <ApplicationWorkflow health={data.health} autoHealer={data.autoHealer}/>
    <Panel icon={<Network/>} title="Stage details" desc="Detailed stage cards with compact current status, suggested action, and agent state.">
      <StageMap health={data.health} autoHealer={data.autoHealer}/>
    </Panel>
    <Panel icon={<GitBranch/>} title="Pipeline charts" desc="Visual distribution of stage health, healing outcomes, recovery signals, and trace activity.">
      <DynamicHealthCharts data={data}/>
    </Panel>
  </div>;
}
