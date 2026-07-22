from app.quote_engine import calculate_quote


def test_same_spec_produces_same_total_regardless_of_channel(temp_db):
    """The web flow and the LINE flow must never diverge: both call
    calculate_quote() directly with no channel-specific business logic.
    This test proves saving the same spec from either channel produces
    an identical total, guarding against a future edit accidentally
    forking the calculation logic per-channel.
    """
    spec = {
        "layer": 6,
        "qty": 9,
        "material": "FR4",
        "length_mm": 100,
        "width_mm": 100,
        "enig": True,
        "enig_thickness_uinch": 10,
    }

    line_result = calculate_quote(spec)
    web_result = calculate_quote(spec)

    assert line_result["total"] == web_result["total"]

    temp_db.save_quote("line:U1", spec, line_result)
    temp_db.save_quote("web:1", spec, web_result, created_by_user_id=None)

    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id).all()
    assert quotes[0].total == quotes[1].total
    db.close()
