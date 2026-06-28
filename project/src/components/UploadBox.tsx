import { useRef, useState, useCallback, useEffect } from 'react';
import { Upload, FileText, X, AlertCircle } from 'lucide-react';

interface FileInfo {
  name: string;
  size: number;
  patientId: string;
}

interface UploadBoxProps {
  file: File | null;
  onFile: (file: File | null) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function extractPatientId(text: string): string {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return 'UNKNOWN';
  const firstDataRow = lines[1].trim().split(',');
  return firstDataRow[0]?.replace(/"/g, '').trim() || 'UNKNOWN';
}

export default function UploadBox({ file, onFile }: UploadBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);

  useEffect(() => {
    if (!file) {
      setFileInfo(null);
      setError(null);
      return;
    }

    if (!fileInfo || fileInfo.name !== file.name || fileInfo.size !== file.size) {
      setReading(true);
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        const patientId = extractPatientId(text);
        setFileInfo({ name: file.name, size: file.size, patientId });
        setReading(false);
      };
      reader.onerror = () => {
        setError('Failed to read file');
        setReading(false);
      };
      reader.readAsText(file.slice(0, 4096));
    }
  }, [file, fileInfo]);

  const processFile = useCallback((file: File) => {
    if (!file.name.endsWith('.csv')) {
      setError('Please upload a CSV file');
      return;
    }
    setError(null);
    onFile(file);
  }, [onFile]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }, [processFile]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const clear = () => {
    setFileInfo(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
    onFile(null);
  };

  return (
    <div className="w-full">
      {!fileInfo ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-300 ${dragging
            ? 'border-cyan-400 bg-cyan-500/10 scale-[1.01]'
            : 'border-gray-700 bg-gray-900/40 hover:border-gray-600 hover:bg-gray-900/60'
            }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleChange}
          />
          <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 transition-colors ${dragging ? 'bg-cyan-500/20' : 'bg-gray-800'
            }`}>
            <Upload size={28} className={dragging ? 'text-cyan-400' : 'text-gray-400'} />
          </div>
          <p className="text-gray-200 font-medium text-lg mb-1">
            {dragging ? 'Drop your CSV here' : 'Drag & drop your CSV file'}
          </p>
          <p className="text-gray-500 text-sm mb-4">or click to browse files</p>
          <span className="text-xs text-gray-600 bg-gray-800 px-3 py-1 rounded-full">
            Accepts .csv gene expression files
          </span>
          {reading && (
            <div className="absolute inset-0 bg-gray-950/60 rounded-2xl flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
      ) : (
        <div className="border border-gray-700 rounded-2xl p-6 bg-gray-900/60 backdrop-blur-sm">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0">
                <FileText size={22} className="text-cyan-400" />
              </div>
              <div>
                <p className="font-medium text-gray-100 mb-0.5">{fileInfo.name}</p>
                <p className="text-sm text-gray-500">{formatBytes(fileInfo.size)}</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-gray-500">Detected Patient ID:</span>
                  <span className="text-xs font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2 py-0.5 rounded">
                    {fileInfo.patientId}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={clear}
              className="text-gray-600 hover:text-gray-300 transition-colors p-1"
            >
              <X size={18} />
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={14} />
          {error}
        </div>
      )}
    </div>
  );
}
