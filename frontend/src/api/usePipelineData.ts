import {useEffect, useState} from 'react';
import {safeGet} from '../lib/api';
import type {PipelineData, Summary, Order, Incident, Journey} from '../types/pipeline';

const emptyData: PipelineData = {summary:null, orders:[], incidents:[], journey:[], health:null, pipelineIncidents:[], flow:null, replayAudit:[], schema:null, rag:[], pressure:null, lag:null, aiCoverage:null, aiCosts:null, aiEvals:null, langsmith:null, pipelineMetrics:null, approvals:[], alerts:[], traces:[], recoveryMemory:null, promptInjection:null, semanticCache:null, retrievalEval:null, toolUseEval:null, trajectory:null, aiOps:null, autoHealer:null};

export function usePipelineData(){
  const [data,setData]=useState<PipelineData>(emptyData);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  async function refresh(){
    const errors:string[]=[];
    setError('');
    const [summary,orders,incidents,journey,health,pipelineIncidents,flow,replayAudit,schema,rag,pressure,lag,aiCoverage,aiCosts,aiEvals,langsmith,pipelineMetrics,approvals,alerts,traces,recoveryMemory,promptInjection,semanticCache,retrievalEval,toolUseEval,trajectory,aiOps,autoHealer]=await Promise.all([
      safeGet<Summary | null>('/summary', null, errors),
      safeGet<Order[]>('/orders?limit=100', [], errors),
      safeGet<Incident[]>('/incidents?limit=100', [], errors),
      safeGet<Journey[]>('/event-journey?limit=300', [], errors),
      safeGet<any>('/pipeline/health', null, errors),
      safeGet<any[]>('/pipeline/incidents?limit=100', [], errors),
      safeGet<any>('/flow/live', null, errors),
      safeGet<any[]>('/dlq/replay-audit?limit=100', [], errors),
      safeGet<any>('/schema/evolution', null, errors),
      safeGet<any[]>('/rag/evidence?limit=100', [], errors),
      safeGet<any>('/pressure-test/summary', null, errors),
      safeGet<any>('/kafka/lag', null, errors),
      safeGet<any>('/ai/coverage', null, errors),
      safeGet<any>('/ai/costs', null, errors),
      safeGet<any>('/ai/evals', null, errors),
      safeGet<any>('/ai/langsmith/status', null, errors),
      safeGet<any>('/pipeline/metrics', null, errors),
      safeGet<any[]>('/pipeline/approvals?limit=50', [], errors),
      safeGet<any[]>('/pipeline/alerts?limit=50', [], errors),
      safeGet<any[]>('/pipeline/traces?limit=50', [], errors),
      safeGet<any>('/pipeline/recovery-memory', null, errors),
      safeGet<any>('/ai/security/prompt-injection', null, errors),
      safeGet<any>('/ai/semantic-cache', null, errors),
      safeGet<any>('/ai/retrieval-eval', null, errors),
      safeGet<any>('/ai/tool-use-eval', null, errors),
      safeGet<any>('/ai/trajectory', null, errors),
      safeGet<any>('/ai/ops-observatory', null, errors),
      safeGet<any>('/auto-healer/status', null, errors)
    ]);
    setData({summary,orders,incidents,journey,health,pipelineIncidents,flow,replayAudit,schema,rag,pressure,lag,aiCoverage,aiCosts,aiEvals,langsmith,pipelineMetrics,approvals,alerts,traces,recoveryMemory,promptInjection,semanticCache,retrievalEval,toolUseEval,trajectory,aiOps,autoHealer});
    setError(errors.length ? `${errors.length} section(s) could not load. First issue: ${errors[0]}` : '');
    setLoading(false);
  }
  useEffect(()=>{ refresh(); const t=setInterval(refresh,2000); return()=>clearInterval(t);},[]);
  return {data,error,loading,refresh};
}
