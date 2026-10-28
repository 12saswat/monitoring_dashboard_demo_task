import uuid
import time
import json
import logging
from typing import Dict, Any, Optional
import httpx
from datetime import datetime, timezone

from app.core.config import settings
from app.database.session import SessionLocal
from app.database.models import AlertLog

logger = logging.getLogger("api.alerting")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class AlertService:
    """
    Manages incident detection, de-duplication, persistence in SQLite,
    and multi-channel notifications (Slack, Email, Pager/Call).
    """
    
    # Cooldown memory to prevent alert flooding: {dedup_key: last_triggered_epoch}
    _cooldown_cache: Dict[str, float] = {}
    COOLDOWN_SECONDS = 15.0

    @classmethod
    def trigger_alert(
        cls,
        rule_name: str,
        severity: str,
        title: str,
        description: str,
        rca: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates deduplication, logs alert in SQLite, and dispatches to notification channels.
        """
        dedup_key = f"{rule_name}:{title}"
        now_epoch = time.time()
        
        # Check cooldown
        last_time = cls._cooldown_cache.get(dedup_key, 0)
        if (now_epoch - last_time) < cls.COOLDOWN_SECONDS:
            logger.info("Alert '%s' suppressed by cooldown (active within last %ss)", title, cls.COOLDOWN_SECONDS)
            return None

        cls._cooldown_cache[dedup_key] = now_epoch
        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        
        # Build notification payload previews
        slack_blocks = cls._build_slack_payload(alert_id, rule_name, severity, title, description, rca)
        email_body = cls._build_email_html(alert_id, rule_name, severity, title, description, rca)
        
        preview_data = {
            "slack_payload": slack_blocks,
            "email_preview": {
                "to": settings.email_recipient,
                "from": settings.email_sender,
                "subject": f"[{severity}] API Alert: {title}",
                "body_html": email_body
            },
            "call_alert_simulated": severity == "CRITICAL" and not bool(settings.call_webhook_url),
            "call_alert_live": severity == "CRITICAL" and bool(settings.call_webhook_url)
        }
        
        # Determine active channels
        channel_list = []
        if settings.email_smtp_host:
            channel_list.append("Email (Live SMTP)")
        else:
            channel_list.append("Email (simulated)")

        if settings.slack_webhook_url:
            channel_list.append("Slack (Live Webhook)")
        else:
            channel_list.append("Slack (simulated)")

        if severity == "CRITICAL":
            if settings.call_webhook_url:
                channel_list.append("Call (Live Webhook)")
            else:
                channel_list.append("Call (simulated pager)")
            
        channels = ", ".join(channel_list)

        db = SessionLocal()
        try:
            alert_entry = AlertLog(
                alert_id=alert_id,
                rule_name=rule_name,
                severity=severity,
                title=title,
                description=description,
                rca_summary=rca.get("summary", ""),
                rca_recommendation=rca.get("recommendation", ""),
                channels_notified=channels,
                notification_preview=json.dumps(preview_data),
                status="ACTIVE",
                created_at=datetime.now(timezone.utc)
            )
            db.add(alert_entry)
            db.commit()
            db.refresh(alert_entry)
        except Exception as e:
            logger.error("Failed to persist alert in SQLite: %s", e)
            db.rollback()
        finally:
            db.close()

        # Dispatch async to channels
        cls._dispatch_notifications(alert_id, severity, title, slack_blocks, email_body)

        return {
            "alert_id": alert_id,
            "rule_name": rule_name,
            "severity": severity,
            "title": title,
            "description": description,
            "rca": rca,
            "channels": channels
        }

    @classmethod
    def _build_slack_payload(
        cls,
        alert_id: str,
        rule_name: str,
        severity: str,
        title: str,
        description: str,
        rca: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Constructs a Slack Block Kit formatted message payload."""
        color = "#e02424" if severity == "CRITICAL" else "#d97706" if severity == "WARNING" else "#2563eb"
        
        return {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": f"🚨 [{severity}] {title}"}
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
                                {"type": "mrkdwn", "text": f"*Rule:*\n`{rule_name}`"},
                                {"type": "mrkdwn", "text": f"*Triggered At:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"},
                                {"type": "mrkdwn", "text": f"*Severity:*\n*{severity}*"}
                            ]
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Root Cause Analysis:*\n{rca.get('summary', '')}"}
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Action Items:*\n```{rca.get('recommendation', '')}```"}
                        }
                    ]
                }
            ]
        }

    @classmethod
    def _build_email_html(
        cls,
        alert_id: str,
        rule_name: str,
        severity: str,
        title: str,
        description: str,
        rca: Dict[str, Any]
    ) -> str:
        """Constructs a responsive HTML email alert body."""
        badge_bg = "#dc2626" if severity == "CRITICAL" else "#f59e0b" if severity == "WARNING" else "#3b82f6"
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #0f172a; padding: 20px; color: white;">
                <span style="background-color: {badge_bg}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase;">{severity}</span>
                <h2 style="margin: 12px 0 0 0; font-size: 18px;">{title}</h2>
            </div>
            <div style="padding: 20px; background-color: #ffffff; color: #334155; line-height: 1.5;">
                <p><strong>Alert ID:</strong> <code>{alert_id}</code></p>
                <p><strong>Rule Violated:</strong> <code>{rule_name}</code></p>
                <p><strong>Description:</strong> {description}</p>
                
                <div style="background-color: #f8fafc; border-left: 4px solid {badge_bg}; padding: 12px; margin: 16px 0; border-radius: 0 4px 4px 0;">
                    <h4 style="margin: 0 0 8px 0; color: #0f172a;">Root Cause Analysis</h4>
                    <p style="margin: 0 0 8px 0; font-size: 14px;">{rca.get('summary', '')}</p>
                    <h4 style="margin: 12px 0 4px 0; color: #0f172a;">Recommended Remediation</h4>
                    <pre style="background: #e2e8f0; padding: 8px; border-radius: 4px; font-size: 12px; white-space: pre-wrap;">{rca.get('recommendation', '')}</pre>
                </div>
                
                <p style="font-size: 12px; color: #64748b; margin-top: 24px;">FastAPI Monitoring Sentinel &bull; SQLite Telemetry Store &bull; Automated RCA</p>
            </div>
        </div>
        """

    @classmethod
    def _dispatch_notifications(
        cls,
        alert_id: str,
        severity: str,
        title: str,
        slack_payload: Dict[str, Any],
        email_body: str
    ):
        """Sends live notifications if credentials configured, otherwise logs."""
        logger.warning("🔔 ALERT TRIGGERED [%s] %s (ID: %s)", severity, title, alert_id)
        
        # 1. Slack Webhook live call if configured
        if settings.slack_webhook_url:
            if not settings.slack_webhook_url.startswith("https://hooks.slack.com/"):
                logger.error(
                    "⚠️ SLACK URL ERROR: The provided SLACK_WEBHOOK_URL '%s' appears to be an invite link, not an incoming webhook URL! "
                    "Slack Incoming Webhooks must start with 'https://hooks.slack.com/services/...'.",
                    settings.slack_webhook_url
                )
            else:
                try:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.post(settings.slack_webhook_url, json=slack_payload)
                        if resp.status_code == 200:
                            logger.info("✅ Slack message successfully delivered! Status: 200")
                        else:
                            logger.warning("⚠️ Slack webhook responded with HTTP %s: %s", resp.status_code, resp.text)
                except Exception as ex:
                    logger.error("Failed to post to live Slack webhook: %s", ex)
        else:
            logger.info("Slack Webhook: [SIMULATED] -> Payload ready for webhook dispatch.")

        # 2. Live Email dispatch via SMTP
        sender = (settings.email_sender or "").strip().strip('"').strip("'")
        recipient_str = (settings.email_recipient or "").strip().strip('"').strip("'")
        recipient_list = [r.strip() for r in recipient_str.split(",") if r.strip()]
        if not recipient_list and sender:
            recipient_list = [sender]
        pwd = (settings.email_password or "").replace(" ", "").strip().strip('"').strip("'")
        host = (settings.email_smtp_host or "").strip().strip('"').strip("'")

        if host and sender and recipient_list:
            try:
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText

                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"[{severity}] API Alert: {title} ({alert_id})"
                msg["From"] = sender
                msg["To"] = ", ".join(recipient_list)

                html_part = MIMEText(email_body, "html")
                msg.attach(html_part)

                port = settings.email_smtp_port
                
                # Gmail works most reliably with SSL on port 465
                if "gmail" in host.lower() or port == 465:
                    server = smtplib.SMTP_SSL(host, 465, timeout=10.0)
                else:
                    server = smtplib.SMTP(host, port, timeout=10.0)
                    server.ehlo()
                    server.starttls()
                    server.ehlo()

                with server:
                    if pwd:
                        server.login(sender, pwd)
                    server.sendmail(sender, recipient_list, msg.as_string())
                
                logger.info("📧 Email Alert successfully delivered via SMTP to %s", ", ".join(recipient_list))
            except Exception as e:
                logger.error(
                    "❌ Failed to send live email via SMTP to %s: %s", 
                    ", ".join(recipient_list),
                    e
                )
        else:
            logger.info("Email Dispatch: [SIMULATED] -> Sent to %s: '%s'", recipient_str or 'admin', title)

        # 3. Phone / Call alert for CRITICAL (live webhook or simulated pager)
        if severity == "CRITICAL":
            call_payload = {
                "alert_id": alert_id,
                "severity": severity,
                "title": title,
                "message": f"Paging on-call engineer for {alert_id}: {title}",
            }
            preview_call = True
            if settings.call_webhook_url:
                try:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.post(settings.call_webhook_url, json=call_payload)
                        if resp.status_code < 300:
                            logger.critical("📞 PHONE ALERT delivered via CALL_WEBHOOK_URL for %s", alert_id)
                            preview_call = False
                        else:
                            logger.warning("Call webhook HTTP %s: %s", resp.status_code, resp.text)
                except Exception as ex:
                    logger.error("Failed to post call webhook: %s", ex)
            if preview_call:
                logger.critical(
                    "📞 PHONE ALERT: [SIMULATED ESCALATION CALL] Paging on-call engineer for Alert %s!",
                    alert_id
                )
