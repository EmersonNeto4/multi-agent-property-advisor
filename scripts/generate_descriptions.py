"""
Gera data/portugal_locations_descriptions.json a partir de
data/portugal_locations.json: uma descrição textual (2-3 frases, PT) por
localização, usada como documento a indexar pelo retrieval semântico
(tools/semantic_search.py). Ver docs/FASE2_DECISOES.txt para o porquê de
gerar por template em vez de pedir a um LLM, e para o benchmark que levou
à v2 deste template (carácter primeiro, sem número de população no texto).

As descrições são geradas UMA vez e commitadas como dado estático — não são
geradas em runtime. Regenerar sempre que data/portugal_locations.json mudar:

    python scripts/generate_descriptions.py

Abordagem (determinística, sem chamadas a LLM):
    1. Frase de carácter: todas as tags de characteristics exceto as de
       geografia (GEOGRAPHY_TAGS), traduzidas por um dicionário de
       fragmentos (TAG_PHRASES) e combinadas numa frase "Destaca-se por...".
       Vem PRIMEIRO porque é o sinal mais importante para o retrieval
       semântico (ambiente/vibe) - ver benchmark na secção 2 de
       docs/FASE2_DECISOES.txt.
    2. Frase de geografia: litoral / interior / montanha, mais nota de
       clima frio/neve quando aplicável.
    3. Frase de identidade: dimensão (por escalão de população, sem o
       número exato - é ruído para o embedding) e região.
Cada frase só existe se houver tags que a justifiquem — nunca se inventa
informação que não esteja nos campos de origem.
"""

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations_descriptions.json"

# Tags tratadas pela lógica dedicada de geografia/clima (_geography_sentence)
# - nunca entram na frase de carácter, para não duplicar a mesma ideia.
GEOGRAPHY_TAGS = {"costeiro", "interior", "montanha", "frio", "neve"}

# Fragmentos de caracterização (frase 1), um por tag. Todas as tags que não
# sejam de geografia passam por aqui - não há mais distinção entre "mood" e
# "carácter": simplifica o template e evita problemas de concordância de
# género (ex: "uma das maiores cidades do país urbana", corrigido na v1).
TAG_PHRASES = {
    "capital": "estatuto de capital do país",
    "urbano": "ambiente urbano",
    "vibrante": "vida vibrante e animada",
    "histórico": "um centro histórico relevante",
    "jovem": "população jovem",
    "universitário": "forte presença universitária",
    "tranquilo": "ambiente calmo e tranquilo",
    "natureza": "proximidade à natureza",
    "cultural": "oferta cultural ativa",
    "canais": "canais navegáveis característicos",
    "familiar": "perfil familiar",
    "comercial": "atividade comercial relevante",
    "crescimento": "crescimento urbano recente",
    "cosmopolita": "carácter cosmopolita",
    "praia": "praias procuradas",
    "luxo": "oferta turística de luxo",
    "turístico": "forte vocação turística",
    "residencial": "carácter predominantemente residencial",
    "industrial": "atividade industrial relevante",
    "patrimônio": "património histórico classificado",
    "rural": "ambiente rural",
    "quente": "clima quente durante grande parte do ano",
    "sol": "muitas horas de sol",
    "vida noturna": "vida noturna intensa",
    "autêntico": "carácter autêntico, pouco massificado",
    "vinho do porto": "tradição ligada ao vinho do Porto",
    "gastronômico": "tradição gastronómica reconhecida",
    "vinhos": "tradição vinícola",
    "veraneio": "vocação de veraneio",
    "cassino": "casino e oferta de lazer noturno",
    "acessível": "custo de vida mais acessível",
    "multicultural": "população multicultural",
    "tecnologia": "polo de empresas tecnológicas",
    "qualidade de vida": "boa qualidade de vida",
    "empresarial": "polo empresarial relevante",
    "artesanato": "tradição de artesanato",
    "tradicional": "carácter tradicional",
    "feiras": "feiras e mercados tradicionais",
    "joalharia": "tradição na indústria de joalharia",
    "têxtil": "tradição na indústria têxtil",
    "cerâmica": "tradição de cerâmica artística",
    "termas": "termas e águas termais",
    "arte": "cena artística ativa",
    "templários": "património ligado à Ordem dos Templários",
    "porto": "porto marítimo relevante",
    "esqui": "estância de esqui na proximidade",
    "pesca": "tradição piscatória",
    "ria formosa": "proximidade à Ria Formosa",
    "surf": "praias muito procuradas para o surf",
    "douro": "ligação à região vinhateira do Douro",
}


def _size_descriptor(population: int) -> str:
    if population >= 300000:
        return "uma das maiores cidades do país"
    if population >= 30000:
        return "uma cidade"
    return "uma pequena cidade"


def _region_part(loc: dict) -> str:
    nuts_ii, nuts_iii = loc["nuts_ii"], loc["nuts_iii"]
    if nuts_ii == nuts_iii:
        return nuts_ii
    return f"{nuts_ii} ({nuts_iii})"


def _geography_sentence(chars: set) -> str:
    if "costeiro" in chars and "montanha" in chars:
        base = "Está localizada no litoral, com relevo montanhoso nas proximidades."
    elif "costeiro" in chars:
        base = "Está localizada no litoral."
    elif "montanha" in chars:
        base = "É uma zona de interior, de relevo montanhoso."
    elif "interior" in chars:
        base = "É uma zona de interior, longe do litoral."
    else:
        base = ""

    if "neve" in chars:
        climate = " O clima é frio, com possibilidade de neve no inverno."
    elif "frio" in chars:
        climate = " O clima é mais frio do que a média do país."
    else:
        climate = ""

    return (base + climate).strip()


def _character_sentence(name: str, chars_ordered: list) -> str:
    remaining = [c for c in chars_ordered if c not in GEOGRAPHY_TAGS]

    # "surf" já implica praia - evita repetir a mesma ideia duas vezes
    # (ex: Peniche tem tags "surf" e "praia" em simultâneo).
    if "surf" in remaining and "praia" in remaining:
        remaining = [c for c in remaining if c != "praia"]

    phrases = [TAG_PHRASES[c] for c in remaining if c in TAG_PHRASES][:4]
    if not phrases:
        return ""

    if len(phrases) == 1:
        joined = phrases[0]
    else:
        joined = ", ".join(phrases[:-1]) + " e " + phrases[-1]

    return f"{name} destaca-se por {joined}."


def _identity_sentence(loc: dict) -> str:
    size = _size_descriptor(loc["population"])
    region = _region_part(loc)
    return f"É {size}, na região {region}."


def generate_description(loc: dict) -> str:
    chars_ordered = loc["characteristics"]
    chars_set = set(chars_ordered)

    character = _character_sentence(loc["name"], chars_ordered)
    geography = _geography_sentence(chars_set)
    identity = _identity_sentence(loc)

    sentences = [s for s in (character, geography, identity) if s]
    return " ".join(sentences)


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    descriptions = {}
    for loc in data["locations"]:
        descriptions[loc["id"]] = {
            "name": loc["name"],
            "description": generate_description(loc),
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)

    print(f"Geradas {len(descriptions)} descrições em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
