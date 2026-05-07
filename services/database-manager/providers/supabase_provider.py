from supabase import create_client
from typing import Any, Dict
import os
import json
import uuid
import psycopg2


class SupabaseProvider:
    def __init__(self, config: Dict[str, str]):
        url = config.get('SUPABASE_URL') or os.getenv('SUPABASE_URL')
        key = config.get('SUPABASE_KEY') or os.getenv('SUPABASE_KEY')
        if not url or not key:
            raise RuntimeError('SUPABASE_URL and SUPABASE_KEY must be set for SupabaseProvider')
        self.client = create_client(url, key)

    def table(self, table_name: str) -> Any:
        # Return the supabase table proxy (chainable API)
        return self.client.table(table_name)

    def ping(self):
        # Minimal ping: fetch a tiny setting row
        try:
            _ = self.client.table('openai_settings').select('key').limit(1).execute()
            return True
        except Exception:
            raise

    def populate_langchain_embeddings(self, collection_name: str, chunk_records: list, subject_id: int) -> int:
        """Insert chunk embeddings into langchain_pg_embedding for PGVector usage.

        Returns number of inserted rows.
        """
        inserted = 0
        try:
            db_conn = psycopg2.connect(
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT'),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            )
            db_cur = db_conn.cursor()

            # Get collection ID
            db_cur.execute("SELECT uuid FROM langchain_pg_collection WHERE name = %s;", (collection_name,))
            collection_row = db_cur.fetchone()
            if not collection_row:
                raise RuntimeError(f"Collection '{collection_name}' not found in langchain_pg_collection")
            collection_id = collection_row[0]

            for chunk_record in chunk_records:
                if 'embedding' in chunk_record and chunk_record['embedding']:
                    embedding_id = str(uuid.uuid4())
                    cmetadata = {
                        'subject_id': subject_id,
                        'source_file': chunk_record.get('source_file'),
                        'chunk_index': chunk_record.get('chunk_metadata', {}).get('chunk_index'),
                    }
                    db_cur.execute(
                        """
                        INSERT INTO langchain_pg_embedding (id, collection_id, embedding, document, cmetadata)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            embedding_id,
                            collection_id,
                            chunk_record['embedding'],
                            chunk_record['content'],
                            json.dumps(cmetadata)
                        )
                    )
                    inserted += 1

            db_conn.commit()
            db_cur.close()
            db_conn.close()
            return inserted
        except Exception:
            try:
                if 'db_conn' in locals():
                    db_conn.rollback()
            except Exception:
                pass
            raise
