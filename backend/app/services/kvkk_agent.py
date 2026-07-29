"""KVKK risk analiz ajanı (SCRUM-24).

Üç ayrı muhakeme adımından oluşan, LangGraph StateGraph ile bağlanmış bir
pipeline. Tek bir "veriyi al, rapor yaz" LLM çağrısı DEĞİL:

1. analyze_columns  - saf Python. detection.py + anonymization.py'nin
   çıktısını (detections, actions) birleştirir; hangi quasi-identifier
   kolonların birlikte "kept" bırakıldığını (kombinasyon riski adayı) bulur;
   anonimleştirilmiş DataFrame üzerinde JENERİK veri kalitesi taraması yapar
   (yüksek korelasyon, dağılımda capping/censoring belirtisi). Belirli bir
   veri setine (örn. Kaggle Bank Churn) özel kolon adı hiçbir yerde
   hardcode edilmez - taramalar herhangi bir CSV'de çalışır.

2. score_risks - saf Python. Kategori + sensitivity + uygulanan action'a
   göre ağırlıklı, deterministik bir risk skoru üretir. Bu adımda LLM YOK;
   skorların her çalıştırmada aynı çıkması isteniyor.

3. generate_narrative - LLM. Girdisi zaten yapılandırılmış (adım 1+2
   çıktısı); görevi sadece gerekçe/öneri metni üretmek, skorları icat etmek
   değil. LLM çağrısı başarısız olursa (anahtar yok, timeout, kota, bozuk
   yanıt) kural tabanlı şablona düşer - synthetic.py'deki CTGAN->Faker
   fallback deseninin aynısı.

Üç adım da (analyze_columns, score_risks, generate_narrative) bu modülün
dışından, dosya sistemine veya LLM'e dokunmadan tek başına çağrılıp test
edilebilir. run_kvkk_agent bunları LangGraph ile bağlayan tek giriş
noktasıdır ve agent_steps trace'ini üretir.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

LEGAL_NOTICE = (
    "Bu rapor hukuki danışmanlık değildir, teknik risk analizi amacıyla "
    "oluşturulmuştur."
)

# category -> temel risk ağırlığı (0-100). detection.py'deki kategori
# isimleriyle birebir eşleşmeli (lowercase, snake_case).
_BASE_RISK_WEIGHTS: dict[str, int] = {
    "national_id": 95,
    "iban": 85,
    "card_number": 85,
    "address": 70,
    "name": 65,
    "email": 60,
    "phone": 55,
    "birthdate": 45,
    "id": 40,
    "age": 25,
    "location": 30,
    "gender": 15,
}
_DEFAULT_RISK_WEIGHT = 50

_ACTION_MULTIPLIER: dict[str, float] = {
    "kept": 1.0,
    "masked": 0.35,
    "hashed": 0.2,
}

_CORR_THRESHOLD = 0.99
_CAPPING_MIN_UNIQUE = 20
_CAPPING_MIN_SHARE = 0.02


# ── Veri sözleşmeleri ────────────────────────────────────────────────────────


class ColumnAssessment(TypedDict):
    column: str
    category: str
    sensitivity: str
    applied_action: str


class CombinationCandidate(TypedDict):
    columns: list[str]
    risk: str


class ColumnAnalysis(TypedDict):
    columns: list[ColumnAssessment]
    combination_candidates: list[CombinationCandidate]
    data_quality_notes: list[str]
    summary: str


class RiskedColumn(ColumnAssessment):
    risk_score: int


class RiskedCombination(CombinationCandidate):
    risk_score: int


class RiskScoring(TypedDict):
    columns: list[RiskedColumn]
    combination_risks: list[RiskedCombination]
    overall_risk_score: int
    risk_level: str
    summary: str


class CombinationNarrative(TypedDict):
    columns: list[str]
    risk: str
    reasoning: str


class ReportNarrative(TypedDict):
    column_reasonings: dict[str, str]
    combination_reasonings: list[CombinationNarrative]
    recommendations: list[str]
    generation_method: str  # "llm" | "rule_based_fallback"
    fallback_reason: str | None
    summary: str


class NarrativeLLM(Protocol):
    """generate_narrative'in beklediği minimum arayüz.

    Gerçek kullanımda bir LangChain chat model (ör. ChatGoogleGenerativeAI)
    geçilir. Testte bu protokolü karşılayan basit bir sahte (fake) obje de
    geçilebilir - gerçek bir API anahtarı gerekmez.
    """

    def invoke(self, prompt: str): ...


class KvkkAgentState(TypedDict):
    detections: list[dict]
    actions: list[dict]
    column_analysis: ColumnAnalysis | None
    risk_scoring: RiskScoring | None
    narrative: ReportNarrative | None


# ── Adım 1: kolon analizi (saf Python) ──────────────────────────────────────


def _detect_correlated_pairs(
    df: pd.DataFrame, threshold: float = _CORR_THRESHOLD
) -> list[tuple[str, str, float]]:
    """Sayısal kolonlar arasında aşırı yüksek korelasyon çiftlerini bulur.

    Bu bir KVKK riski değil, veri tekrarı/sızıntı belirtisidir (ör. aynı
    bilginin iki farklı kolonda kodlanması). Kolon adına bakmaz, herhangi
    bir veri setinde çalışır.
    """
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return []
    corr = numeric_df.corr().abs()
    cols = corr.columns
    pairs: list[tuple[str, str, float]] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = corr.iloc[i, j]
            if pd.notna(value) and value >= threshold:
                pairs.append((str(cols[i]), str(cols[j]), float(value)))
    return pairs


def _detect_capping(series: pd.Series) -> bool:
    """Bir sayısal kolonun sınırda (max/min) anormal yığılıp yığılmadığını
    (capping/censoring) jenerik bir heuristikle tahmin eder.

    Mantık: kolon sürekli görünüyorsa (yeterince farklı değer var) ve en sık
    görülen değer kolonun uç noktasıysa (max ya da min) ve bu değerin payı
    "uniform dağılımda beklenenin" belirgin üzerindeyse, muhtemelen bir üst/
    alt sınır uygulanmış demektir.
    """
    s = series.dropna()
    if s.empty or s.nunique() < _CAPPING_MIN_UNIQUE:
        return False
    counts = s.value_counts()
    top_value = counts.index[0]
    top_share = counts.iloc[0] / len(s)
    expected_share = 1 / s.nunique()
    is_extreme = top_value == s.max() or top_value == s.min()
    return bool(is_extreme and top_share > max(_CAPPING_MIN_SHARE, expected_share * 5))


def analyze_columns(
    detections: list[dict],
    actions: list[dict],
    df: pd.DataFrame,
) -> ColumnAnalysis:
    """Adım 1: detections + actions birleştirir, kombinasyon riski adaylarını
    ve jenerik veri kalitesi bulgularını çıkarır. LLM kullanmaz.
    """
    action_by_column = {a["column"]: a["action"] for a in actions}

    columns: list[ColumnAssessment] = [
        {
            "column": d["column"],
            "category": d["category"],
            "sensitivity": d["sensitivity"],
            "applied_action": action_by_column.get(d["column"], "kept"),
        }
        for d in detections
    ]

    kept_quasi = [
        c["column"] for c in columns if c["sensitivity"] == "quasi" and c["applied_action"] == "kept"
    ]
    combination_candidates: list[CombinationCandidate] = []
    if len(kept_quasi) >= 2:
        combination_candidates.append({"columns": kept_quasi, "risk": "Yeniden kimliklendirme"})

    data_quality_notes: list[str] = []
    for col_a, col_b, corr_value in _detect_correlated_pairs(df):
        data_quality_notes.append(
            f"{col_a} ve {col_b} kolonları arasında {corr_value:.2f} korelasyon var; "
            "bu bir KVKK riski değil, olası veri tekrarı/sızıntı sorunudur."
        )
    for col in df.select_dtypes(include="number").columns:
        if _detect_capping(df[col]):
            data_quality_notes.append(
                f"{col} kolonunun dağılımında sınırda (muhtemelen üst sınır) "
                "anormal bir yığılma var; bu bir veri toplama artefaktı olabilir."
            )

    direct_count = sum(1 for c in columns if c["sensitivity"] == "direct")
    summary = (
        f"{len(columns)} hassas kolon sınıflandırıldı, {direct_count} doğrudan tanımlayıcı bulundu, "
        f"{len(combination_candidates)} kombinasyon riski adayı ve "
        f"{len(data_quality_notes)} veri kalitesi bulgusu tespit edildi."
    )

    return {
        "columns": columns,
        "combination_candidates": combination_candidates,
        "data_quality_notes": data_quality_notes,
        "summary": summary,
    }


# ── Adım 2: risk skorlama (saf Python) ──────────────────────────────────────


def score_risks(column_analysis: ColumnAnalysis) -> RiskScoring:
    """Adım 2: kategori/sensitivity/action ağırlıklarıyla deterministik risk
    skoru üretir. LLM kullanmaz; aynı girdi her zaman aynı skoru verir.
    """
    scored_columns: list[RiskedColumn] = []
    for c in column_analysis["columns"]:
        base = _BASE_RISK_WEIGHTS.get(c["category"], _DEFAULT_RISK_WEIGHT)
        multiplier = _ACTION_MULTIPLIER.get(c["applied_action"], 1.0)
        scored_columns.append({**c, "risk_score": round(base * multiplier)})  # type: ignore[typeddict-item]

    combination_risks: list[RiskedCombination] = []
    for combo in column_analysis["combination_candidates"]:
        n = len(combo["columns"])
        score = min(90, 55 + (n - 2) * 15)
        combination_risks.append({**combo, "risk_score": score})  # type: ignore[typeddict-item]

    if scored_columns:
        overall = round(sum(c["risk_score"] for c in scored_columns) / len(scored_columns))
    else:
        overall = 0
    if combination_risks:
        overall = min(100, overall + max(cr["risk_score"] for cr in combination_risks) // 4)

    if overall >= 70:
        risk_level = "high"
    elif overall >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    summary = f"Ağırlıklı skorlama ile toplam risk {overall}/100 hesaplandı ({risk_level})."

    return {
        "columns": scored_columns,
        "combination_risks": combination_risks,
        "overall_risk_score": overall,
        "risk_level": risk_level,
        "summary": summary,
    }


# ── Adım 3: rapor üretimi (LLM, kural tabanlı yedekli) ──────────────────────

_NARRATIVE_PROMPT_TEMPLATE = """Sen bir KVKK (Türkiye kişisel verilerin korunması kanunu) teknik risk \
analistisin. Aşağıda bir CSV veri setinin anonimleştirme analizi ve \
deterministik risk skorları var. Görevin SADECE gerekçe ve öneri metni \
üretmek; risk skorlarını DEĞİŞTİRME.

