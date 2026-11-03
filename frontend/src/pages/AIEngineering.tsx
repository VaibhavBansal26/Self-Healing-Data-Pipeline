import {Bot, BarChart3, DollarSign, GitCompare, Telescope, ShieldAlert, DatabaseZap, SearchCheck, PlugZap, Route} from 'lucide-react';
import {Panel} from '../components/Panel';
import {JsonBlock} from '../components/JsonBlock';
import {DataTable} from '../components/DataTable';
import {AIOpsVisuals} from '../components/AIOpsVisuals';

export function AIEngineering({coverage,costs,evals,langsmith,promptInjection,semanticCache,retrievalEval,toolUseEval,trajectory,aiOps}:{coverage:any; costs:any; evals:any; langsmith:any; promptInjection:any; semanticCache:any; retrievalEval:any; toolUseEval:any; trajectory:any; aiOps?:any}){
  const agentRows = evals?.by_agent ? Object.entries(evals.by_agent).map(([agent,stats]:any)=>({agent,...stats})) : [];
  const trajectoryRows = trajectory?.trajectory_steps || [];
  const toolRows = toolUseEval?.results || [];
  const retrievalRows = retrievalEval?.results?.map((r:any)=>({query:r.query, expected_memory:r.expected_memory, rank:r.rank, hit_at_1:r.hit_at_1, hit_at_k:r.hit_at_k, top_match:r.retrieved?.[0]?.id, top_score:r.retrieved?.[0]?.score})) || [];
  return <div>
    <Panel icon={<Bot/>} title="AI engineering coverage" desc="Agentic workflow, RAG memory, MCP tools, guardrails, human approval, and measurable repair quality.">
      <div className="journey-grid">
        <div className="journey-card"><h3>Agent workflow</h3><p>LangGraph models detection, memory retrieval, reasoning, repair, human approval, and verification.</p></div>
        <div className="journey-card"><h3>Safe tool use</h3><p>MCP decouples the agent from Kafka, Postgres, Redis, vector memory, and reconciliation tools.</p></div>
        <div className="journey-card"><h3>RAG memory</h3><p>Similar historic incidents are retrieved before decisions to make repairs more consistent.</p></div>
        <div className="journey-card"><h3>Measurable agents</h3><p>Offline evals compare rules repair, conservative reviewer, and LLM planner proxy on expected repair actions.</p></div>
      </div>
      <JsonBlock data={coverage}/>
    </Panel>

    <AIOpsVisuals ops={aiOps}/>

    <Panel icon={<Route/>} title="Agent trajectory timeline" desc="Step level view of what the agent observed, retrieved, selected, gated, verified, and remembered.">
      <div className="trajectory-summary">
        <div><span>Agent state</span><strong>{trajectory?.agent_state || 'sleeping'}</strong></div>
        <div><span>Active stages</span><strong>{trajectory?.active_stage_count ?? 0}</strong></div>
        <div><span>Evaluation dimensions</span><strong>{trajectory?.evaluation_dimensions?.length ?? 0}</strong></div>
      </div>
      <div className="timeline">
        {trajectoryRows.map((s:any,idx:number)=><div className={`timeline-item ${s.status || 'complete'}`} key={idx}>
          <div className="timeline-dot"/>
          <div><b>{s.step}</b> {s.component && <span className="pill">{s.component}</span>}<p>{s.message}</p><small>{s.timestamp}</small></div>
        </div>)}
      </div>
      <JsonBlock data={trajectory?.recent_system_traces?.slice?.(0,5) || []}/>
    </Panel>

    <Panel icon={<ShieldAlert/>} title="Prompt injection defense" desc="Tests that malicious text inside event payloads is not treated as instructions for the LLM.">
      <div className="cards-grid">
        <div className="stat-card green"><div><div className="stat-title">Defense accuracy</div><div className="stat-value">{Math.round((promptInjection?.accuracy ?? 0)*100)}%</div></div></div>
        <div className="stat-card blue"><div><div className="stat-title">Cases</div><div className="stat-value">{promptInjection?.total ?? 0}</div></div></div>
        <div className="stat-card yellow"><div><div className="stat-title">Passed</div><div className="stat-value">{promptInjection?.passed ?? 0}</div></div></div>
      </div>
      <DataTable rows={promptInjection?.results || []} cols={['name','expected_safe','actual_safe','passed','decision']}/>
      <JsonBlock data={{policy:promptInjection?.policy}}/>
    </Panel>

    <Panel icon={<DatabaseZap/>} title="Semantic cache for repeated incidents" desc="Verified prior decisions can be reused for similar future incidents to reduce LLM calls, cost, and latency.">
      <div className="cards-grid">
        <div className="stat-card purple"><div><div className="stat-title">Cache entries</div><div className="stat-value">{semanticCache?.entries ?? 0}</div></div></div>
        <div className="stat-card green"><div><div className="stat-title">Cache hits</div><div className="stat-value">{semanticCache?.total_hits ?? 0}</div></div></div>
        <div className="stat-card blue"><div><div className="stat-title">Threshold</div><div className="stat-value">{semanticCache?.threshold ?? 0}</div></div></div>
      </div>
      <JsonBlock data={semanticCache}/>
    </Panel>

    <Panel icon={<SearchCheck/>} title="Retrieval evaluation for vector memory" desc="Measures whether the RAG memory retrieves the right past incident before the agent chooses an action.">
      <div className="cards-grid">
        <div className="stat-card green"><div><div className="stat-title">Precision@1</div><div className="stat-value">{Math.round((retrievalEval?.precision_at_1 ?? 0)*100)}%</div></div></div>
        <div className="stat-card blue"><div><div className="stat-title">Hit@K</div><div className="stat-value">{Math.round((retrievalEval?.hit_rate_at_k ?? 0)*100)}%</div></div></div>
        <div className="stat-card purple"><div><div className="stat-title">MRR</div><div className="stat-value">{retrievalEval?.mean_reciprocal_rank ?? 0}</div></div></div>
      </div>
      <DataTable rows={retrievalRows} cols={['query','expected_memory','rank','hit_at_1','hit_at_k','top_match','top_score']}/>
    </Panel>

    <Panel icon={<PlugZap/>} title="MCP tool-use evaluation" desc="Checks whether the agent selects the right operational tool for each pipeline failure pattern.">
      <div className="cards-grid">
        <div className="stat-card green"><div><div className="stat-title">Tool accuracy</div><div className="stat-value">{Math.round((toolUseEval?.tool_accuracy ?? 0)*100)}%</div></div></div>
        <div className="stat-card blue"><div><div className="stat-title">Action accuracy</div><div className="stat-value">{Math.round((toolUseEval?.action_accuracy ?? 0)*100)}%</div></div></div>
        <div className="stat-card yellow"><div><div className="stat-title">Cases</div><div className="stat-value">{toolUseEval?.cases ?? 0}</div></div></div>
      </div>
      <DataTable rows={toolRows} cols={['component','problem','expected_tool','tool','tool_ok','expected_action','action','action_ok']}/>
    </Panel>

    <Panel icon={<Telescope/>} title="LangSmith tracing" desc="Optional hosted tracing for prompts, LangGraph runs, metadata, and agent decisions.">
      <JsonBlock data={langsmith}/>
    </Panel>

    <Panel icon={<BarChart3/>} title="Measurable agent evaluation" desc="Offline eval dataset with winner accuracy, per agent accuracy, latency, and estimated cost.">
      <div className="cards-grid">
        <div className="stat-card blue"><div><div className="stat-title">Eval cases</div><div className="stat-value">{evals?.cases ?? 0}</div></div></div>
        <div className="stat-card green"><div><div className="stat-title">Winner accuracy</div><div className="stat-value">{Math.round((evals?.winner_accuracy ?? 0)*100)}%</div></div></div>
      </div>
      <DataTable rows={agentRows} cols={['agent','correct','total','accuracy','avg_latency_ms','cost_usd']}/>
      <JsonBlock data={evals?.results?.slice?.(0,3) ?? []}/>
    </Panel>

    <Panel icon={<DollarSign/>} title="LLM cost tracking" desc="Tracks estimated prompt, completion, total tokens, and USD cost per incident and agent.">
      <div className="cards-grid">
        <div className="stat-card purple"><div><div className="stat-title">LLM calls</div><div className="stat-value">{costs?.total_calls ?? 0}</div></div></div>
        <div className="stat-card yellow"><div><div className="stat-title">Tokens</div><div className="stat-value">{costs?.total_tokens ?? 0}</div></div></div>
        <div className="stat-card green"><div><div className="stat-title">Est. cost</div><div className="stat-value">${costs?.estimated_total_cost_usd ?? 0}</div></div></div>
      </div>
      <JsonBlock data={costs}/>
    </Panel>

    <Panel icon={<GitCompare/>} title="Multi agent comparison" desc="Backend endpoint POST /ai/multi-agent/compare ranks detector, repair, reviewer, and LLM planner approaches.">
      <JsonBlock data={{endpoint:'POST /ai/multi-agent/compare', selection_policy:'Prefer verified safe repair, then no human approval, then lower cost, then lower latency.'}}/>
    </Panel>
  </div>;
}
