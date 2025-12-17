"""
Context Enricher for AI Analysis
Gathers comprehensive context (workspace, file types, rules, rule_recon_state_map)
and formats it for AI prompts.
"""

from typing import Dict, Any, List, Optional
import json
import re
from src.services.trino_client import TrinoClient
from src.services.recon_client import ReconClient
from src.utils.logging import logger
from src.utils.config_reader import get_config_value


class ContextEnricher:
    """
    Enriches AI analysis with comprehensive context from workspace, rules, and configurations.
    """

    def __init__(self):
        """Initialize context enricher with clients."""
        self.use_local_db = get_config_value("local_db.enabled", False)
        if self.use_local_db:
            from src.data.local_db import get_local_db
            self.local_db = get_local_db()
            self.trino_client = None
        else:
            self.trino_client = TrinoClient()
            self.local_db = None
        self.recon_client = ReconClient()
        self._context_cache: Dict[str, Dict[str, Any]] = {}

    def enrich(
        self,
        workspace_id: str,
        workspace_name: Optional[str] = None,
        file_type_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Gather comprehensive context for AI analysis.

        Args:
            workspace_id: Workspace ID
            workspace_name: Optional workspace name (for lookup)
            file_type_ids: Optional list of file type IDs to focus on

        Returns:
            Dict containing enriched context
        """
        cache_key = f"{workspace_id}_{','.join(sorted(file_type_ids or []))}"
        
        # Check cache first
        if cache_key in self._context_cache:
            logger.debug("Using cached context", workspace_id=workspace_id)
            return self._context_cache[cache_key]

        try:
            logger.info(
                "Enriching context for AI analysis",
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                file_type_ids=file_type_ids,
            )

            context = {
                "workspace": {},
                "file_types": [],
                "rules": {},
                "rule_recon_state_map": [],
                "resolved_rules": [],
            }

            # Step 1: Fetch workspace
            workspace = self._fetch_workspace(workspace_id, workspace_name)
            context["workspace"] = workspace

            # Step 2: Fetch file types
            file_types = self._fetch_file_types(workspace_id, file_type_ids)
            context["file_types"] = file_types

            # Extract file_type_ids if not provided
            if not file_type_ids and file_types:
                file_type_ids = [ft.get("id") for ft in file_types if ft.get("id")]

            # Step 3: Fetch rules
            rules = self._fetch_rules(workspace_id, file_type_ids)
            context["rules"] = rules

            # Step 4: Fetch rule_recon_state_map with recon_state
            rule_recon_state_map = self._fetch_rule_recon_state_map(
                workspace_id, file_type_ids
            )
            context["rule_recon_state_map"] = rule_recon_state_map

            # Step 5: Resolve rule expressions
            resolved_rules = self._resolve_rule_expressions(
                rule_recon_state_map, rules
            )
            context["resolved_rules"] = resolved_rules

            # Cache the context
            self._context_cache[cache_key] = context

            logger.info(
                "Context enrichment completed",
                workspace_id=workspace_id,
                file_type_count=len(file_types),
                rule_count=len(rules),
                rule_recon_state_map_count=len(rule_recon_state_map),
            )

            return context

        except Exception as e:
            logger.error(
                "Failed to enrich context",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "workspace": {},
                "file_types": [],
                "rules": {},
                "rule_recon_state_map": [],
                "resolved_rules": [],
                "error": str(e),
            }

    def _fetch_workspace(
        self, workspace_id: str, workspace_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch workspace information from local DB or Trino.

        Args:
            workspace_id: Workspace ID
            workspace_name: Optional workspace name

        Returns:
            Workspace data dict
        """
        try:
            # Use local DB if enabled
            if self.use_local_db and self.local_db:
                workspace = self.local_db.query_workspace(workspace_id)
                if workspace:
                    return workspace
            
            # Try via recon service first (fallback)
            if workspace_name:
                result = self.recon_client.get_workspace_by_name(workspace_name)
                if result.get("success"):
                    return result.get("workspace", {})

            # Query Trino for workspace
            if self.trino_client:
                query = f"""
                SELECT 
                    id,
                    merchant_id,
                    name,
                    workspace_metadata,
                    reporting_emails,
                    email_cut_off_time,
                    automatic_fetching,
                    migrated_to_hudi
                FROM workspaces
                WHERE id = '{workspace_id}'
                AND deleted_at IS NULL
                LIMIT 1
                """

                result = self.trino_client.execute_query(query)
                if result.get("success") and result.get("results"):
                    workspace = result["results"][0]
                    # Parse JSONB fields if needed
                    if isinstance(workspace.get("workspace_metadata"), str):
                        try:
                            workspace["workspace_metadata"] = json.loads(
                                workspace["workspace_metadata"]
                            )
                        except json.JSONDecodeError:
                            pass
                    return workspace

            return {}

        except Exception as e:
            logger.warning(
                "Failed to fetch workspace, using empty context",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {}

    def _fetch_file_types(
        self, workspace_id: str, file_type_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch file types from local DB or Trino.

        Args:
            workspace_id: Workspace ID
            file_type_ids: Optional list of file type IDs to filter

        Returns:
            List of file type dicts
        """
        try:
            # Use local DB if enabled
            if self.use_local_db and self.local_db:
                return self.local_db.query_file_types(workspace_id, file_type_ids)
            
            # Query Trino
            if self.trino_client:
                query = f"""
                SELECT 
                    id,
                    workspace_id,
                    merchant_id,
                    source_id,
                    name,
                    schema,
                    file_metadata,
                    validators,
                    transformations,
                    recon_pivot_metadata,
                    source_category
                FROM file_types
                WHERE workspace_id = '{workspace_id}'
                AND deleted_at IS NULL
                """

                if file_type_ids:
                    file_type_ids_str = "', '".join(file_type_ids)
                    query += f" AND id IN ('{file_type_ids_str}')"

                result = self.trino_client.execute_query(query)
                if result.get("success"):
                    file_types = result.get("results", [])
                    # Parse JSONB fields
                    for ft in file_types:
                        for jsonb_field in ["schema", "file_metadata", "validators", "transformations", "recon_pivot_metadata"]:
                            if isinstance(ft.get(jsonb_field), str):
                                try:
                                    ft[jsonb_field] = json.loads(ft[jsonb_field])
                                except (json.JSONDecodeError, TypeError):
                                    pass
                    return file_types

            return []

        except Exception as e:
            logger.warning(
                "Failed to fetch file types",
                workspace_id=workspace_id,
                error=str(e),
            )
            return []

    def _fetch_rules(
        self, workspace_id: str, file_type_ids: Optional[List[str]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        Fetch rules from local DB or Trino and return as dict keyed by rule ID.

        Args:
            workspace_id: Workspace ID
            file_type_ids: Optional list of file type IDs to filter

        Returns:
            Dict mapping rule_id -> rule data
        """
        try:
            # Use local DB if enabled
            if self.use_local_db and self.local_db:
                return self.local_db.query_rules(workspace_id, file_type_ids)
            
            # Query Trino
            if self.trino_client:
                query = f"""
                SELECT 
                    id,
                    rule,
                    file_type1_id,
                    file_type2_id,
                    workspace_id,
                    merchant_id,
                    is_self_rule,
                    job_context_id
                FROM rules
                WHERE workspace_id = '{workspace_id}'
                AND deleted_at IS NULL
                """

                if file_type_ids:
                    file_type_ids_str = "', '".join(file_type_ids)
                    query += f" AND (file_type1_id IN ('{file_type_ids_str}') OR file_type2_id IN ('{file_type_ids_str}'))"

                query += " ORDER BY id"

                result = self.trino_client.execute_query(query)
                if result.get("success"):
                    rules_list = result.get("results", [])
                    # Convert to dict keyed by id
                    rules_dict = {}
                    for rule in rules_list:
                        rule_id = rule.get("id")
                        if rule_id:
                            rules_dict[int(rule_id)] = rule
                    return rules_dict

            return {}

        except Exception as e:
            logger.warning(
                "Failed to fetch rules",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {}

    def _fetch_rule_recon_state_map(
        self, workspace_id: str, file_type_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch rule_recon_state_map with recon_state from local DB or Trino.

        Args:
            workspace_id: Workspace ID
            file_type_ids: Optional list of file type IDs to filter

        Returns:
            List of rule_recon_state_map entries with recon_state info
        """
        try:
            # Use local DB if enabled
            if self.use_local_db and self.local_db:
                return self.local_db.query_rule_recon_state_map(workspace_id, file_type_ids)
            
            # Query Trino
            if self.trino_client:
                query = f"""
                SELECT 
                    rrsm.id,
                    rrsm.workspace_id,
                    rrsm.merchant_id,
                    rrsm.rule_expression,
                    rrsm.file_type1_id,
                    rrsm.file_type2_id,
                    rrsm.recon_state_id,
                    rrsm.seq_number,
                    rrsm.workflow_id,
                    rrsm.job_context_id,
                    rrsm.is_unreconciled_enrichment_rule,
                    rs.state as recon_state,
                    rs.art_remarks,
                    rs.rank,
                    rs.is_internal,
                    rs.parent_id
                FROM rule_recon_state_map rrsm
                JOIN recon_state rs ON rrsm.recon_state_id = rs.id
                WHERE rrsm.workspace_id = '{workspace_id}'
                AND rrsm.deleted_at IS NULL
                AND rs.deleted_at IS NULL
                """

                if file_type_ids:
                    file_type_ids_str = "', '".join(file_type_ids)
                    query += f"""
                    AND (
                        (rrsm.file_type1_id IN ('{file_type_ids_str}') AND rrsm.file_type2_id IN ('{file_type_ids_str}'))
                        OR (rrsm.file_type1_id = rrsm.file_type2_id AND rrsm.file_type1_id IN ('{file_type_ids_str}'))
                    )
                    """

                query += " ORDER BY rrsm.seq_number"

                result = self.trino_client.execute_query(query)
                if result.get("success"):
                    return result.get("results", [])

            return []

        except Exception as e:
            logger.warning(
                "Failed to fetch rule_recon_state_map",
                workspace_id=workspace_id,
                error=str(e),
            )
            return []

    def _resolve_rule_expressions(
        self,
        rule_recon_state_map: List[Dict[str, Any]],
        rules: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Resolve rule expressions by replacing rule IDs with actual rule expressions.

        Args:
            rule_recon_state_map: List of rule_recon_state_map entries
            rules: Dict mapping rule_id -> rule data

        Returns:
            List of resolved rule_recon_state_map entries with resolved_expression
        """
        resolved = []

        for rrsm in rule_recon_state_map:
            rule_expression = rrsm.get("rule_expression", "")
            if not rule_expression:
                continue

            # Extract rule IDs from expression (e.g., "1 and 2" -> [1, 2])
            rule_ids = re.findall(r"\d+", rule_expression)
            rule_ids_int_list = [int(rid) for rid in rule_ids]

            # Replace rule IDs with actual rule expressions
            resolved_expression = rule_expression
            for rule_id in rule_ids_int_list:
                if rule_id in rules:
                    rule_obj = rules[rule_id]
                    rule_text = rule_obj.get("rule", "")
                    # Replace the rule ID with the actual rule expression in parentheses
                    resolved_expression = resolved_expression.replace(
                        str(rule_id), f"({rule_text})"
                    )

            # Create resolved entry
            resolved_entry = rrsm.copy()
            resolved_entry["resolved_expression"] = resolved_expression
            resolved_entry["rule_ids"] = rule_ids_int_list
            resolved.append(resolved_entry)

        return resolved

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format context for inclusion in AI prompts.

        Args:
            context: Enriched context dict

        Returns:
            Formatted string for prompt
        """
        parts = []

        # Workspace info
        workspace = context.get("workspace", {})
        if workspace:
            parts.append("Workspace Configuration:")
            parts.append(f"  - Name: {workspace.get('name', 'N/A')}")
            parts.append(f"  - ID: {workspace.get('id', 'N/A')}")
            parts.append(f"  - Merchant ID: {workspace.get('merchant_id', 'N/A')}")
            parts.append("")

        # File types
        file_types = context.get("file_types", [])
        if file_types:
            parts.append(f"File Types ({len(file_types)}):")
            for ft in file_types[:5]:  # Limit to first 5 for prompt size
                parts.append(
                    f"  - {ft.get('name', 'N/A')} (ID: {ft.get('id', 'N/A')}, Source: {ft.get('source_category', 'N/A')})"
                )
            if len(file_types) > 5:
                parts.append(f"  ... and {len(file_types) - 5} more")
            parts.append("")

        # Resolved rules
        resolved_rules = context.get("resolved_rules", [])
        if resolved_rules:
            parts.append(f"Reconciliation Rules ({len(resolved_rules)}):")
            for i, rule in enumerate(resolved_rules[:10], 1):  # Limit to first 10
                seq = rule.get("seq_number", 0)
                state = rule.get("recon_state", "N/A")
                art_remarks = rule.get("art_remarks", "")
                resolved_expr = rule.get("resolved_expression", "")
                parts.append(
                    f"  Rule {i} (seq={seq}): {resolved_expr[:100]}..."
                    if len(resolved_expr) > 100
                    else f"  Rule {i} (seq={seq}): {resolved_expr}"
                )
                parts.append(f"    → If matched: State='{state}', art_remarks='{art_remarks}'")
            if len(resolved_rules) > 10:
                parts.append(f"  ... and {len(resolved_rules) - 10} more rules")
            parts.append("")

        return "\n".join(parts)

    def get_resolved_rules_for_file_types(
        self,
        context: Dict[str, Any],
        file_type1_id: str,
        file_type2_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get resolved rules applicable to a specific file type pair.

        Args:
            context: Enriched context
            file_type1_id: First file type ID
            file_type2_id: Second file type ID

        Returns:
            List of applicable resolved rules
        """
        resolved_rules = context.get("resolved_rules", [])
        applicable = []

        for rule in resolved_rules:
            ft1 = rule.get("file_type1_id")
            ft2 = rule.get("file_type2_id")

            # Check if rule applies to this file type pair
            if (ft1 == file_type1_id and ft2 == file_type2_id) or (
                ft1 == file_type2_id and ft2 == file_type1_id
            ):
                applicable.append(rule)
            # Also check self-rules (same file type)
            elif ft1 == ft2 and (ft1 == file_type1_id or ft1 == file_type2_id):
                applicable.append(rule)

        # Sort by seq_number (handle None values)
        applicable.sort(key=lambda x: x.get("seq_number") if x.get("seq_number") is not None else 999)

        return applicable

    def clear_cache(self, workspace_id: Optional[str] = None):
        """
        Clear context cache.

        Args:
            workspace_id: Optional workspace ID to clear specific cache entry
        """
        if workspace_id:
            keys_to_remove = [
                k for k in self._context_cache.keys() if k.startswith(workspace_id)
            ]
            for key in keys_to_remove:
                del self._context_cache[key]
            logger.info("Cleared cache for workspace", workspace_id=workspace_id)
        else:
            self._context_cache.clear()
            logger.info("Cleared all context cache")

