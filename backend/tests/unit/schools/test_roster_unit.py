"""UNIT-SEC-* secrets, SEC-14 join codes, UNIT-CSV-* roster parsing — pure logic, no DB."""
import pytest

from app.services.school_class_service import JOIN_CODE_ALPHABET, new_join_code, normalize_join_code
from app.services.school_login_service import roster_name
from app.services.school_student_service import (
    canonical_secret, default_secret_kind, generate_secret, parse_roster_csv, verify_secret,
)
from app.services.profile_service import hash_pin


# ── secrets ──

@pytest.mark.parametrize("grade,kind", [(None, "picture"), (0, "picture"), (4, "picture"), (5, "pin"), (12, "pin")])
def test_default_secret_kind(grade, kind):
    assert default_secret_kind(grade) == kind


def test_generated_secrets_round_trip():
    for kind in ("picture", "pin"):
        canonical, shown = generate_secret(kind)
        assert canonical_secret(kind, shown) == canonical
        assert verify_secret(canonical, hash_pin(canonical))
        assert not verify_secret(canonical, None)


@pytest.mark.parametrize("kind,value", [
    ("picture", [1, 2]), ("picture", [1, 2, 16]), ("picture", [1, 2, -1]), ("picture", "1-2-3"),
    ("picture", [True, 2, 3]), ("pin", "12345"), ("pin", "1234567"), ("pin", "12a456"), ("pin", 123456),
    ("password", "123456"),
])
def test_malformed_secrets_rejected(kind, value):
    assert canonical_secret(kind, value) is None


# ── SEC-14 join codes ──

def test_sec14_join_codes():
    assert not set("ILO01") & set(JOIN_CODE_ALPHABET)
    codes = {new_join_code() for _ in range(10_000)}
    assert len(codes) == 10_000
    assert all(len(c) == 8 and set(c) <= set(JOIN_CODE_ALPHABET) for c in codes)


@pytest.mark.parametrize("raw,expected", [
    ("abcd-efgh", "ABCDEFGH"), (" ABCD EFGH ", "ABCDEFGH"), ("ABCDEFG", None), ("ABCDEFGI", None), ("", None),
])
def test_normalize_join_code(raw, expected):
    assert normalize_join_code(raw) == expected


@pytest.mark.parametrize("name,shown", [("Asha", "Asha"), ("Asha Rao", "Asha R."), ("Asha Kumari Rao", "Asha R.")])
def test_roster_name(name, shown):
    assert roster_name(name) == shown


# ── UNIT-CSV ──

def test_csv_header_aliases_and_values():
    rows, errors = parse_roster_csv(
        "﻿Student Name,STD,Admission No,Section,Login\nAsha,3rd,A1,6A,Picture\nBen,UKG,,6B,\n")
    assert errors == []
    assert [(r["display_name"], r["grade"], r["external_ref"], r["class_name"], r["secret_kind"]) for r in rows] == [
        ("Asha", 3, "A1", "6A", "picture"), ("Ben", 0, None, "6B", None)]


def test_csv_formula_cells_are_plain_text():
    rows, _ = parse_roster_csv('name,roll\n"=HYPERLINK(""http://x"")",@SUM(1)\n')
    assert rows[0]["display_name"] == '=HYPERLINK("http://x")' and rows[0]["external_ref"] == "@SUM(1)"


def test_csv_errors():
    assert parse_roster_csv("")[1] == ["The file is empty."]
    assert "name" in parse_roster_csv("grade\n3\n")[1][0]
    assert parse_roster_csv("name\n\n\n")[1] == ["No students found under the header row."]
    rows, _ = parse_roster_csv("name,grade,login\n" + "x" * 81 + ",13,face\n")
    assert rows[0]["errors"] == ["name is longer than 80 characters",
                                 "grade must be a number from 0 (KG) to 12",
                                 "sign-in must be 'picture' or 'pin'"]


def test_csv_row_cap():
    rows, errors = parse_roster_csv("name\n" + "".join(f"S{i}\n" for i in range(2001)))
    assert len(rows) == 2000 and errors == ["Only 2000 students can be imported at once."]
