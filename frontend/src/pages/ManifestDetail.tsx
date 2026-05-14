import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { manifestsApi, Manifest } from '../api/client';
import ClassificationReview from '../components/ClassificationReview';
import DutyBreakdown from '../components/DutyBreakdown';

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Uploaded',
  processing: '⏳ Processing — please wait...',
  classified: 'Classified',
  pending_approval: '🔔 Pending Your Approval',
  approved: '✓ Approved',
  rejected: '✗ Rejected',
  filed: '✓ Filed with ICEGATE',
};

export default function ManifestDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [overrides, setOverrides] = useState<Array<{ item_id: number; hs_code: string; note: string }>>([]);
  const [approverName, setApproverName] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [acting, setActing] = useState(false);

  const fetchManifest = async () => {
    if (!id) return;
    try {
      const res = await manifestsApi.get(Number(id));
      setManifest(res.data);
    } catch {
      toast.error('Failed to load manifest');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchManifest();
    const interval = setInterval(() => {
      if (manifest?.status === 'processing' || manifest?.status === 'uploaded') {
        fetchManifest();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [id, manifest?.status]);

  const handleApprove = async () => {
    if (!manifest || !approverName.trim()) {
      toast.error('Please enter your name to approve');
      return;
    }
    setActing(true);
    try {
      await manifestsApi.approve(manifest.id, approverName, overrides.length > 0 ? overrides : undefined);
      toast.success('Manifest approved! ICEGATE XML generated.');
      fetchManifest();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Approval failed');
    } finally {
      setActing(false);
    }
  };

  const handleReject = async () => {
    if (!manifest || !approverName.trim() || !rejectReason.trim()) {
      toast.error('Please enter your name and rejection reason');
      return;
    }
    setActing(true);
    try {
      await manifestsApi.reject(manifest.id, approverName, rejectReason);
      toast.success('Manifest rejected');
      fetchManifest();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Rejection failed');
    } finally {
      setActing(false);
    }
  };

  if (loading) return <div style={styles.center}>Loading...</div>;
  if (!manifest) return <div style={styles.center}>Manifest not found</div>;

  const isProcessing = manifest.status === 'processing' || manifest.status === 'uploaded';
  const isPendingApproval = manifest.status === 'pending_approval';
  const isApproved = manifest.status === 'approved';
  const isRejected = manifest.status === 'rejected';
  const flaggedCount = manifest.items.filter(i => i.needs_manual_review).length;

  return (
    <div style={styles.page}>
      <div style={styles.breadcrumb}>
        <button style={styles.backBtn} onClick={() => navigate('/')}>← Dashboard</button>
        <span style={styles.breadSep}>/</span>
        <span>{manifest.reference_number}</span>
      </div>

      {/* Header */}
      <div style={styles.headerCard}>
        <div>
          <h1 style={styles.title}>{manifest.reference_number}</h1>
          <p style={styles.subtitle}>
            {manifest.file_name} · {manifest.shipment_mode?.toUpperCase()} ·{' '}
            {new Date(manifest.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div style={styles.statusBox}>
          <div style={styles.statusLabel}>{STATUS_LABELS[manifest.status] || manifest.status}</div>
          {isApproved && manifest.total_duty != null && (
            <div style={styles.dutyBig}>₹ {manifest.total_duty.toLocaleString('en-IN')}</div>
          )}
        </div>
      </div>

      {isProcessing && (
        <div style={styles.processingBanner}>
          <div style={styles.spinnerInline} />
          AI is classifying line items and calculating duty. This usually takes 30–60 seconds.
          Page auto-refreshes every 5 seconds.
        </div>
      )}

      {isRejected && (
        <div style={styles.rejectedBanner}>
          <strong>Rejected:</strong> {manifest.rejection_reason}
        </div>
      )}

      {/* Consignment info */}
      <div style={styles.infoGrid}>
        {[
          ['Shipper', manifest.shipper_name],
          ['Country of Origin', manifest.country_of_origin || manifest.shipper_country],
          ['Consignee', manifest.consignee_name],
          ['B/L Number', manifest.bill_of_lading_number],
          ['Port of Loading', manifest.port_of_loading],
          ['Port of Discharge', manifest.port_of_discharge],
          ['Incoterms', manifest.incoterms],
          ['FTA', manifest.fta_applicable ? `${manifest.fta_name}${manifest.coo_available ? ' ✓ COO' : ' (no COO)'}` : 'Not applicable'],
        ].map(([label, value]) => (
          <div key={label} style={styles.infoCell}>
            <div style={styles.infoLabel}>{label}</div>
            <div style={styles.infoValue}>{value || '—'}</div>
          </div>
        ))}
      </div>

      {/* Items table (only when processed) */}
      {manifest.items.length > 0 && (
        <>
          <DutyBreakdown manifest={manifest} />
          <ClassificationReview
            items={manifest.items}
            onOverridesChange={setOverrides}
          />
        </>
      )}

      {/* Approval actions */}
      {isPendingApproval && (
        <div style={styles.approvalCard}>
          <h3 style={styles.approvalTitle}>Approval Required</h3>

          {flaggedCount > 0 && (
            <div style={styles.flagWarning}>
              ⚠ <strong>{flaggedCount} item(s) have low classification confidence.</strong>{' '}
              Review them above and override if needed before approving.
            </div>
          )}

          <div style={styles.approvalForm}>
            <label style={styles.label}>Your name / designation</label>
            <input
              type="text"
              placeholder="e.g. Rajesh Kumar, Import Manager"
              value={approverName}
              onChange={e => setApproverName(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.approvalButtons}>
            <button
              style={{ ...styles.approveBtn, opacity: acting ? 0.7 : 1 }}
              onClick={handleApprove}
              disabled={acting}
            >
              {acting ? 'Processing...' : '✓ Approve & Generate ICEGATE XML'}
            </button>
            <button
              style={styles.rejectToggleBtn}
              onClick={() => setShowRejectForm(!showRejectForm)}
            >
              ✗ Reject
            </button>
          </div>

          {showRejectForm && (
            <div style={styles.rejectForm}>
              <label style={styles.label}>Rejection reason</label>
              <textarea
                placeholder="Describe why this manifest is being rejected..."
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                style={styles.textarea}
                rows={3}
              />
              <button
                style={{ ...styles.rejectBtn, opacity: acting ? 0.7 : 1 }}
                onClick={handleReject}
                disabled={acting}
              >
                Confirm Rejection
              </button>
            </div>
          )}
        </div>
      )}

      {/* ICEGATE download (post-approval) */}
      {isApproved && (
        <div style={styles.iceGateCard}>
          <h3 style={styles.iceGateTitle}>V2: File with ICEGATE</h3>
          <p style={styles.iceGateDesc}>
            The Bill of Entry EDI XML has been generated. Upload it to the ICEGATE portal to file.
          </p>
          <div style={styles.iceGateSteps}>
            <div style={styles.step}><strong>1.</strong> Download the XML below</div>
            <div style={styles.step}><strong>2.</strong> Log in to <a href="https://www.icegate.gov.in" target="_blank" rel="noreferrer" style={styles.link}>icegate.gov.in</a></div>
            <div style={styles.step}><strong>3.</strong> Navigate: Services → Bill of Entry → Upload EDI BE</div>
            <div style={styles.step}><strong>4.</strong> Upload the XML and verify pre-filled data</div>
            <div style={styles.step}><strong>5.</strong> Submit and note the BE number assigned</div>
          </div>
          <button
            style={styles.downloadBtn}
            onClick={() => manifestsApi.downloadIceGateXml(manifest.id)}
          >
            ⬇ Download ICEGATE EDI XML
          </button>
          <div style={styles.iceGateNote}>
            <strong>Note:</strong> For fully automated filing without manual upload, register as an ICEGATE EDI user
            at icegate.gov.in under Services → EDI Registration. We can then submit directly via API.
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 1100, margin: '0 auto', padding: '32px 24px' },
  center: { textAlign: 'center', padding: 80, color: '#888' },
  breadcrumb: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, fontSize: 13, color: '#888' },
  backBtn: { background: 'none', border: 'none', color: '#1565c0', cursor: 'pointer', fontSize: 13 },
  breadSep: { color: '#ccc' },
  headerCard: {
    background: '#1a237e', color: '#fff', borderRadius: 12, padding: '24px 32px',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24,
  },
  title: { margin: 0, fontSize: 22 },
  subtitle: { margin: '4px 0 0', opacity: 0.8, fontSize: 13 },
  statusBox: { textAlign: 'right' },
  statusLabel: { fontSize: 14, opacity: 0.9, fontWeight: 600 },
  dutyBig: { fontSize: 28, fontWeight: 700, marginTop: 4 },
  processingBanner: {
    background: '#fff3e0', border: '1px solid #ffcc80', borderRadius: 8,
    padding: '14px 20px', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12, fontSize: 14,
  },
  spinnerInline: {
    width: 20, height: 20, border: '2px solid #ffe0b2', borderTop: '2px solid #e65100',
    borderRadius: '50%', animation: 'spin 1s linear infinite', flexShrink: 0,
  },
  rejectedBanner: {
    background: '#ffebee', borderLeft: '4px solid #ef5350', padding: '12px 20px',
    borderRadius: 6, marginBottom: 24, fontSize: 14,
  },
  infoGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 16, marginBottom: 24,
  },
  infoCell: { background: '#fff', borderRadius: 8, padding: '14px 18px', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  infoLabel: { fontSize: 11, color: '#999', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 },
  infoValue: { fontSize: 14, color: '#333', fontWeight: 500 },
  approvalCard: {
    background: '#fff', borderRadius: 12, padding: 28, boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
    border: '2px solid #7986cb', marginBottom: 24,
  },
  approvalTitle: { margin: '0 0 16px', color: '#1a237e' },
  flagWarning: { background: '#fff3e0', borderLeft: '4px solid #ff9800', padding: '10px 16px', borderRadius: 4, marginBottom: 16, fontSize: 13 },
  approvalForm: { marginBottom: 20 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, color: '#555', marginBottom: 6 },
  input: { width: '100%', padding: '10px 12px', fontSize: 14, border: '1px solid #ddd', borderRadius: 6 },
  approvalButtons: { display: 'flex', gap: 12 },
  approveBtn: {
    background: '#2e7d32', color: '#fff', border: 'none', borderRadius: 8,
    padding: '12px 24px', fontSize: 15, cursor: 'pointer', fontWeight: 600,
  },
  rejectToggleBtn: {
    background: '#fff', color: '#c62828', border: '2px solid #ef9a9a',
    borderRadius: 8, padding: '12px 24px', fontSize: 15, cursor: 'pointer',
  },
  rejectForm: { marginTop: 16 },
  textarea: { width: '100%', padding: '10px 12px', fontSize: 14, border: '1px solid #ddd', borderRadius: 6, resize: 'vertical' },
  rejectBtn: {
    background: '#c62828', color: '#fff', border: 'none', borderRadius: 8,
    padding: '10px 20px', fontSize: 14, cursor: 'pointer', marginTop: 8,
  },
  iceGateCard: {
    background: '#fff', borderRadius: 12, padding: 28,
    boxShadow: '0 2px 16px rgba(0,0,0,0.08)', border: '2px solid #81c784',
  },
  iceGateTitle: { margin: '0 0 8px', color: '#2e7d32' },
  iceGateDesc: { color: '#555', marginBottom: 16, fontSize: 14 },
  iceGateSteps: { marginBottom: 20 },
  step: { padding: '6px 0', fontSize: 13, color: '#444', borderBottom: '1px solid #f0f0f0' },
  link: { color: '#1565c0' },
  downloadBtn: {
    background: '#1565c0', color: '#fff', border: 'none', borderRadius: 8,
    padding: '12px 24px', fontSize: 15, cursor: 'pointer', fontWeight: 600, marginBottom: 16,
  },
  iceGateNote: { background: '#e8f5e9', padding: '12px 16px', borderRadius: 6, fontSize: 12, color: '#555' },
};
