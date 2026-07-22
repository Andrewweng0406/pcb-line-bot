from app.core.auth import (
    hash_password,
    verify_password,
    create_session_token,
    read_session_token,
)


def test_hash_password_does_not_return_plaintext():
    hashed = hash_password("s3cr3t-password")
    assert hashed != "s3cr3t-password"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("s3cr3t-password")
    assert verify_password("s3cr3t-password", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("s3cr3t-password")
    assert verify_password("wrong-password", hashed) is False


def test_session_token_roundtrip():
    token = create_session_token(user_id=42)
    assert read_session_token(token) == 42


def test_read_session_token_rejects_garbage():
    assert read_session_token("not-a-real-token") is None
