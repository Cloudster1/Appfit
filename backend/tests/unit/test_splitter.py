from appfit.services.search.splitter import split_requirements

BULLET = chr(0x2022)


def texts(text: str) -> list[str]:
    return [r.text for r in split_requirements(text)]


def test_bullets_and_numbering_are_stripped() -> None:
    text = f"- SSO via Azure AD\n* Export to PDF\n{BULLET} Audit log\n1. REST API\n2) Webhooks\n[x] Mobile app"
    assert texts(text) == ["SSO via Azure AD", "Export to PDF", "Audit log", "REST API", "Webhooks", "Mobile app"]


def test_single_line_is_one_requirement() -> None:
    reqs = split_requirements("We need a tool for travel expense reports")
    assert len(reqs) == 1
    assert reqs[0].priority is None
    assert reqs[0].weight == 1.0


def test_moscow_headers_set_priority_until_next_header() -> None:
    text = "Must have:\n- SSO\n- Audit log\nShould:\n- Dark mode\nNice to have:\n- Mobile app\n- Offline mode"
    got = [(r.text, r.priority) for r in split_requirements(text)]
    assert got == [
        ("SSO", "must"),
        ("Audit log", "must"),
        ("Dark mode", "should"),
        ("Mobile app", "could"),
        ("Offline mode", "could"),
    ]


def test_german_headers_and_inline_priorities() -> None:
    text = "Muss-Kriterien:\n- Anmeldung per SSO\nKann:\n- Export nach Excel\n- Pflicht: DSGVO-konforme Löschung"
    got = [(r.text, r.priority) for r in split_requirements(text)]
    assert got == [
        ("Anmeldung per SSO", "must"),
        ("Export nach Excel", "could"),
        ("DSGVO-konforme Löschung", "must"),
    ]


def test_parenthetical_priority_is_removed_from_text() -> None:
    reqs = split_requirements("- Mobile app (optional)\n- Reporting [must]")
    assert [(r.text, r.priority) for r in reqs] == [("Mobile app", "could"), ("Reporting", "must")]


def test_long_line_is_split_into_sentences_with_abbreviations_protected() -> None:
    text = (
        "Das System muss eingehende Rechnungen verarbeiten, z.B. PDF-Rechnungen aus einem Postfach. "
        "Es soll einen mehrstufigen Freigabe-Workflow geben. Die Daten müssen nach SAP exportiert werden."
    )
    got = texts(text)
    assert len(got) == 3
    assert got[0].endswith("aus einem Postfach.")
    assert "z.B." in got[0]


def test_short_trailing_fragment_is_merged() -> None:
    text = (
        "The platform must support single sign-on with our corporate identity provider for all employees. "
        "Very important."
    )
    got = texts(text)
    assert len(got) == 1
    assert got[0].endswith("Very important.")


def test_context_headers_are_dropped_and_wrapped_lines_joined() -> None:
    text = "Our requirements:\nthe tool must integrate with\nexisting ticket systems\n\n- Reporting"
    assert texts(text) == ["the tool must integrate with existing ticket systems", "Reporting"]


def test_empty_and_header_only_input() -> None:
    assert split_requirements("") == []
    assert split_requirements("Must have:\n\n") == []


def test_requirement_cap() -> None:
    text = "\n".join(f"- requirement number {i}" for i in range(50))
    assert len(split_requirements(text)) == 30
