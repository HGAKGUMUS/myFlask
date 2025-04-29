import pandas as pd
import matplotlib.pyplot as plt

# training_log.csv dosyasını oku
log_path = "training_log.csv"
df_log = pd.read_csv(log_path, parse_dates=["timestamp"])

# Grafik çizimi
plt.figure(figsize=(8, 5))
plt.plot(df_log['num_ratings'], df_log['rmse'], marker='o', linestyle='-')
plt.xlabel('Toplam Rating Sayısı')
plt.ylabel('CV RMSE')
plt.title('Model Performansının Rating Sayısına Göre Değişimi')
plt.grid(True)

# PNG olarak kaydet ve göster
output_path = 'rmse_vs_ratings.png'
plt.savefig(output_path, dpi=150)
plt.show()

print(f"Grafik oluşturuldu ve kaydedildi: {output_path}")
