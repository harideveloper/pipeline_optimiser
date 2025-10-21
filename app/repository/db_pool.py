"""
Database connection pool for better performance
"""

import psycopg2
import psycopg2.extras
from psycopg2 import pool
from contextlib import contextmanager
from typing import Generator

from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__, "DBPool")


class DatabasePool:
    """ database connection pooling uses singleton pattern (similar to java's singleton pattern)
    threads safe, unwanted connections leaks"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        """Ensure only one instance of DatabasePool exists """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize connection pool if not already initialized."""
        if self._pool is None:
            try:
                self._pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=config.DB_POOL_SIZE,
                    host=config.DB_HOST,
                    port=config.DB_PORT,
                    dbname=config.DB_NAME,
                    user=config.DB_USER,
                    password=config.DB_PASS,
                    cursor_factory=psycopg2.extras.RealDictCursor
                )
                logger.info(
                    f"Database connection pool initialized: "
                    f"minconn=1, maxconn={config.DB_POOL_SIZE}",
                    correlation_id="SYSTEM"
                )
            except Exception as e:
                logger.exception(
                    f"Failed to create connection pool: {e}",
                    correlation_id="SYSTEM"
                )
                raise
    
    @contextmanager
    def get_connection(self) -> Generator:
        """
        Get a connection from the pool.        
        Returns:
            Connection from the pool
        """
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}", correlation_id="SYSTEM")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def close_all(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("Database connection pool closed", correlation_id="SYSTEM")


# Singleton instance
db_pool = DatabasePool()