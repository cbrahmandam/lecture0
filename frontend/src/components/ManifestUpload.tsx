import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { manifestsApi } from '../api/client';

interface Props {
  onUploaded: (manifestId: number) => void;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
  'text/csv': ['.csv'],
  'application/xml': ['.xml'],
  'text/xml': ['.xml'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
};

export default function ManifestUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [shipmentMode, setShipmentMode] = useState<'sea' | 'air'>('sea');
  const [countryOfOrigin, setCountryOfOrigin] = useState('');
  const [notifyEmail, setNotifyEmail] = useState('');
  const [cooAvailable, setCooAvailable] = useState(false);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('shipment_mode', shipmentMode);
    if (countryOfOrigin) formData.append('country_of_origin', countryOfOrigin);
    if (notifyEmail) formData.append('notify_email', notifyEmail);
    formData.append('coo_available', cooAvailable.toString());

    try {
      const res = await manifestsApi.upload(formData);
      toast.success(`Manifest uploaded! Reference: ${res.data.reference_number}. Classification in progress...`);
      onUploaded(res.data.manifest_id);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, [shipmentMode, countryOfOrigin, notifyEmail, cooAvailable, onUploaded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Upload Manifest</h2>

      <div style={styles.formRow}>
        <label style={styles.label}>Shipment Mode</label>
        <select
          value={shipmentMode}
          onChange={e => setShipmentMode(e.target.value as 'sea' | 'air')}
          style={styles.select}
        >
          <option value="sea">Sea Freight</option>
          <option value="air">Air Freight</option>
        </select>
      </div>

      <div style={styles.formRow}>
        <label style={styles.label}>Country of Origin</label>
        <input
          type="text"
          placeholder="e.g. China, Thailand, UAE"
          value={countryOfOrigin}
          onChange={e => setCountryOfOrigin(e.target.value)}
          style={styles.input}
        />
      </div>

      <div style={styles.formRow}>
        <label style={styles.label}>Notify Email (for approval)</label>
        <input
          type="email"
          placeholder="approver@company.com"
          value={notifyEmail}
          onChange={e => setNotifyEmail(e.target.value)}
          style={styles.input}
        />
      </div>

      <div style={styles.checkRow}>
        <input
          type="checkbox"
          id="coo"
          checked={cooAvailable}
          onChange={e => setCooAvailable(e.target.checked)}
        />
        <label htmlFor="coo" style={styles.checkLabel}>
          Certificate of Origin (COO) available — enables FTA preferential duty rates
        </label>
      </div>

      <div
        {...getRootProps()}
        style={{
          ...styles.dropzone,
          ...(isDragActive ? styles.dropzoneActive : {}),
          ...(uploading ? styles.dropzoneDisabled : {}),
        }}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div>
            <div style={styles.spinner} />
            <p style={styles.dropText}>Uploading and processing...</p>
          </div>
        ) : isDragActive ? (
          <p style={styles.dropText}>Drop the manifest here</p>
        ) : (
          <div>
            <div style={styles.uploadIcon}>📄</div>
            <p style={styles.dropText}>Drag & drop your manifest here, or click to browse</p>
            <p style={styles.dropSubText}>
              Supports: PDF (scanned or digital), Excel, CSV, XML/EDI, Word (.docx)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: '#fff',
    borderRadius: 12,
    padding: 32,
    boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
    maxWidth: 640,
    margin: '0 auto',
  },
  title: { color: '#1a237e', marginTop: 0, marginBottom: 24 },
  formRow: { marginBottom: 16 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, color: '#444', marginBottom: 6 },
  input: {
    width: '100%', padding: '10px 12px', fontSize: 14,
    border: '1px solid #ddd', borderRadius: 6, outline: 'none',
  },
  select: {
    width: '100%', padding: '10px 12px', fontSize: 14,
    border: '1px solid #ddd', borderRadius: 6, background: '#fff',
  },
  checkRow: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 },
  checkLabel: { fontSize: 13, color: '#444', cursor: 'pointer' },
  dropzone: {
    border: '2px dashed #9fa8da',
    borderRadius: 10,
    padding: 40,
    textAlign: 'center',
    cursor: 'pointer',
    background: '#f8f9ff',
    transition: 'all 0.2s',
  },
  dropzoneActive: { borderColor: '#1a237e', background: '#e8eaf6' },
  dropzoneDisabled: { opacity: 0.6, cursor: 'not-allowed' },
  uploadIcon: { fontSize: 48, marginBottom: 8 },
  dropText: { fontSize: 15, color: '#333', margin: '8px 0' },
  dropSubText: { fontSize: 12, color: '#888', margin: 0 },
  spinner: {
    width: 32, height: 32, border: '3px solid #e8eaf6',
    borderTop: '3px solid #1a237e', borderRadius: '50%',
    animation: 'spin 1s linear infinite', margin: '0 auto 12px',
  },
};
