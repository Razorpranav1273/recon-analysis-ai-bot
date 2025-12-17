"""
Command Handlers for Slack Bot
Handles /recon-analyze command and related functionality.
"""

import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from src.services.recon_client import ReconClient
from src.analysis.report_parser import ReportParser
from src.analysis.unified_analyzer import UnifiedAnalyzer
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
        self.unified_analyzer = UnifiedAnalyzer()
        self.slack_service = SlackService()

    def handle_recon_analyze(
        self, command_text: str, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """
        Handle /recon-analyze command.

        Args:
            command_text: Command text (e.g., "workspace=XXX file_type=XXX unique_value=XXX [output_file=...]")
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
            file_type_name = parsed.get("file_type")
            unique_value = parsed.get("unique_value")
            output_file = parsed.get("output_file")
            report_url = parsed.get("report_url")
            date_start = parsed.get("date_start")
            date_end = parsed.get("date_end")

            if not workspace_name:
                return self.slack_service.format_simple_message(
                    "❌ Error: workspace_name is required.\n\nUsage: `workspace_name=NETBANKING_AUSF file_type=bank_payment_report unique_column_value=RrQHFDvwIQIKiH`"
                )

            if not file_type_name:
                return self.slack_service.format_simple_message(
                    "❌ Error: file_type is required.\n\nUsage: `workspace_name=NETBANKING_AUSF file_type=bank_payment_report unique_column_value=RrQHFDvwIQIKiH`"
                )

            if not unique_value:
                return self.slack_service.format_simple_message(
                    "❌ Error: unique_column_value is required.\n\nUsage: `workspace_name=NETBANKING_AUSF file_type=bank_payment_report unique_column_value=RrQHFDvwIQIKiH`"
                )

            # Get workspace - try API first, fallback to local DB
            workspace_result = self.recon_client.get_workspace_by_name(workspace_name)
            workspace_id = None
            
            if workspace_result.get("success"):
                workspace_id = workspace_result.get("workspace_id")
            else:
                # Fallback to local DB if API fails
                logger.info("API call failed, trying local DB", error=workspace_result.get("error"))
                from src.data.local_db import get_local_db
                local_db = get_local_db()
                workspace_data = local_db.query_workspace_by_name(workspace_name)
                if workspace_data:
                    workspace_id = workspace_data.get("id")
                    logger.info("Found workspace in local DB", workspace_id=workspace_id)
                else:
                    return self.slack_service.format_simple_message(
                        f"Error: Workspace '{workspace_name}' not found in API or local database"
                    )
            
            if not workspace_id:
                return self.slack_service.format_simple_message(
                    f"Error: Workspace '{workspace_name}' found but no ID available"
                )

            # No date range needed for simple analysis
            transaction_date_range = None

            # Run unified analysis
            logger.info(
                "Running unified analysis",
                workspace_id=workspace_id,
                file_type_name=file_type_name,
                unique_value=unique_value,
            )

            analysis_result = self.unified_analyzer.analyze(
                workspace_id=workspace_id,
                file_type_name=file_type_name,
                output_file_path=None,
                unique_column_value=unique_value,
                transaction_date_range=transaction_date_range,
            )

            if not analysis_result.get("success"):
                return self.slack_service.format_simple_message(
                    f"Error: {analysis_result.get('error', 'Analysis failed')}"
                )

            # Format results for Slack
            findings = analysis_result.get("findings", [])
            scenarios_detected = analysis_result.get("scenarios_detected", [])

            if not findings:
                return self.slack_service.format_simple_message(
                    f"✅ *Analysis Complete*\n\n"
                    f"Workspace: `{workspace_name}`\n"
                    f"File Type: `{file_type_name}`\n"
                    f"Unique Value: `{unique_value}`\n\n"
                    f"*Result:* No issues found. The record does not match any of the three analysis scenarios:\n"
                    f"• Scenario A: Reconciled but recon_at not updated\n"
                    f"• Scenario B: MIS data present but no matching internal data\n"
                    f"• Scenario C: Both datasets present but rules not matching\n\n"
                    f"All scenarios are working correctly for this record."
                )

            # Format findings by scenario
            scenario_a_findings = [f for f in findings if f.get("scenario") == "A"]
            scenario_b_findings = [f for f in findings if f.get("scenario") == "B"]
            scenario_c_findings = [f for f in findings if f.get("scenario") == "C"]

            # Format results
            analysis_results = {
                "workspace_name": workspace_name,
                "workspace_id": workspace_id,
                "file_type_name": file_type_name,
                "unique_column_value": unique_value,
                "scenarios_detected": scenarios_detected,
                "scenario_a": {
                    "findings": scenario_a_findings,
                    "count": len(scenario_a_findings),
                } if scenario_a_findings else None,
                "scenario_b": {
                    "findings": scenario_b_findings,
                    "count": len(scenario_b_findings),
                } if scenario_b_findings else None,
                "scenario_c": {
                    "findings": scenario_c_findings,
                    "count": len(scenario_c_findings),
                } if scenario_c_findings else None,
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
        Supports format: workspace_name=XXX file_type=XXX unique_column_value=XXX

        Args:
            command_text: Command text

        Returns:
            Dict containing parsed parameters
        """
        parsed = {}

        # Parse workspace_name=XXX or workspace=XXX
        workspace_match = re.search(r"workspace_name=(\S+)|workspace=(\S+)", command_text)
        if workspace_match:
            parsed["workspace"] = workspace_match.group(1) or workspace_match.group(2)

        # Parse file_type=XXX
        file_type_match = re.search(r"file_type\s*=\s*(\S+)", command_text)
        if file_type_match:
            parsed["file_type"] = file_type_match.group(1)

        # Parse unique_column_value=XXX or unique_value=XXX
        unique_value_match = re.search(r"unique_column_value\s*=\s*(\S+)|unique_value\s*=\s*(\S+)", command_text)
        if unique_value_match:
            parsed["unique_value"] = unique_value_match.group(1) or unique_value_match.group(2)

        return parsed

    def handle_list_workspaces(self) -> Dict[str, Any]:
        """
        Handle /recon-list-workspaces command to list all available workspaces.

        Returns:
            Dict containing Slack response with workspace list
        """
        try:
            logger.info("Handling /recon-list-workspaces command")

            # Get all workspaces - try API first, fallback to local DB
            result = self.recon_client.list_all_workspaces()
            workspaces = []

            if result.get("success"):
                workspaces = result.get("workspaces", [])
            else:
                # Fallback to local DB if API fails
                logger.info("API call failed, trying local DB", error=result.get("error"))
                from src.data.local_db import get_local_db
                local_db = get_local_db()
                cursor = local_db.conn.cursor()
                cursor.execute("SELECT id, name, merchant_id FROM workspaces WHERE deleted_at IS NULL")
                rows = cursor.fetchall()
                workspaces = [{"id": row[0], "name": row[1], "merchant_id": row[2]} for row in rows]
                logger.info("Found workspaces in local DB", count=len(workspaces))

            if not workspaces:
                return self.slack_service.format_simple_message(
                    "No workspaces found. Make sure the recon service is running and configured correctly."
                )

            # Format workspace list
            workspace_list = []
            for ws in workspaces[:20]:  # Limit to first 20
                name = ws.get("name", "N/A")
                workspace_id = ws.get("id", "N/A")
                merchant_id = ws.get("merchant_id", "N/A")
                workspace_list.append(f"• *{name}* (ID: `{workspace_id}`, Merchant: `{merchant_id}`)")

            message = f"📋 *Available Workspaces ({len(workspaces)} total):*\n\n"
            message += "\n".join(workspace_list)

            if len(workspaces) > 20:
                message += f"\n\n_... and {len(workspaces) - 20} more_"

            message += "\n\n💡 *Usage:* `/recon-analyze workspace=WORKSPACE_NAME file_type=FILE_TYPE unique_value=VALUE`"
            if workspaces:
                example_ws = workspaces[0].get('name', 'WORKSPACE_NAME')
                message += f"\n   Example: `/recon-analyze workspace={example_ws} file_type=bank_payment_report unique_value=PAYMENT_ID`"

            return self.slack_service.format_simple_message(message)

        except Exception as e:
            logger.error("Error handling /recon-list-workspaces", error=str(e))
            return self.slack_service.format_simple_message(f"Error: {str(e)}")

    def handle_mention(self, message_text: str, user_id: str, channel_id: str) -> Dict[str, Any]:
        """
        Handle app mention - simple command format.
        Format: workspace_name=XXX file_type=XXX unique_column_value=XXX
        
        Args:
            message_text: The message text (with @bot mention removed)
            user_id: Slack user ID
            channel_id: Slack channel ID
            
        Returns:
            Dict containing Slack response
        """
        try:
            logger.info(
                "Handling app mention",
                message=message_text,
                user_id=user_id,
                channel_id=channel_id,
            )
            
            # Parse the command text directly
            parsed = self._parse_command(message_text)
            
            logger.info(
                "Parsed command",
                parsed=parsed,
                has_workspace=bool(parsed.get("workspace")),
                has_file_type=bool(parsed.get("file_type")),
                has_unique_value=bool(parsed.get("unique_value")),
            )
            
            # If we have the required parameters, run analysis
            if parsed.get("workspace") and parsed.get("file_type") and parsed.get("unique_value"):
                logger.info("All parameters found, running analysis")
                return self.handle_recon_analyze(
                    command_text=message_text,
                    user_id=user_id,
                    channel_id=channel_id,
                )
            
            # Otherwise show help
            logger.info("Missing parameters, showing help message")
            return self.slack_service.format_simple_message(
                "👋 *Recon Analysis Bot*\n\n"
                "Usage: `workspace_name=NETBANKING_AUSF file_type=bank_payment_report unique_column_value=RrQHFDvwIQIKiH`\n\n"
                "Example:\n"
                "`@Recon Analysis Bot workspace_name=NETBANKING_AUSF file_type=bank_payment_report unique_column_value=RrQHFDvwIQIKiH`"
            )
                
        except Exception as e:
            logger.error("Error handling mention", error=str(e), exc_info=True)
            return self.slack_service.format_simple_message(f"Error: {str(e)}")

    def _extract_workspace_from_text(self, text: str) -> Optional[str]:
        """
        Extract workspace name from natural language text.
        
        Args:
            text: Natural language text
            
        Returns:
            Workspace name if found, None otherwise
        """
        # Patterns to extract workspace name
        patterns = [
            r"workspace\s+([a-zA-Z0-9_-]+)",
            r"for\s+([a-zA-Z0-9_-]+)",
            r"on\s+([a-zA-Z0-9_-]+)",
            r"([a-zA-Z0-9_-]+)\s+workspace",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                workspace_name = match.group(1)
                # Filter out common words that might be matched
                if workspace_name.lower() not in ["the", "a", "an", "all", "this", "that"]:
                    return workspace_name
        
        # Try to find quoted strings
        quoted_match = re.search(r"['\"]([a-zA-Z0-9_-]+)['\"]", text)
        if quoted_match:
            return quoted_match.group(1)
        
        return None

