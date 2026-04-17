"""Policy ingestion script — embeds system + user policy content into Qdrant.

Sources:
  1. System policies: src/agentic_claims/policy/system/*.md (hard rules, Docker image)
  2. User policies:   policy_content DB table (editable via /policies UI)

Both are chunked, embedded with SentenceTransformer, and stored in Qdrant.
"""

import os
import re
from pathlib import Path
from typing import Any

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "expense_policies")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agentic:password@localhost:5432/agentic_claims")

SCRIPT_DIR = Path(__file__).parent
POLICY_DIR = SCRIPT_DIR.parent / "src" / "agentic_claims" / "policy"

# Use mounted host volume if available (persists edits), else fall back to source
_MOUNTED_SYSTEM_DIR = Path("/usr/local/lib/python3.11/policy/system")
SYSTEM_POLICY_DIR = _MOUNTED_SYSTEM_DIR if _MOUNTED_SYSTEM_DIR.exists() else POLICY_DIR / "system"

VECTOR_DIMENSION = 384
MAX_CHUNK_WORDS = 400
CHUNK_OVERLAP_WORDS = 50


def splitIntoChunks(text: str, fileName: str, category: str, source: str) -> list[dict[str, Any]]:
    """Split markdown text into semantic chunks on ## Section headers."""
    chunks = []

    sectionPattern = re.compile(r"^## (Section \d+(?:\.\d+)?:? .+|.+)$", re.MULTILINE)
    sections = sectionPattern.split(text)

    # Content before first section (title/intro)
    if sections[0].strip():
        chunks.append({
            "text": sections[0].strip(),
            "file": fileName,
            "category": category,
            "section": "Introduction",
            "source": source,
        })

    for i in range(1, len(sections), 2):
        if i + 1 < len(sections):
            sectionHeader = sections[i].strip()
            sectionContent = sections[i + 1].strip()
            fullSection = f"## {sectionHeader}\n\n{sectionContent}"
            words = fullSection.split()

            if len(words) <= MAX_CHUNK_WORDS:
                chunks.append({
                    "text": fullSection,
                    "file": fileName,
                    "category": category,
                    "section": sectionHeader,
                    "source": source,
                })
            else:
                chunkStartIdx = 0
                chunkNum = 1
                while chunkStartIdx < len(words):
                    chunkEndIdx = min(chunkStartIdx + MAX_CHUNK_WORDS, len(words))
                    chunks.append({
                        "text": " ".join(words[chunkStartIdx:chunkEndIdx]),
                        "file": fileName,
                        "category": category,
                        "section": f"{sectionHeader} (part {chunkNum})",
                        "source": source,
                    })
                    chunkStartIdx += MAX_CHUNK_WORDS - CHUNK_OVERLAP_WORDS
                    chunkNum += 1

    return chunks


def loadSystemPolicies() -> list[dict[str, Any]]:
    """Load and chunk system policy files from the system/ subdirectory."""
    allChunks = []
    policyFiles = sorted(SYSTEM_POLICY_DIR.glob("*.md"))

    if not policyFiles:
        print(f"WARNING: No system policy files found in {SYSTEM_POLICY_DIR}")
        return allChunks

    print(f"\n[System] Processing {len(policyFiles)} system policy files...")
    for policyFile in policyFiles:
        category = policyFile.stem.replace("_system", "")
        content = policyFile.read_text(encoding="utf-8")
        chunks = splitIntoChunks(content, policyFile.name, category, "system")
        allChunks.extend(chunks)
        print(f"  - {policyFile.name}: {len(chunks)} chunks")

    return allChunks


def loadUserPolicies() -> list[dict[str, Any]]:
    """Load active user-editable policy sections from the DB."""
    allChunks = []

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            rows = conn.execute(
                "SELECT category, section_key, title, content FROM policy_content WHERE is_active = TRUE ORDER BY category, id"
            ).fetchall()

        if not rows:
            print("\n[User] No active user policy sections found in DB.")
            return allChunks

        print(f"\n[User] Processing {len(rows)} user policy sections from DB...")
        for category, section_key, title, content in rows:
            chunks = splitIntoChunks(content, f"{section_key}.md", category, "user")
            allChunks.extend(chunks)
            print(f"  - {section_key} ({category}): {len(chunks)} chunks")

    except Exception as e:
        print(f"\n[User] WARNING: Could not load user policies from DB: {e}")
        print("  Continuing with system policies only.")

    return allChunks


def ingestPolicies():
    """Main ingestion: combine system + user policies → embed → store in Qdrant."""
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    client = QdrantClient(url=QDRANT_URL)

    print(f"Loading embedding model {EMBEDDING_MODEL}...")
    encoder = SentenceTransformer(EMBEDDING_MODEL)

    print(f"\nRecreating collection '{COLLECTION_NAME}'...")
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        print(f"Collection '{COLLECTION_NAME}' did not exist (first run)")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE),
    )
    print(f"Created collection '{COLLECTION_NAME}' with {VECTOR_DIMENSION} dimensions")

    # Load from both sources
    systemChunks = loadSystemPolicies()
    userChunks = loadUserPolicies()
    allChunks = systemChunks + userChunks

    if not allChunks:
        print("ERROR: No policy content found. Aborting.")
        return

    print(f"\nEmbedding {len(allChunks)} total chunks ({len(systemChunks)} system + {len(userChunks)} user)...")
    texts = [chunk["text"] for chunk in allChunks]
    embeddings = encoder.encode(texts, show_progress_bar=True)

    print(f"\nUpserting {len(allChunks)} points to Qdrant...")
    points = [
        PointStruct(
            id=idx,
            vector=embeddings[idx].tolist(),
            payload={
                "text": chunk["text"],
                "file": chunk["file"],
                "category": chunk["category"],
                "section": chunk["section"],
                "source": chunk["source"],
            },
        )
        for idx, chunk in enumerate(allChunks)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)

    print("\n=== Ingestion Complete ===")
    print(f"System chunks: {len(systemChunks)}")
    print(f"User chunks:   {len(userChunks)}")
    print(f"Total:         {len(allChunks)}")
    collectionInfo = client.get_collection(collection_name=COLLECTION_NAME)
    print(f"Collection points: {collectionInfo.points_count} | Status: {collectionInfo.status}")


if __name__ == "__main__":
    ingestPolicies()
