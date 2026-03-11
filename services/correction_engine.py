import json
import uuid
import logging
from typing import Dict, Any, Optional
from database import get_db_connection

logger = logging.getLogger(__name__)

class CorrectionEngine:
    @staticmethod
    def get_corrections(tool_name: str) -> Dict[str, str]:
        """Fetches all active correction rules for a specific tool."""
        rules = {}
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(
                "SELECT pattern, replacement FROM correction_rules WHERE tool_scope = ? OR tool_scope IS NULL",
                (tool_name,)
            )
            for row in c.fetchall():
                rules[row['pattern']] = row['replacement']
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch correction rules: {e}")
        return rules

    @staticmethod
    def apply_corrections(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Applies correction rules to tool parameters."""
        rules = CorrectionEngine.get_corrections(tool_name)
        if not rules:
            return params

        corrected_params = params.copy()
        
        # Simple string replacement for now. 
        # Future versions can support regex or key-specific targeting.
        param_str = json.dumps(params)
        modified = False
        
        for pattern, replacement in rules.items():
            if pattern in param_str:
                logger.info(f"Applying correction: '{pattern}' -> '{replacement}' for tool '{tool_name}'")
                param_str = param_str.replace(pattern, replacement)
                modified = True
        
        if modified:
            try:
                corrected_params = json.loads(param_str)
            except Exception as e:
                logger.error(f"Failed to re-parse corrected params: {e}")
        
        return corrected_params

    @staticmethod
    def record_failure(tool_name: str, params: Dict[str, Any], error_message: str, package_id: Optional[str] = None):
        """Records a tool failure in the 'Mistake Journal' (tool_failures table)."""
        try:
            conn = get_db_connection()
            c = conn.cursor()
            failure_id = str(uuid.uuid4())
            c.execute(
                "INSERT INTO tool_failures (id, tool_name, input_params, error_message, package_id) VALUES (?, ?, ?, ?, ?)",
                (failure_id, tool_name, json.dumps(params), error_message, package_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Recorded tool failure: {tool_name} (ID: {failure_id})")
        except Exception as e:
            logger.error(f"Failed to record tool failure: {e}")
