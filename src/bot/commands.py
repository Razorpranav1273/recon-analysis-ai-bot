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

    def handle_list_workspaces(self) -> Dict[str, Any]:
        """
        Handle /recon-list-workspaces command to list all available workspaces.

        Returns:
            Dict containing Slack response with workspace list
        """
        try:
            logger.info("Handling /recon-list-workspaces command")

            # Get all workspaces
            result = self.recon_client.list_all_workspaces()

            if not result["success"]:
                return self.slack_service.format_simple_message(
                    f"Error: {result.get('error', 'Failed to fetch workspaces')}"
                )

            workspaces = result.get("workspaces", [])

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

            message += "\n\n💡 *Usage:* `/recon-analyze workspace=WORKSPACE_NAME`"
            message += f"\n   Example: `/recon-analyze workspace={workspaces[0].get('name', 'WORKSPACE_NAME')}`"

            return self.slack_service.format_simple_message(message)

        except Exception as e:
            logger.error("Error handling /recon-list-workspaces", error=str(e))
            return self.slack_service.format_simple_message(f"Error: {str(e)}")

    def handle_mention(self, message_text: str, user_id: str, channel_id: str) -> Dict[str, Any]:
        """
        Handle app mention with natural language processing.
        
        Args:
            message_text: The message text (with @bot mention removed)
            user_id: Slack user ID
            channel_id: Slack channel ID
            
        Returns:
            Dict containing Slack response
        """
        try:
            # Remove bot mention and clean up text
            cleaned_text = message_text.strip().lower()
            
            logger.info(
                "Handling app mention",
                message=cleaned_text,
                user_id=user_id,
                channel_id=channel_id,
            )
            
            # Intent detection using keywords
            if any(keyword in cleaned_text for keyword in [
                "list", "show", "what", "available", "all", "workspaces", "workspace"
            ]) and any(keyword in cleaned_text for keyword in ["workspace", "workspaces"]):
                # List workspaces intent
                return self.handle_list_workspaces()
            
            elif any(keyword in cleaned_text for keyword in [
                "analyze", "analysis", "check", "run", "recon"
            ]):
                # Analyze intent - try to extract workspace name
                workspace_name = self._extract_workspace_from_text(cleaned_text)
                
                if workspace_name:
                    # Use existing analyze handler
                    return self.handle_recon_analyze(
                        command_text=f"workspace={workspace_name}",
                        user_id=user_id,
                        channel_id=channel_id,
                    )
                else:
                    return self.slack_service.format_simple_message(
                        "I can help you analyze a workspace! Please specify which workspace to analyze.\n\n"
                        "Examples:\n"
                        "• `analyze workspace XYZ`\n"
                        "• `check recon for workspace ABC`\n"
                        "• `run analysis on workspace TEST`\n\n"
                        "Or use `/recon-list-workspaces` to see all available workspaces."
                    )
            
            elif any(keyword in cleaned_text for keyword in [
                "hello", "hi", "hey", "help", "what can you do"
            ]):
                # Greeting/help intent
                return self.slack_service.format_simple_message(
                    "👋 Hi! I'm the Recon Analysis Bot. I can help you:\n\n"
                    "📋 *List Workspaces:*\n"
                    "   • `@Recon Analysis Bot list workspaces`\n"
                    "   • `@Recon Analysis Bot show all workspaces`\n"
                    "   • `/recon-list-workspaces`\n\n"
                    "🔍 *Analyze Workspace:*\n"
                    "   • `@Recon Analysis Bot analyze workspace XYZ`\n"
                    "   • `@Recon Analysis Bot check recon for workspace ABC`\n"
                    "   • `/recon-analyze workspace=XYZ`\n\n"
                    "💡 Just mention me and ask naturally, or use slash commands!"
                )
            
            else:
                # Unknown intent - provide helpful response
                return self.slack_service.format_simple_message(
                    "I can help you with reconciliation analysis! Here's what I can do:\n\n"
                    "• *List workspaces:* `@Recon Analysis Bot list workspaces`\n"
                    "• *Analyze workspace:* `@Recon Analysis Bot analyze workspace NAME`\n"
                    "• *Get help:* `@Recon Analysis Bot help`\n\n"
                    "Or use slash commands:\n"
                    "• `/recon-list-workspaces` - List all workspaces\n"
                    "• `/recon-analyze workspace=NAME` - Analyze a workspace"
                )
                
        except Exception as e:
            logger.error("Error handling mention", error=str(e))
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

