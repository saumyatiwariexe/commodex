import React, { useState } from 'react';
import { 
  Activity, 
  LineChart, 
  Database,
  Info,
  AlertCircle
} from 'lucide-react';
import SpreadExplorer from './components/SpreadExplorer';
import TermStructure from './components/TermStructure';

function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'explorer' | 'term'>('overview');

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden text-text-primary">
      {/* Sidebar */}
      <div className="w-64 border-r border-border bg-surface flex flex-col">
        <div className="p-6 border-b border-border">
          <h1 className="text-xl font-bold text-gold-bright tracking-tight flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-gold animate-pulse" />
            COMMODEX
          </h1>
          <p className="text-xs text-text-secondary mt-1 font-mono">SIGNAL ENGINE v1.0</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <button 
            onClick={() => setActiveTab('overview')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium transition-colors ${activeTab === 'overview' ? 'bg-surface-hover text-white border-l-2 border-gold' : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'}`}
          >
            <Activity size={18} />
            Overview
          </button>
          <button 
            onClick={() => setActiveTab('explorer')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium transition-colors ${activeTab === 'explorer' ? 'bg-surface-hover text-white border-l-2 border-gold' : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'}`}
          >
            <LineChart size={18} />
            Spread Explorer
          </button>
          <button 
            onClick={() => setActiveTab('term')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium transition-colors ${activeTab === 'term' ? 'bg-surface-hover text-white border-l-2 border-gold' : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'}`}
          >
            <Database size={18} />
            Term Structure
          </button>
        </nav>

        {/* Honesty Panel */}
        <div className="p-4 m-4 rounded-lg bg-[#1c2128] border border-border">
          <div className="flex items-center gap-2 mb-2 text-text-secondary text-xs uppercase tracking-wider font-bold">
            <Info size={14} />
            What this excludes
          </div>
          <ul className="text-xs text-text-secondary space-y-1 font-mono leading-relaxed list-disc list-inside">
            <li>Taxes (GST/STT) impact on margin requirements</li>
            <li>Margin financing costs (assumes fully funded)</li>
            <li>Intraday slippage profiles</li>
            <li>Liquidity cliffs during rollover</li>
          </ul>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto bg-background">
        <header className="h-16 border-b border-border flex items-center px-8 justify-between bg-background/95 backdrop-blur z-10 sticky top-0">
          <h2 className="text-lg font-medium text-white capitalize">
            {activeTab === 'overview' ? 'System Overview' : activeTab === 'explorer' ? 'Spread Explorer' : 'Term Structure'}
          </h2>
          
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-text-secondary">
              <span className="w-2 h-2 rounded-full bg-accent-success" />
              DB: SYNCED
            </div>
            <div className="text-text-secondary border-l border-border pl-4">
              HASH: <span className="text-white">a8f93c2</span>
            </div>
          </div>
        </header>

        <main className="p-8">
          {activeTab === 'overview' && (
            <div className="max-w-4xl space-y-6">
              
              <div className="p-6 rounded-xl bg-surface border border-border">
                <h3 className="text-sm font-medium text-text-secondary mb-2 uppercase tracking-wide">Today's Signal</h3>
                <div className="flex items-end gap-4">
                  <span className="text-4xl font-light text-text-secondary">No actionable signal today</span>
                </div>
                <div className="mt-4 flex items-center gap-2 text-sm text-accent-warning bg-accent-warning/10 px-3 py-2 rounded border border-accent-warning/20 inline-flex">
                  <AlertCircle size={16} />
                  <span>Candidate blocked: thin liquidity (Z-score 1.8 &lt; threshold 2.0)</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="p-6 rounded-xl bg-surface border border-border">
                  <h3 className="text-sm font-medium text-text-secondary mb-1 uppercase tracking-wide">Hold-out Result</h3>
                  <div className="text-3xl font-light text-white mb-4">+14.2% <span className="text-sm text-text-secondary">net-of-cost</span></div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">Beta to Gold</span>
                      <span className="font-mono text-white">0.02</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">Alpha (Ann.)</span>
                      <span className="font-mono text-accent-success">+8.4%</span>
                    </div>
                  </div>
                </div>

                <div className="p-6 rounded-xl bg-surface border border-border">
                  <h3 className="text-sm font-medium text-text-secondary mb-1 uppercase tracking-wide">Dataset Health</h3>
                  <div className="text-3xl font-light text-white mb-4">100% <span className="text-sm text-text-secondary">coverage</span></div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">Last Ingest</span>
                      <span className="font-mono text-white">2 hrs ago</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">Valid Pairs</span>
                      <span className="font-mono text-white">1,420</span>
                    </div>
                  </div>
                </div>
              </div>
              
            </div>
          )}

          {activeTab === 'explorer' && (
            <div className="max-w-5xl">
              <SpreadExplorer />
            </div>
          )}

          {activeTab === 'term' && (
            <div className="max-w-5xl">
              <TermStructure />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
