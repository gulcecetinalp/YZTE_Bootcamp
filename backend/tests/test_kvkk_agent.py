"""SCRUM-24 KVKK risk ajanı testleri.

Gerçek API anahtarı gerekmez: LLM'li senaryolar NarrativeLLM protokolünü
karşılayan sahte (fake) bir istemciyle test edilir. Her adım
(analyze_columns, score_risks, generate_narrative) izole test edilir;
run_kvkk_agent ile uçtan uca da doğrulanır.
"""

import pandas as pd
import pytest

from app.services.kvkk_agent import (
    analyze_columns,
    generate_narrative,
    run_kvkk_agent,
    score_risks,
)


class FakeLLM:
    """NarrativeLLM protokolünü karşılayan sahte istemci. Gerçek API
    çağrısı yapmaz; sabit bir yanıt ya da bir exception döndürür.
    """

    def __init__(self, response_text: str | None = None, raises: Exception | None = None):
        self._response_text = response_text
        self._raises = raises

    def invoke(self, prompt: str):
        if self._raises is not None:
            raise self._raises

        class _Response:
            def __init__(self, content: str):
                self.content = content

        return _Response(self._response_text)


# ── Örnek 1: dolaylı tanımlayıcı kombinasyon riski ──────────────────────────


def test_combination_risk_detected_for_kept_quasi_columns():
    detections = [
        {"column": "Geography", "category": "location", "sensitivity": "quasi", "detected_by": "column_name", "match_ratio": None},
        {"column": "Gender", "category": "gender", "sensitivity": "quasi", "detected_by": "column_name", "match_ratio": None},
        {"column": "Age", "category": "age", "sensitivity": "quasi", "detected_by": "column_name", "match_ratio": None},
    ]
    actions = [
        {"column": "Geography", "category": "location", "action": "kept"},
        {"column": "Gender", "category": "gender", "action": "kept"},
        {"column": "Age", "category": "age", "action": "kept"},
    ]
    df = pd.DataFrame({"Geography": ["TR"], "Gender": ["F"], "Age": [30]})

    analysis = analyze_columns(detections, actions, df)

    assert len(analysis["combination_candidates"]) == 1
    combo = analysis["combination_candidates"][0]
    assert set(combo["columns"]) == {"Geography", "Gender", "Age"}
    assert combo["risk"] == "Yeniden kimliklendirme"

    scoring = score_risks(analysis)
    assert scoring["combination_risks"][0]["risk_score"] > 0

    narrative = generate_narrative(analysis, scoring, llm=None)
    combo_reasoning = narrative["combination_reasonings"][0]["reasoning"]
    # Tek tek "hepsi düşük risk" demek yerine kombinasyonun kendisini açıklamalı
    assert "birlikte" in combo_reasoning or "kombinasyon" in combo_reasoning


# ── Örnek 2: veri kalitesi anomalisi KVKK riskinden ayrı tutulmalı ──────────


def test_perfect_correlation_reported_as_data_quality_not_kvkk_risk():
    detections: list[dict] = []
    actions: list[dict] = []
    df = pd.DataFrame({"Exited": [0, 1, 0, 1, 0, 1] * 10, "Complain": [0, 1, 0, 1, 0, 1] * 10})

    analysis = analyze_columns(detections, actions, df)

    assert len(analysis["data_quality_notes"]) == 1
    note = analysis["data_quality_notes"][0]
    assert "Exited" in note and "Complain" in note
    assert "KVKK riski değil" in note


def test_capping_detected_generically_without_hardcoded_column_names():
    # CreditScore adı hiçbir yerde kodda geçmiyor - kasıtlı olarak farklı bir
    # kolon adıyla (Skor) test ediyoruz, jenerik olduğunu kanıtlamak için.
    values = [500 + i for i in range(80)] + [900] * 20  # üstte anormal yığılma
    df = pd.DataFrame({"Skor": values})

    analysis = analyze_columns([], [], df)

    assert any("Skor" in note for note in analysis["data_quality_notes"])


# ── Örnek 3: hassas veri bulunamadığında risk uydurulmamalı ─────────────────


def test_no_fabricated_risk_when_no_detections():
    df = pd.DataFrame({"a": [1, 2, 3]})
    report = run_kvkk_agent("file-x", detections=[], actions=[], df=df, llm=None)

    assert report["overall_risk_score"] == 0
    assert report["risk_level"] == "low"
    assert report["column_assessments"] == []
    assert report["combination_risks"] == []
    # tespitin sınırlı olduğu açıkça belirtilmeli
    assert any("regex" in rec or "sınırlı" in rec for rec in report["recommendations"])


