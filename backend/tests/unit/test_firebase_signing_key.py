"""SC-802: the service-account RSA key is parsed once, not per sign-in."""
import json
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services import firebase_admin


def _sa_json() -> tuple[str, object]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    raw = json.dumps({"client_email": "sa@test.iam.gserviceaccount.com", "private_key": pem,
                      "private_key_id": "kid-1", "token_uri": "https://oauth2.invalid/token"})
    return raw, key.public_key()


def _mint(raw: str) -> str:
    with patch.object(firebase_admin.settings, "FIREBASE_SERVICE_ACCOUNT_JSON", raw):
        return firebase_admin.mint_custom_token("stu_abc", {"kind": "school_student"})


def test_key_parsed_once_and_reparsed_on_rotation():
    firebase_admin._sa_cache.clear()
    raw1, pub1 = _sa_json()
    raw2, pub2 = _sa_json()
    real_load = serialization.load_pem_private_key
    with patch("cryptography.hazmat.primitives.serialization.load_pem_private_key",
               side_effect=real_load) as load:
        t1 = _mint(raw1)
        _mint(raw1)
        _mint(raw1)
        assert load.call_count == 1
        t2 = _mint(raw2)
        assert load.call_count == 2

    claims = jwt.decode(t1, pub1, algorithms=["RS256"], audience=firebase_admin._CUSTOM_TOKEN_AUD)
    assert claims["uid"] == "stu_abc" and claims["claims"] == {"kind": "school_student"}
    assert jwt.get_unverified_header(t1)["kid"] == "kid-1"
    jwt.decode(t2, pub2, algorithms=["RS256"], audience=firebase_admin._CUSTOM_TOKEN_AUD)


def test_unset_service_account_returns_none():
    firebase_admin._sa_cache.clear()
    assert _mint("") is None
