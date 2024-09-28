# database_handler.py

import psycopg2
import psycopg2.extras
import logging

class DatabaseHandler:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None

    def connect(self):
        if self.conn is None or self.conn.closed != 0:
            try:
                self.conn = psycopg2.connect(
                    host=self.db_config['host'],
                    port=self.db_config['port'],
                    database=self.db_config['database'],
                    user=self.db_config['user'],
                    password=self.db_config['password']
                )
                logging.info("Connected to the PostgreSQL database.")
            except psycopg2.Error as e:
                logging.error(f"Error connecting to PostgreSQL database: {e}")
                self.conn = None

    def close(self):
        if self.conn is not None and self.conn.closed == 0:
            self.conn.close()
            logging.info("Database connection closed.")

    def execute_query(self, query, params=None):
        self.connect()
        if self.conn is None:
            return None
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query, params)
                self.conn.commit()
                return cursor
        except psycopg2.Error as e:
            logging.error(f"Database query error: {e}")
            self.conn.rollback()
            return None
