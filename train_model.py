#!/usr/bin/env python3
# train_model.py
"""
Komut satırı:
    python train_model.py --model xgb      # (varsayılan) XGBoost
    python train_model.py --model cat      # CatBoost
    python train_model.py --model dt       # Decision Tree
    python train_model.py --model rf       # Random Forest
    python train_model.py --model dummy    # Basit ortalama
"""

import os
import csv
import json
import argparse
from datetime import datetime

import joblib
import pandas as pd
from sqlalchemy import create_engine

from app import app, db

# ────────────────────────────────────
# Sklearn + Boosting kütüphaneleri
# ────────────────────────────────────
from sklearn.model_selection import cross_val_score, KFold
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder

from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor

from tempfile import gettempdir        # dosyanın üst kısmındaki import’lara ekle


from xgboost import XGBRegressor
from catboost import CatBoostRegressor

# ────────────────────────────────────
# 0) Komut satırı argümanı
# ────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--model",
                    choices=["xgb", "cat", "dt", "rf",
                             "dummy", "lr"],
                    default="xgb",
                    help="Eğitilecek algoritma")
model_key = parser.parse_args().model

# ────────────────────────────────────
# 1) MODELS sözlüğü
# ────────────────────────────────────
MODELS = {
    "dummy": DummyRegressor(strategy="mean"),

    "lr": LinearRegression(),

    "dt": DecisionTreeRegressor(
        max_depth=8,
        random_state=42
    ),

    "rf": RandomForestRegressor(
        n_estimators=300,
        n_jobs=-1,
        random_state=42
    ),

    "xgb": XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        n_jobs=-1,
        random_state=42
    ),

    "cat": CatBoostRegressor(
        iterations=200,
        depth=6,
        learning_rate=0.05,
        loss_function="RMSE",
        task_type="CPU",
        verbose=False,
        allow_writing_files=False,                    # geçici klasör istemesin
        train_dir=os.path.join(gettempdir(), "cb_info"),
        random_seed=42
    )
}

# ────────────────────────────────────
# 2) App context – veri çekme
# ────────────────────────────────────
with app.app_context():
    engine = create_engine(db.engine.url)
    df = pd.read_sql("""
        SELECT upr.rating,
               up.age,
               up.gender,
               up.experience_level,
               up.height,
               up.weight,
               p.level        AS program_level,
               p.difficulty,
               p.type,
               p.duration           AS program_duration,
               upr.duration         AS user_duration,
               upr.progress         AS progress_pct,
               p.days_per_week,
               p.weeks_total,
               p.focus_area
        FROM user_program_ratings upr
        JOIN user_profiles   up ON upr.user_id = up.user_id
        JOIN programs        p  ON upr.program_id = p.id
    """, engine)

    print(f"Veri seti boyutu: {df.shape}")

    if df.shape[0] < 10:
        print("⚠️ 10’dan az kayıt var → model eğitimi atlandı.")
        exit()

    # Ek feature: experience_diff
    df["exp_level_num"] = df["experience_level"].map(
        {"Beginner": 0, "Intermediate": 1, "Advanced": 2})
    df["experience_diff"] = df["difficulty"] - df["exp_level_num"]

    # Feature listeleri
    num_cols = [
        "age", "height", "weight",
        "program_duration", "user_duration", "progress_pct",
        "experience_diff",
        "days_per_week", "weeks_total", "difficulty"
    ]
    cat_cols = [
        "gender", "experience_level", "program_level",
        "type", "focus_area"
    ]

    preproc = ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols)
    ])

    pipeline = Pipeline([
        ("preproc", preproc),
        ("model", MODELS[model_key])
    ])

    # Split X / y
    X = df.drop("rating", axis=1)
    y = df["rating"]

    # 5-fold CV (RMSE)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    rmse = -cross_val_score(
        pipeline, X, y,
        scoring="neg_root_mean_squared_error",
        cv=cv, n_jobs=-1
    ).mean()
    print(f"[{model_key.upper()}] CV RMSE: {rmse:.4f}")

    # Fit & kaydet
    pipeline.fit(X, y)
    os.makedirs("models", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    model_path = f"models/{model_key}_{timestamp}.pkl"
    joblib.dump(pipeline, model_path)
    # Sembolîk "latest.pkl" linkini/koopasını güncelle
    latest_symlink = "models/latest.pkl"
    try:
        if os.path.exists(latest_symlink) or os.path.islink(latest_symlink):
            os.remove(latest_symlink)
        os.symlink(model_path, latest_symlink)   # Unix
    except Exception:
        # Windows: kopyala
        joblib.dump(pipeline, latest_symlink)
    print(f"✅ Model kaydedildi → {model_path}")

    # Metrics JSON
    metrics = {
        "model": model_key,
        "num_ratings": int(df.shape[0]),
        "rmse": float(rmse),
        "trained_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join("models", "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # CSV log
    log_path = "training_log.csv"
    header = ["timestamp", "num_ratings", "rmse", "model"]
    if not os.path.exists(log_path):
        with open(log_path, "w", newline="") as f:
            csv.writer(f).writerow(header)

    with open(log_path, "a", newline="") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(),
                                df.shape[0], rmse, model_key])

    print(f"📊 Log satırı eklendi ({model_key}) → {log_path}")
