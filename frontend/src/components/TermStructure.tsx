import React, { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { useCurve } from '../api';

export default function TermStructure() {
  const asOfDate = '2026-10-09';
  const { data: goldmCurve } = useCurve('GOLDM', asOfDate);

  // Transform curve data to chart format
  const chartData = (goldmCurve || []).map((point: any) => ({
    name: point.expiry_date,
    GOLDM: point.px_per_gram_999,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-white">Term Structure</h3>
          <p className="text-sm text-text-secondary mt-1">GOLDM forward curve</p>
        </div>
      </div>

      <div className="p-6 bg-surface border border-border rounded-xl">
        <div className="flex items-center justify-between mb-6">
          <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            Curve as of: <span className="text-white font-mono">{asOfDate}</span>
          </h4>
        </div>

        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#30363D" vertical={false} />
              <XAxis dataKey="name" stroke="#8B949E" fontSize={12} tickMargin={10} />
              <YAxis stroke="#8B949E" fontSize={12} domain={['auto', 'auto']} tickFormatter={(val) => `₹${val}`} width={80} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#161B22', borderColor: '#30363D', color: '#C9D1D9' }}
                itemStyle={{ color: '#C9D1D9' }}
                labelStyle={{ color: '#8B949E', marginBottom: '8px' }}
                formatter={(value: number) => [`₹${value.toFixed(2)}`, undefined]}
              />
              
              <Line type="monotone" dataKey="GOLDM" name="GOLDM" stroke="#D4AF37" strokeWidth={3} dot={{ r: 4, fill: '#D4AF37', strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        <div className="flex gap-6 mt-4 text-xs justify-center">
          <div className="flex items-center gap-2 text-text-secondary"><span className="w-3 h-3 bg-[#D4AF37] rounded-sm"></span> GOLDM (100g)</div>
          <div className="flex items-center gap-2 text-text-secondary"><span className="w-3 h-3 bg-[#58A6FF] rounded-sm"></span> GOLDGUINEA (8g)</div>
          <div className="flex items-center gap-2 text-text-secondary"><span className="w-3 h-3 bg-[#2EA043] rounded-sm"></span> GOLDPETAL (1g)</div>
        </div>
      </div>
    </div>
  );
}
