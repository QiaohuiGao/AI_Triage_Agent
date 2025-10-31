SNOMED = {
    "chest pain": "29857009",
    "shortness of breath": "267036007",
    "fever": "386661006"
}
ICD10 = {
    "chest pain": "R07.9",
    "shortness of breath": "R06.02",
    "fever": "R50.9"
}
def snomed_lookup(surface: str): return SNOMED.get(surface.lower())
def icd_lookup(surface: str): return ICD10.get(surface.lower())