Kurallar:
- Kesin hukuki hüküm cümleleri kurma (ör. "KVKK'ya aykırıdır"). Teknik risk \
dili kullan (ör. "yeniden kimliklendirme riski taşır").
- Hassas veri tespit edilmemişse risk uydurma; tespitin regex ve kolon adı \
analiziyle sınırlı olduğunu, serbest metin alanlarında gözden kaçan veri \
olabileceğini belirt.
- Veri kalitesi notlarını (korelasyon/capping) KVKK riskiyle karıştırma.
- SADECE aşağıdaki JSON şemasıyla yanıt ver, başka hiçbir metin, açıklama \
veya kod bloğu işareti ekleme:

{{"column_reasonings": {{"<kolon_adi>": "<1-2 cumlelik gerekce>"}}, \
"combination_reasonings": [{{"columns": ["<kolon1>", "<kolon2>"], "risk": \
"<kisa risk adi>", "reasoning": "<gerekce>"}}], "recommendations": \
["<oneri1>"]}}

Girdi:
{payload}
"""

_TEMPLATE_REASONING: dict[tuple[str, str], str] = {
    ("direct", "kept"): (
        "Doğrudan tanımlayıcı; herhangi bir anonimleştirme uygulanmamış, "
        "kişiyi doğrudan ifşa etme riski taşıyor."
    ),
    ("direct", "masked"): (
        "Doğrudan tanımlayıcı; maskeleme uygulanmış olsa da alan adı ve "
        "kısmi değerler üzerinden çıkarım riski sürüyor."
    ),
    ("direct", "hashed"): (
        "Doğrudan tanımlayıcı; hash'lenerek geri döndürülemez hale "
        "getirilmiş, kayıtlar arası eşleşme (joinability) hâlâ mümkün."
    ),
    ("quasi", "kept"): (
        "Dolaylı tanımlayıcı; tek başına düşük risklidir, diğer dolaylı "
        "tanımlayıcılarla birleşince yeniden kimliklendirme riski "
        "oluşturabilir."
    ),
}


def _template_reasoning(col: RiskedColumn) -> str:
    key = (col["sensitivity"], col["applied_action"])
    return _TEMPLATE_REASONING.get(
        key,
        f"{col['category']} kategorisinde, {col['applied_action']} işlemi uygulanmış bir kolon.",
    )


def _template_recommendations(risk_scoring: RiskScoring) -> list[str]:
    recs = [
        (
            f"{', '.join(combo['columns'])} kolonlarını genelleştirin "
            "(ör. yaşı aralığa, konumu bölgeye çevirin) veya k-anonimlik uygulayın."
        )
        for combo in risk_scoring["combination_risks"]
    ]
    if not risk_scoring["columns"] and not risk_scoring["combination_risks"]:
        recs.append(
            "Bu veri setinde doğrudan tanımlayıcı tespit edilmedi. Tespit yalnızca "
            "kolon adı ve regex tabanlı içerik taramasıyla sınırlı; serbest metin "
            "alanlarında gözden kaçan veri olabilir."
        )
    return recs


def _generate_narrative_fallback(
    column_analysis: ColumnAnalysis,
    risk_scoring: RiskScoring,
    fallback_reason: str,
) -> ReportNarrative:
    column_reasonings = {c["column"]: _template_reasoning(c) for c in risk_scoring["columns"]}
    combination_reasonings: list[CombinationNarrative] = [
        {
            "columns": combo["columns"],
            "risk": combo["risk"],
            "reasoning": (
                f"{', '.join(combo['columns'])} kolonları birlikte kullanıldığında "
                "yeniden kimliklendirme riski oluşturabilir; tek tek düşük riskli "
                "görünseler de kombinasyon halinde küçük gruplarda kişiyi "
                "tekilleştirebilirler."
            ),
        }
        for combo in risk_scoring["combination_risks"]
    ]
    return {
        "column_reasonings": column_reasonings,
        "combination_reasonings": combination_reasonings,
        "recommendations": _template_recommendations(risk_scoring),
        "generation_method": "rule_based_fallback",
        "fallback_reason": fallback_reason,
        "summary": f"Şablon tabanlı yedek modda çalıştı: {fallback_reason}",
    }


def _extract_text(content) -> str:
    """response.content her zaman düz string olmuyor.

    Bazı modeller (ör. gemini-flash-latest) content'i "content blocks"
    listesi olarak dönüyor: [{"type": "text", "text": "..."}]. Burada
    hem düz string hem de bu liste formatını tek bir metne indirgiyoruz.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _parse_llm_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        first_newline = text.find("\n")
        if first_newline != -1 and text[:first_newline].strip().lower() in ("json", ""):
            text = text[first_newline + 1 :]
    return json.loads(text)


