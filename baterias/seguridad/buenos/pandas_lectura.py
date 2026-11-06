import pandas as pd
def analizar(datos):
    df = pd.read_csv(datos['t'], dtype=str)
    return df.head(0).to_dict(orient='records')
