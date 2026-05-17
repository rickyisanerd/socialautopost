"""Email notifications for completed post cycles via Resend HTTP API."""
import logging
import base64
from pathlib import Path
import httpx
from app.core.config import settings

log = logging.getLogger("socialautopost")

RESEND_API_URL = "https://api.resend.com/emails"



def send_post_notification(
    business_name: str,
    post_type: str,
    content_text: str,
    image_path: str | None,
    deliveries: list[dict],
):
    """Send an email summarizing a completed post cycle.

    deliveries: list of {"platform": str, "status": str, "error": str | None}
    """
    if not settings.resend_api_key or not settings.notification_email:
        log.debug("Resend not configured — skipping email notification")
        return

    all_delivered = all(d["status"] == "delivered" for d in deliveries)
    any_failed = any(d["status"] == "failed" for d in deliveries)

    # Build platform results table rows
    rows = ""
    for d in deliveries:
        color = "#2ea043" if d["status"] == "delivered" else "#da3633"
        icon = "✅" if d["status"] == "delivered" else "❌"
        error_note = f' — {d["error"]}' if d.get("error") else ""
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #30363d;">{d['platform'].title()}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #30363d;color:{color};">{icon} {d['status'].title()}{error_note}</td>
        </tr>"""

    status_label = "All Platforms Delivered" if all_delivered else "Partial Failure" if any_failed else "Completed"
    status_color = "#2ea043" if all_delivered else "#da3633"

    # Inline the generated image if available (as base64 data URI)
    image_html = ""
    if image_path:
        p = Path(image_path)
        if p.exists():
            suffix = p.suffix.lower().lstrip(".")
            if suffix in ("png", "jpg", "jpeg", "gif"):
                try:
                    if p.stat().st_size < 5_000_000:
                        b64 = base64.b64encode(p.read_bytes()).decode()
                        mime = "jpeg" if suffix == "jpg" else suffix
                        image_html = f"""
                        <div style="margin:20px 0;text-align:center;">
                          <p style="color:#8b949e;font-size:13px;margin-bottom:8px;">Generated Ad:</p>
                          <img src="data:image/{mime};base64,{b64}" style="max-width:500px;width:100%;border-radius:8px;border:1px solid #30363d;" />
                        </div>"""
                except Exception as e:
                    log.warning(f"Could not embed image in email: {e}")
            elif suffix in ("mp4", "mov"):
                image_html = f"""
                <div style="margin:20px 0;text-align:center;">
                  <p style="color:#8b949e;font-size:13px;">Video reel generated ({p.name}) — see platforms for preview.</p>
                </div>"""

    # Escape the post text for HTML
    safe_text = content_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

    subject = f"{'✅' if all_delivered else '⚠️'} {business_name} — {post_type.title()} Post {status_label}"

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;background:#0f1117;color:#e1e4e8;border-radius:12px;overflow:hidden;">
      <div style="background:#161b22;padding:20px 24px;border-bottom:2px solid {status_color};">
        <h1 style="margin:0;font-size:20px;color:#58a6ff;">SocialAutoPost</h1>
        <p style="margin:6px 0 0;font-size:14px;color:#8b949e;">Post cycle notification</p>
      </div>

      <div style="padding:24px;">
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px;">
          <h2 style="margin:0 0 4px;font-size:18px;color:#c9d1d9;">{business_name}</h2>
          <span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;background:{status_color};color:#fff;">{status_label}</span>
          <span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;background:#30363d;color:#c9d1d9;margin-left:6px;">{post_type.title()} Post</span>
        </div>

        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px;">
          <h3 style="margin:0 0 8px;font-size:14px;color:#8b949e;">Post Content</h3>
          <p style="margin:0;font-size:14px;line-height:1.5;color:#c9d1d9;">{safe_text}</p>
        </div>

        {image_html}

        <table style="width:100%;border-collapse:collapse;background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden;">
          <tr style="background:#0d1117;">
            <th style="padding:10px 12px;text-align:left;font-size:13px;color:#8b949e;">Platform</th>
            <th style="padding:10px 12px;text-align:left;font-size:13px;color:#8b949e;">Status</th>
          </tr>
          {rows}
        </table>
      </div>

      <div style="background:#161b22;padding:12px 24px;text-align:center;border-top:1px solid #30363d;">
        <p style="margin:0;font-size:12px;color:#484f58;">SocialAutoPost Automated Notification</p>
      </div>
    </div>
    """

    # Build the Resend API payload
    from_email = settings.smtp_from or "notifications@rickysautomations.com"
    payload: dict = {
        "from": from_email,
        "to": [settings.notification_email],
        "subject": subject,
        "html": html,
    }

    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(RESEND_API_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code in (200, 201):
            log.info(f"Notification email sent for {business_name} via Resend")
        else:
            log.error(f"Resend API error for {business_name}: {resp.status_code} {resp.text}")
    except Exception as e:
        log.error(f"Failed to send notification email for {business_name}: {e}")