def _generate_narrative_llm(
    column_analysis: ColumnAnalysis,
    risk_scoring: RiskScoring,
    llm: NarrativeLLM,
) -> ReportNarrative:
    payload = json.dumps(
        {
            "columns": risk_scoring["columns"],
            "combination_candidates": column_analysis["combination_candidates"],
            "data_quality_notes": column_analysis["data_quality_notes"],
        },
        ensure_ascii=False,
    )
    prompt = _NARRATIVE_PROMPT_TEMPLATE.format(payload=payload)
    response = llm.invoke(prompt)
    raw_text = _extract_text(getattr(response, "content", response))
    parsed = _parse_llm_json(raw_text)

    column_reasonings = parsed["column_reasonings"]
    combination_reasonings = parsed.get("combination_reasonings", [])
    recommendations = parsed.get("recommendations", [])

    return {
        "column_reasonings": column_reasonings,
        "combination_reasonings": combination_reasonings,
        "recommendations": recommendations,
        "generation_method": "llm",
        "fallback_reason": None,
        "summary": f"{len(column_reasonings)} kolon için LLM gerekçesi üretildi.",
    }


def generate_narrative(
    column_analysis: ColumnAnalysis,
    risk_scoring: RiskScoring,
    llm: NarrativeLLM | None,
) -> ReportNarrative:
    """Adım 3: LLM ile gerekçe/öneri üretir; LLM yoksa veya çağrı/parse
    başarısız olursa kural tabanlı şablona düşer. Asla exception fırlatmaz -
    bu fonksiyonun sözleşmesi budur, çağıran taraf hep geçerli bir
    ReportNarrative alır.
    """
    if llm is None:
        return _generate_narrative_fallback(
            column_analysis, risk_scoring, fallback_reason="LLM istemcisi verilmedi (API anahtarı yok)."
        )
    try:
        return _generate_narrative_llm(column_analysis, risk_scoring, llm)
    except Exception as exc:  # noqa: BLE001 - kasıtlı geniş except: LLM sağlayıcıya
        # göre farklı exception hiyerarşileri fırlatır (google/anthropic/openai);
        # amaç hangi hata olursa olsun demoyu ayakta tutmak.
        logger.warning("LLM rapor üretimi başarısız oldu, şablona düşülüyor: %s", exc)
        return _generate_narrative_fallback(column_analysis, risk_scoring, fallback_reason=str(exc))


