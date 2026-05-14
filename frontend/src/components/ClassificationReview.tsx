import React, { useState } from 'react';
import { ManifestItem } from '../api/client';

interface Override {
  item_id: number;
  hs_code: string;
  note: string;
}

interface Props {
  items: ManifestItem[];
  onOverridesChange: (overrides: Override[]) => void;
}

function confidenceColor(c: number | null): string {
  if (c == null) return '#9e9e9e';
  if (c >= 0.9) return '#2e7d32';
  if (c >= 0.85) return '#f57f17';
  return '#c62828';
}

function confidenceLabel(c: number | null): string {
  if (c == null) return 'N/A';
  return `${Math.round(c * 100)}%`;
}

export default function ClassificationReview({ items, onOverridesChange }: Props) {
  const [overrides, setOverrides] = useState<Record<number, { hs_code: string; note: string }>>({});
  const [expanded, setExpanded] = useState<number | null>(null);

  const updateOverride = (itemId: number, field: 'hs_code' | 'note', value: string) => {
    const updated = {
      ...overrides,
      [itemId]: { ...(overrides[itemId] || { hs_code: '', note: '' }), [field]: value },
    };
    setOverrides(updated);
    onOverridesChange(
      Object.entries(updated)
        .filter(([, v]) => v.hs_code)
        .map(([id, v]) => ({ item_id: Number(id), hs_code: v.hs_code, note: v.note }))
    );
  };

  const flaggedItems = items.filter(i => i.needs_manual_review);
  const okItems = items.filter(i => !i.needs_manual_review);

  return (
    <div style={styles.wrap}>
      <h3 style={styles.title}>
        Line Item Classification
        {flaggedItems.length > 0 && (
          <span style={styles.flagBadge}>{flaggedItems.length} need review</span>
        )}
      </h3>

      {flaggedItems.length > 0 && (
        <div style={styles.flagBanner}>
          <strong>Items below require review</strong> — confidence below 85% or ambiguous classification.
          You can override the HS code before approving.
        </div>
      )}

      <table style={styles.table}>
        <thead>
          <tr style={styles.theadRow}>
            <th style={styles.th}>#</th>
            <th style={styles.th}>Description</th>
            <th style={styles.th}>ITC-HS Code</th>
            <th style={styles.th}>Confidence</th>
            <th style={styles.th}>Duty (INR)</th>
            <th style={styles.th}>Override</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => {
            const override = overrides[item.id];
            const isExpanded = expanded === item.id;
            return (
              <React.Fragment key={item.id}>
                <tr
                  style={{
                    ...styles.row,
                    ...(item.needs_manual_review ? styles.flaggedRow : {}),
                    cursor: 'pointer',
                  }}
                  onClick={() => setExpanded(isExpanded ? null : item.id)}
                >
                  <td style={styles.td}>{item.line_number}</td>
                  <td style={styles.td}>
                    <div style={styles.descCell}>
                      {item.needs_manual_review && <span style={styles.flagIcon}>⚠</span>}
                      <span>{item.description}</span>
                    </div>
                  </td>
                  <td style={styles.td}>
                    <code style={styles.hsCode}>
                      {override?.hs_code || item.overridden_hs_code || item.itc_hs_code || '—'}
                    </code>
                    {(override?.hs_code || item.overridden_hs_code) && (
                      <span style={styles.overriddenBadge}>overridden</span>
                    )}
                  </td>
                  <td style={styles.td}>
                    <span style={{ color: confidenceColor(item.classification_confidence), fontWeight: 600 }}>
                      {confidenceLabel(item.classification_confidence)}
                    </span>
                  </td>
                  <td style={styles.td}>
                    {item.total_duty_inr != null
                      ? `₹ ${item.total_duty_inr.toLocaleString('en-IN')}`
                      : '—'}
                  </td>
                  <td style={styles.td} onClick={e => e.stopPropagation()}>
                    <input
                      type="text"
                      placeholder="Enter HS code"
                      value={override?.hs_code || ''}
                      onChange={e => updateOverride(item.id, 'hs_code', e.target.value)}
                      style={styles.overrideInput}
                      maxLength={10}
                    />
                  </td>
                </tr>
                {isExpanded && (
                  <tr style={styles.expandedRow}>
                    <td colSpan={6} style={styles.expandedCell}>
                      <div style={styles.expandedContent}>
                        <div style={styles.expandedGrid}>
                          <div>
                            <strong>HS Description:</strong> {item.hs_description || '—'}
                          </div>
                          <div>
                            <strong>Reasoning:</strong> {item.classification_reasoning || '—'}
                          </div>
                          <div>
                            <strong>Country of Origin:</strong> {item.country_of_origin || '—'}
                          </div>
                          <div>
                            <strong>FTA Applied:</strong> {item.fta_applied ? `Yes (BCD ${item.fta_bcd_rate}%)` : 'No'}
                          </div>
                          <div>
                            <strong>BCD:</strong> {item.bcd_rate}% = ₹{item.bcd_amount?.toLocaleString('en-IN')}
                          </div>
                          <div>
                            <strong>IGST:</strong> {item.igst_rate}% = ₹{item.igst_amount?.toLocaleString('en-IN')}
                          </div>
                        </div>
                        {overrides[item.id]?.hs_code && (
                          <div style={{ marginTop: 8 }}>
                            <label style={{ fontSize: 12, fontWeight: 600 }}>Override reason:</label>
                            <input
                              type="text"
                              placeholder="Reason for HS code change"
                              value={overrides[item.id]?.note || ''}
                              onChange={e => updateOverride(item.id, 'note', e.target.value)}
                              style={{ ...styles.overrideInput, width: '100%', marginTop: 4 }}
                            />
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 8px rgba(0,0,0,0.07)', marginBottom: 24 },
  title: { color: '#1a237e', marginTop: 0, marginBottom: 16, fontSize: 16, display: 'flex', alignItems: 'center', gap: 12 },
  flagBadge: { background: '#fff3e0', color: '#e65100', padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600 },
  flagBanner: { background: '#fff3e0', borderLeft: '4px solid #ff9800', padding: '10px 16px', marginBottom: 16, borderRadius: 4, fontSize: 13 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  theadRow: { background: '#f5f5f5' },
  th: { padding: '10px 12px', textAlign: 'left', borderBottom: '2px solid #e0e0e0', fontWeight: 600, color: '#555' },
  row: { borderBottom: '1px solid #f0f0f0' },
  flaggedRow: { background: '#fffde7' },
  td: { padding: '10px 12px', verticalAlign: 'middle' },
  descCell: { display: 'flex', alignItems: 'center', gap: 6 },
  flagIcon: { color: '#ff9800', fontSize: 14 },
  hsCode: { background: '#f5f5f5', padding: '2px 6px', borderRadius: 4, fontSize: 12 },
  overriddenBadge: { background: '#e3f2fd', color: '#1565c0', padding: '1px 6px', borderRadius: 10, fontSize: 10, marginLeft: 6 },
  overrideInput: { padding: '6px 8px', fontSize: 12, border: '1px solid #ddd', borderRadius: 4, width: 120 },
  expandedRow: { background: '#fafafa' },
  expandedCell: { padding: 0 },
  expandedContent: { padding: '12px 16px', borderTop: '1px solid #f0f0f0' },
  expandedGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13, color: '#444' },
};
