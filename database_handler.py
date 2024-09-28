# database_handler.py

import psycopg2
import psycopg2.extras
import logging
import config  # Import your config.py file

class DatabaseHandler:
    def __init__(self):
        self.host = config.DB_HOST
        self.port = config.DB_PORT or '5432'
        self.database = config.DB_NAME
        self.user = config.DB_USER
        self.password = config.DB_PASSWORD
        self.conn = None

    def connect(self):
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
            except psycopg2.Error as e:
                logging.error(f"Error connecting to PostgreSQL database: {e}")
                self.conn = None

    def close(self):
        if self.conn is not None and self.conn.closed == 0:
            self.conn.close()
            logging.info("Database connection closed.")

    def execute_query(self, query, params=None, fetch=False):
        self.connect()
        if self.conn is None:
            return None
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    results = cursor.fetchall()
                    return results
                else:
                    self.conn.commit()
                    return cursor
        except psycopg2.Error as e:
            logging.error(f"Database query error: {e}")
            self.conn.rollback()
            return None

    def __del__(self):
        self.close()