def test_korunmus_kolon_eklemek_genel_skoru_dusurmez():
    """Regresyon testi: eskiden ortalama alındığı için, iyi korunmuş kolonlar
    eklendikçe açıkta duran bir alanın riski gizleniyordu. Düz metin bir
    parola tek başına 90 puan alırken 10 hash'li kolon yanına konduğunda 15
    puana iniyordu. Kolon eklemek skoru DÜŞÜREMEZ.
    """
    df = pd.DataFrame({"x": [1, 2, 3]})

    parola_dets = [{"column": "password", "category": "credential", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}]
    parola_acts = [{"column": "password", "category": "credential", "action": "kept"}]

    tek_basina = score_risks(analyze_columns(parola_dets, parola_acts, df))

    # aynı parola + 10 tane iyi korunmuş (hash'lenmiş) kolon
    genis_dets = parola_dets + [
        {"column": f"id{i}", "category": "id", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}
        for i in range(10)
    ]
    genis_acts = parola_acts + [
        {"column": f"id{i}", "category": "id", "action": "hashed"} for i in range(10)
    ]
    kalabalik = score_risks(analyze_columns(genis_dets, genis_acts, df))

    assert kalabalik["overall_risk_score"] >= tek_basina["overall_risk_score"]
    assert kalabalik["risk_level"] == "high"


def test_genel_skor_en_riskli_kolondan_dusuk_olamaz():
    df = pd.DataFrame({"x": [1]})
    detections = [
        {"column": "tc", "category": "national_id", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None},
        {"column": "cinsiyet", "category": "gender", "sensitivity": "quasi", "detected_by": "column_name", "match_ratio": None},
    ]
    actions = [
        {"column": "tc", "category": "national_id", "action": "kept"},
        {"column": "cinsiyet", "category": "gender", "action": "kept"},
    ]

    scoring = score_risks(analyze_columns(detections, actions, df))
    en_yuksek_kolon = max(c["risk_score"] for c in scoring["columns"])

    assert scoring["overall_risk_score"] >= en_yuksek_kolon


# ── LLM / fallback davranışı ─────────────────────────────────────────────────


def test_falls_back_to_template_when_llm_is_none():
    df = pd.DataFrame({"Email": ["a@b.com"]})
    detections = [{"column": "Email", "category": "email", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}]
    actions = [{"column": "Email", "category": "email", "action": "masked"}]

    report = run_kvkk_agent("file-y", detections, actions, df, llm=None)

    assert report["agent_steps"][2]["step"] == "report_generation"
    assert "yedek" in report["agent_steps"][2]["summary"].lower()
    assert report["legal_notice"].startswith("Bu rapor hukuki danışmanlık değildir")


def test_falls_back_when_llm_raises():
    df = pd.DataFrame({"Email": ["a@b.com"]})
    detections = [{"column": "Email", "category": "email", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}]
    actions = [{"column": "Email", "category": "email", "action": "masked"}]
    broken_llm = FakeLLM(raises=TimeoutError("kota doldu"))

    report = run_kvkk_agent("file-z", detections, actions, df, llm=broken_llm)

    assert "kota doldu" in report["agent_steps"][2]["summary"]
    assert report["column_assessments"][0]["reasoning"]  # yine de boş kalmamalı


def test_falls_back_when_llm_returns_malformed_json():
    df = pd.DataFrame({"Email": ["a@b.com"]})
    detections = [{"column": "Email", "category": "email", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}]
    actions = [{"column": "Email", "category": "email", "action": "masked"}]
    broken_llm = FakeLLM(response_text="bu json değil, düz metin")

    report = run_kvkk_agent("file-w", detections, actions, df, llm=broken_llm)

    assert report["agent_steps"][2]["step"] == "report_generation"
    assert report["column_assessments"][0]["reasoning"]


def test_uses_llm_output_when_valid_json_returned():
    df = pd.DataFrame({"Email": ["a@b.com"]})
    detections = [{"column": "Email", "category": "email", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}]
    actions = [{"column": "Email", "category": "email", "action": "masked"}]
    fake_json = (
        '{"column_reasonings": {"Email": "LLM tarafından yazılan özel gerekçe."}, '
        '"combination_reasonings": [], "recommendations": ["LLM önerisi"]}'
    )
    ok_llm = FakeLLM(response_text=fake_json)

    report = run_kvkk_agent("file-v", detections, actions, df, llm=ok_llm)

    assert report["column_assessments"][0]["reasoning"] == "LLM tarafından yazılan özel gerekçe."
    assert report["recommendations"] == ["LLM önerisi"]
    assert "LLM" in report["agent_steps"][2]["summary"] or "gerekçe" in report["agent_steps"][2]["summary"]


def test_handles_llm_response_wrapped_in_markdown_code_fence():
    df = pd.DataFrame({"Email": ["a@b.com"]})
    detections = [{"column": "Email", "category": "email", "sensitivity": "direct", "detected_by": "column_name", "match_ratio": None}]
    actions = [{"column": "Email", "category": "email", "action": "masked"}]
    fenced = (
        "```json\n"
        '{"column_reasonings": {"Email": "gerekce"}, "combination_reasonings": [], "recommendations": []}'
        "\n```"
    )
    fenced_llm = FakeLLM(response_text=fenced)

    report = run_kvkk_agent("file-u", detections, actions, df, llm=fenced_llm)

    assert report["column_assessments"][0]["reasoning"] == "gerekce"
