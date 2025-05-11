#!/usr/bin/env python
"""
plot_importance.py — XGB • CatBoost • RF • DT
► python plot_importance.py                    # en yeni XGB
► python plot_importance.py --model cat --top 0
"""

import argparse, glob, os, joblib, numpy as np, matplotlib.pyplot as plt
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor

# ───────── yardımcılar ─────────
def resolve_model_path(key: str) -> str:
    if os.path.exists(key):
        return key
    cand = sorted(glob.glob(f"models/{key}_*.pkl"), reverse=True)
    if cand:
        return cand[0]
    raise FileNotFoundError(f"{key} modeli için .pkl bulunamadı.")

def get_feature_names(pipe):
    return pipe.named_steps["preproc"].get_feature_names_out()

def extract_imp(pipe):
    est = pipe.named_steps["model"]
    if isinstance(est, XGBRegressor):
        return est.feature_importances_
    if isinstance(est, CatBoostRegressor):
        return est.get_feature_importance(type="FeatureImportance")
    if isinstance(est, (RandomForestRegressor, DecisionTreeRegressor)):
        return est.feature_importances_
    raise ValueError("Desteklenmeyen model")

# ───────── çizim ─────────
def plot_bar(names, imp, out_path, top_n, label):
    mask = imp > 0                # 0'ları at
    names, imp = names[mask], imp[mask]

    idx = np.argsort(imp)[::-1]
    if top_n:
        idx = idx[:top_n]
    names, imp = names[idx], imp[idx]

    colors, heights = [], []
    for v in imp:
        if v < 0.01:
            colors.append("#9bd49b")   # açık yeşil
            heights.append(0.35)
        else:
            colors.append("#2ca02c")   # koyu yeşil
            heights.append(0.7)

    y_pos = np.arange(len(names))[::-1]
    plt.figure(figsize=(8, max(4, 0.45 * len(names))))
    for y, v, c, h in zip(y_pos, imp[::-1], colors[::-1], heights[::-1]):
        plt.barh(y, v, color=c, height=h)
        fmt = f"{v:.3f}" if v >= 0.001 else f"{v:.1e}"    # 0.001'den küçükse bilimsel
        plt.text(v * 1.05, y, fmt, va="center", fontsize=7)

    plt.yticks(y_pos, names[::-1], fontsize=8)
    plt.xscale("log")
    plt.xlabel("Importance (log scale)")
    plt.title(f"Feature Importance – Top {len(names)}  ({label.upper()})")
    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    plt.savefig(out_path, dpi=160)
    print(f"✔ Kaydedildi → {out_path}")

# ───────── main ─────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="xgb",
                    help="xgb / cat / rf / dt veya .pkl yolu")
    ap.add_argument("--out", default="feature_importance.png")
    ap.add_argument("--top", type=int, default=20,
                    help="En önemli N sütun (0=tümü)")
    args = ap.parse_args()

    path = resolve_model_path(args.model)
    pipe = joblib.load(path)
    names = get_feature_names(pipe)
    imp = extract_imp(pipe)

    plot_bar(np.array(names), imp,
             args.out,
             None if args.top == 0 else args.top,
             args.model)
