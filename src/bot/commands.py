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
            command_text: Command text (e.g., "report_url=URL" or just a URL)
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
            report_url = parsed.get("report_url")
            report_file = parsed.get("report_file")
            
            # If command_text looks like a URL, use it directly
            if command_text.strip().startswith("http"):
                report_url = command_text.strip()
            
            # Check if we have a report to analyze
            if not report_url and not report_file:
                return self.slack_service.format_simple_message(
                    "📊 *Recon Analysis Bot*\n\n"
                    "Please provide a report file to analyze.\n\n"
                    "*Usage:*\n"
                    "• `/recon-analyze report_url=https://example.com/report.csv`\n"
                    "• `/recon-analyze https://example.com/report.csv`\n"
                    "• `@Recon Analysis Bot analyze https://example.com/report.csv`\n\n"
                    "*Supported formats:* CSV, Excel (.xlsx, .xls)"
                )

            # Parse report
            logger.info("Parsing report", report_url=report_url, report_file=report_file)
            report_result = self.report_parser.parse_report(
                file_path=report_file, url=report_url
            )
            
            if not report_result["success"]:
                return self.slack_service.format_simple_message(
                    f"❌ Failed to parse report: {report_result.get('error', 'Unknown error')}"
                )
            
            report_data = report_result.get("records", [])
            if not report_data:
                return self.slack_service.format_simple_message(
                    "⚠️ Report parsed but no records found. Please check the file format."
                )
            
            logger.info("Report parsed successfully", record_count=len(report_data))

            # Run analyses directly on report data (no API calls needed)
            logger.info("Running analyses on report data", record_count=len(report_data))

            # Scenario A: recon_at not updated (analyze from report data)
            scenario_a = self.recon_status_analyzer.analyze_from_report(
                records=report_data
            )

            # Scenario B: Missing internal data (analyze from report data)
            scenario_b = self.gap_analyzer.analyze_from_report(
                records=report_data
            )

            # Scenario C: Rule matching failures (analyze from report data)
            scenario_c = self.rule_analyzer.analyze_from_report(
                records=report_data
            )

            # Format results
            report_source = report_url or report_file or "Unknown"
            analysis_results = {
                "report_source": report_source,
                "total_records": len(report_data),
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
            # Keep original text for URL extraction
            original_text = message_text.strip()
            cleaned_text = original_text.lower()
            
            logger.info(
                "Handling app mention",
                message=cleaned_text,
                user_id=user_id,
                channel_id=channel_id,
            )
            
            # First, check if there's a URL or file path in the message
            url = self._extract_url_from_text(original_text)
            file_path = self._extract_file_path_from_text(original_text)
            
            if url:
                logger.info("Found URL in mention, analyzing report", url=url)
                return self.handle_recon_analyze(
                    command_text=f"report_url={url}",
                    user_id=user_id,
                    channel_id=channel_id,
                )
            
            if file_path:
                logger.info("Found file path in mention, analyzing report", file_path=file_path)
                return self.handle_recon_analyze(
                    command_text=f"report_file={file_path}",
                    user_id=user_id,
                    channel_id=channel_id,
                )
            
            # Intent detection using keywords
            if any(keyword in cleaned_text for keyword in [
                "analyze", "analysis", "check", "run", "recon"
            ]):
                # Analyze intent - need a report URL
                return self.slack_service.format_simple_message(
                    "📊 *I can analyze your recon reports!*\n\n"
                    "Please provide a report file URL:\n\n"
                    "*Examples:*\n"
                    "• `@Recon Analysis Bot analyze https://example.com/report.csv`\n"
                    "• `/recon-analyze https://example.com/report.xlsx`\n"
                    "• Just paste the URL: `@Recon Analysis Bot https://...`\n\n"
                    "*Supported formats:* CSV, Excel (.xlsx, .xls)\n\n"
                    "I'll analyze the report for:\n"
                    "• 🔴 Missing recon_at updates\n"
                    "• 🟡 Missing internal data\n"
                    "• 🟠 Rule matching failures"
                )
            
            elif any(keyword in cleaned_text for keyword in [
                "hello", "hi", "hey", "help", "what can you do"
            ]):
                # Greeting/help intent
                return self.slack_service.format_simple_message(
                    "👋 *Hi! I'm the Recon Analysis Bot.*\n\n"
                    "I analyze recon reports (CSV/Excel) and find issues like:\n"
                    "• Missing recon_at updates (Scenario A)\n"
                    "• Missing internal data (Scenario B)\n"
                    "• Rule matching failures (Scenario C)\n\n"
                    "*How to use:*\n"
                    "1️⃣ Share a report URL with me:\n"
                    "   `@Recon Analysis Bot https://example.com/report.csv`\n\n"
                    "2️⃣ Or use slash command:\n"
                    "   `/recon-analyze https://example.com/report.csv`\n\n"
                    "💡 Just paste a report URL and I'll analyze it!"
                )
            
            else:
                # Unknown intent - provide helpful response
                return self.slack_service.format_simple_message(
                    "📊 *Recon Analysis Bot*\n\n"
                    "I can analyze your recon reports! Just share a report URL:\n\n"
                    "`@Recon Analysis Bot https://example.com/report.csv`\n\n"
                    "Or use: `/recon-analyze https://example.com/report.xlsx`\n\n"
                    "*Supported formats:* CSV, Excel (.xlsx, .xls)"
                )
                
        except Exception as e:
            logger.error("Error handling mention", error=str(e))
            return self.slack_service.format_simple_message(f"Error: {str(e)}")

    def _extract_url_from_text(self, text: str) -> Optional[str]:
        """
        Extract URL from text.
        
        Args:
            text: Text to search for URL
            
        Returns:
            URL if found, None otherwise
        """
        # Pattern to match URLs
        url_pattern = r'https?://[^\s<>"\'\)>]+'
        match = re.search(url_pattern, text)
        if match:
            url = match.group(0)
            # Clean up any trailing punctuation
            url = url.rstrip('.,;:!?')
            return url
        return None

    def _extract_file_path_from_text(self, text: str) -> Optional[str]:
        """
        Extract file path from text.
        
        Args:
            text: Text to search for file path
            
        Returns:
            File path if found, None otherwise
        """
        # Pattern to match file paths (Unix-style)
        path_pattern = r'(/[^\s<>"\']+\.(csv|xlsx|xls))'
        match = re.search(path_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

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

