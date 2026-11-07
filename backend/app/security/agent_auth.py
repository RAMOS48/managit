import hmac
import os

from fastapi import Header, HTTPException


def require_agent_token(x_agent_token: str = Header(default="")):
    expected = os.getenv("AGENT_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=500, detail="Agent authentication is not configured")
    if not hmac.compare_digest(x_agent_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid agent token")
