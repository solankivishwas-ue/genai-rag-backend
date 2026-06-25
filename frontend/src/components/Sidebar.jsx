import { useState, useEffect } from 'react';
import {
  FileText, File, Trash2, Upload, Plus,
  Search, RefreshCw, Database, ChevronRight
} from 'lucide-react';
import { documentsApi } from '../api/client';
import UploadModal from './UploadModal';
import './Sidebar.css';

export default function Sidebar({ selectedDoc, onSelectDoc, onNewChat, refreshTrigger }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const data = await documentsApi.list(1, 100);
      setDocs(data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocs(); }, [refreshTrigger]);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Delete this document and all its chunks?')) return;
    setDeletingId(id);
    try {
      await documentsApi.delete(id);
      setDocs((d) => d.filter((x) => x.id !== id));
      if (selectedDoc?.id === id) onSelectDoc(null);
    } catch (err) {
      alert(err.message);
    } finally {
      setDeletingId(null);
    }
  };

  const fileIcon = (doc) => {
    const src = (doc.source || '').toLowerCase();
    if (src.endsWith('.pdf')) return <FileText size={15} className="doc-icon pdf" />;
    if (src.endsWith('.docx')) return <File size={15} className="doc-icon docx" />;
    return <FileText size={15} className="doc-icon" />;
  };

  const filtered = docs.filter((d) =>
    d.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      <aside className="sidebar">
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">
              <Database size={16} />
            </div>
            <span>Knowledge Base</span>
          </div>
          <button className="icon-btn" onClick={fetchDocs} title="Refresh">
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
          </button>
        </div>

        {/* Actions */}
        <div className="sidebar-actions">
          <button className="btn-new-chat" onClick={onNewChat}>
            <Plus size={15} /> New Chat
          </button>
          <button className="btn-upload-small" onClick={() => setShowUpload(true)} title="Upload document">
            <Upload size={15} />
          </button>
        </div>

        {/* Search */}
        <div className="sidebar-search">
          <Search size={14} className="search-icon" />
          <input
            type="text"
            placeholder="Search documents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Doc count */}
        <div className="sidebar-count">
          <span>{filtered.length} document{filtered.length !== 1 ? 's' : ''}</span>
        </div>

        {/* Document list */}
        <div className="doc-list">
          {loading ? (
            <div className="doc-list-empty">
              <RefreshCw size={20} className="spin" />
              <p>Loading…</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="doc-list-empty">
              <Database size={28} />
              <p>{search ? 'No results' : 'No documents yet'}</p>
              {!search && (
                <button className="btn-upload-empty" onClick={() => setShowUpload(true)}>
                  <Upload size={14} /> Upload your first file
                </button>
              )}
            </div>
          ) : (
            filtered.map((doc) => (
              <div
                key={doc.id}
                className={`doc-item ${selectedDoc?.id === doc.id ? 'active' : ''}`}
                onClick={() => onSelectDoc(doc)}
              >
                <div className="doc-item-icon">{fileIcon(doc)}</div>
                <div className="doc-item-body">
                  <p className="doc-title">{doc.title}</p>
                  <p className="doc-date">
                    {new Date(doc.created_at).toLocaleDateString(undefined, {
                      month: 'short', day: 'numeric'
                    })}
                  </p>
                </div>
                {selectedDoc?.id === doc.id && <ChevronRight size={14} className="doc-chevron" />}
                <button
                  className="doc-delete"
                  onClick={(e) => handleDelete(e, doc.id)}
                  disabled={deletingId === doc.id}
                  title="Delete document"
                >
                  {deletingId === doc.id
                    ? <RefreshCw size={13} className="spin" />
                    : <Trash2 size={13} />}
                </button>
              </div>
            ))
          )}
        </div>

        {/* Upload CTA if docs exist */}
        {docs.length > 0 && (
          <button className="sidebar-upload-cta" onClick={() => setShowUpload(true)}>
            <Upload size={15} /> Upload Document
          </button>
        )}
      </aside>

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={(doc) => { setDocs((d) => [doc, ...d]); }}
        />
      )}
    </>
  );
}
