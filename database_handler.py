# database_handler.py

import psycopg2
import psycopg2.extras
import logging
import config  # Ensure your config.py is correctly set up with environment variables

class DatabaseHandler:
    """A handler for PostgreSQL database interactions."""

    def __init__(self):
        """Initialize the DatabaseHandler with connection parameters."""
        self.host = config.DB_HOST
        self.port = config.DB_PORT or '5432'
        self.database = config.DB_NAME
        self.user = config.DB_USER
        self.password = config.DB_PASSWORD
        self.conn = None

    def connect(self):
        """Establish a connection to the PostgreSQL database."""
        if self.conn is None or self.conn.closed != 0:
            try:
                self.conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )
                logging.info("Connected to the PostgreSQL database.")
            except psycopg2.OperationalError as e:
                logging.error(f"OperationalError connecting to PostgreSQL: {e}")
                self.conn = None
            except psycopg2.Error as e:
                logging.error(f"Error connecting to PostgreSQL database: {e}")
                self.conn = None

    def close(self):
        """Close the database connection."""
        if self.conn is not None and self.conn.closed == 0:
            try:
                self.conn.close()
                logging.info("Database connection closed.")
            except psycopg2.Error as e:
                logging.error(f"Error closing the database connection: {e}")

    def __enter__(self):
        """Enter the runtime context related to the object."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context and close the connection."""
        self.close()

    def execute(self, query, params=None):
        """
        Execute a data modification query (INSERT, UPDATE, DELETE).

        Args:
            query (str): The SQL query to execute.
            params (tuple or dict, optional): The parameters to pass with the query.

        Returns:
            bool: True if the query was executed successfully, False otherwise.
        """
        self.connect()
        if self.conn is None:
            logging.error("No database connection available.")
            return False
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                self.conn.commit()
                logging.debug(f"Executed query: {cursor.query.decode()}")
                return True
        except psycopg2.Error as e:
            logging.error(f"Error executing query: {e}")
            self.conn.rollback()
            return False

    def fetch_one(self, query, params=None):
        """
        Execute a SELECT query and fetch a single record.

        Args:
            query (str): The SQL SELECT query to execute.
            params (tuple or dict, optional): The parameters to pass with the query.

        Returns:
            dict or None: The fetched record as a dictionary, or None if no record is found.
        """
        self.connect()
        if self.conn is None:
            logging.error("No database connection available.")
            return None
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                logging.debug(f"Fetched one: {result}")
                return result
        except psycopg2.Error as e:
            logging.error(f"Error fetching one: {e}")
            return None

    def fetch_all(self, query, params=None):
        """
        Execute a SELECT query and fetch all records.

        Args:
            query (str): The SQL SELECT query to execute.
            params (tuple or dict, optional): The parameters to pass with the query.

        Returns:
            list of dict: A list of fetched records as dictionaries.
        """
        self.connect()
        if self.conn is None:
            logging.error("No database connection available.")
            return []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                logging.debug(f"Fetched all: {results}")
                return results
        except psycopg2.Error as e:
            logging.error(f"Error fetching all: {e}")
            return []

    def execute_and_fetch_all(self, query, params=None):
        """
        Execute a SELECT query and fetch all records.
        This is an alias for fetch_all to provide a consistent interface.

        Args:
            query (str): The SQL SELECT query to execute.
            params (tuple or dict, optional): The parameters to pass with the query.

        Returns:
            list of dict: A list of fetched records as dictionaries.
        """
        return self.fetch_all(query, params)

    def execute_and_fetch_one(self, query, params=None):
        """
        Execute a SELECT query and fetch one record.
        This is an alias for fetch_one to provide a consistent interface.

        Args:
            query (str): The SQL SELECT query to execute.
            params (tuple or dict, optional): The parameters to pass with the query.

        Returns:
            dict or None: The fetched record as a dictionary, or None if no record is found.
        """
        return self.fetch_one(query, params)
