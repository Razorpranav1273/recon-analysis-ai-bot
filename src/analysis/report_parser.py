"""
Report Parser for ART Reports
Parses CSV/Excel ART reports to extract transaction data.
"""

import pandas as pd
import requests
from typing import Dict, Any, List, Optional
from io import BytesIO
from src.utils.logging import logger


class ReportParser:
    """
    Parser for ART (Auto Reconciliation Tool) reports.
    Supports both CSV and Excel formats.
    """

    def __init__(self):
        """Initialize report parser."""
        self.supported_formats = [".csv", ".xlsx", ".xls"]

    def parse_report(
        self, file_path: Optional[str] = None, url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse ART report from file path or URL.

        Args:
            file_path: Path to local file
            url: URL to download report from

        Returns:
            Dict containing parsed report data
        """
        try:
            if file_path:
                return self._parse_from_file(file_path)
            elif url:
                return self._parse_from_url(url)
            else:
                return {
                    "success": False,
                    "error": "Either file_path or url must be provided",
                    "records": [],
                }

        except Exception as e:
            logger.error("Failed to parse report", error=str(e))
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "records": [],
            }

    def _parse_from_file(self, file_path: str) -> Dict[str, Any]:
        """Parse report from local file."""
        logger.info("Parsing report from file", file_path=file_path)

        # Determine file format
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
        else:
            return {
                "success": False,
                "error": f"Unsupported file format. Supported: {self.supported_formats}",
                "records": [],
            }

        return self._process_dataframe(df)

    def _parse_from_url(self, url: str) -> Dict[str, Any]:
        """Parse report from URL."""
        logger.info("Parsing report from URL", url=url)

        # Download file
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        # Determine file format from URL or content
        if url.endswith(".csv") or "text/csv" in response.headers.get("content-type", ""):
            df = pd.read_csv(BytesIO(response.content))
        elif url.endswith((".xlsx", ".xls")) or "spreadsheet" in response.headers.get(
            "content-type", ""
        ):
            df = pd.read_excel(BytesIO(response.content))
        else:
            # Try to detect format
            try:
                df = pd.read_csv(BytesIO(response.content))
            except Exception:
                try:
                    df = pd.read_excel(BytesIO(response.content))
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Could not parse file format: {str(e)}",
                        "records": [],
                    }

        return self._process_dataframe(df)

    def _process_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Process pandas DataFrame into structured records."""
        try:
            # Normalize column names (lowercase, strip spaces, replace spaces with underscores)
            df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

            # Convert entire dataframe to records (keep all columns)
            records = []
            for _, row in df.iterrows():
                # Convert row to dict, keeping all columns
                record = row.to_dict()
                
                # Also add normalized versions of common fields for consistency
                record["transaction_date"] = self._extract_date(row)
                record["record_id"] = self._extract_value(row, ["record_id", "id"])
                record["entity_id"] = self._extract_value(row, ["entity_id", "rzp_entity_id", "payment_id"])
                record["recon_status"] = self._extract_value(row, ["recon_status", "status"])
                record["recon_at"] = self._extract_value(row, ["recon_at", "reconciled_at", "recon_timestamp"])
                record["amount"] = self._extract_value(row, ["amount", "transaction_amount", "internal_amount"])
                record["bank_amount"] = self._extract_value(row, ["bank_amount", "mis_amount", "external_amount"])
                record["rrn"] = self._extract_value(row, ["rrn", "internal_rrn", "payment_id"])
                record["bank_rrn"] = self._extract_value(row, ["bank_rrn", "mis_rrn", "external_rrn"])
                record["source_type"] = self._extract_value(row, ["source_type", "file_type", "type"])
                record["art_remarks"] = self._extract_value(row, ["art_remarks", "remarks", "note"])
                record["failure_reason"] = self._extract_value(row, ["failure_reason", "error", "error_message"])
                
                records.append(record)

            logger.info(
                "Report parsed successfully",
                record_count=len(records),
                columns=list(df.columns),
            )

            return {
                "success": True,
                "records": records,
                "total_records": len(records),
                "columns": list(df.columns),
            }

        except Exception as e:
            logger.error("Failed to process dataframe", error=str(e))
            return {
                "success": False,
                "error": f"Dataframe processing error: {str(e)}",
                "records": [],
            }

    def _extract_date(self, row: pd.Series) -> Optional[str]:
        """Extract transaction date from row."""
        date_columns = [
            "transaction_date",
            "date",
            "transaction date",
            "txn_date",
            "created_at",
        ]
        for col in date_columns:
            if col in row and pd.notna(row[col]):
                date_val = row[col]
                # Convert to string if it's a datetime
                if hasattr(date_val, "strftime"):
                    return date_val.strftime("%Y-%m-%d")
                return str(date_val)
        return None

    def _extract_value(self, row: pd.Series, possible_columns: List[str]) -> Optional[Any]:
        """Extract value from row using possible column names."""
        for col in possible_columns:
            if col in row and pd.notna(row[col]):
                return row[col]
        return None

