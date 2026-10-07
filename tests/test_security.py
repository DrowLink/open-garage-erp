from open_garage_erp.security import hash_password, verify_password


def test_hash_password_uses_argon2id_and_verifies_plaintext() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("$argon2id$")
    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash) is True


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("wrong password", password_hash) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("correct horse battery staple", "not-an-argon2-hash") is False
