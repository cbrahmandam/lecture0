import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api/v1',
});

export interface ManifestListItem {
  id: number;
  reference_number: string;
  file_name: string | null;
  status: string;
  shipper_country: string | null;
  total_duty: number | null;
  total_cif_value: number | null;
  created_at: string;
  approved_at: string | null;
}

export interface ManifestItem {
  id: number;
  line_number: number | null;
  description: string;
  quantity: number | null;
  unit: string | null;
  total_value: number | null;
  currency: string | null;
  country_of_origin: string | null;
  itc_hs_code: string | null;
  hs_description: string | null;
  classification_confidence: number | null;
  classification_reasoning: string | null;
  needs_manual_review: boolean;
  assessable_value_inr: number | null;
  bcd_rate: number | null;
  bcd_amount: number | null;
  sws_amount: number | null;
  igst_rate: number | null;
  igst_amount: number | null;
  total_duty_inr: number | null;
  fta_applied: boolean;
  fta_bcd_rate: number | null;
  overridden_hs_code: string | null;
  override_note: string | null;
}

export interface Manifest {
  id: number;
  reference_number: string;
  file_name: string | null;
  status: string;
  shipment_mode: string | null;
  shipper_name: string | null;
  shipper_country: string | null;
  consignee_name: string | null;
  port_of_loading: string | null;
  port_of_discharge: string | null;
  bill_of_lading_number: string | null;
  incoterms: string | null;
  currency: string | null;
  total_cif_value: number | null;
  country_of_origin: string | null;
  fta_applicable: boolean;
  fta_name: string | null;
  coo_available: boolean;
  total_assessable_value: number | null;
  total_bcd: number | null;
  total_sws: number | null;
  total_igst: number | null;
  total_duty: number | null;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  icegate_be_number: string | null;
  icegate_filed_at: string | null;
  created_at: string;
  items: ManifestItem[];
}

export const manifestsApi = {
  list: (status?: string) =>
    api.get<ManifestListItem[]>('/manifests', { params: { status } }),

  get: (id: number) =>
    api.get<Manifest>(`/manifests/${id}`),

  upload: (formData: FormData) =>
    api.post('/manifests', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  approve: (id: number, approvedBy: string, overrides?: Array<{item_id: number; hs_code: string; note?: string}>) =>
    api.post(`/manifests/${id}/approve`, {
      approved_by: approvedBy,
      item_overrides: overrides,
    }),

  reject: (id: number, rejectedBy: string, reason: string) =>
    api.post(`/manifests/${id}/reject`, { rejected_by: rejectedBy, reason }),

  reprocess: (id: number) =>
    api.post(`/manifests/${id}/reprocess`),

  downloadIceGateXml: (id: number) => {
    window.open(`/api/v1/manifests/${id}/icegate-xml`, '_blank');
  },
};

export default api;
