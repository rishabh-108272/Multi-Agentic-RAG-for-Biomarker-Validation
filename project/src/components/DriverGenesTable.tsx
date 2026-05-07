import { TrendingUp, TrendingDown } from 'lucide-react';
import type { DriverGene } from '../types';

interface DriverGenesTableProps {
  genes: DriverGene[];
}

function SHAPCell({ value }: { value: number }) {
  const abs = Math.abs(value);
  const positive = value >= 0;
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden" style={{ maxWidth: 48 }}>
        <div
          className={`h-full rounded-full ${positive ? 'bg-emerald-500' : 'bg-red-500'}`}
          style={{ width: `${Math.min(abs / 0.5, 1) * 100}%`, marginLeft: positive ? '50%' : `${50 - Math.min(abs / 0.5, 1) * 50}%` }}
        />
      </div>
      <span className={`text-xs font-mono ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
        {value > 0 ? '+' : ''}{value.toFixed(3)}
      </span>
    </div>
  );
}

export default function DriverGenesTable({ genes }: DriverGenesTableProps) {
  return (
    <div className="rounded-2xl border border-gray-700/60 bg-gray-900/60 backdrop-blur-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Key Driver Genes</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800/60">
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Gene Index</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Symbol</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">SHAP</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Direction</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/40">
            {genes.map((gene, i) => (
              <tr key={gene.index} className={`transition-colors hover:bg-gray-800/30 ${i % 2 === 0 ? '' : 'bg-gray-900/20'}`}>
                <td className="px-6 py-3.5 text-xs font-mono text-gray-500">#{gene.index}</td>
                <td className="px-6 py-3.5">
                  <span className="font-semibold text-cyan-400 text-sm">{gene.symbol}</span>
                </td>
                <td className="px-6 py-3.5 min-w-32">
                  <SHAPCell value={gene.shap} />
                </td>
                <td className="px-6 py-3.5">
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                    gene.direction === 'up'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-red-500/10 text-red-400 border border-red-500/20'
                  }`}>
                    {gene.direction === 'up' ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                    {gene.direction === 'up' ? 'Up' : 'Down'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
