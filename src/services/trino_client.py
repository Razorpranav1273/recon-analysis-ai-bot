"""
Trino Client for Recon Analysis Bot
Provides database connectivity and query execution for Querybook queries.
Based on poc_risk_agent Trino client pattern.
"""

from typing import Dict, Any, Optional
from datetime import datetime

# Fail fast if trino is not available
import trino

from src.utils.config_reader import get_config_value
from src.utils.logging import logger


class TrinoClient:
    """
    Trino database client with proper connection management and error handling.
    """

    def __init__(self):
        """Initialize Trino client with configuration."""
        # Get configuration values
        self.host = get_config_value("trino.host", "localhost")
        self.port = get_config_value("trino.port", 443)
        self.catalog = get_config_value("trino.catalog", "hive")
        self.schema = get_config_value("trino.schema", "default")
        self.username = get_config_value("trino.username", "user")
        self.proto = get_config_value("trino.proto", "https")
        self.timeout = get_config_value("trino.timeout", 60)
        # Ensure timeout is always a positive integer
        if self.timeout is None or self.timeout <= 0:
            self.timeout = 60
        self.debug = get_config_value("trino.debug", False)

        logger.info(
            "Trino client initialized",
            host=self.host,
            port=self.port,
            catalog=self.catalog,
            schema=self.schema,
        )

        # Setup logging if debug is enabled
        if self.debug:
            import logging

            logging.basicConfig(level=logging.INFO)
            logging.getLogger("trino").setLevel(logging.INFO)

        self._connection = None

    def _get_connection(self):
        """Get or create Trino connection."""
        if self._connection is None:
            try:
                logger.debug(
                    f"[TRINO] Creating connection with timeout: {self.timeout}"
                )

                # Validate timeout before connection
                if self.timeout <= 0:
                    logger.warning(
                        f"[TRINO] Invalid timeout {self.timeout}, using default 60"
                    )
                    self.timeout = 60

                # Create connection
                self._connection = trino.dbapi.connect(
                    host=self.host,
                    port=self.port,
                    user=self.username,
                    catalog=self.catalog,
                    schema=self.schema,
                    http_scheme=self.proto,
                    request_timeout=self.timeout,
                )

                if self.debug:
                    logger.debug(
                        f"[TRINO] Connected to {self.proto}://{self.host}:{self.port}"
                    )
                    logger.debug(
                        f"[TRINO] Catalog: {self.catalog}, Schema: {self.schema}"
                    )

            except Exception as e:
                raise ConnectionError(f"Failed to connect to Trino: {str(e)}")

        return self._connection

    def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Trino query and return results.

        Args:
            query: SQL query to execute
            parameters: Optional query parameters for parameterized queries

        Returns:
            Dict containing query results and metadata
        """
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            if self.debug:
                logger.debug(f"[TRINO] Executing query: {query[:200]}...")
                if parameters:
                    logger.debug(f"[TRINO] Parameters: {parameters}")

            start_time = datetime.now()

            # Execute query with parameters if provided
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)

            # Fetch results
            rows = cursor.fetchall()
            columns = (
                [desc[0] for desc in cursor.description] if cursor.description else []
            )

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # Convert rows to list of dictionaries
            results = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                results.append(row_dict)

            if self.debug:
                logger.debug(
                    f"[TRINO] Query executed successfully in {execution_time:.2f}s"
                )
                logger.debug(f"[TRINO] Returned {len(results)} rows")

            return {
                "success": True,
                "results": results,
                "row_count": len(results),
                "columns": columns,
                "execution_time_seconds": execution_time,
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "host": self.host,
                    "catalog": self.catalog,
                    "schema": self.schema,
                },
            }

        except Exception as e:
            error_msg = f"Trino query execution failed: {str(e)}"
            if self.debug:
                logger.error(f"[TRINO] ERROR: {error_msg}")

            return {
                "success": False,
                "error": error_msg,
                "error_type": type(e).__name__,
                "results": [],
                "row_count": 0,
                "columns": [],
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "host": self.host,
                    "catalog": self.catalog,
                    "schema": self.schema,
                },
            }

    def execute_querybook_query(
        self, query_name: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Querybook query by name.

        This is a flexible method that can be used to execute predefined Querybook queries.
        The actual query SQL should be provided or loaded from a query registry.

        Args:
            query_name: Name of the Querybook query
            params: Parameters for the query

        Returns:
            Dict containing query results and metadata
        """
        # For now, this is a placeholder that can be extended with a query registry
        # Users can provide their Querybook queries and map them to query_name
        logger.warning(
            f"Querybook query '{query_name}' not found in registry. "
            "Please provide the query SQL or add it to the query registry."
        )

        return {
            "success": False,
            "error": f"Querybook query '{query_name}' not found",
            "query_name": query_name,
            "results": [],
        }

    def fetch_txn_entity_data(
        self, entity_ids: list, check_recon_at: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch txn_entity data from Trino for given entity IDs.

        Args:
            entity_ids: List of entity IDs to query
            check_recon_at: Whether to check for recon_at timestamp

        Returns:
            Dict containing txn_entity data
        """
        try:
            if not entity_ids:
                return {
                    "success": True,
                    "results": [],
                    "row_count": 0,
                }

            # Build query with safe parameter handling
            # Note: Trino doesn't support parameterized queries like PostgreSQL
            # So we validate and sanitize inputs instead
            
            # Validate entity IDs (should be alphanumeric, hyphens, underscores)
            # This prevents SQL injection by only allowing safe characters
            import re
            safe_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
            
            safe_entity_ids = []
            for eid in entity_ids:
                eid_str = str(eid).strip()
                if safe_pattern.match(eid_str):
                    # Escape single quotes for SQL (double them)
                    safe_entity_ids.append(eid_str.replace("'", "''"))
                else:
                    logger.warning(f"Invalid entity_id format, skipping: {eid_str}")
            
            if not safe_entity_ids:
                return {
                    "success": False,
                    "error": "No valid entity IDs provided",
                    "results": [],
                    "row_count": 0,
                }
            
            # Build IN clause safely
            entity_ids_str = "', '".join(safe_entity_ids)
            
            query = f"""
            SELECT 
                entity_id,
                recon_at,
                created_at,
                updated_at
            FROM txn_entity
            WHERE entity_id IN ('{entity_ids_str}')
            """

            if check_recon_at:
                query += " AND recon_at IS NULL"

            logger.info(
                "Fetching txn_entity data",
                entity_count=len(entity_ids),
                check_recon_at=check_recon_at,
            )

            return self.execute_query(query)

        except Exception as e:
            logger.error(
                "Failed to fetch txn_entity data",
                entity_count=len(entity_ids) if entity_ids else 0,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "results": [],
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Trino connection with a simple query.

        Returns:
            Dict containing connection test results
        """
        test_query = "SELECT 1 as test_value"

        if self.debug:
            logger.debug("[TRINO] Testing connection...")

        result = self.execute_query(test_query)

        if result["success"]:
            return {
                "success": True,
                "message": "Trino connection successful",
                "host": self.host,
                "catalog": self.catalog,
                "schema": self.schema,
            }
        else:
            return {
                "success": False,
                "message": f'Trino connection failed: {result["error"]}',
                "host": self.host,
                "error": result["error"],
            }

    def close(self):
        """Close the Trino connection."""
        if self._connection:
            try:
                self._connection.close()
                if self.debug:
                    logger.debug("[TRINO] Connection closed")
            except Exception as e:
                if self.debug:
                    logger.error(f"[TRINO] Error closing connection: {e}")
            finally:
                self._connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions
def get_trino_client() -> TrinoClient:
    """
    Get a Trino client instance.

    Returns:
        TrinoClient instance
    """
    return TrinoClient()


def test_trino_connection() -> Dict[str, Any]:
    """
    Convenience function to test Trino connection.

    Returns:
        Dict containing connection test results
    """
    with TrinoClient() as client:
        return client.test_connection()

