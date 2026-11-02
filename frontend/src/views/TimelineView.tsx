import React, { useState, useEffect } from 'react';
import { 
  Clock, 
  Flame, 
  Calendar, 
  Filter, 
  ChevronDown, 
  ChevronUp, 
  ShieldCheck, 
  Activity,
  Layers
} from 'lucide-react';
import { osintApi } from '../services/api';
import { TimelineResult, TimelineEvent } from '../types/osint';

export const TimelineView: React.FC = () => {
  const [timeline, setTimeline] = useState<TimelineResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterType, setFilterType] = useState<string>('all');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        setLoading(true);
        const res = await osintApi.getTimeline();
        setTimeline(res);
      } catch (err) {
        console.error('Timeline fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchTimeline();
  }, []);

  const filteredEvents = timeline?.events.filter(e => {
    if (filterType !== 'all' && e.event_type !== filterType) return false;
    return true;
  }) || [];

  return (
    <div className="flex-1 bg-[#080D1A] text-slate-200 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div>
            <div className="flex items-center space-x-2">
              <Clock className="w-5 h-5 text-sky-400" />
              <h1 className="text-lg font-bold text-white tracking-wide">CHRONOLOGICAL TIMELINE ANALYSIS</h1>
            </div>
            <p className="text-xs text-slate-400 mt-1">Multi-source temporal sequencing, infrastructure observation times, and burst detection.</p>
          </div>

          {timeline && (
            <div className="flex items-center space-x-4 text-xs font-mono">
              <div className="bg-[#0F172A] px-3 py-1.5 rounded border border-[#1E293B]">
                <span className="text-slate-500 block text-[10px]">TOTAL EVENTS</span>
                <span className="text-sky-400 font-bold">{timeline.total_events}</span>
              </div>
              <div className="bg-[#0F172A] px-3 py-1.5 rounded border border-[#1E293B]">
                <span className="text-slate-500 block text-[10px]">TIME SPAN</span>
                <span className="text-emerald-400 font-bold">
                  {timeline.earliest_event ? new Date(timeline.earliest_event).toLocaleDateString() : 'N/A'} - {timeline.latest_event ? new Date(timeline.latest_event).toLocaleDateString() : 'N/A'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Activity Bursts Banner */}
        {timeline && timeline.detected_bursts && timeline.detected_bursts.length > 0 && (
          <div className="p-4 bg-amber-950/30 border border-amber-800/40 rounded-lg">
            <div className="flex items-center space-x-2 text-amber-400 text-xs font-semibold mb-2">
              <Flame className="w-4 h-4" />
              <span>DETECTED ACTIVITY BURSTS ({timeline.detected_bursts.length})</span>
            </div>
            <div className="space-y-1.5">
              {timeline.detected_bursts.map((burst, idx) => (
                <div key={idx} className="text-xs text-slate-300 flex items-center justify-between bg-[#101B33]/60 px-3 py-1.5 rounded">
                  <span>{burst.description}</span>
                  <span className="font-mono text-[11px] text-amber-400">{new Date(burst.start_time).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Filter Controls */}
        <div className="flex items-center justify-between text-xs bg-[#0F172A] p-3 rounded-lg border border-[#1E293B]">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <span className="text-slate-400">Filter Event Type:</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-[#131F37] border border-[#1E293B] rounded px-2.5 py-1 text-white focus:outline-none focus:border-sky-500 text-xs"
            >
              <option value="all">All Types ({timeline?.total_events || 0})</option>
              {timeline && Array.from(new Set(timeline.events.map(e => e.event_type))).map(t => (
                <option key={t} value={t}>{t.toUpperCase()}</option>
              ))}
            </select>
          </div>
          <span className="text-slate-500 font-mono text-[11px]">
            Showing {filteredEvents.length} chronological events
          </span>
        </div>

        {/* Timeline Event Stream */}
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-500">Processing timeline sequences...</div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-500 border border-dashed border-[#1E293B] rounded-lg">
            No temporal events recorded for the active investigation.
          </div>
        ) : (
          <div className="relative pl-6 space-y-4 before:content-[''] before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-[#1E293B]">
            {filteredEvents.map(ev => {
              const isExpanded = expandedEventId === ev.id;
              return (
                <div key={ev.id} className="relative group">
                  {/* Timeline Dot */}
                  <div className="absolute -left-6 top-3.5 w-3 h-3 rounded-full bg-sky-500 border-2 border-[#080D1A] group-hover:scale-125 transition-transform" />

                  <div className="bg-[#0F172A] border border-[#1E293B] hover:border-slate-600 rounded-lg p-3.5 transition">
                    <div className="flex items-start justify-between cursor-pointer" onClick={() => setExpandedEventId(isExpanded ? null : ev.id)}>
                      <div>
                        <div className="flex items-center space-x-2 mb-1">
                          <span className="font-mono text-[11px] text-sky-400">
                            {new Date(ev.timestamp).toLocaleString()}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                            {ev.event_type}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-semibold bg-sky-950 text-sky-400 border border-sky-800/40">
                            {ev.source}
                          </span>
                        </div>
                        <h4 className="text-xs font-semibold text-white break-all">{ev.summary}</h4>
                      </div>

                      <button className="text-slate-400 hover:text-white p-1">
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>

                    {/* Expanded Metadata */}
                    {isExpanded && ev.raw_metadata && Object.keys(ev.raw_metadata).length > 0 && (
                      <div className="mt-3 pt-3 border-t border-[#1E293B] text-[11px] font-mono bg-[#080D1A] p-2.5 rounded text-slate-300 overflow-x-auto">
                        <pre>{JSON.stringify(ev.raw_metadata, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

