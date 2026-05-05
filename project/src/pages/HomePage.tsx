import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, ArrowRight, Dna, Eye } from 'lucide-react';
import UploadBox from '../components/UploadBox';
import { api } from '../lib/api';

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

const statusStyles: Record<string, string> = {
  complete: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  running: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  pending: 'bg-gray-700/50 text-gray-400 border-gray-600',
  error: 'bg-red-500/10 text-red-400 border-red-500/20',
};

// Map every known subtype to a color style.
// Lung subtypes (LUAD, LUSC, SCLC) → cyan family
// Colorectal subtypes (COAD, READ) → orange family
// Unknown/other → gray fallback
function getSubtypeStyle(subtype: string): string {
  const s = subtype.toUpperCase();
  if (['LUAD', 'LUSC'].includes(s)) {
    return 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20';
  }
  if (['COAD', 'READ'].includes(s)) {
    return 'bg-orange-500/10 text-orange-400 border border-orange-500/20';
  }
  return 'bg-gray-700/50 text-gray-400 border border-gray-600';
}

export default function HomePage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [classifierType, setClassifierType] = useState<'lung' | 'colorectal'>('lung');
  const [loading, setLoading] = useState(false);
  const [recentLoading, setRecentLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryStats, setSummaryStats] = useState<{
    analyses_run: number;
    genes_profiled: number;
    drug_candidates: number;
    avg_pipeline_minutes: number | null;
  } | null>(null);
  const [recentAnalyses, setRecentAnalyses] = useState<Array<{
    id: string;
    patient_id: string;
    predicted_subtype: string | null;
    status: string;
    created_at: string;
  }>>([]);

  const loadRecent = async () => {
    try {
      const data = await api.recent();

      const mapped = data.map((item) => ({
        id: String(item.id || ''),
        patient_id: String(item.patient_id || 'N/A'),
        // Prefer the subtype from the full results if the item is complete,
        // falling back to predicted_subtype from the summary row.
        predicted_subtype:
          (item.results as { subtype?: string } | undefined)?.subtype ||
          (item.predicted_subtype as string | null) ||
          null,
        status: String(item.status || 'pending'),
        created_at: String(item.created_at || new Date().toISOString()),
      }));

      // For completed analyses that still show a mismatched subtype, fetch
      // the full result in parallel so the table reflects the final report.
      const resolved = await Promise.all(
        mapped.map(async (row) => {
          if (row.status !== 'complete') return row;
          try {
            const full = await api.results(row.id);
            const finalSubtype =
              (full as { results?: { subtype?: string } })?.results?.subtype ||
              (full as { subtype?: string })?.subtype ||
              row.predicted_subtype;
            return { ...row, predicted_subtype: finalSubtype || row.predicted_subtype };
          } catch {
            return row;
          }
        })
      );

      setRecentAnalyses(resolved);
    } catch (err) {
      console.error(err);
      setRecentAnalyses([]);
    }
  };

  const handleFile = (f: File) => {
    setFile(f);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const result = await api.analyze(file, classifierType);
      navigate(`/results/${result.analysis_id}?cancerType=${classifierType}`);
    } catch (error) {
      console.error('Analysis upload failed:', error);
      alert('Failed to start analysis: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    try {
      const data = await api.summary();
      setSummaryStats(data);
    } catch (err) {
      console.error(err);
      setSummaryStats(null);
    }
  };

  useEffect(() => {
    const run = async () => {
      try {
        await Promise.all([loadRecent(), loadSummary()]);
      } finally {
        setRecentLoading(false);
        setSummaryLoading(false);
      }
    };
    run();
  }, []);

  const stats = [
    {
      label: 'Analyses Run',
      value: summaryLoading ? '...' : (summaryStats?.analyses_run ?? recentAnalyses.length).toLocaleString(),
    },
    {
      label: 'Genes Profiled',
      value: summaryLoading ? '...' : (summaryStats?.genes_profiled ?? 0).toLocaleString(),
    },
    {
      label: 'Drug Candidates',
      value: summaryLoading ? '...' : (summaryStats?.drug_candidates ?? 0).toLocaleString(),
    },
    {
      label: 'Avg. Pipeline Time',
      value:
        summaryLoading
          ? '...'
          : summaryStats?.avg_pipeline_minutes != null
            ? `${summaryStats.avg_pipeline_minutes} min`
            : 'N/A',
    },
  ];

  return (
    <div className="space-y-16">
      {/* Hero */}
      <section className="text-center pt-8 pb-4">
        <div className="inline-flex items-center gap-2 bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-medium px-4 py-1.5 rounded-full mb-6">
          <Activity size={12} className="animate-pulse" />
          Gene Expression Analysis Pipeline v1.0
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-gray-50 tracking-tight leading-tight mb-4">
          Cancer Gene
          <br />
          <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
            Analysis Pipeline
          </span>
        </h1>

        <p className="text-gray-400 text-lg max-w-xl mx-auto mb-12">
          Upload a patient gene expression CSV to begin analysis
        </p>

        {/* Upload section */}
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="text-left">
            <label htmlFor="classifierType" className="block text-sm font-medium text-gray-300 mb-2">
              Classifier
            </label>
            <select
              id="classifierType"
              value={classifierType}
              onChange={(e) => setClassifierType(e.target.value as 'lung' | 'colorectal')}
              className="w-full rounded-xl border border-gray-700 bg-gray-900/80 px-4 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            >
              <option value="lung">Lung Classifier</option>
              <option value="colorectal">Colorectal Classifier</option>
            </select>
          </div>

          <UploadBox onFile={handleFile} />

          <button
            onClick={handleAnalyze}
            disabled={!file || loading}
            className={`w-full py-4 rounded-2xl text-base font-semibold flex items-center justify-center gap-2.5 transition-all duration-300 ${
              file && !loading
                ? 'bg-cyan-500 hover:bg-cyan-400 text-gray-950 shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 hover:-translate-y-0.5'
                : 'bg-gray-800 text-gray-600 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-gray-950/30 border-t-gray-950 rounded-full animate-spin" />
                Starting Pipeline...
              </>
            ) : (
              <>
                <Dna size={18} />
                Analyze Patient
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
      </section>

      {/* Stats strip */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-xl border border-gray-800 bg-gray-900/40 p-4 text-center">
            <p className="text-2xl font-black text-gray-100">{stat.value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{stat.label}</p>
          </div>
        ))}
      </section>

      {/* Recent analyses */}
      <section>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-200">Recent Analyses</h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-600">{recentLoading ? 'Loading...' : `${recentAnalyses.length} records`}</span>
            <button
              onClick={async () => {
                if (recentAnalyses.length === 0 || clearing) return;
                const ok = window.confirm('Clear all recent analyses? This will delete records from the database.');
                if (!ok) return;
                setClearing(true);
                try {
                  await api.clearRecent();
                  await Promise.all([loadRecent(), loadSummary()]);
                } catch (err) {
                  console.error(err);
                } finally {
                  setClearing(false);
                }
              }}
              disabled={recentAnalyses.length === 0 || recentLoading || clearing}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
                recentAnalyses.length === 0 || recentLoading || clearing
                  ? 'bg-gray-900/40 text-gray-600 border-gray-800 cursor-not-allowed'
                  : 'bg-red-500/10 text-red-300 border-red-500/20 hover:bg-red-500/15'
              }`}
            >
              {clearing ? 'Clearing…' : 'Clear'}
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-700/60 bg-gray-900/60 backdrop-blur-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Patient ID</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Subtype</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">View</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/40">
                {recentAnalyses.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <span className="text-sm font-mono text-gray-200">{a.patient_id}</span>
                    </td>
                    <td className="px-6 py-4">
                      {a.predicted_subtype ? (
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-lg ${getSubtypeStyle(a.predicted_subtype)}`}>
                          {a.predicted_subtype}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-600">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full border capitalize ${statusStyles[a.status]}`}>
                        {a.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{formatDate(a.created_at)}</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => navigate(`/results/${a.id}`)}
                        className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                      >
                        <Eye size={12} />
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}