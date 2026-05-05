import { Link, useLocation } from 'react-router-dom';
import { Activity, Dna, Home, ChevronRight } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const isResults = location.pathname.startsWith('/results');

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      <header className="border-b border-gray-800/60 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center group-hover:bg-cyan-500/20 transition-colors">
              <Dna size={16} className="text-cyan-400" />
            </div>
            <span className="font-semibold text-sm text-gray-200 tracking-wide">Gene Expression Pipeline</span>
          </Link>

          <nav className="flex items-center gap-1">
            <Link
              to="/"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                !isResults ? 'text-cyan-400 bg-cyan-500/10' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Home size={14} />
              Home
            </Link>
            {isResults && (
              <>
                <ChevronRight size={14} className="text-gray-600" />
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-cyan-400 bg-cyan-500/10">
                  <Activity size={14} />
                  Results
                </span>
              </>
            )}
          </nav>

          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-gray-500">Pipeline Active</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
