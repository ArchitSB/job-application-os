from app.services.normalization import normalize_company, normalize_text, normalize_url


def test_company_and_role_normalization():
    assert normalize_company(" OpenAI, Inc. ") == normalize_company("openai")
    assert normalize_text("Senior Backend Engineer") != normalize_text("Backend Engineer")
    assert normalize_text("C++ Engineer") != normalize_text("C# Engineer")


def test_url_normalization_preserves_real_identifiers():
    assert normalize_url("https://jobs.example.com/job/123/?utm_source=post#apply") == normalize_url(
        "https://jobs.example.com/job/123"
    )
    assert normalize_url("https://jobs.example.com/apply?id=1") != normalize_url(
        "https://jobs.example.com/apply?id=2"
    )