# ── Orkestrasyon: LangGraph StateGraph ───────────────────────────────────────


def _build_agent_graph(df: pd.DataFrame, llm: NarrativeLLM | None):
    """df ve llm, node'lara closure ile bağlanır (graph state'i JSON'a
    yakın ve sade kalır - DataFrame/LLM istemcisi gibi serileştirilemeyen
    nesneleri state şemasına sokmuyoruz).
    """

    def node_column_analysis(state: KvkkAgentState) -> dict:
        return {"column_analysis": analyze_columns(state["detections"], state["actions"], df)}

    def node_risk_scoring(state: KvkkAgentState) -> dict:
        assert state["column_analysis"] is not None
        return {"risk_scoring": score_risks(state["column_analysis"])}

    def node_report_generation(state: KvkkAgentState) -> dict:
        assert state["column_analysis"] is not None and state["risk_scoring"] is not None
        return {"narrative": generate_narrative(state["column_analysis"], state["risk_scoring"], llm)}

    graph = StateGraph(KvkkAgentState)
    graph.add_node("column_analysis", node_column_analysis)
    graph.add_node("risk_scoring", node_risk_scoring)
    graph.add_node("report_generation", node_report_generation)
    graph.add_edge(START, "column_analysis")
    graph.add_edge("column_analysis", "risk_scoring")
    graph.add_edge("risk_scoring", "report_generation")
    graph.add_edge("report_generation", END)
    return graph.compile()


