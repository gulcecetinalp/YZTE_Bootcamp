"""Orijinal ↔ sentetik veri karşılaştırması: özet istatistikler + grafikler."""

from __future__ import annotations

import base64
import io
import logging

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

logger = logging.getLogger(__name__)

MAX_NUMERIC_CHARTS = 8
MAX_CATEGORICAL_CHARTS = 8
TOP_CATEGORIES = 10


def compute_stats(original: pd.DataFrame, synthetic: pd.DataFrame) -> dict:
    stats: dict = {}
    for col in original.columns:
        col_stats: dict = {"dtype": str(original[col].dtype)}

        if pd.api.types.is_numeric_dtype(original[col]):
            for label, df in [("original", original), ("synthetic", synthetic)]:
                if col in df.columns:
                    col_stats[label] = {
                        "mean": round(float(df[col].mean()), 4),
                        "std": round(float(df[col].std()), 4),
                        "min": round(float(df[col].min()), 4),
                        "max": round(float(df[col].max()), 4),
                    }
            col_stats["similarity"] = _mean_similarity(col_stats)
        else:
            for label, df in [("original", original), ("synthetic", synthetic)]:
                if col in df.columns:
                    vc = df[col].astype(str).value_counts(normalize=True)
                    col_stats[label] = {
                        "unique": int(df[col].nunique()),
                        "top": str(vc.index[0]) if not vc.empty else None,
                        "top_freq": round(float(vc.iloc[0]), 4) if not vc.empty else None,
                    }

        stats[col] = col_stats
    return stats


def _mean_similarity(col_stats: dict) -> float | None:
    orig = col_stats.get("original")
    syn = col_stats.get("synthetic")
    if not orig or not syn:
        return None
    o_mean, s_mean = orig["mean"], syn["mean"]
    diff = abs(o_mean - s_mean) / (abs(o_mean) + 1e-9)
    return round(max(0.0, 1.0 - min(1.0, diff)), 4)


def build_comparison_charts(original: pd.DataFrame, synthetic: pd.DataFrame) -> dict[str, str]:
    charts: dict[str, str] = {}

    numeric_cols = [c for c in original.columns if pd.api.types.is_numeric_dtype(original[c])]
    categorical_cols = [c for c in original.columns if c not in numeric_cols]

    if len(numeric_cols) >= 2:
        try:
            charts["correlation"] = _correlation_chart(original, synthetic, numeric_cols)
        except Exception as exc:
            logger.warning("Korelasyon grafiği üretilemedi: %s", exc)

    if len(numeric_cols) > MAX_NUMERIC_CHARTS:
        logger.info("Sayısal kolon limiti aşıldı (%d), ilk %d çiziliyor.", len(numeric_cols), MAX_NUMERIC_CHARTS)
    for col in numeric_cols[:MAX_NUMERIC_CHARTS]:
        try:
            charts[f"dist__{col}"] = _distribution_chart(original, synthetic, col)
        except Exception as exc:
            logger.warning("'%s' dağılım grafiği üretilemedi: %s", col, exc)

    if len(categorical_cols) > MAX_CATEGORICAL_CHARTS:
        logger.info("Kategorik kolon limiti aşıldı (%d), ilk %d çiziliyor.", len(categorical_cols), MAX_CATEGORICAL_CHARTS)
    for col in categorical_cols[:MAX_CATEGORICAL_CHARTS]:
        try:
            charts[f"count__{col}"] = _count_chart(original, synthetic, col)
        except Exception as exc:
            logger.warning("'%s' frekans grafiği üretilemedi: %s", col, exc)

    return charts


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _correlation_chart(original: pd.DataFrame, synthetic: pd.DataFrame, numeric_cols: list[str]) -> str:
    syn_cols = [c for c in numeric_cols if c in synthetic.columns]
    orig_corr = original[numeric_cols].corr()
    syn_corr = synthetic[syn_cols].corr()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, corr, title in [(axes[0], orig_corr, "Orijinal"), (axes[1], syn_corr, "Sentetik")]:
        sns.heatmap(corr, ax=ax, cmap="coolwarm", vmin=-1, vmax=1,
                    annot=True, fmt=".2f", annot_kws={"size": 7}, cbar=True)
        ax.set_title(f"{title} korelasyon", fontsize=11)
        ax.tick_params(labelsize=8)
    fig.suptitle("Korelasyon Matrisi Karşılaştırması", fontsize=13)
    return _fig_to_base64(fig)


def _distribution_chart(original: pd.DataFrame, synthetic: pd.DataFrame, col: str) -> str:
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.histplot(original[col].dropna(), ax=ax, color="#10b981", label="Orijinal",
                 stat="density", kde=True, alpha=0.45, bins=30)
    if col in synthetic.columns:
        sns.histplot(synthetic[col].dropna(), ax=ax, color="#0ea5e9", label="Sentetik",
                     stat="density", kde=True, alpha=0.45, bins=30)
    ax.set_title(f"{col} dağılımı", fontsize=12)
    ax.set_xlabel(col)
    ax.set_ylabel("Yoğunluk")
    ax.legend()
    return _fig_to_base64(fig)


def _count_chart(original: pd.DataFrame, synthetic: pd.DataFrame, col: str) -> str:
    orig_freq = original[col].astype(str).value_counts(normalize=True)
    top_categories = list(orig_freq.head(TOP_CATEGORIES).index)
    syn_freq = (
        synthetic[col].astype(str).value_counts(normalize=True)
        if col in synthetic.columns else pd.Series(dtype=float)
    )

    plot_df = pd.DataFrame({
        "Kategori": top_categories * 2,
        "Frekans": (
            [round(float(orig_freq.get(c, 0.0)), 4) for c in top_categories]
            + [round(float(syn_freq.get(c, 0.0)), 4) for c in top_categories]
        ),
        "Kaynak": ["Orijinal"] * len(top_categories) + ["Sentetik"] * len(top_categories),
    })

    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(data=plot_df, x="Kategori", y="Frekans", hue="Kaynak", ax=ax,
                palette={"Orijinal": "#10b981", "Sentetik": "#0ea5e9"})
    ax.set_title(f"{col} frekans karşılaştırması", fontsize=12)
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.legend(title=None)
    return _fig_to_base64(fig)
