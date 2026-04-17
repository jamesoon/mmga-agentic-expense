"""Policies router — /policies page for reviewers to manage user-editable policy sections."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from agentic_claims.core.config import getSettings, setModelOverride
from agentic_claims.web.auth import requireRole
from agentic_claims.web.db import getAsyncSession
from agentic_claims.web.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policies", dependencies=[Depends(requireRole("reviewer"))])

# Available OpenRouter models for the Models tab
AVAILABLE_MODELS = [
    "qwen/qwen3-235b-a22b-2507",
    "google/gemini-2.0-flash-001",
    "google/gemini-2.0-flash-lite-001",
    "qwen/qwen-2.5-72b-instruct",
    "qwen/qwen-2.5-vl-72b-instruct",
    "google/gemma-4-31b-it",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "deepseek/deepseek-chat-v3-0324",
]

CATEGORIES = {
    "meals": "Meals",
    "transport": "Transport",
    "accommodation": "Accommodation",
    "office_supplies": "Office Supplies",
    "general": "General",
}

# Mounted host volume — persists across restarts
SYSTEM_POLICY_DIR = Path("/usr/local/lib/python3.11/policy/system")
# Fallback for local dev
if not SYSTEM_POLICY_DIR.exists():
    SYSTEM_POLICY_DIR = Path(__file__).parent.parent.parent.parent.parent / "policy" / "system"


def _readSystemPolicies() -> dict[str, str]:
    """Read system policy markdown files. Returns {category: content}."""
    result = {}
    for category in CATEGORIES:
        path = SYSTEM_POLICY_DIR / f"{category}.md"
        if path.exists():
            result[category] = path.read_text(encoding="utf-8")
        else:
            result[category] = f"*System policy file not found: {path}*"
    return result


async def _getUserSections() -> list[dict[str, Any]]:
    """Load all active user policy sections from DB, grouped by category."""
    async with getAsyncSession() as session:
        rows = await session.execute(
            text("""
                SELECT id, category, section_key, title, content, updated_at, updated_by
                FROM policy_content
                WHERE is_active = TRUE
                ORDER BY category, id
            """)
        )
        return [dict(r._mapping) for r in rows]


async def _getLastIngestTime() -> str | None:
    """Get the last time policies were ingested (stored as a special meta row)."""
    try:
        async with getAsyncSession() as session:
            row = await session.execute(
                text("SELECT content FROM policy_content WHERE section_key = '_meta.last_ingest'")
            )
            result = row.scalar()
            return result
    except Exception:
        return None


@router.get("")
async def policiesPage(request: Request):
    """Render the policies management page."""
    userSections = await _getUserSections()
    systemPolicies = _readSystemPolicies()
    lastIngest = await _getLastIngestTime()
    settings = getSettings()

    # Group user sections by category
    byCategory: dict[str, list] = {cat: [] for cat in CATEGORIES}
    for section in userSections:
        cat = section["category"]
        if cat in byCategory:
            byCategory[cat].append(section)

    currentUser = {
        "role": request.session.get("role", ""),
        "displayName": request.session.get("display_name", ""),
    }

    return templates.TemplateResponse(
        request,
        "policies.html",
        context={
            "activePage": "policies",
            "categories": CATEGORIES,
            "byCategory": byCategory,
            "systemPolicies": systemPolicies,
            "lastIngest": lastIngest,
            "userRole": currentUser["role"],
            "displayName": currentUser["displayName"],
            "username": request.session.get("username", ""),
            "currentLlm": settings.openrouter_model_llm,
            "currentVlm": settings.openrouter_model_vlm,
            "availableModels": AVAILABLE_MODELS,
        },
    )


@router.post("/section/{section_id}")
async def updateSection(request: Request, section_id: int, content: str = Form(...)):
    """Save a user policy section to DB and write to the mounted system policy file."""
    username = request.session.get("username", "system")

    async with getAsyncSession() as session:
        # Fetch category for file write
        row = await session.execute(
            text("SELECT category, section_key FROM policy_content WHERE id = :id"),
            {"id": section_id},
        )
        record = row.mappings().first()

        await session.execute(
            text("""
                UPDATE policy_content
                SET content = :content, updated_at = NOW(), updated_by = :updatedBy
                WHERE id = :id
            """),
            {"content": content, "updatedBy": username, "id": section_id},
        )
        await session.commit()

    # Write to mounted file — rebuilds the category file by concatenating all sections
    if record:
        category = record["category"]
        await _rebuildSystemFile(category)

    return templates.TemplateResponse(
        request,
        "partials/policy_save_confirm.html",
        context={"savedAt": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")},
    )


async def _rebuildSystemFile(category: str) -> None:
    """Rebuild the mounted system policy file for a category from all its DB sections."""
    try:
        async with getAsyncSession() as session:
            rows = await session.execute(
                text("""
                    SELECT title, content FROM policy_content
                    WHERE category = :cat AND is_active = TRUE AND section_key != '_meta.last_ingest'
                    ORDER BY id
                """),
                {"cat": category},
            )
            sections = rows.mappings().all()

        if not sections:
            return

        categoryLabel = CATEGORIES.get(category, category.title())
        parts = [f"# SUTD {categoryLabel} Expense Policy — System Prompts\n"]
        for s in sections:
            parts.append(s["content"])

        filePath = SYSTEM_POLICY_DIR / f"{category}.md"
        filePath.parent.mkdir(parents=True, exist_ok=True)
        filePath.write_text("\n\n".join(parts), encoding="utf-8")
        logger.info(f"Rebuilt system policy file: {filePath}")
    except Exception as e:
        logger.error(f"Failed to rebuild system policy file for {category}: {e}")


@router.post("/reingest")
async def reingestPolicies(request: Request):
    """Trigger policy re-ingestion into Qdrant. Runs in background."""
    username = request.session.get("username", "system")

    async def _runIngest():
        """Run policy ingestion in a thread pool (SentenceTransformer is CPU-bound)."""
        import os
        from concurrent.futures import ThreadPoolExecutor

        from agentic_claims.core.config import getSettings

        settings = getSettings()

        def _ingestSync():
            """Run the ingestion synchronously in a thread."""
            os.environ["QDRANT_URL"] = settings.qdrant_url
            os.environ["DATABASE_URL"] = settings.postgres_dsn
            os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"

            # Import and run the ingestion function
            import importlib.util
            from pathlib import Path as _Path
            scriptPath = _Path("/app/scripts/ingest_policies.py")
            if not scriptPath.exists():
                # Local dev fallback
                scriptPath = _Path(__file__).parent.parent.parent.parent.parent.parent / "scripts" / "ingest_policies.py"
            spec = importlib.util.spec_from_file_location("ingest_policies", scriptPath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.ingestPolicies()

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as pool:
                await loop.run_in_executor(pool, _ingestSync)
            success = True
            output = "Ingestion completed successfully"
        except Exception as e:
            success = False
            output = str(e)
            logger.error(f"Policy reingest failed: {e}")

        # Record ingest timestamp in DB
        timestamp = datetime.now(timezone.utc).isoformat()
        status = "success" if success else f"failed: {output[:200]}"
        try:
            async with getAsyncSession() as session:
                await session.execute(
                    text("""
                        INSERT INTO policy_content (category, section_key, title, content, updated_by)
                        VALUES ('_meta', '_meta.last_ingest', 'Last Ingest', :content, :updatedBy)
                        ON CONFLICT (section_key) DO UPDATE SET content = :content, updated_at = NOW(), updated_by = :updatedBy
                    """),
                    {"content": f"{timestamp} — {status}", "updatedBy": username},
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to record ingest timestamp: {e}")

        logger.info(f"Policy reingest completed: success={success}")

    # Run in background
    asyncio.create_task(_runIngest())

    return JSONResponse({"status": "started", "message": "Re-ingestion started. This takes ~30 seconds."})


@router.get("/models")
async def getModels(request: Request):
    """Return current LLM and VLM model names plus available options."""
    settings = getSettings()
    return JSONResponse({
        "llm": settings.openrouter_model_llm,
        "vlm": settings.openrouter_model_vlm,
        "available": AVAILABLE_MODELS,
    })


@router.post("/models")
async def updateModels(request: Request, llm: str = Form(...), vlm: str = Form(...)):
    """Update the active LLM and VLM models at runtime."""
    setModelOverride(llm=llm, vlm=vlm)
    logger.info(f"Models updated by {request.session.get('username', '?')}: LLM={llm}, VLM={vlm}")
    return JSONResponse({"status": "ok", "llm": llm, "vlm": vlm})
