"""
Command Handlers for Slack Bot
Handles /recon-analyze command and related functionality.
"""

import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from src.services.recon_client import ReconClient
from src.analysis.report_parser import ReportParser
from src.analysis.recon_status_analyzer import ReconStatusAnalyzer
from src.analysis.gap_analyzer import GapAnalyzer
from src.analysis.rule_analyzer import RuleAnalyzer
from src.services.slack_service import SlackService
from src.utils.logging import logger


class CommandHandler:
    """
    Handler for Slack slash commands.
    """

    def __init__(self):
        """Initialize command handler."""
        self.recon_client = ReconClient()
        self.report_parser = ReportParser()
        self.recon_status_analyzer = ReconStatusAnalyzer()
        self.gap_analyzer = GapAnalyzer()
        self.rule_analyzer = RuleAnalyzer()
        self.slack_service = SlackService()

    def handle_recon_analyze(
        self, command_text: str, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """
        Handle /recon-analyze command.

        Args:
            command_text: Command text (e.g., "workspace=XXX report_url=...")
            user_id: Slack user ID
            channel_id: Slack channel ID

        Returns:
            Dict containing Slack response
        """
        try:
            logger.info(
                "Handling /recon-analyze command",
                command_text=command_text,
                user_id=user_id,
                channel_id=channel_id,
            )

            # Parse command
            parsed = self._parse_command(command_text)
            workspace_name = parsed.get("workspace")
            report_url = parsed.get("report_url")
            report_file = parsed.get("report_file")

            if not workspace_name:
                return self.slack_service.format_simple_message(
                    "Error: workspace name is required. Usage: /recon-analyze workspace=WORKSPACE_NAME [report_url=URL]"
                )

            # Get workspace
            workspace_result = self.recon_client.get_workspace_by_name(workspace_name)
            if not workspace_result["success"]:
                return self.slack_service.format_simple_message(
                    f"Error: {workspace_result.get('error', 'Failed to find workspace')}"
                )

            workspace_id = workspace_result.get("workspace_id")
            if not workspace_id:
                return self.slack_service.format_simple_message(
                    f"Error: Workspace '{workspace_name}' found but no ID available"
                )

            # Parse report if provided
            report_data = None
            if report_url or report_file:
                report_result = self.report_parser.parse_report(
                    file_path=report_file, url=report_url
                )
                if report_result["success"]:
                    report_data = report_result.get("records", [])

            # Run analyses
            logger.info("Running analyses", workspace_id=workspace_id)

            # Scenario A: recon_at not updated
            scenario_a = self.recon_status_analyzer.analyze_recon_at_missing(
                workspace_id=workspace_id
            )

            # Scenario B: Missing internal data
            scenario_b = self.gap_analyzer.analyze_missing_internal_data(
                workspace_id=workspace_id
            )

            # Scenario C: Rule matching failures
            scenario_c = self.rule_analyzer.analyze_rule_failures(
                workspace_id=workspace_id, unreconciled_records=None
            )

            # Format results
            analysis_results = {
                "workspace_name": workspace_name,
                "workspace_id": workspace_id,
                "scenario_a": scenario_a,
                "scenario_b": scenario_b,
                "scenario_c": scenario_c,
                "timestamp": datetime.now().isoformat(),
            }

            blocks = self.slack_service.format_analysis_report(analysis_results)

            return {
                "response_type": "in_channel",
                "blocks": blocks,
            }

        except Exception as e:
            logger.error(
                "Failed to handle /recon-analyze command",
                error=str(e),
                command_text=command_text,
            )
            return self.slack_service.format_simple_message(
                f"Error: Failed to analyze. {str(e)}"
            )

    def _parse_command(self, command_text: str) -> Dict[str, Any]:
        """
        Parse command text into parameters.

        Args:
            command_text: Command text

        Returns:
            Dict containing parsed parameters
        """
        parsed = {}

        # Parse workspace=XXX
        workspace_match = re.search(r"workspace=(\S+)", command_text)
        if workspace_match:
            parsed["workspace"] = workspace_match.group(1)

        # Parse report_url=XXX
        report_url_match = re.search(r"report_url=(\S+)", command_text)
        if report_url_match:
            parsed["report_url"] = report_url_match.group(1)

        # Parse report_file=XXX (for file attachments)
        report_file_match = re.search(r"report_file=(\S+)", command_text)
        if report_file_match:
            parsed["report_file"] = report_file_match.group(1)

        return parsed

