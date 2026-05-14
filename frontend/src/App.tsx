import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Dashboard from './pages/Dashboard';
import ManifestDetail from './pages/ManifestDetail';

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', background: '#f4f6fb' }}>
        <nav style={styles.nav}>
          <div style={styles.navInner}>
            <span style={styles.logo}>🇮🇳 India Customs Processor</span>
            <span style={styles.navRight}>Powered by Claude AI</span>
          </div>
        </nav>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/manifests/:id" element={<ManifestDetail />} />
          <Route path="/manifests/:id/review" element={<ManifestDetail />} />
        </Routes>
      </div>
      <Toaster position="top-right" />
    </BrowserRouter>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    background: '#1a237e',
    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
  },
  navInner: {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '14px 24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logo: { color: '#fff', fontSize: 17, fontWeight: 700 },
  navRight: { color: '#9fa8da', fontSize: 13 },
};
