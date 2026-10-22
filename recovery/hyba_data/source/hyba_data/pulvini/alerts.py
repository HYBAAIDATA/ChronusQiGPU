"""
Enterprise Alerting - Slack/Discord notifications
"""

import os
from typing import Dict

import aiohttp


class AlertManager:
    """
    Enterprise alerting for critical drift events
    Supports Slack and Discord webhooks
    """

    def __init__(self, slack_webhook: str = None, discord_webhook: str = None):
        self.slack_webhook = slack_webhook or os.getenv("SLACK_WEBHOOK_URL")
        self.discord_webhook = discord_webhook or os.getenv("DISCORD_WEBHOOK_URL")

    async def critical_drift_alert(self, assessment: Dict):
        """
        Send CRITICAL drift alerts to configured endpoints

        Args:
            assessment: Assessment dictionary with drift details
        """
        if not (self.slack_webhook or self.discord_webhook):
            return

        # Format message
        circuit_status = "🔒 OPEN" if assessment.get("circuit_open") else "✅ CLOSED"
        message_text = (
            f"🚨 *PULVINI φ²⁰ CRITICAL DRIFT*\n"
            f"H_eff: `{assessment.get('h_eff_x', 0):.1f}x`\n"
            f"Ratio: `{assessment.get('ratio', 0):.2f}`\n"
            f"Circuit: {circuit_status}\n"
            f"Action: `{assessment.get('action', 'UNKNOWN')}`\n"
            f"θ: `{assessment.get('theta', 0):.0f}`\n"
            f"Drift Count: `{assessment.get('drift_count', 0)}`"
        )

        # Send to Slack
        if self.slack_webhook:
            await self._send_slack_alert(message_text)

        # Send to Discord
        if self.discord_webhook:
            await self._send_discord_alert(message_text)

    async def _send_slack_alert(self, message: str):
        """Send alert to Slack webhook"""
        payload = {"text": message, "username": "φ²⁰ Oracle", "icon_emoji": ":warning:"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook, json=payload) as response:
                    if response.status != 200:
                        print(f"Failed to send Slack alert: {response.status}")
        except Exception as e:
            print(f"Error sending Slack alert: {e}")

    async def _send_discord_alert(self, message: str):
        """Send alert to Discord webhook"""
        payload = {"content": message, "username": "φ²⁰ Oracle"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord_webhook, json=payload) as response:
                    if response.status != 200:
                        print(f"Failed to send Discord alert: {response.status}")
        except Exception as e:
            print(f"Error sending Discord alert: {e}")

    async def incident_alert(self, incident_id: str, assessment: Dict):
        """
        Send incident creation alert

        Args:
            incident_id: Incident identifier
            assessment: Assessment dictionary
        """
        if not (self.slack_webhook or self.discord_webhook):
            return

        message_text = (
            f"📋 *PULVINI φ²⁰ INCIDENT CREATED*\n"
            f"Incident ID: `{incident_id}`\n"
            f"H_eff: `{assessment.get('h_eff_x', 0):.1f}x`\n"
            f"θ: `{assessment.get('theta', 0):.0f}`\n"
            f"Status: `{assessment.get('status', 'UNKNOWN')}`"
        )

        if self.slack_webhook:
            await self._send_slack_alert(message_text)
        if self.discord_webhook:
            await self._send_discord_alert(message_text)

    async def recovery_alert(self, incident_id: str, assessment: Dict):
        """
        Send incident recovery alert

        Args:
            incident_id: Incident identifier
            assessment: Assessment dictionary
        """
        if not (self.slack_webhook or self.discord_webhook):
            return

        message_text = (
            f"✅ *PULVINI φ²⁰ INCIDENT RESOLVED*\n"
            f"Incident ID: `{incident_id}`\n"
            f"H_eff: `{assessment.get('h_eff_x', 0):.1f}x`\n"
            f"Ratio: `{assessment.get('ratio', 0):.2f}`\n"
            f"Status: STABLE"
        )

        if self.slack_webhook:
            await self._send_slack_alert(message_text)
        if self.discord_webhook:
            await self._send_discord_alert(message_text)

    async def circuit_open_alert(self, assessment: Dict):
        """
        Send circuit breaker open alert

        Args:
            assessment: Assessment dictionary
        """
        if not (self.slack_webhook or self.discord_webhook):
            return

        message_text = (
            f"🔒 *PULVINI φ²⁰ CIRCUIT BREAKER OPEN*\n"
            f"H_eff: `{assessment.get('h_eff_x', 0):.1f}x`\n"
            f"Drift Count: `{assessment.get('drift_count', 0)}`\n"
            f"⚠️ MANUAL INTERVENTION REQUIRED"
        )

        if self.slack_webhook:
            await self._send_slack_alert(message_text)
        if self.discord_webhook:
            await self._send_discord_alert(message_text)
