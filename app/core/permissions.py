from fastapi import HTTPException


ROLE_PERMISSIONS = {
    "viewer": frozenset({"read"}),
    "staff": frozenset({"read", "edit", "ai", "review", "export_internal", "preview_import"}),
    "manager": frozenset({"read", "edit", "ai", "review", "export_internal", "preview_import", "approve", "financial", "export_formal", "import"}),
}
ROLE_PERMISSIONS["admin"] = ROLE_PERMISSIONS["manager"] | {"delete"}
FINANCIAL_FIELDS = frozenset({"final_price", "actual_cost", "competitor_price"})


def can(user, permission):
    return user is not None and permission in ROLE_PERMISSIONS.get(getattr(user, "role", None), frozenset())


def require_permission(user, permission):
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not can(user, permission):
        raise HTTPException(status_code=403, detail="Your role does not allow this action")


def authorize_quote_update(user, quote, data):
    require_permission(user, "edit")
    if "status" in data and data["status"] != quote.status:
        require_permission(user, "approve")
    if FINANCIAL_FIELDS.intersection(data):
        require_permission(user, "financial")
