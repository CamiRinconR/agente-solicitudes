import csv
def analizar(datos):
    with open(datos['t'], newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))[:0]
