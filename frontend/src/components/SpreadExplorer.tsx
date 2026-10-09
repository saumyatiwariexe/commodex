import React, { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea
} from 'recharts';
import { useSpread } from '../api';

export default function SpreadExplorer() {
  const [useCarryAdj, setUseCarryAdj] = useState(false);
  const { data: spreadData, isLoading } = useSpread('GOLDM/GOLDPETAL', '2026-01-01', '2026-12-31');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-white">GOLDM vs GOLDPETAL</h3>
          <p className="text-sm text-text-secondary font-mono mt-1">Exp: 05-Feb-2026</p>
        </div>
        
        <div className="flex items-center gap-3 bg-surface p-1 rounded-md border border-border">
          <button 
            onClick={() => setUseCarryAdj(false)}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${!useCarryAdj ? 'bg-background text-white shadow-sm border border-border' : 'text-text-secondary hover:text-white'}`}
          >
            Raw Spread
          </button>
          <button 
            onClick={() => setUseCarryAdj(true)}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${useCarryAdj ? 'bg-background text-white shadow-sm border border-border' : 'text-text-secondary hover:text-white'}`}
          >
            Carry Adjusted
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {/* Price Chart */}
        <div className="p-5 bg-surface border border-border rounded-xl">
          <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-4">Normalized Price (INR/g)</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spreadData || []} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363D" vertical={false} />
                <XAxis dataKey="date" stroke="#8B949E" fontSize={12} tickMargin={10} minTickGap={30} />
                <YAxis stroke="#8B949E" fontSize={12} domain={['auto', 'auto']} tickFormatter={(val) => `₹${val}`} width={60} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#161B22', borderColor: '#30363D', color: '#C9D1D9' }}
                  itemStyle={{ color: '#C9D1D9' }}
                />
                
                {/* Highlight regions */}
                {(spreadData || []).map((d: any, i: number) => (
                  d.is_thin && <ReferenceArea key={`thin-${i}`} x1={d.date} x2={spreadData[i+1]?.date || d.date} fill="#F85149" fillOpacity={0.1} />
                ))}
                {(spreadData || []).map((d: any, i: number) => (
                  d.is_tender && <ReferenceArea key={`tender-${i}`} x1={d.date} x2={spreadData[i+1]?.date || d.date} fill="#D29922" fillOpacity={0.1} />
                ))}

                <Line type="monotone" dataKey="px_a" name="GOLDM" stroke="#D4AF37" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="px_b" name="GOLDPETAL" stroke="#8B949E" strokeWidth={2} dot={false} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 mt-4 text-xs">
            <div className="flex items-center gap-1.5 text-text-secondary"><span className="w-3 h-3 bg-[#D4AF37] rounded-sm"></span> GOLDM</div>
            <div className="flex items-center gap-1.5 text-text-secondary"><span className="w-3 h-3 border-2 border-dashed border-[#8B949E] rounded-sm"></span> GOLDPETAL</div>
            <div className="flex items-center gap-1.5 text-text-secondary ml-auto"><span className="w-3 h-3 bg-[#F85149] opacity-20 rounded-sm"></span> Thin Liquidity</div>
            <div className="flex items-center gap-1.5 text-text-secondary"><span className="w-3 h-3 bg-[#D29922] opacity-20 rounded-sm"></span> Tender Period</div>
          </div>
        </div>

        {/* Spread Chart */}
        <div className="p-5 bg-surface border border-border rounded-xl">
          <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-4">
            {useCarryAdj ? 'Carry Adjusted Spread' : 'Raw Spread'} (INR)
          </h4>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spreadData || []} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363D" vertical={false} />
                <XAxis dataKey="date" hide />
                <YAxis stroke="#8B949E" fontSize={12} width={60} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#161B22', borderColor: '#30363D', color: '#C9D1D9' }}
                />
                <Line type="stepAfter" dataKey={useCarryAdj ? 'carry_adj_spread' : 'raw_spread'} name="Spread" stroke="#2EA043" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Z-Score Chart */}
        <div className="p-5 bg-surface border border-border rounded-xl">
          <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-4">Z-Score</h4>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spreadData || []} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363D" vertical={false} />
                <XAxis dataKey="date" stroke="#8B949E" fontSize={12} tickMargin={10} minTickGap={30} />
                <YAxis stroke="#8B949E" fontSize={12} domain={[-5, 5]} ticks={[-4, -2, 0, 2, 4]} width={60} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#161B22', borderColor: '#30363D', color: '#C9D1D9' }}
                />
                
                {/* Threshold lines */}
                <ReferenceArea y1={2} y2={5} fill="#F85149" fillOpacity={0.05} />
                <ReferenceArea y1={-5} y2={-2} fill="#F85149" fillOpacity={0.05} />
                
                <Line type="monotone" dataKey="z_score" name="Z-Score" stroke="#58A6FF" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
