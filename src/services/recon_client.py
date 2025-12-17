"""
Recon Service Client
Client to interact with recon service APIs.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from src.utils.http_client import HTTPClient
from src.utils.config_reader import get_config_value
from src.utils.logging import logger


class ReconClient:
    """
    Client for interacting with recon service APIs.
    """

    def __init__(self):
        """Initialize recon client with configuration."""
        self.base_url = get_config_value("recon.base_url", "http://localhost:5000")
        self.api_key = get_config_value("recon.api_key", "")
        self.api_username = get_config_value("recon.api_username", "")
        self.api_password = get_config_value("recon.api_password", "")
        self.basic_auth_token = get_config_value("recon.basic_auth_token", "")
        self.http_client = HTTPClient(
            verify_ssl=False, timeout=60, use_shared_session=True
        )

        # Set authentication: Priority order:
        # 1. Basic Auth token (if provided directly)
        # 2. Username + Password (to build Basic Auth)
        # 3. Bearer token (fallback)
        
        if self.basic_auth_token:
            # Use Basic Auth token directly (e.g., "Basic cmVjb25fYXBpX3VzZXI6c3RhZ2UuYXBpQGFydA==")
            auth_header = self.basic_auth_token
            if not auth_header.startswith("Basic "):
                auth_header = f"Basic {auth_header}"
            self.http_client.session.headers.update(
                {"Authorization": auth_header}
            )
            logger.info(
                "Recon client initialized with Basic Auth token",
                base_url=self.base_url,
            )
        elif self.api_username and self.api_password:
            # Basic Authentication (username:password)
            import base64
            credentials = f"{self.api_username}:{self.api_password}"
            encoded_creds = base64.b64encode(credentials.encode()).decode('utf-8')
            self.http_client.session.headers.update(
                {"Authorization": f"Basic {encoded_creds}"}
            )
            logger.info(
                "Recon client initialized with Basic Auth (username:password)",
                base_url=self.base_url,
                username=self.api_username,
            )
        elif self.api_key:
            # Bearer token (fallback)
            self.http_client.session.headers.update(
                {"Authorization": f"Bearer {self.api_key}"}
            )
            logger.info(
                "Recon client initialized with Bearer token",
                base_url=self.base_url,
                has_api_key=bool(self.api_key),
            )
        else:
            logger.warning(
                "Recon client initialized without authentication",
                base_url=self.base_url,
            )

    def get_workspace_by_name(self, workspace_name: str) -> Dict[str, Any]:
        """
        Get workspace by name.

        Args:
            workspace_name: Name of the workspace

        Returns:
            Dict containing workspace data or error
        """
        try:
            logger.info("Fetching workspace by name", workspace_name=workspace_name)

            # Call /workspaces API and filter by name
            url = f"{self.base_url}/api/v1/workspaces"
            logger.debug("Calling workspaces API", url=url, headers=self.http_client.session.headers.get("Authorization", "None"))
            response = self.http_client.get(url)
            
            # Log response details for debugging
            if not response["success"]:
                logger.error(
                    "Failed to fetch workspaces",
                    url=url,
                    status_code=response.get("status_code"),
                    error=response.get("error"),
                    response_body=response.get("data", {}),
                )

            if not response["success"]:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch workspaces"),
                    "workspace_name": workspace_name,
                }

            # Find workspace by name
            # Handle different response structures
            response_data = response.get("data", {})
            if isinstance(response_data, list):
                workspaces = response_data
            elif isinstance(response_data, dict):
                workspaces = response_data.get("data", response_data.get("workspaces", []))
            else:
                workspaces = []
            
            if isinstance(workspaces, list):
                for workspace in workspaces:
                    if workspace.get("name") == workspace_name:
                        return {
                            "success": True,
                            "workspace": workspace,
                            "workspace_id": workspace.get("id"),
                        }

            return {
                "success": False,
                "error": f"Workspace '{workspace_name}' not found",
                "workspace_name": workspace_name,
            }

        except Exception as e:
            logger.error(
                "Failed to get workspace by name",
                workspace_name=workspace_name,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "workspace_name": workspace_name,
            }

    def list_all_workspaces(self) -> Dict[str, Any]:
        """
        List all available workspaces.

        Returns:
            Dict containing list of workspaces or error
        """
        try:
            logger.info("Fetching all workspaces")

            # Call /workspaces API
            url = f"{self.base_url}/api/v1/workspaces"
            response = self.http_client.get(url)

            if not response["success"]:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch workspaces"),
                    "workspaces": [],
                }

            # Parse response
            response_data = response.get("data", {})
            if isinstance(response_data, list):
                workspaces = response_data
            elif isinstance(response_data, dict):
                workspaces = response_data.get("data", response_data.get("workspaces", []))
            else:
                workspaces = []

            return {
                "success": True,
                "workspaces": workspaces if isinstance(workspaces, list) else [],
            }

        except Exception as e:
            logger.error("Failed to list workspaces", error=str(e))
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "workspaces": [],
            }

    def get_unreconciled_records(
        self,
        workspace_id: str,
        source_id: Optional[str] = None,
        transaction_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get unreconciled records.

        Args:
            workspace_id: Workspace ID
            source_id: Optional source ID filter
            transaction_date: Optional transaction date filter
            page: Page number (default: 1)
            page_size: Records per page (default: 50)

        Returns:
            Dict containing unreconciled records
        """
        try:
            logger.info(
                "Fetching unreconciled records",
                workspace_id=workspace_id,
                source_id=source_id,
                transaction_date=transaction_date,
            )

            url = f"{self.base_url}/api/v1/records"
            params = {
                "recon_status": "unreconciled",
                "tenant_id": workspace_id,
                "page": page,
            }

            if source_id:
                params["source_id"] = source_id
            if transaction_date:
                params["transaction_date"] = transaction_date

            response = self.http_client.get(url, params=params)

            if response["success"]:
                # Handle different response structures
                response_data = response.get("data", {})
                if isinstance(response_data, list):
                    records = response_data
                elif isinstance(response_data, dict):
                    records = response_data.get("data", response_data.get("records", []))
                else:
                    records = []
                
                return {
                    "success": True,
                    "records": records,
                    "page": page,
                    "page_size": page_size,
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch records"),
                    "records": [],
                }

        except Exception as e:
            logger.error(
                "Failed to get unreconciled records",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "records": [],
            }

    def get_recon_results(
        self, record_id: Optional[str] = None, workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recon results.

        Args:
            record_id: Optional record ID filter
            workspace_id: Optional workspace ID filter

        Returns:
            Dict containing recon results
        """
        try:
            logger.info(
                "Fetching recon results",
                record_id=record_id,
                workspace_id=workspace_id,
            )

            url = f"{self.base_url}/api/v1/recon_result"
            params = {}

            if record_id:
                params["record_id"] = record_id
            if workspace_id:
                params["tenant_id"] = workspace_id

            response = self.http_client.get(url, params=params)

            if response["success"]:
                data = response.get("data", {})
                results = data.get("data", []) if isinstance(data, dict) else data
                return {
                    "success": True,
                    "results": results if isinstance(results, list) else [results],
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch recon results"),
                    "results": [],
                }

        except Exception as e:
            logger.error(
                "Failed to get recon results",
                record_id=record_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "results": [],
            }

    def get_recon_result_by_entity_id(
        self,
        entity_id: str,
        workspace_id: str,
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get recon result by entity ID.

        Args:
            entity_id: Entity ID (rzp_entity_id)
            workspace_id: Workspace ID
            source_id: Optional source ID filter

        Returns:
            Dict containing recon result
        """
        try:
            logger.info(
                "Fetching recon result by entity ID",
                entity_id=entity_id,
                workspace_id=workspace_id,
            )

            url = f"{self.base_url}/api/v1/records/fetch_by_entity_id"
            data = {
                "rzp_entity_id": entity_id,
                "workspace_id": workspace_id,
            }

            if source_id:
                data["source_id"] = source_id

            response = self.http_client.post(url, data=data)

            if response["success"]:
                data = response.get("data", {})
                results = data.get("data", []) if isinstance(data, dict) else data
                return {
                    "success": True,
                    "results": results if isinstance(results, list) else [results],
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch recon result"),
                    "results": [],
                }

        except Exception as e:
            logger.error(
                "Failed to get recon result by entity ID",
                entity_id=entity_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "results": [],
            }

    def check_file_ingestion(
        self, workspace_id: str, transaction_date: str, file_type_name: str = "internal"
    ) -> Dict[str, Any]:
        """
        Check if file was ingested for a given date.

        Args:
            workspace_id: Workspace ID
            transaction_date: Transaction date (YYYY-MM-DD)
            file_type_name: File type name filter (e.g., "internal", "rzp")

        Returns:
            Dict containing ingestion status
        """
        try:
            logger.info(
                "Checking file ingestion",
                workspace_id=workspace_id,
                transaction_date=transaction_date,
                file_type_name=file_type_name,
            )

            # Use file_details API with date filter
            url = f"{self.base_url}/api/v1/file_details"
            params = {
                "workspace_id": workspace_id,
                "transaction_date": transaction_date,
            }
            response = self.http_client.get(url, params=params)

            if response["success"]:
                data = response.get("data", {})
                file_details = data.get("data", []) if isinstance(data, dict) else data
                
                if not isinstance(file_details, list):
                    file_details = [file_details] if file_details else []

                # Filter for internal file types
                internal_files = []
                for file_detail in file_details:
                    file_type = file_detail.get("file_type", {})
                    if isinstance(file_type, dict):
                        file_type_name_lower = file_type.get("name", "").lower()
                    else:
                        file_type_name_lower = str(file_type).lower()

                    # Check if it's an internal file type
                    if file_type_name.lower() in file_type_name_lower or "internal" in file_type_name_lower or "rzp" in file_type_name_lower:
                        # Check ingestion status
                        ingestion_status = file_detail.get("ingestion_status")
                        ingestion_status_code = file_detail.get("ingestion_status_code")
                        
                        # File is ingested if status is "processed" or status_code is 200
                        if ingestion_status == "processed" or ingestion_status_code == 200:
                            internal_files.append(file_detail)

                return {
                    "success": True,
                    "file_ingested": len(internal_files) > 0,
                    "file_count": len(internal_files),
                    "files": internal_files,
                }

            return {
                "success": False,
                "error": response.get("error", "Failed to check file ingestion"),
                "file_ingested": False,
            }

        except Exception as e:
            logger.error("Failed to check file ingestion", error=str(e))
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "file_ingested": False,
            }

    def get_rules(
        self, workspace_id: str, file_type_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get rules for workspace.

        Args:
            workspace_id: Workspace ID
            file_type_ids: Optional list of file type IDs to filter rules

        Returns:
            Dict containing rules
        """
        try:
            logger.info(
                "Fetching rules",
                workspace_id=workspace_id,
                file_type_ids=file_type_ids,
            )

            url = f"{self.base_url}/api/v1/rules"
            params = {"tenant_id": workspace_id}

            response = self.http_client.get(url, params=params)

            if response["success"]:
                data = response.get("data", {})
                rules = data.get("data", []) if isinstance(data, dict) else data
                rules_list = rules if isinstance(rules, list) else [rules]

                # Filter by file_type_ids if provided
                if file_type_ids:
                    filtered_rules = [
                        rule
                        for rule in rules_list
                        if rule.get("file_type_id") in file_type_ids
                    ]
                    rules_list = filtered_rules

                return {
                    "success": True,
                    "rules": rules_list,
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch rules"),
                    "rules": [],
                }

        except Exception as e:
            logger.error(
                "Failed to get rules",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "rules": [],
            }

    def get_file_types(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get file types for workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            Dict containing file types
        """
        try:
            logger.info("Fetching file types", workspace_id=workspace_id)

            url = f"{self.base_url}/api/v1/file_types"
            params = {"tenant_id": workspace_id}

            response = self.http_client.get(url, params=params)

            if response["success"]:
                data = response.get("data", {})
                file_types = data.get("data", []) if isinstance(data, dict) else data
                return {
                    "success": True,
                    "file_types": file_types if isinstance(file_types, list) else [file_types],
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to fetch file types"),
                    "file_types": [],
                }

        except Exception as e:
            logger.error(
                "Failed to get file types",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "file_types": [],
            }

