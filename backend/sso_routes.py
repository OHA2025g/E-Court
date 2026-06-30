"""e-Office / DigiLocker SSO adapter (OIDC-ready stub)."""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from security import client_ip

SSO_ISSUER = os.environ.get("SSO_ISSUER", "")
SSO_CLIENT_ID = os.environ.get("SSO_CLIENT_ID", "")


def register_sso_routes(api, db, require_role, serialize_fn):
    @api.get("/public/sso")
    async def public_sso_status(request: Request):
        """Unauthenticated — whether SSO login button should appear."""
        from api_rate_limit import enforce_public_ip_rate_limit
        enforce_public_ip_rate_limit(client_ip(request))
        return {"enabled": bool(SSO_ISSUER and SSO_CLIENT_ID)}

    @api.get("/sso/config")
    async def sso_config(_: dict = Depends(require_role("Admin"))):
        return {
            "enabled": bool(SSO_ISSUER and SSO_CLIENT_ID),
            "issuer_present": bool(SSO_ISSUER),
        }

    @api.get("/sso/login")
    async def sso_login():
        if not SSO_ISSUER:
            raise HTTPException(status_code=503, detail="SSO not configured — set SSO_ISSUER and SSO_CLIENT_ID")
        return RedirectResponse(f"{SSO_ISSUER.rstrip('/')}/authorize?client_id={SSO_CLIENT_ID}&response_type=code")

    @api.get("/sso/callback")
    async def sso_callback(code: str = ""):
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
        raise HTTPException(
            status_code=501,
            detail="SSO token exchange not configured — provision SSO_CLIENT_SECRET and callback handler",
        )
