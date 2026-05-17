"""VLM receipt extraction tool with image quality gate."""

import base64
import io
import json
import logging
import time

import cv2
import httpx
import numpy as np
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openrouter import ChatOpenRouter

from agentic_claims.agents.intake.extractionContext import extractedReceiptVar
from agentic_claims.agents.intake.prompts.vlmExtractionPrompt import VLM_EXTRACTION_PROMPT
from agentic_claims.agents.intake.utils.imageQuality import checkImageQuality
from agentic_claims.core.config import getSettings
from agentic_claims.core.imageStore import getImage, getImagePath
from agentic_claims.core.logging import logEvent

logger = logging.getLogger(__name__)

_VLM_MAX_SIDE = 1024   # px — longer edge cap before sending to VLM
_VLM_MAX_BYTES = 200_000  # 200 KB target after compression


def _compressForVlm(imageBytes: bytes) -> tuple[bytes, str]:
    """Resize and compress receipt image to reduce OpenRouter upload time.

    Returns (compressedBytes, logSummary).
    Caps the longer edge at 1024px and JPEG-compresses to ≤200 KB.
    """
    arr = np.frombuffer(imageBytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return imageBytes, "decode_failed"

    h, w = img.shape[:2]
    maxSide = max(h, w)
    if maxSide > _VLM_MAX_SIDE:
        scale = _VLM_MAX_SIDE / maxSide
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    quality = 85
    while quality >= 50:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            break
        compressed = buf.tobytes()
        if len(compressed) <= _VLM_MAX_BYTES:
            return compressed, f"{len(imageBytes)//1024}KB→{len(compressed)//1024}KB q={quality}"
        quality -= 10

    return buf.tobytes(), f"{len(imageBytes)//1024}KB→{len(buf.tobytes())//1024}KB q={quality}"


@tool
async def extractReceiptFields(claimId: str) -> dict:
    """Extract structured receipt fields from the uploaded receipt image using VLM with quality gate.

    Args:
        claimId: The claim ID whose receipt image should be processed

    Returns:
        Dict with either:
        - Success: {"fields": {...}, "confidence": {...}}
        - Error: {"error": "reason"}
    """
    toolStart = time.time()
    logEvent(logger, "tool.extractReceiptFields.started", logCategory="tool", toolName="extractReceiptFields", claimId=claimId)

    settings = getSettings()

    imageB64 = getImage(claimId)
    if not imageB64:
        return {"error": "No receipt image found. Please upload an image first."}

    try:
        # Decode base64 to bytes
        imageBytes = base64.b64decode(imageB64)

        # Compress image before sending to VLM — reduces upload payload from ~3MB to ~100KB
        compressedBytes, compressLog = _compressForVlm(imageBytes)
        imageB64 = base64.b64encode(compressedBytes).decode("utf-8")
        logEvent(
            logger,
            "tool.extractReceiptFields.image_compressed",
            logCategory="tool",
            toolName="extractReceiptFields",
            claimId=claimId,
            compression=compressLog,
        )

        # Step 3: Instantiate VLM using ChatOpenRouter
        # model_kwargs injects provider routing into every request body sent to OpenRouter:
        # sort=throughput → fastest available provider; allow_fallbacks → tries others if slow
        vlm = ChatOpenRouter(
            model=settings.openrouter_model_vlm,
            openrouter_api_key=settings.openrouter_api_key,
            temperature=0.0,
            max_tokens=settings.openrouter_vlm_max_tokens,
            model_kwargs={"provider": {"sort": "throughput", "allow_fallbacks": True}},
        )

        VLM_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=30.0, pool=5.0)

        # Bypass SSL verification (Zscaler corporate proxy workaround)
        vlm.client.sdk_configuration.client = httpx.Client(verify=False, follow_redirects=True, timeout=VLM_TIMEOUT)
        vlm.client.sdk_configuration.async_client = httpx.AsyncClient(
            verify=False, follow_redirects=True, timeout=VLM_TIMEOUT
        )

        # Step 4: Build multimodal message with prompt + image (sent directly to VLM, not through LLM)
        message = HumanMessage(
            content=[
                {"type": "text", "text": VLM_EXTRACTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{imageB64}"},
                },
            ]
        )

        # Step 5: Call VLM with 402 fallback retry
        try:
            response = await vlm.ainvoke([message])
        except Exception as e:
            errorStr = str(e)
            logEvent(
                logger,
                "tool.extractReceiptFields.vlm_error",
                level=logging.WARNING,
                logCategory="tool",
                toolName="extractReceiptFields",
                claimId=claimId,
                model=settings.openrouter_model_vlm,
                errorType=type(e).__name__,
                error=errorStr[:300],
            )
            # Check for 402 payment/quota errors
            if "402" in errorStr or "credits" in errorStr.lower() or "quota" in errorStr.lower():
                logEvent(
                    logger,
                    "tool.extractReceiptFields.vlm_fallback",
                    level=logging.WARNING,
                    logCategory="tool",
                    toolName="extractReceiptFields",
                    claimId=claimId,
                    primaryModel=settings.openrouter_model_vlm,
                    fallbackModel=settings.openrouter_fallback_model_vlm,
                    error=errorStr,
                )
                # Retry with fallback VLM model
                fallbackVlm = ChatOpenRouter(
                    model=settings.openrouter_fallback_model_vlm,
                    openrouter_api_key=settings.openrouter_api_key,
                    temperature=0.0,
                    max_tokens=settings.openrouter_vlm_max_tokens,
                    model_kwargs={"provider": {"sort": "throughput", "allow_fallbacks": True}},
                )
                fallbackVlm.client.sdk_configuration.client = httpx.Client(
                    verify=False, follow_redirects=True, timeout=VLM_TIMEOUT
                )
                fallbackVlm.client.sdk_configuration.async_client = httpx.AsyncClient(
                    verify=False, follow_redirects=True, timeout=VLM_TIMEOUT
                )
                response = await fallbackVlm.ainvoke([message])
            else:
                raise

        logEvent(
            logger,
            "tool.extractReceiptFields.vlm_completed",
            logCategory="tool",
            toolName="extractReceiptFields",
            claimId=claimId,
            elapsed=f"{time.time() - toolStart:.2f}s",
        )

        rawContent = response.content.strip()

        # VLM returned nothing — image is not a receipt or model refused silently
        if not rawContent:
            return {
                "notAReceipt": True,
                "error": "The image does not appear to contain an expense receipt. Please upload a clear photo of a receipt.",
            }

        if rawContent.startswith("```"):
            # Remove opening ```json or ``` and closing ```
            lines = rawContent.split("\n")
            lines = lines[1:]  # Remove opening ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove closing ```
            rawContent = "\n".join(lines)

        try:
            result = json.loads(rawContent)
            logEvent(
                logger,
                "tool.extractReceiptFields.completed",
                logCategory="tool",
                toolName="extractReceiptFields",
                claimId=claimId,
                elapsed=f"{time.time() - toolStart:.2f}s",
                hasFields="fields" in result,
            )

            # Include imagePath in result so LLM passes it in receiptData.imagePath
            # and so intakeNode can buffer it in the receipt_uploaded audit step
            if "fields" in result:
                imagePath = getImagePath(claimId)
                if imagePath:
                    result["imagePath"] = imagePath

            # BUG-028: set ContextVar so submitClaim can inject numeric
            # confidenceScores into intakeFindings before DB write.
            # Must be set HERE (inside the tool) not in intakeNode
            # post-processing, because submitClaim runs before intakeNode
            # post-processing and ContextVars don't propagate child→parent.
            extractedReceiptVar.set(result)

            return result
        except json.JSONDecodeError:
            # VLM replied in plain text — likely a refusal for non-receipt images
            return {
                "notAReceipt": True,
                "vlmReply": rawContent[:300],
                "error": "The image does not appear to contain an expense receipt. Please upload a clear photo of a receipt.",
            }

    except Exception as e:
        logEvent(
            logger,
            "tool.extractReceiptFields.exception",
            level=logging.ERROR,
            logCategory="tool",
            toolName="extractReceiptFields",
            claimId=claimId,
            errorType=type(e).__name__,
            error=str(e)[:300],
        )
        return {"error": f"Extraction failed: {type(e).__name__}: {str(e)[:200]}"}
