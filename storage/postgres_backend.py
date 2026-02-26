"""PostgreSQL backend for storing semantic events"""

import psycopg2
import json
import os
from datetime import datetime


class PostgresBackend:
    """Store and retrieve semantic events from PostgreSQL"""
    
    def __init__(self, host=None, port=None, user=None, password=None, db=None):
        self.host = host or os.getenv('POSTGRES_HOST', 'postgres')
        self.port = port or os.getenv('POSTGRES_PORT', 5432)
        self.user = user or os.getenv('POSTGRES_USER', 'spectra')
        self.password = password or os.getenv('POSTGRES_PASSWORD', 'spectra_dev')
        self.db = db or os.getenv('POSTGRES_DB', 'spectra_db')
        
        self.conn = None
        self.connect()
    
    def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db
            )
            print(f"✓ Connected to PostgreSQL ({self.host}:{self.port}/{self.db})")
        except Exception as e:
            print(f"✗ Failed to connect to PostgreSQL: {e}")
            raise
    
    def store_event(self, event: dict):
        """Store a semantic event"""
        if not self.conn:
            return False
        
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO semantic_events 
                (event_id, event_type, agent_id, timestamp, correlation_id, payload)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                event['event_id'],
                event['event_type'],
                event['agent_id'],
                int(event['timestamp'] * 1000),  # Convert to milliseconds
                event.get('correlation_id', ''),
                json.dumps(event.get('payload', {}))
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error storing event: {e}")
            self.conn.rollback()
            return False
    
    def store_events_batch(self, events: list):
        """Store multiple events efficiently"""
        if not self.conn:
            return False
        
        try:
            cur = self.conn.cursor()
            for event in events:
                cur.execute("""
                    INSERT INTO semantic_events 
                    (event_id, event_type, agent_id, timestamp, correlation_id, payload)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    event['event_id'],
                    event['event_type'],
                    event['agent_id'],
                    int(event['timestamp'] * 1000),
                    event.get('correlation_id', ''),
                    json.dumps(event.get('payload', {}))
                ))
            self.conn.commit()
            print(f"✓ Stored {len(events)} events")
            return True
        except Exception as e:
            print(f"Error storing batch: {e}")
            self.conn.rollback()
            return False
    
    def store_causal_edge(self, from_id: str, to_id: str, reason: str):
        """Store a causal edge"""
        if not self.conn:
            return False
        
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO causal_edges (from_event_id, to_event_id, reason)
                VALUES (%s, %s, %s)
            """, (from_id, to_id, reason))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error storing edge: {e}")
            self.conn.rollback()
            return False
    
    def get_events(self, agent_id=None, event_type=None, correlation_id=None):
        """Retrieve events with optional filters"""
        if not self.conn:
            return []
        
        try:
            cur = self.conn.cursor()
            query = "SELECT * FROM semantic_events WHERE 1=1"
            params = []
            
            if agent_id:
                query += " AND agent_id = %s"
                params.append(agent_id)
            if event_type:
                query += " AND event_type = %s"
                params.append(event_type)
            if correlation_id:
                query += " AND correlation_id = %s"
                params.append(correlation_id)
            
            query += " ORDER BY timestamp ASC"
            
            cur.execute(query, params)
            return cur.fetchall()
        except Exception as e:
            print(f"Error retrieving events: {e}")
            return []
    
    def get_causal_edges(self, correlation_id=None):
        """Retrieve causal edges"""
        if not self.conn:
            return []
        
        try:
            cur = self.conn.cursor()
            if correlation_id:
                query = """
                    SELECT ce.* FROM causal_edges ce
                    JOIN semantic_events se_from ON ce.from_event_id = se_from.event_id
                    WHERE se_from.correlation_id = %s
                """
                cur.execute(query, (correlation_id,))
            else:
                cur.execute("SELECT * FROM causal_edges")
            
            return cur.fetchall()
        except Exception as e:
            print(f"Error retrieving edges: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✓ Disconnected from PostgreSQL")
