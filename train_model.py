import pandas as pd
from sqlalchemy import create_engine
from app import app, db, UserProgramRating, UserProfile, Program
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
import xgboost as xgb
import joblib
from sklearn.metrics import mean_squared_error

with app.app_context():
    # Veritabanı bağlantısını SQLAlchemy engine üzerinden kuruyoruz
    engine = create_engine(db.engine.url)

    # SQL sorgusu ile verilerinizi çekelim (kullanıcı, profil ve program bilgilerini birleştiriyoruz)
    query = """
    SELECT 
        upr.rating,
        up.age,
        up.gender,
        up.experience_level,
        up.height,
        up.weight,
        p.level as program_level,
        p.difficulty,
        p.type,
        p.duration
    FROM user_program_ratings upr
    JOIN user_profiles up ON upr.user_id = up.user_id
    JOIN programs p ON upr.program_id = p.id;
    """

    # Verileri pandas DataFrame'e aktarın
    df = pd.read_sql(query, engine)
    print("Veri seti boyutu:", df.shape)

    # Kategorik sütunları sayısal değerlere çeviriyoruz
    categorical_cols = ["gender", "experience_level", "program_level", "type"]
    for col in categorical_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        # Not: Daha sonra canlıda aynı dönüşümleri yapabilmek için encoder'ları saklamak isteyebilirsiniz.

    # Sayısal verileri ölçeklendiriyoruz
    scaler = StandardScaler()
    numerical_cols = ["age", "height", "weight", "duration"]
    df[numerical_cols] = scaler.fit_transform(df[numerical_cols])

    # Özellikler (X) ve etiket (y) ayırıyoruz
    X = df.drop("rating", axis=1)
    y = df["rating"]

    # Eğitim ve test setlerine ayırma (test boyutu %20)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # XGBoost modeli tanımlanıyor ve eğitim verileri ile eğitiliyor
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        objective="reg:squarederror",
        random_state=42
    )
    model.fit(X_train, y_train)

    # Modelin test performansını ölçüyoruz (RMSE)
    y_pred = model.predict(X_test)
    rmse = mean_squared_error(y_test, y_pred, squared=False)
    print("Test RMSE:", rmse)

    # Eğitilmiş modeli ve scaler'ı dosyaya kaydediyoruz
    joblib.dump(model, "xgboost_model.pkl")
    joblib.dump(scaler, "scaler.pkl")
