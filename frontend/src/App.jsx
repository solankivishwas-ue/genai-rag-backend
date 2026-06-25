import { useState } from 'react';
import { LogOut, Bot } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthPage from './components/AuthPage';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import './App.css';

function AppShell() {
  const { user, loading, logout } = useAuth();
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [chatKey, setChatKey] = useState(0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-logo">
          <Bot size={32} />
        </div>
        <p>Loading…</p>
      </div>
    );
  }

  if (!user) return <AuthPage />;

  const handleNewChat = () => {
    setSelectedDoc(null);
    setChatKey((k) => k + 1);
  };

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <Sidebar
        selectedDoc={selectedDoc}
        onSelectDoc={setSelectedDoc}
        onNewChat={handleNewChat}
        refreshTrigger={refreshTrigger}
      />

      {/* Main content */}
      <div className="app-main">
        {/* Top nav */}
        <nav className="app-nav">
          <div className="app-nav-brand">
            <div className="nav-logo-icon"><Bot size={18} /></div>
            <span className="nav-logo-text">RAG<span className="nav-accent">Chat</span></span>
          </div>

          <div className="app-nav-right">
            <a
              className="nav-link"
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              title="API Documentation"
            >
              API Docs
            </a>
            <div className="nav-user">
              <div className="nav-avatar">
                {user.full_name?.[0]?.toUpperCase() || user.email[0].toUpperCase()}
              </div>
              <span className="nav-email">{user.full_name || user.email.split('@')[0]}</span>
            </div>
            <button className="nav-logout" onClick={logout} title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </nav>

        {/* Chat */}
        <ChatWindow key={chatKey} selectedDoc={selectedDoc} />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
