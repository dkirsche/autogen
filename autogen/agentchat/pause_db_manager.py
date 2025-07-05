"""
Database manager for agent pause functionality using PostgreSQL.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available. Database pause functionality will be disabled.")


class PauseDBManager:
    """Manages agent pause state in PostgreSQL database."""

    def __init__(self):
        """
        Initialize the database manager.

        Reads connection string from environment variable POSTGRES_URL.
        Format: "postgresql://user:password@host:port/database"
        """
        self.connection_string = os.getenv("POSTGRES_URL")
        self.enabled = PSYCOPG2_AVAILABLE and self.connection_string is not None

        if self.enabled:
            logger.info("Database pause functionality enabled")
            self._ensure_table_exists()
        else:
            if not PSYCOPG2_AVAILABLE:
                logger.info("Database pause functionality disabled (psycopg2 not available)")
            else:
                logger.info("Database pause functionality disabled (POSTGRES_URL environment variable not set)")

    def _get_connection(self):
        """Get a database connection."""
        if not self.enabled:
            return None

        try:
            return psycopg2.connect(self.connection_string)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None

    def _ensure_table_exists(self):
        """Create the agent_status table if it doesn't exist."""
        if not self.enabled:
            return

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS agent_status (
            agent_id UUID PRIMARY KEY,
            agent_name VARCHAR(255) NOT NULL,
            is_paused BOOLEAN DEFAULT FALSE,
            pause_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_agent_status_name ON agent_status(agent_name);
        """

        conn = self._get_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # Execute table creation first
                    cursor.execute(create_table_sql)
                    # Execute index creation separately
                    cursor.execute(create_index_sql)
                conn.commit()
                logger.info("Agent status table and index ensured to exist")
            except Exception as e:
                logger.error(f"Failed to create agent_status table: {e}")
            finally:
                conn.close()

    def upsert_agent_status(
        self, agent_id: str, agent_name: str, is_paused: bool = False, pause_message: Optional[str] = None
    ) -> bool:
        """
        Insert or update agent status in database.

        Args:
            agent_id (str): Unique agent identifier
            agent_name (str): Agent name
            is_paused (bool): Whether agent is paused
            pause_message (str, optional): Custom pause message

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False

        upsert_sql = """
        INSERT INTO agent_status (agent_id, agent_name, is_paused, pause_message, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (agent_id)
        DO UPDATE SET
            agent_name = EXCLUDED.agent_name,
            is_paused = EXCLUDED.is_paused,
            pause_message = EXCLUDED.pause_message,
            updated_at = EXCLUDED.updated_at;
        """

        conn = self._get_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    now = datetime.now(timezone.utc)
                    cursor.execute(upsert_sql, (agent_id, agent_name, is_paused, pause_message, now, now))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to upsert agent status: {e}")
                conn.rollback()
            finally:
                conn.close()

        return False

    def get_agent_pause_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent pause status from database.

        Args:
            agent_id (str): Unique agent identifier

        Returns:
            dict: Agent status information or empty dict if not found/error
        """
        if not self.enabled:
            return {}

        select_sql = """
        SELECT agent_id, agent_name, is_paused, pause_message, created_at, updated_at
        FROM agent_status
        WHERE agent_id = %s;
        """

        conn = self._get_connection()
        if conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(select_sql, (agent_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else {}
            except Exception as e:
                logger.error(f"Failed to get agent pause status: {e}")
            finally:
                conn.close()

        return {}

    def set_agent_pause_state(self, agent_id: str, is_paused: bool, pause_message: Optional[str] = None) -> bool:
        """
        Update agent pause state in database.

        Args:
            agent_id (str): Unique agent identifier
            is_paused (bool): Whether agent should be paused
            pause_message (str, optional): Custom pause message

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False

        update_sql = """
        UPDATE agent_status
        SET is_paused = %s, pause_message = %s, updated_at = %s
        WHERE agent_id = %s;
        """

        conn = self._get_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(update_sql, (is_paused, pause_message, datetime.now(timezone.utc), agent_id))
                    success = cursor.rowcount > 0
                conn.commit()
                return success
            except Exception as e:
                logger.error(f"Failed to set agent pause state: {e}")
                conn.rollback()
            finally:
                conn.close()

        return False

    def is_agent_paused(self, agent_id: str) -> bool:
        """
        Quick check if agent is paused.

        Args:
            agent_id (str): Unique agent identifier

        Returns:
            bool: True if paused, False otherwise
        """
        status = self.get_agent_pause_status(agent_id)
        return status.get("is_paused", False)

    def get_pause_message(self, agent_id: str) -> str:
        """
        Get the pause message for an agent.

        Args:
            agent_id (str): Unique agent identifier

        Returns:
            str: Pause message or default message
        """
        status = self.get_agent_pause_status(agent_id)
        return status.get("pause_message") or "Conversation is paused. Use resume() to continue."


# Global instance - will be configured by agents
_global_pause_db_manager: Optional[PauseDBManager] = None


def get_pause_db_manager() -> Optional[PauseDBManager]:
    """Get the global pause database manager instance."""
    return _global_pause_db_manager


def initialize_pause_db_manager() -> PauseDBManager:
    """Initialize the global pause database manager from environment variable."""
    global _global_pause_db_manager
    if _global_pause_db_manager is None:
        _global_pause_db_manager = PauseDBManager()
    return _global_pause_db_manager
