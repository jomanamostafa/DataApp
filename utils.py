"""
utils.py — Charts, Cleaning, Metrics, Statistics
Charts: Bar, Line, Scatter, Pie, Box, Histogram, Area, Heatmap, Violin
"""
import logging
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from io import BytesIO
import base64

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {"csv"}

COLORS = ["#4F46E5","#10B981","#EF4444","#F59E0B","#3B82F6","#8B5CF6","#EC4899","#14B8A6","#F97316","#06B6D4"]

PLOTLY_BASE = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(family="Segoe UI, sans-serif", size=13, color="#1e293b"),
    margin=dict(l=55, r=30, t=60, b=55),
    title_font=dict(size=15, color="#0f172a"),
    legend=dict(bgcolor="rgba(255,255,255,0.85)", bordercolor="#e2e8f0", borderwidth=1),
    xaxis=dict(showgrid=True, gridcolor="#f1f5f9", linecolor="#cbd5e1", automargin=True, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9", linecolor="#cbd5e1", automargin=True, zeroline=False),
    height=460, autosize=True,
)


# ── Validation ────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Metrics ───────────────────────────────────────────────────

def mean_squared_error(y_true, y_pred):
    return ((y_true - y_pred) ** 2).mean()

def root_mean_squared_error(y_true, y_pred):
    return mean_squared_error(y_true, y_pred) ** 0.5

def mean_absolute_error(y_true, y_pred):
    return (y_true - y_pred).abs().mean()


# ── Cleaning ──────────────────────────────────────────────────

def clean_dataframe(df: pd.DataFrame, remove_outliers: bool = True, convert_dtypes: bool = True) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(r"[\s\-\.]+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )
    before = len(df)
    df.drop_duplicates(inplace=True)

    # Fill missing values
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        else:
            df[col] = df[col].fillna("Unknown")

    # Remove outliers for numeric columns
    if remove_outliers:
        for col in df.select_dtypes(include="number").columns:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]

    # Convert data types
    if convert_dtypes:
        df = df.convert_dtypes()

    logger.info("Cleaned %d → %d rows", before, len(df))
    return df


# ── Statistics ────────────────────────────────────────────────

