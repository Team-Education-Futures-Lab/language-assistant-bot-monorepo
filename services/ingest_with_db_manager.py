#!/usr/bin/env python3
"""
Updated ingest.py - Now uses DATABASE_MANAGER Service
Parses PDF/TXT documents and ingests chunks into the remote Supabase database
via the Database Manager Service REST API
"""

import os
import sys
import requests
import json
from pathlib import Path
from typing import List, Dict

# ============================================================================
# CONFIGURATION
# ============================================================================

# Database Manager Service URL
DB_MANAGER_URL = os.getenv('DB_MANAGER_URL', 'http://localhost:5004')

# Course materials directory
MATERIALS_DIR = 'course_materials'

# Chunk size for text splitting
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_txt_file(filepath: str) -> str:
    """Load content from TXT file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Fout bij lezen {filepath}: {e}")
        return ""


def create_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        if chunk.strip():
            chunks.append(chunk)
        
        start += chunk_size - overlap
    
    return chunks


def get_or_create_subject(name: str, description: str = "") -> Dict:
    """Get existing subject or create new one"""
    try:
        # Check if subject exists
        response = requests.get(f"{DB_MANAGER_URL}/subjects")
        subjects = response.json().get('subjects', [])
        
        existing = next((s for s in subjects if s['name'].lower() == name.lower()), None)
        if existing:
            print(f"✓ Subject '{name}' al aanwezig (ID: {existing['id']})")
            return existing
        
        # Create new subject
        response = requests.post(
            f"{DB_MANAGER_URL}/subjects",
            json={"name": name, "description": description}
        )
        
        if response.status_code == 201:
            subject = response.json()['subject']
            print(f"✓ Subject '{name}' aangemaakt (ID: {subject['id']})")
            return subject
        else:
            print(f"✗ Fout bij aanmaken subject: {response.json()}")
            return None
            
    except Exception as e:
        print(f"✗ Fout bij subject check: {e}")
        return None


def ingest_chunks_bulk(subject_id: int, chunks: List[Dict], source_file: str) -> bool:
    """Upload chunks in bulk to database manager"""
    try:
        payload = {
            "chunks": [
                {
                    "content": chunk,
                    "source_file": source_file,
                    "metadata": {
                        "chunk_size": len(chunk),
                        "chunk_index": i,
                        "source": source_file
                    }
                }
                for i, chunk in enumerate(chunks)
            ]
        }
        
        response = requests.post(
            f"{DB_MANAGER_URL}/subjects/{subject_id}/chunks/bulk",
            json=payload
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"  ✓ {result['count']} chunks ingested voor {source_file}")
            return True
        else:
            print(f"  ✗ Fout bij ingestie: {response.json()}")
            return False
            
    except Exception as e:
        print(f"  ✗ Fout bij bulk ingestie: {e}")
        return False


def ingest_file(subject_id: int, filepath: str) -> bool:
    """Ingest single file into subject"""
    print(f"\nVerwerking: {filepath}")
    
    # Load content
    content = load_txt_file(filepath)
    if not content:
        print(f"  ✗ Geen content geladen")
        return False
    
    # Create chunks
    chunks = create_chunks(content)
    print(f"  ✓ {len(chunks)} chunks gemaakt")
    
    # Upload to database manager
    filename = Path(filepath).name
    return ingest_chunks_bulk(subject_id, chunks, filename)


def ingest_course_materials():
    """Main ingest process"""
    print("\n" + "="*70)
    print("COURSE MATERIALS INGESTOR")
    print("Remote Database via Database Manager Service")
    print("="*70)
    print(f"DB Manager URL: {DB_MANAGER_URL}")
    print(f"Materials Directory: {MATERIALS_DIR}\n")
    
    # Check if materials directory exists
    if not os.path.exists(MATERIALS_DIR):
        print(f"✗ Directory '{MATERIALS_DIR}' niet gevonden")
        return False
    
    # Get all text files
    txt_files = list(Path(MATERIALS_DIR).glob('*.txt'))
    
    if not txt_files:
        print(f"✗ Geen .txt bestanden in '{MATERIALS_DIR}'")
        return False
    
    print(f"Gevonden {len(txt_files)} bestanden:\n")
    
    total_success = 0
    total_failed = 0
    
    # Process each file
    for filepath in txt_files:
        # Extract subject name from filename (e.g., "biology.txt" → "Biology")
        subject_name = filepath.stem.capitalize()
        
        # Get or create subject
        subject = get_or_create_subject(subject_name)
        if not subject:
            total_failed += 1
            continue
        
        # Ingest file
        if ingest_file(subject['id'], str(filepath)):
            total_success += 1
        else:
            total_failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SAMENVATTING")
    print(f"{'='*70}")
    print(f"Succesvol:  {total_success} bestanden")
    print(f"Mislukt:    {total_failed} bestanden")
    print(f"Total:      {len(txt_files)} bestanden\n")
    
    return total_failed == 0


# ============================================================================
# CLI OPERATIONS
# ============================================================================

def list_subjects():
    """List all subjects in database"""
    try:
        response = requests.get(f"{DB_MANAGER_URL}/subjects")
        subjects = response.json()['subjects']
        
        print(f"\n{'='*70}")
        print(f"ONDERWERPEN IN DATABASE")
        print(f"{'='*70}\n")
        
        if not subjects:
            print("Geen onderwerpen gevonden\n")
            return
        
        for subject in subjects:
            print(f"ID: {subject['id']:<3} | {subject['name']:<20} | {subject['chunk_count']} chunks")
            if subject['description']:
                print(f"       {subject['description'][:50]}...")
        print()
        
    except Exception as e:
        print(f"✗ Fout: {e}")


def inspect_subject(subject_id: int):
    """Show details of specific subject"""
    try:
        response = requests.get(f"{DB_MANAGER_URL}/subjects/{subject_id}/chunks")
        data = response.json()
        
        print(f"\n{'='*70}")
        print(f"ONDERWERP ID: {subject_id}")
        print(f"{'='*70}\n")
        
        chunks = data.get('chunks', [])
        print(f"Total chunks: {data['count']}\n")
        
        for i, chunk in enumerate(chunks[:5], 1):  # Show first 5
            print(f"{i}. Source: {chunk['source_file']}")
            print(f"   Content preview: {chunk['content'][:100]}...")
            print()
        
        if data['count'] > 5:
            print(f"... en {data['count']-5} meer chunks")
        
    except Exception as e:
        print(f"✗ Fout: {e}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Course Materials Ingestor')
    parser.add_argument('--list', action='store_true', help='List all subjects')
    parser.add_argument('--inspect', type=int, metavar='ID', help='Show details of subject')
    parser.add_argument('--db-url', default=DB_MANAGER_URL, help='Database Manager URL')
    
    args = parser.parse_args()
    
    if args.db_url != DB_MANAGER_URL:
        DB_MANAGER_URL = args.db_url
    
    if args.list:
        list_subjects()
    elif args.inspect:
        inspect_subject(args.inspect)
    else:
        success = ingest_course_materials()
        sys.exit(0 if success else 1)