def run_kvkk_agent(
    file_id: str,
    detections: list[dict],
    actions: list[dict],
    df: pd.DataFrame,
    llm: NarrativeLLM | None = None,
) -> dict:
    """AegisAI KVKK risk ajanının tek giriş noktası (SCRUM-25 router'ının
    çağıracağı fonksiyon budur).

    Parametreler:
    - file_id: raporun ait olduğu (orijinal) dosya kimliği.
    - detections, actions: detect_sensitive_columns() ve
      anonymize_dataframe()'in çıktısı (anonymize.py router'ıyla aynı
      fonksiyonlar tekrar çağrılarak elde edilir).
    - df: anonimleştirilmiş DataFrame (veri kalitesi taraması için).
    - llm: opsiyonel bir chat model. None ise doğrudan kural tabanlı
      şablonla rapor üretilir (API anahtarı yokken de endpoint çalışır).

    Dönen dict, POST /api/kvkk-report/{file_id} yanıt şemasıyla birebir
    eşleşir (agent_steps dahil).
    """
    graph = _build_agent_graph(df, llm)
    result = graph.invoke(
        {
            "detections": detections,
            "actions": actions,
            "column_analysis": None,
            "risk_scoring": None,
            "narrative": None,
        }
    )

    column_analysis: ColumnAnalysis = result["column_analysis"]
    risk_scoring: RiskScoring = result["risk_scoring"]
    narrative: ReportNarrative = result["narrative"]

    reasoning_by_combo = {
        tuple(cr["columns"]): cr["reasoning"] for cr in narrative["combination_reasonings"]
    }

    column_assessments = [
        {
            "column": c["column"],
            "category": c["category"],
            "sensitivity": c["sensitivity"],
            "applied_action": c["applied_action"],
            "risk_score": c["risk_score"],
            "reasoning": narrative["column_reasonings"].get(c["column"], ""),
        }
        for c in risk_scoring["columns"]
    ]

    combination_risks = [
        {
            "columns": cr["columns"],
            "risk": cr["risk"],
            "reasoning": reasoning_by_combo.get(tuple(cr["columns"]), ""),
        }
        for cr in risk_scoring["combination_risks"]
    ]

    return {
        "file_id": file_id,
        "overall_risk_score": risk_scoring["overall_risk_score"],
        "risk_level": risk_scoring["risk_level"],
        "column_assessments": column_assessments,
        "combination_risks": combination_risks,
        "data_quality_notes": column_analysis["data_quality_notes"],
        "recommendations": narrative["recommendations"],
        "agent_steps": [
            {"step": "column_analysis", "summary": column_analysis["summary"]},
            {"step": "risk_scoring", "summary": risk_scoring["summary"]},
            {"step": "report_generation", "summary": narrative["summary"]},
        ],
        "legal_notice": LEGAL_NOTICE,
    }
