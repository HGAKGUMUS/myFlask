# plot_log.py  (proje kökündeki dosya)

import pandas as pd
import matplotlib.pyplot as plt

# 1) CSV'yi oku
df = pd.read_csv("training_log.csv")

# 2) İstenirse model sırasını sabitle
order = ["dt", "rf", "xgb", "cat"]
df["model"] = pd.Categorical(df["model"], categories=order, ordered=True)
df = df.sort_values("model")

# 3) Model-renk eşlemesi
color_map = {
    "dt":  "#1f77b4",   # mavi
    "rf":  "#ff7f0e",   # turuncu
    "xgb": "#2ca02c",   # yeşil
    "cat": "#d62728"    # kırmızı
}
colors = df["model"].map(color_map)

# 4) Grafik
plt.figure(figsize=(6, 4))
plt.scatter(df["model"], df["rmse"], s=120, c=colors)

# RMSE etiketleri
for _, row in df.iterrows():
    plt.text(row["model"], row["rmse"] + 0.005,
             f"{row['rmse']:.3f}",
             ha="center", va="bottom", fontsize=8)

plt.xlabel("Model")
plt.ylabel("CV RMSE")

# Toplam rating sayısını başlığa ekle
total_ratings = int(df["num_ratings"].iloc[0])
plt.title(f"Modellerin Karşılaştırması (Toplam Rating Sayısı = {total_ratings})")

plt.grid(True, axis="y", ls="--", alpha=0.4)
plt.tight_layout()

# 5) Kaydet + göster
plt.savefig("rmse_vs_models.png", dpi=120)
plt.show()
