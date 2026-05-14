import React from 'react';
import { Manifest } from '../api/client';

interface Props {
  manifest: Manifest;
}

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '—';
  return v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export default function DutyBreakdown({ manifest }: Props) {
  const rows = [
    { label: 'Total CIF Value', value: `USD ${fmt(manifest.total_cif_value)}`, highlight: false },
    { label: 'Assessable Value (CIF + 1% landing)', value: `₹ ${fmt(manifest.total_assessable_value)}`, highlight: false },
    { label: 'Basic Customs Duty (BCD)', value: `₹ ${fmt(manifest.total_bcd)}`, highlight: false },
    { label: 'Social Welfare Surcharge (SWS) @ 10% of BCD', value: `₹ ${fmt(manifest.total_sws)}`, highlight: false },
    { label: 'IGST', value: `₹ ${fmt(manifest.total_igst)}`, highlight: false },
    { label: 'Total Duty Payable', value: `₹ ${fmt(manifest.total_duty)}`, highlight: true },
  ];

  return (
    <div style={styles.card}>
      <h3 style={styles.title}>Duty Summary</h3>

      {manifest.fta_applicable && (
        <div style={styles.ftaBanner}>
          <strong>FTA Applicable:</strong> {manifest.fta_name}{' '}
          {manifest.coo_available
            ? '✓ Certificate of Origin available — preferential rates applied'
            : '⚠ Certificate of Origin not marked — MFN rates used. Provide COO to claim FTA benefit.'}
        </div>
      )}

      <table style={styles.table}>
        <tbody>
          {rows.map(row => (
            <tr key={row.label} style={row.highlight ? styles.highlightRow : {}}>
              <td style={styles.labelCell}>{row.label}</td>
              <td style={{ ...styles.valueCell, ...(row.highlight ? styles.highlightValue : {}) }}>
                {row.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={styles.meta}>
        <span>Exchange rate: USD 1 = INR {manifest.items[0]?.assessable_value_inr && manifest.items[0]?.total_value
          ? (manifest.items[0].assessable_value_inr / manifest.items[0].total_value / 1.01).toFixed(2)
          : '83.50'}</span>
        <span style={{ marginLeft: 24 }}>
          Incoterms: <strong>{manifest.incoterms || 'CIF'}</strong>
        </span>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: '#fff',
    borderRadius: 10,
    padding: 24,
    boxShadow: '0 1px 8px rgba(0,0,0,0.07)',
    marginBottom: 24,
  },
  title: { color: '#1a237e', marginTop: 0, marginBottom: 16, fontSize: 16 },
  ftaBanner: {
    background: '#e3f2fd',
    borderLeft: '4px solid #1565c0',
    padding: '10px 16px',
    marginBottom: 16,
    borderRadius: 4,
    fontSize: 13,
  },
  table: { width: '100%', borderCollapse: 'collapse' },
  labelCell: {
    padding: '10px 12px', borderBottom: '1px solid #f0f0f0',
    fontSize: 13, color: '#555',
  },
  valueCell: {
    padding: '10px 12px', borderBottom: '1px solid #f0f0f0',
    fontSize: 13, textAlign: 'right', fontWeight: 500,
  },
  highlightRow: { background: '#e8f5e9' },
  highlightValue: { fontSize: 17, fontWeight: 700, color: '#2e7d32' },
  meta: { marginTop: 12, fontSize: 12, color: '#888' },
};
