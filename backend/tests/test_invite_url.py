def test_invite_url_path() -> None:
    from app.services.members import invite_url_for

    url = invite_url_for("tok_abc")
    assert url.endswith("/invite/tok_abc")
