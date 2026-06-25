import { useState, useCallback } from 'react';
import { Upload, X, FileText, File, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { documentsApi } from '../api/client';
import './UploadModal.css';

const ACCEPT = '.pdf,.docx,.txt';
const MAX_MB = 50;

export default function UploadModal({ onClose, onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('idle'); // idle | uploading | success | error
  const [errorMsg, setErrorMsg] = useState('');

  const validateFile = (f) => {
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext))
      return `Unsupported file type: .${ext}`;
    if (f.size > MAX_MB * 1024 * 1024)
      return `File exceeds ${MAX_MB} MB limit`;
    return null;
  };

  const pickFile = (f) => {
    const err = validateFile(f);
    if (err) { setErrorMsg(err); return; }
    setFile(f);
    setErrorMsg('');
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''));
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }, [title]);

  const handleUpload = async () => {
    if (!file) return;
    setStatus('uploading');
    try {
      const doc = await documentsApi.upload(file, title || undefined);
      setStatus('success');
      setTimeout(() => { onUploaded(doc); onClose(); }, 1200);
    } catch (err) {
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  const fileIcon = () => {
    if (!file) return null;
    const ext = file.name.split('.').pop().toLowerCase();
    return ext === 'pdf' ? <FileText size={20} className="file-icon pdf" />
         : ext === 'docx' ? <File size={20} className="file-icon docx" />
         : <FileText size={20} className="file-icon txt" />;
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card">
        <div className="modal-header">
          <h2>Upload Document</h2>
          <button className="modal-close" onClick={onClose}><X size={18} /></button>
        </div>

        {/* Drop zone */}
        <div
          className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !file && document.getElementById('file-input').click()}
        >
          <input
            id="file-input"
            type="file"
            accept={ACCEPT}
            style={{ display: 'none' }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); }}
          />
          {file ? (
            <div className="file-preview">
              {fileIcon()}
              <div>
                <p className="file-name">{file.name}</p>
                <p className="file-size">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <button className="remove-file" onClick={(e) => { e.stopPropagation(); setFile(null); setTitle(''); }}>
                <X size={16} />
              </button>
            </div>
          ) : (
            <>
              <div className="drop-icon"><Upload size={28} /></div>
              <p className="drop-label">Drop your file here or <span>browse</span></p>
              <p className="drop-hint">Supports PDF, DOCX, TXT · Max {MAX_MB} MB</p>
            </>
          )}
        </div>

        {/* Title override */}
        {file && (
          <div className="modal-field">
            <label>Document Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter a custom title…"
            />
          </div>
        )}

        {/* Error */}
        {errorMsg && (
          <div className="modal-error">
            <AlertCircle size={15} /> {errorMsg}
          </div>
        )}

        {/* Success */}
        {status === 'success' && (
          <div className="modal-success">
            <CheckCircle size={15} /> Document ingested successfully!
          </div>
        )}

        {/* Actions */}
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onClose}>Cancel</button>
          <button
            className="btn-upload"
            onClick={handleUpload}
            disabled={!file || status === 'uploading' || status === 'success'}
          >
            {status === 'uploading'
              ? <><Loader size={15} className="spin" /> Processing…</>
              : <><Upload size={15} /> Upload & Ingest</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
