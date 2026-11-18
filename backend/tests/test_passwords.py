from app.core.passwords import hash_password, verify_password


def test_hash_is_not_plain_text() -> None:
    hashed = hash_password("mat-khau-123")

    assert hashed != "mat-khau-123"
    assert hashed.startswith("$argon2")


def test_verify_correct_password() -> None:
    assert verify_password("mat-khau-123", hash_password("mat-khau-123"))


def test_verify_wrong_password_false() -> None:
    assert not verify_password("sai-roi-nhe", hash_password("mat-khau-123"))


def test_verify_empty_or_garbage_hash_false() -> None:
    assert not verify_password("abc", "")
    assert not verify_password("abc", "abc")


def test_password_is_not_stripped() -> None:
    hashed = hash_password(" Mật khẩu ")

    assert verify_password(" Mật khẩu ", hashed)
    assert not verify_password("Mật khẩu", hashed)


def test_two_hashes_of_same_password_differ() -> None:
    assert hash_password("mat-khau-123") != hash_password("mat-khau-123")