def calculate_statistics(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes(include="number")
    col_stats = {}

    for col in numeric.columns:
        s = numeric[col].dropna()
        if len(s) == 0:
            continue

        q1  = float(s.quantile(0.25))
        q3  = float(s.quantile(0.75))
        iqr = q3 - q1
        outliers = s[(s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)]

        skew = float(s.skew())
        if   abs(skew) < 0.5: skew_label = "Symmetric ✓"
        elif skew > 0:         skew_label = "Right-skewed →"
        else:                  skew_label = "Left-skewed ←"

        mean_val = float(s.mean())
        cv = round(s.std() / mean_val * 100, 2) if mean_val != 0 else None

        col_stats[col] = {
            "count":    int(s.count()),
            "sum":      round(float(s.sum()), 4),
            "mean":     round(mean_val, 4),
            "median":   round(float(s.median()), 4),
            "mode":     round(float(s.mode().iloc[0]), 4) if len(s.mode()) else "N/A",
            "std":      round(float(s.std()), 4),
            "variance": round(float(s.var()), 4),
            "cv_pct":   cv,
            "min":      round(float(s.min()), 4),
            "max":      round(float(s.max()), 4),
            "range":    round(float(s.max() - s.min()), 4),
            "q1":       round(q1, 4),
            "q3":       round(q3, 4),
            "iqr":      round(iqr, 4),
            "p5":       round(float(s.quantile(0.05)), 4),
            "p95":      round(float(s.quantile(0.95)), 4),
            "skewness": round(skew, 4),
            "skew_label": skew_label,
            "kurtosis": round(float(s.kurtosis()), 4),
            "outliers": int(len(outliers)),
        }

    corr = {}
    if len(numeric.columns) > 1:
        corr = numeric.corr().round(3).to_dict()

    return {"columns": col_stats, "correlation": corr}


def summarize_dataframe(df: pd.DataFrame) -> dict:
    num_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = list(df.select_dtypes(exclude="number").columns)
    return {
        "rows": len(df), "cols": len(df.columns),
        "columns": list(df.columns),
        "numeric_columns": num_cols,
        "categorical_columns": cat_cols,
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing": df.isnull().sum().to_dict(),
    }


def get_data_preview(df: pd.DataFrame, rows: int = 10) -> str:
    return df.head(rows).to_html(
        classes="table table-sm table-hover table-bordered align-middle mb-0",
        index=False, border=0,
    )


# ── Column Picker ─────────────────────────────────────────────

def _pick(df, x_col, y_col):
    num = list(df.select_dtypes(include="number").columns)
    all_c = list(df.columns)
    if not x_col or x_col not in all_c:
        x_col = all_c[0]
    if not y_col or y_col not in all_c:
        y_col = num[0] if num else all_c[min(1, len(all_c)-1)]
    return x_col, y_col


# ════════════════════════════════════════════════════════════
#  PLOTLY (interactive)
# ════════════════════════════════════════════════════════════

def generate_plotly_chart(df, chart_type, x_col=None, y_col=None):
    x_col, y_col = _pick(df, x_col, y_col)
    num_cols = list(df.select_dtypes(include="number").columns)

    if chart_type == "bar":
        fig = px.bar(df, x=x_col, y=y_col, title=f"Bar — {y_col} by {x_col}",
                     color_discrete_sequence=COLORS, text_auto=".2s")
        fig.update_traces(textposition="outside", marker_line_width=0)
        fig.update_layout(**PLOTLY_BASE)
        fig.update_xaxes(tickangle=-90)

    elif chart_type == "line":
        fig = px.line(df, x=x_col, y=y_col, title=f"Line — {y_col} over {x_col}",
                      color_discrete_sequence=COLORS, markers=True)
        fig.update_traces(line_width=2.5, marker_size=6)
        fig.update_layout(**PLOTLY_BASE)
        fig.update_xaxes(tickangle=-90)

    elif chart_type == "scatter":
        kw = {"trendline": "ols"} if pd.api.types.is_numeric_dtype(df[x_col]) else {}
        fig = px.scatter(df, x=x_col, y=y_col, title=f"Scatter — {x_col} vs {y_col}",
                         color_discrete_sequence=COLORS, opacity=0.72, **kw)
        fig.update_traces(marker_size=8, marker_line_width=0.5, marker_line_color="white")
        fig.update_layout(**PLOTLY_BASE)
        fig.update_xaxes(tickangle=-90)

    elif chart_type == "pie":
        src = x_col if df[x_col].dtype == object else y_col
        vc  = df[src].value_counts().head(14).reset_index()
        vc.columns = ["label", "value"]
        fig = px.pie(vc, names="label", values="value",
                     title=f"Pie — {src} Distribution",
                     color_discrete_sequence=COLORS, hole=0.35)
        fig.update_traces(textposition="inside", textinfo="percent+label",
                          pull=[0.03]*len(vc))
        base = {k:v for k,v in PLOTLY_BASE.items() if k not in ("xaxis","yaxis")}
        fig.update_layout(**base)

    elif chart_type == "box":
        cols = num_cols[:10]
        fig = go.Figure()
        for i, c in enumerate(cols):
            fig.add_trace(go.Box(y=df[c], name=c, marker_color=COLORS[i % len(COLORS)],
                                 boxmean="sd", jitter=0.35, pointpos=-1.6,
                                 marker_size=3))
        fig.update_layout(title="Box Plot — Numeric Distributions",
                          showlegend=False, **PLOTLY_BASE)

    elif chart_type == "histogram":
        fig = px.histogram(df, x=y_col, nbins=35,
                           title=f"Histogram — {y_col}",
                           color_discrete_sequence=COLORS,
                           marginal="box", opacity=0.85)
        fig.update_layout(**PLOTLY_BASE)

    elif chart_type == "area":
        fig = px.area(df, x=x_col, y=y_col,
                      title=f"Area — {y_col} over {x_col}",
                      color_discrete_sequence=COLORS)
        fig.update_layout(**PLOTLY_BASE)
        fig.update_xaxes(tickangle=-90)

    elif chart_type == "heatmap":
        if len(num_cols) < 2:
            raise ValueError("Need ≥ 2 numeric columns for heatmap.")
        corr = df[num_cols].corr().round(2)
        fig = px.imshow(corr, text_auto=True, title="Correlation Heatmap",
                        color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto")
        base = {k:v for k,v in PLOTLY_BASE.items() if k not in ("xaxis","yaxis")}
        fig.update_layout(**base)

    elif chart_type == "violin":
        cols = num_cols[:8]
        fig = go.Figure()
        for i, c in enumerate(cols):
            fig.add_trace(go.Violin(y=df[c], name=c,
                                    box_visible=True, meanline_visible=True,
                                    fillcolor=COLORS[i % len(COLORS)],
                                    line_color=COLORS[i % len(COLORS)],
                                    opacity=0.72))
        fig.update_layout(title="Violin Plot — Distributions",
                          showlegend=False, **PLOTLY_BASE)

    else:
        raise ValueError(f"Unknown chart type: {chart_type}")

    return pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                       config={"responsive": True, "displayModeBar": True,
                               "toImageButtonOptions": {"format": "png", "scale": 2}})


# ════════════════════════════════════════════════════════════
#  MATPLOTLIB (static PNG)
# ════════════════════════════════════════════════════════════

def _save_fig(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

MPL_RC = {
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": "#cbd5e1", "axes.grid": True,
    "grid.color": "#f1f5f9", "grid.linestyle": "--", "grid.alpha": 0.7,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlepad": 12,
    "axes.labelsize": 11, "axes.labelpad": 7,
    "xtick.labelsize": 9, "ytick.labelsize": 9,
}

def generate_matplotlib_chart(df, chart_type, x_col=None, y_col=None):
    x_col, y_col = _pick(df, x_col, y_col)
    num_cols = list(df.select_dtypes(include="number").columns)

    with plt.rc_context(MPL_RC):

        if chart_type == "bar":
            fig, ax = plt.subplots(figsize=(12, 5))
            vals = df[y_col].values
            xs   = range(len(vals))
            bars = ax.bar(xs, vals, color=COLORS[0], edgecolor="white", width=0.65)
            ax.set_xticks(xs)
            ax.set_xticklabels(df[x_col].astype(str), rotation=90, ha="center")
            ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
            ax.set_xlabel(x_col); ax.set_ylabel(y_col)
            ax.set_title(f"Bar Chart — {y_col}")
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v,_: f"{v:,.1f}"))

        elif chart_type == "line":
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(df[x_col], df[y_col], color=COLORS[0], lw=2.5,
                    marker="o", ms=5, mfc="white", mew=2)
            ax.fill_between(df[x_col], df[y_col], alpha=0.1, color=COLORS[0])
            ax.set_xlabel(x_col); ax.set_ylabel(y_col)
            ax.set_title(f"Line Chart — {y_col}")
            if df[x_col].dtype == object or len(df[x_col].unique()) > 10:
                ax.tick_params(axis='x', rotation=90)

        elif chart_type == "scatter":
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(df[x_col], df[y_col], color=COLORS[0],
                       alpha=0.65, edgecolors="white", lw=0.5, s=65)
            if pd.api.types.is_numeric_dtype(df[x_col]) and HAS_SCIPY:
                m, b, r, _, _ = scipy_stats.linregress(df[x_col].dropna(), df[y_col].dropna())
                xs = np.linspace(df[x_col].min(), df[x_col].max(), 200)
                ax.plot(xs, m*xs+b, color=COLORS[2], lw=2, ls="--",
                        label=f"Trend  R²={r**2:.3f}")
                ax.legend()
            ax.set_xlabel(x_col); ax.set_ylabel(y_col)
            ax.set_title(f"Scatter — {x_col} vs {y_col}")
            if df[x_col].dtype == object or len(df[x_col].unique()) > 10:
                ax.tick_params(axis='x', rotation=90)

        elif chart_type == "pie":
            fig, ax = plt.subplots(figsize=(8, 7))
            src = x_col if df[x_col].dtype == object else y_col
            vc  = df[src].value_counts().head(10)
            wedges, texts, auto = ax.pie(
                vc.values, labels=vc.index, autopct="%1.1f%%",
                colors=COLORS[:len(vc)], startangle=140, pctdistance=0.82,
                wedgeprops=dict(width=0.6, edgecolor="white", lw=2))
            for t in auto: t.set_fontsize(9)
            ax.set_title(f"Pie — {src}")

        elif chart_type == "box":
            cols = num_cols[:10]
            fig, ax = plt.subplots(figsize=(max(8, len(cols)*1.8), 6))
            bp = ax.boxplot([df[c].dropna() for c in cols], patch_artist=True,
                            medianprops=dict(color="white", lw=2.5),
                            whiskerprops=dict(lw=1.5), capprops=dict(lw=1.5),
                            flierprops=dict(marker="o", ms=4, alpha=0.5))
            for patch, col in zip(bp["boxes"], COLORS):
                patch.set_facecolor(col); patch.set_alpha(0.78)
            ax.set_xticklabels(cols, rotation=90, ha="center")
            ax.set_title("Box Plot — Numeric Distributions")

        elif chart_type == "histogram":
            fig, ax = plt.subplots(figsize=(11, 5))
            ax.hist(df[y_col].dropna(), bins=30, color=COLORS[0],
                    edgecolor="white", lw=0.4, alpha=0.85)
            mu = df[y_col].mean(); sd = df[y_col].std()
            ax.axvline(mu,    color=COLORS[2], lw=2,   ls="--", label=f"Mean {mu:.2f}")
            ax.axvline(mu+sd, color=COLORS[3], lw=1.5, ls=":",  label=f"+1σ {mu+sd:.2f}")
            ax.axvline(mu-sd, color=COLORS[3], lw=1.5, ls=":",  label=f"-1σ {mu-sd:.2f}")
            ax.legend()
            ax.set_xlabel(y_col); ax.set_ylabel("Frequency")
            ax.set_title(f"Histogram — {y_col}")

        elif chart_type == "area":
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.fill_between(range(len(df)), df[y_col], alpha=0.45, color=COLORS[0])
            ax.plot(range(len(df)), df[y_col], color=COLORS[0], lw=2.2)
            ax.set_xlabel(x_col); ax.set_ylabel(y_col)
            ax.set_title(f"Area Chart — {y_col}")
            if df[x_col].dtype == object or len(df[x_col].unique()) > 10:
                ax.set_xticks(range(len(df)))
                ax.set_xticklabels(df[x_col].astype(str), rotation=90, ha="center")

        elif chart_type == "heatmap":
            if len(num_cols) < 2:
                raise ValueError("Need ≥ 2 numeric columns for heatmap.")
            corr = df[num_cols].corr()
            n = len(corr)
            fig, ax = plt.subplots(figsize=(max(7, n), max(5, n-1)))
            im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
            plt.colorbar(im, ax=ax, fraction=0.04, pad=0.03)
            ax.set_xticks(range(n)); ax.set_yticks(range(n))
            ax.set_xticklabels(corr.columns, rotation=90, ha="center", fontsize=9)
            ax.set_yticklabels(corr.columns, fontsize=9)
            for i in range(n):
                for j in range(n):
                    ax.text(j, i, f"{corr.iloc[i,j]:.2f}", ha="center", va="center",
                            fontsize=8, color="white" if abs(corr.iloc[i,j]) > 0.5 else "#1e293b")
            ax.set_title("Correlation Heatmap")

        elif chart_type == "violin":
            cols = num_cols[:8]
            fig, ax = plt.subplots(figsize=(max(8, len(cols)*2), 6))
            parts = ax.violinplot([df[c].dropna() for c in cols],
                                   positions=range(1, len(cols)+1),
                                   showmeans=True, showmedians=True)
            for i, pc in enumerate(parts["bodies"]):
                pc.set_facecolor(COLORS[i % len(COLORS)]); pc.set_alpha(0.72)
            ax.set_xticks(range(1, len(cols)+1))
            ax.set_xticklabels(cols, rotation=90, ha="center")
            ax.set_title("Violin Plot — Distributions")

        else:
            raise ValueError(f"Unknown chart type: {chart_type}")

        return _save_fig(fig)
