import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { manifestsApi, ManifestListItem } from '../api/client';
import ManifestUpload from '../components/ManifestUpload';

const STATUS_COLORS: Record<string, string> = {
  uploaded: '#90a4ae',
  processing: '#ffa726',
  classified: '#42a5f5',
  pending_approval: '#ab47bc',
  approved: '#66bb6a',
  rejected: '#ef5350',
  filed: '#26a69a',
  filing_failed: '#ef5350',
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Uploaded',
  processing: 'Processing...',
  classified: 'Classified',
  pending_approval: 'Pending Approval',
  approved: 'Approved',
  rejected: 'Rejected',
  filed: 'Filed',
  filing_failed: 'Filing Failed',
};

export default function Dashboard() {
  const [manifests, setManifests] = useState<ManifestListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const navigate = useNavigate();

  const fetchManifests = async () => {
    try {
      const res = await manifestsApi.list(statusFilter || undefined);
      setManifests(res.data);
    } catch {
      toast.error('Failed to load manifests');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchManifests();
    const interval = setInterval(fetchManifests, 8000); // Auto-refresh for processing status
    return () => clearInterval(interval);
  }, [statusFilter]);

  const handleUploaded = (manifestId: number) => {
    setShowUpload(false);
    setTimeout(() => {
      navigate(`/manifests/${manifestId}`);
    }, 1000);
  };

  const pendingCount = manifests.filter(m => m.status === 'pending_approval').length;
  const processingCount = manifests.filter(m => m.status === 'processing').length;

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>India Customs Manifest Processor</h1>
          <p style={styles.subtitle}>AI-powered HS classification · Duty calculation · ICEGATE filing</p>
        </div>
        <button style={styles.uploadBtn} onClick={() => setShowUpload(!showUpload)}>
          {showUpload ? '✕ Close' : '+ Upload Manifest'}
        </button>
      </div>

      {(pendingCount > 0 || processingCount > 0) && (
        <div style={styles.alertBanner}>
          {pendingCount > 0 && (
            <span style={styles.alertChip}>
              🔔 {pendingCount} manifest{pendingCount > 1 ? 's' : ''} awaiting approval
            </span>
          )}
          {processingCount > 0 && (
            <span style={{ ...styles.alertChip, background: '#fff3e0', color: '#e65100' }}>
              ⏳ {processingCount} processing
            </span>
          )}
        </div>
      )}

      {showUpload && (
        <div style={styles.uploadSection}>
          <ManifestUpload onUploaded={handleUploaded} />
        </div>
      )}

      <div style={styles.filterRow}>
        <label style={styles.filterLabel}>Filter by status:</label>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={styles.filterSelect}
        >
          <option value="">All</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="processing">Processing</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="filed">Filed</option>
        </select>
      </div>

      {loading ? (
        <div style={styles.center}>Loading manifests...</div>
      ) : manifests.length === 0 ? (
        <div style={styles.emptyState}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>📋</div>
          <h3 style={{ color: '#555' }}>No manifests yet</h3>
          <p style={{ color: '#888' }}>Upload your first manifest to get started</p>
          <button style={styles.uploadBtn} onClick={() => setShowUpload(true)}>
            + Upload Manifest
          </button>
        </div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr style={styles.theadRow}>
                <th style={styles.th}>Reference</th>
                <th style={styles.th}>File</th>
                <th style={styles.th}>Origin</th>
                <th style={styles.th}>CIF Value</th>
                <th style={styles.th}>Total Duty</th>
                <th style={styles.th}>Status</th>
                <th style={styles.th}>Date</th>
                <th style={styles.th}></th>
              </tr>
            </thead>
            <tbody>
              {manifests.map(m => (
                <tr
                  key={m.id}
                  style={styles.row}
                  onClick={() => navigate(`/manifests/${m.id}`)}
                >
                  <td style={styles.td}>
                    <code style={styles.ref}>{m.reference_number}</code>
                  </td>
                  <td style={styles.td}>{m.file_name || '—'}</td>
                  <td style={styles.td}>{m.shipper_country || '—'}</td>
                  <td style={styles.td}>
                    {m.total_cif_value != null ? `USD ${m.total_cif_value.toLocaleString()}` : '—'}
                  </td>
                  <td style={styles.td}>
                    {m.total_duty != null
                      ? <strong style={{ color: '#1a237e' }}>₹ {m.total_duty.toLocaleString('en-IN')}</strong>
                      : '—'}
                  </td>
                  <td style={styles.td}>
                    <span style={{
                      ...styles.statusBadge,
                      background: STATUS_COLORS[m.status] + '22',
                      color: STATUS_COLORS[m.status],
                      borderColor: STATUS_COLORS[m.status] + '44',
                    }}>
                      {STATUS_LABELS[m.status] || m.status}
                    </span>
                  </td>
                  <td style={styles.td}>
                    {new Date(m.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </td>
                  <td style={styles.td}>
                    <button style={styles.viewBtn}>View →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 1100, margin: '0 auto', padding: '32px 24px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 },
  title: { margin: 0, color: '#1a237e', fontSize: 24 },
  subtitle: { margin: '4px 0 0', color: '#777', fontSize: 14 },
  uploadBtn: {
    background: '#1a237e', color: '#fff', border: 'none', borderRadius: 8,
    padding: '10px 20px', fontSize: 14, cursor: 'pointer', fontWeight: 600,
  },
  alertBanner: { display: 'flex', gap: 12, marginBottom: 20 },
  alertChip: { background: '#e8eaf6', color: '#1a237e', padding: '6px 14px', borderRadius: 20, fontSize: 13, fontWeight: 600 },
  uploadSection: { marginBottom: 32 },
  filterRow: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 },
  filterLabel: { fontSize: 13, color: '#555', fontWeight: 600 },
  filterSelect: { padding: '6px 12px', fontSize: 13, border: '1px solid #ddd', borderRadius: 6, background: '#fff' },
  center: { textAlign: 'center', padding: 48, color: '#888' },
  emptyState: { textAlign: 'center', padding: 64, color: '#555' },
  tableWrap: { background: '#fff', borderRadius: 10, boxShadow: '0 1px 8px rgba(0,0,0,0.07)', overflow: 'hidden' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  theadRow: { background: '#f5f5f5' },
  th: { padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#555', borderBottom: '2px solid #e0e0e0' },
  row: { borderBottom: '1px solid #f0f0f0', cursor: 'pointer', transition: 'background 0.15s' },
  td: { padding: '12px 16px', verticalAlign: 'middle' },
  ref: { background: '#f5f5f5', padding: '2px 6px', borderRadius: 4, fontSize: 12 },
  statusBadge: { padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, border: '1px solid' },
  viewBtn: { background: 'transparent', border: 'none', color: '#1565c0', cursor: 'pointer', fontSize: 13 },
};
