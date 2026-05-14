"""
Email notification service for customs manifest approval workflow.
Sends approval-request emails with duty summary and one-click approve/reject links.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


def send_approval_request(
    to_email: str,
    manifest_reference: str,
    manifest_id: int,
    approval_token: str,
    summary: dict,
    items_needing_review: int,
) -> bool:
    """Send approval request email with duty summary."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    approve_url = f"{frontend_url}/manifests/{manifest_id}/review?token={approval_token}&action=approve"
    reject_url = f"{frontend_url}/manifests/{manifest_id}/review?token={approval_token}&action=reject"
    review_url = f"{frontend_url}/manifests/{manifest_id}/review"

    total_duty = summary.get("total_duty_inr", 0)
    total_cif = summary.get("total_cif_usd", 0)
    fta_items = summary.get("fta_applied_items", 0)

    flag_html = ""
    if items_needing_review > 0:
        flag_html = f"""
        <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:16px 0;border-radius:4px;">
            <strong>⚠ {items_needing_review} item(s) flagged for manual review</strong>
            (classification confidence below 85%). Please review before approving.
        </div>"""

    fta_html = ""
    if fta_items > 0:
        fta_html = f"""
        <div style="background:#d1ecf1;border-left:4px solid #17a2b8;padding:12px;margin:8px 0;border-radius:4px;">
            <strong>ℹ {fta_items} item(s) qualify for FTA preferential duty rates.</strong>
            Ensure Certificate of Origin is available.
        </div>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#333;">
        <div style="background:#1a237e;color:white;padding:20px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:22px;">India Customs Manifest — Approval Required</h1>
            <p style="margin:4px 0 0;opacity:0.85;">Reference: {manifest_reference}</p>
        </div>

        <div style="border:1px solid #ddd;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
            <p>A manifest has been processed and classified. Please review the duty calculation below and approve or reject.</p>

            {flag_html}
            {fta_html}

            <h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:8px;">Duty Summary</h2>
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#f5f5f5;">
                    <td style="padding:10px;border:1px solid #ddd;"><strong>Total CIF Value</strong></td>
                    <td style="padding:10px;border:1px solid #ddd;">USD {total_cif:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding:10px;border:1px solid #ddd;">Assessable Value (INR)</td>
                    <td style="padding:10px;border:1px solid #ddd;">₹ {summary.get('total_assessable_value_inr', 0):,.2f}</td>
                </tr>
                <tr style="background:#f5f5f5;">
                    <td style="padding:10px;border:1px solid #ddd;">Basic Customs Duty (BCD)</td>
                    <td style="padding:10px;border:1px solid #ddd;">₹ {summary.get('total_bcd_inr', 0):,.2f}</td>
                </tr>
                <tr>
                    <td style="padding:10px;border:1px solid #ddd;">Social Welfare Surcharge (SWS)</td>
                    <td style="padding:10px;border:1px solid #ddd;">₹ {summary.get('total_sws_inr', 0):,.2f}</td>
                </tr>
                <tr style="background:#f5f5f5;">
                    <td style="padding:10px;border:1px solid #ddd;">IGST</td>
                    <td style="padding:10px;border:1px solid #ddd;">₹ {summary.get('total_igst_inr', 0):,.2f}</td>
                </tr>
                <tr style="background:#e8f5e9;">
                    <td style="padding:12px;border:1px solid #4caf50;"><strong>Total Duty Payable</strong></td>
                    <td style="padding:12px;border:1px solid #4caf50;font-size:18px;font-weight:bold;color:#2e7d32;">
                        ₹ {total_duty:,.2f}
                    </td>
                </tr>
            </table>

            <div style="margin-top:28px;text-align:center;">
                <a href="{review_url}" style="display:inline-block;background:#1565c0;color:white;padding:12px 28px;text-decoration:none;border-radius:6px;margin:0 8px;font-size:15px;">
                    Review Details
                </a>
                <a href="{approve_url}" style="display:inline-block;background:#2e7d32;color:white;padding:12px 28px;text-decoration:none;border-radius:6px;margin:0 8px;font-size:15px;">
                    ✓ Approve
                </a>
                <a href="{reject_url}" style="display:inline-block;background:#c62828;color:white;padding:12px 28px;text-decoration:none;border-radius:6px;margin:0 8px;font-size:15px;">
                    ✗ Reject
                </a>
            </div>

            <p style="font-size:12px;color:#777;margin-top:24px;">
                This is an automated notification from India Customs Manifest Processor.
                Direct approval/rejection via link does not allow HS code overrides — use "Review Details" to modify any classifications.
            </p>
        </div>
    </body>
    </html>"""

    subject = f"[ACTION REQUIRED] Customs Duty Approval — {manifest_reference} — ₹{total_duty:,.0f}"
    return _send_email(to_email, subject, html)


def send_approval_confirmation(
    to_email: str,
    manifest_reference: str,
    manifest_id: int,
    approved_by: str,
    total_duty_inr: float,
) -> bool:
    html = f"""
    <!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
        <div style="background:#2e7d32;color:white;padding:20px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;">✓ Manifest Approved</h1>
            <p style="margin:4px 0 0;opacity:0.85;">{manifest_reference}</p>
        </div>
        <div style="border:1px solid #ddd;border-top:none;padding:24px;">
            <p>Manifest <strong>{manifest_reference}</strong> has been approved by <strong>{approved_by}</strong>.</p>
            <p>Total duty approved: <strong>₹ {total_duty_inr:,.2f}</strong></p>
            <p style="color:#555;">The ICEGATE EDI file has been generated and is ready for upload/filing.</p>
        </div>
    </body></html>"""
    return _send_email(to_email, f"Approved — Manifest {manifest_reference}", html)


def send_rejection_notification(
    to_email: str,
    manifest_reference: str,
    rejected_by: str,
    reason: str,
) -> bool:
    html = f"""
    <!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
        <div style="background:#c62828;color:white;padding:20px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;">✗ Manifest Rejected</h1>
            <p style="margin:4px 0 0;opacity:0.85;">{manifest_reference}</p>
        </div>
        <div style="border:1px solid #ddd;border-top:none;padding:24px;">
            <p>Manifest <strong>{manifest_reference}</strong> was rejected by <strong>{rejected_by}</strong>.</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p>Please re-upload the manifest with corrections.</p>
        </div>
    </body></html>"""
    return _send_email(to_email, f"Rejected — Manifest {manifest_reference}", html)


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    smtp_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("MAIL_PORT", "587"))
    username = os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("MAIL_PASSWORD", "")
    from_email = os.environ.get("MAIL_FROM", username)
    from_name = os.environ.get("MAIL_FROM_NAME", "India Customs Processor")

    if not username or not password:
        logger.warning("Email credentials not configured — skipping email send")
        logger.info(f"Would have sent '{subject}' to {to_email}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(from_email, [to_email], msg.as_string())

        logger.info(f"Email sent: '{subject}' to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
