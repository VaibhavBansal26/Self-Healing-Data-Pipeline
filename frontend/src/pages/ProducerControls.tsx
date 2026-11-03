import {Eye, Pause, Play, Send, Zap} from 'lucide-react';
import {useState} from 'react';
import {apiPost} from '../lib/api';
import {Panel} from '../components/Panel';
import {JsonBlock} from '../components/JsonBlock';

const scenarios=['valid_order','amount_string','missing_currency','bad_status','negative_amount','missing_customer','missing_event_id','schema_v2_order','unsupported_schema'];

export function ProducerControls({onChanged}:{onChanged:()=>void}){
  const [customJson,setCustomJson]=useState(JSON.stringify({event_id:'ui_custom_1',customer_id:'cust_ui',amount:'42.50',currency:'usd',status:'PAY',schema_version:1},null,2));
  const [result,setResult]=useState<any>(null);
  const [pressureTotal,setPressureTotal]=useState(1000);
  async function publishDemo(){ setResult(await apiPost('/events/demo')); onChanged(); }
  async function publishScenario(sc:string){ setResult(await apiPost(`/events/test/${sc}`)); onChanged(); }
  async function publishCustom(){ setResult(await apiPost('/events',{payload:JSON.parse(customJson)})); onChanged(); }
  async function previewTransform(){ setResult(await apiPost('/transform',{payload:JSON.parse(customJson)})); }
  async function pause(paused:boolean){ setResult(await apiPost('/consumer/state',{paused})); onChanged(); }
  async function pressureRun(){ setResult(await apiPost(`/events/pressure-test?total=${pressureTotal}`)); onChanged(); }
  return <Panel icon={<Send/>} title="Producer controls and failure data" desc="Publish normal, malformed, schema evolved, and pressure test events."><div className="button-row"><button onClick={publishDemo}><Send size={16}/> Publish Demo</button><button onClick={()=>pause(true)}><Pause size={16}/> Pause</button><button onClick={()=>pause(false)}><Play size={16}/> Resume</button><button onClick={previewTransform}><Eye size={16}/> Preview Transform</button><button onClick={publishCustom}><Send size={16}/> Publish Custom</button><input value={pressureTotal} type="number" min={1} max={100000} onChange={e=>setPressureTotal(Number(e.target.value))}/><button onClick={pressureRun}><Zap size={16}/> Pressure Test</button></div><div className="scenario-grid">{scenarios.map(s=><button className="scenario" key={s} onClick={()=>publishScenario(s)}>{s}</button>)}</div><textarea className="code-input" value={customJson} onChange={e=>setCustomJson(e.target.value)}/>{result&&<JsonBlock data={result}/>}</Panel>;
}
