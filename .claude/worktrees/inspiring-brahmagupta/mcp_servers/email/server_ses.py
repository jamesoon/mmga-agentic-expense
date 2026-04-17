# Author: jamesoon
"""Email MCP Server using AWS SES for Lambda deployment."""

import os
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastmcp import FastMCP

# Environment configuration
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL", "claims@mdaie-sutd.fit")
AWS_REGION = os.getenv("SES_REGION", "ap-southeast-1")

# Initialize
mcp = FastMCP("email-server")
sesClient = boto3.client("ses", region_name=AWS_REGION)


async def sendEmailViaSes(to: str, subject: str, body: str) -> dict[str, Any]:
    """Send email via AWS SES."""
    try:
        response = sesClient.send_email(
            Source=SES_FROM_EMAIL,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        messageId = response.get("MessageId", f"<{uuid.uuid4()}@ses>")
        return {"success": True, "messageId": messageId, "mode": "ses"}
    except ClientError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def sendEmail(to: str, subject: str, body: str) -> dict[str, Any]:
    """
    Send email via AWS SES.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text)

    Returns:
        Success status and message ID
    """
    return await sendEmailViaSes(to, subject, body)


@mcp.tool()
async def sendClaimNotification(
    to: str, claimNumber: str, status: str, message: str
) -> dict[str, Any]:
    """
    Send claim-related notification email.

    Args:
        to: Recipient email address
        claimNumber: Claim number
        status: Claim status (draft, pending, approved, rejected, paid)
        message: Notification message

    Returns:
        Success status and message ID
    """
    subject = f"Expense Claim {claimNumber} - Status: {status.upper()}"

    body = f"""Dear Employee,

Your expense claim has been updated:

Claim Number: {claimNumber}
Status: {status.upper()}

{message}

---
This is an automated notification from SUTD Expense Claims System.
Please do not reply to this email.
"""

    return await sendEmailViaSes(to, subject, body)


@mcp.resource("ses://health")
def getSesHealth() -> str:
    """Check SES configuration."""
    return f"AWS SES mode. From: {SES_FROM_EMAIL}, Region: {AWS_REGION}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
