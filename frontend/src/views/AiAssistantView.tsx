import React, { useState } from 'react';
import { 
  Bot, 
  Sparkles, 
  Send, 
  Lightbulb, 
  AlertCircle, 
  CheckCircle2, 
  ArrowRight, 
  ShieldAlert, 
  BrainCircuit,
  FileText
} from 'lucide-react';
import { osintApi } from '../services/api';
import { AiBriefingResult } from '../types/osint';

export const AiAssistantView: React.FC = () => {
  const [briefing, setBriefing] = useState<AiBriefingResult | null>(null);
  const [loadingBriefing, setLoadingBriefing] = useState<boolean>(false);
  const [query, setQuery] = useState<string>('');
  const [asking, setAsking] = useState<boolean>(false);
  const [chatHistory, setChatHistory] = useState<Array<{ sender: 'user' | 'assistant'; text: string; artifacts?: any[] }>>([
    {
      sender: 'assistant',
      text: 'PRAVISION Analytical Copilot ready. I synthesize collected multi-source OSINT evidence, formulate testable hypotheses, identify intelligence gaps, and provide strictly evidence-grounded assessments.'
    }
  ]);

  const handleGenerateBriefing = async () => {
    setLoadingBriefing(true);
    try {
      const res = await osintApi.getAiBriefing();
      if ((res as any).error) {
        alert((res as any).error);
      } else {
        setBriefing(res);
      }
    } catch (err: any) {
      alert(`Briefing error: ${err.message}`);
    } finally {
      setLoadingBriefing(false);
    }
  };

  const handleAskAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userText = query;
    setQuery('');
    setChatHistory(prev => [...prev, { sender: 'user', text: userText }]);
    setAsking(true);

    try {
      const res = await osintApi.askAiAssistant(userText);
      setChatHistory(prev => [
        ...prev,
        {
          sender: 'assistant',
          text: res.answer,
          artifacts: res.matched_artifacts
        }
      ]);
    } catch (err: any) {
      setChatHistory(prev => [
        ...prev,
        {
          sender: 'assistant',
          text: `Error processing query: ${err.message}`
        }
      ]);
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="flex-1 bg-[#080D1A] text-slate-200 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div>
            <div className="flex items-center space-x-2">
              <Bot className="w-5 h-5 text-sky-400" />
              <h1 className="text-lg font-bold text-white tracking-wide">ANALYTICAL INTELLIGENCE COPILOT</h1>
            </div>
            <p className="text-xs text-slate-400 mt-1">Grounded OSINT assessment, testable hypothesis generation, and hallucination-free QA over active evidence.</p>
          </div>

          <button
            onClick={handleGenerateBriefing}
            disabled={loadingBriefing}
            className="flex items-center space-x-2 px-3.5 py-1.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white rounded text-xs font-semibold shadow-lg transition cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-sky-200" />
            <span>{loadingBriefing ? 'Synthesizing Dossier...' : 'Generate Executive Briefing'}</span>
          </button>
        </div>

        {/* Executive Briefing Card if generated */}
        {briefing && (
          <div className="bg-[#0F172A] border border-sky-500/30 rounded-lg p-6 space-y-5 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/5 rounded-full blur-2xl pointer-events-none" />

            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest block mb-1">AUTOMATED INTELLIGENCE ASSESSMENT</span>
                <h2 className="text-base font-bold text-white">{briefing.title}</h2>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">
                {new Date(briefing.generated_at).toLocaleString()}
              </span>
            </div>

            {/* Metrics Ribbon */}
            <div className="grid grid-cols-4 gap-3 bg-[#131F37] p-3 rounded-lg border border-[#1E293B] text-xs font-mono">
              <div>
                <span className="text-slate-500 block text-[10px]">TOTAL FINDINGS</span>
                <span className="text-sky-400 font-bold">{briefing.metrics.total_findings}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">SOURCES QUERIED</span>
                <span className="text-white font-bold">{briefing.metrics.sources_queried.length}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">GRAPH LINKAGES</span>
                <span className="text-purple-400 font-bold">{briefing.metrics.graph_edges}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">HIGH CONFIDENCE</span>
                <span className="text-emerald-400 font-bold">{briefing.metrics.high_confidence_findings}</span>
              </div>
            </div>

            {/* Executive Summary */}
            <div>
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
                <FileText className="w-3.5 h-3.5 text-sky-400" />
                <span>Executive Summary</span>
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed bg-[#080D1A] p-3 rounded border border-[#1E293B]">
                {briefing.executive_summary}
              </p>
            </div>

            {/* Hypotheses */}
            {briefing.formulated_hypotheses.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
                  <span>Formulated Investigative Hypotheses</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {briefing.formulated_hypotheses.map((hypo, idx) => (
                    <div key={idx} className="p-3 bg-[#131F37] border border-[#1E293B] rounded-lg text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white">{hypo.title}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded font-bold bg-amber-950 text-amber-300 border border-amber-800/40">
                          {hypo.confidence}
                        </span>
                      </div>
                      <p className="text-slate-400 text-[11px]">{hypo.reasoning}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended Next Actions */}
            {briefing.recommended_next_actions.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <ArrowRight className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Recommended Actionable Next Steps</span>
                </h3>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {briefing.recommended_next_actions.map((act, idx) => (
                    <li key={idx} className="flex items-center space-x-2 bg-[#131F37]/60 p-2 rounded">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>{act}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Interactive Copilot Chat Window */}
        <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg flex flex-col h-96">
          <div className="p-3.5 border-b border-[#1E293B] flex items-center space-x-2 text-xs">
            <BrainCircuit className="w-4 h-4 text-sky-400" />
            <span className="font-semibold text-white">INTERACTIVE EVIDENCE QUERY INTERFACE</span>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`max-w-2xl p-3 rounded-lg text-xs ${
                  msg.sender === 'user'
                    ? 'bg-sky-600 text-white rounded-br-none'
                    : 'bg-[#131F37] border border-[#1E293B] text-slate-200 rounded-bl-none'
                }`}>
                  <p className="leading-relaxed">{msg.text}</p>
                  
                  {msg.artifacts && msg.artifacts.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-700/60 space-y-1">
                      <span className="text-[10px] text-sky-300 uppercase font-mono block">Matched Evidence Artifacts:</span>
                      {msg.artifacts.map((art, aIdx) => (
                        <div key={aIdx} className="text-[10px] bg-[#0A1020] p-1.5 rounded flex items-center justify-between">
                          <span className="font-mono text-white break-all">{art.entity}</span>
                          <span className="text-slate-400 ml-2 uppercase">({art.source})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {asking && (
              <div className="flex items-center space-x-2 text-xs text-slate-500 italic">
                <Bot className="w-4 h-4 animate-pulse text-sky-400" />
                <span>Evaluating facts across evidence graph...</span>
              </div>
            )}
          </div>

          {/* Input Bar */}
          <form onSubmit={handleAskAssistant} className="p-3 border-t border-[#1E293B] flex items-center space-x-2">
            <input
              type="text"
              placeholder="Ask anything about current findings, IOCs, or linked infrastructure..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-[#131F37] border border-[#1E293B] rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
            <button
              type="submit"
              disabled={!query.trim() || asking}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition cursor-pointer"
            >
              <span>Query</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

