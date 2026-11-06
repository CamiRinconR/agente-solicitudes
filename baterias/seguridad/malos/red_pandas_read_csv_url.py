import pandas as pd
def analizar(datos):
    return pd.read_csv("https://www.datos.gov.co/resource/jbjy-vk9h.csv", dtype=str).to_dict(orient="records")
