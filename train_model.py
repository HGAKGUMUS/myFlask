import os
import joblib
import pandas as pd
import json
from datetime import datetime
from sqlalchemy import create_engine
from app import app, db
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from xgboost import XGBRegressor

with app.app_context():
    # 1) Veriyi çek, yeni sütunları da include et
    engine = create_engine(db.engine.url)
    df = pd.read_sql("""
        SELECT upr.rating,
               up.age, up.gender, up.experience_level,
               up.height, up.weight,
               p.level        AS program_level,
               p.difficulty,
               p.type,
               p.duration,
               p.days_per_week,
               p.focus_area
        FROM user_program_ratings upr
        JOIN user_profiles up ON upr.user_id = up.user_id
        JOIN programs       p ON upr.program_id = p.id
    """, engine)

    print("Veri seti boyutu:", df.shape)

    # 2) Veri yetersizse çık
    if df.shape[0] < 10:
        print("⚠️ 10’dan az kayıt var → model eğitimi atlandı.")
        exit()

    # 3) Pipeline: yeni feature’lar ekli
    num_cols = ["age", "height", "weight", "duration", "days_per_week"]
    cat_cols = ["gender", "experience_level", "program_level", "type", "focus_area"]

    preproc = ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols)
    ])

    pipeline = Pipeline([
        ("preproc", preproc),
        ("model", XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            objective="reg:squarederror"
        ))
    ])

    # 4) Split X/y
    X = df.drop("rating", axis=1)
    y = df["rating"]

    # 5) 5-fold CV – RMSE
    rmse = -cross_val_score(
        pipeline, X, y,
        scoring="neg_root_mean_squared_error",
        cv=5
    ).mean()
    print("CV RMSE:", rmse)

    # 6) Final fit & kaydet
    pipeline.fit(X, y)
    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, "models/fit_pipeline.pkl")
    print("✅ Model kaydedildi → models/fit_pipeline.pkl")

    # 7) Metrics kaydet
    metrics = {
        "rmse": float(rmse),
        "trained_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join("models", "metrics.json"), "w") as f:
        json.dump(metrics, f)
    print(f"ℹ️ Metrics updated: {metrics}")
