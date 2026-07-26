"""
Gera data/portugal_locations_descriptions.json a partir de
data/portugal_locations.json: uma descrição textual (2-4 frases, PT) por
localização, usada como documento a indexar pelo retrieval semântico
(tools/semantic_search.py). Ver docs/FASE2_DECISOES.txt para o porquê de
gerar por template em vez de pedir a um LLM.

As descrições são geradas UMA vez e commitadas como dado estático — não são
geradas em runtime. Regenerar sempre que data/portugal_locations.json mudar:

    python scripts/generate_descriptions.py

Abordagem (determinística, sem chamadas a LLM):
    1. Frase de identidade: nome + dimensão (por população) + região +
       até 2 adjetivos de "mood" (ex: urbano, tranquilo, turístico,
       histórico) tirados de characteristics, na ordem em que lá aparecem.
    2. Frase de geografia: litoral / interior / montanha, mais nota de
       clima frio/neve quando aplicável.
    3. Frase de carácter: as restantes tags de characteristics (as que não
       entraram nas frases 1/2), traduzidas por um dicionário de
       fragmentos (TAG_PHRASES) e combinadas numa frase "Destaca-se por...".
Cada frase só existe se houver tags que a justifiquem — nunca se inventa
informação que não esteja nos campos de origem.
"""

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations_descriptions.json"

# Tags usadas como adjetivo na frase de identidade (concordância de género
# feminina, porque o "tipo" usado é sempre "cidade"/"vila"/"localidade").
# Tags fora deste dicionário nunca entram na frase 1.
MOOD_ADJ_FEM = {
    "urbano": "urbana",
    "tranquilo": "tranquila",
    "turístico": "turística",
    "histórico": "histórica",
    "vibrante": "vibrante",
    "cosmopolita": "cosmopolita",
    "rural": "rural",
    "residencial": "residencial",
    "industrial": "industrial",
    "familiar": "familiar",
    "multicultural": "multicultural",
}

# Tags tratadas pela lógica dedicada de geografia/clima (_geography_sentence)
# - nunca entram na frase de carácter, para não duplicar a mesma ideia.
GEOGRAPHY_TAGS = {"costeiro", "interior", "montanha", "frio", "neve"}

# Fragmentos de caracterização (frase 3), um por tag. Só as tags aqui
# presentes (e não consumidas nas frases 1/2) aparecem na frase de carácter.
TAG_PHRASES = {
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


def _format_population(population: int) -> str:
    return f"{population:,}".replace(",", " ")


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


def _identity_sentence(loc: dict, chars_ordered: list, used: set) -> str:
    name = loc["name"]
    population = loc["population"]
    region = _region_part(loc)

    if "capital" in chars_ordered:
        used.add("capital")
        return (
            f"{name} é a capital de Portugal e uma das maiores cidades do país, "
            f"na região {region}, com cerca de {_format_population(population)} habitantes."
        )

    # Adjetivos de mood só entram na frase de identidade até "uma cidade"/
    # "uma pequena cidade" (concordância no singular). No balde "uma das
    # maiores cidades do país" a concordância teria de ser no plural
    # ("... cidades urbanas do país") - para não complicar a gramática por
    # causa de ~2 localizações, esses tags ficam para a frase de carácter,
    # tal como já acontece com "capital" acima.
    mood = []
    if population < 300000:
        for tag in chars_ordered:
            if tag in MOOD_ADJ_FEM and tag not in used:
                mood.append(MOOD_ADJ_FEM[tag])
                used.add(tag)
            if len(mood) == 2:
                break

    size = _size_descriptor(population)
    mood_part = f" {mood[0]}" if len(mood) == 1 else ""
    if len(mood) == 2:
        mood_part = f" {mood[0]} e {mood[1]}"

    return f"{name} é {size}{mood_part} na região {region}, com cerca de {_format_population(population)} habitantes."


def _character_sentence(chars_ordered: list, used: set, lead_in_used: bool) -> str:
    remaining = [c for c in chars_ordered if c not in used and c not in GEOGRAPHY_TAGS]

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

    verb = "Destaca-se ainda por" if lead_in_used else "Destaca-se por"
    return f"{verb} {joined}."


def generate_description(loc: dict) -> str:
    chars_ordered = loc["characteristics"]
    chars_set = set(chars_ordered)
    used = set()

    identity = _identity_sentence(loc, chars_ordered, used)
    geography = _geography_sentence(chars_set)
    used |= GEOGRAPHY_TAGS & chars_set
    character = _character_sentence(chars_ordered, used, lead_in_used=bool(used - (GEOGRAPHY_TAGS & chars_set)))

    sentences = [identity]
    if geography:
        sentences.append(geography)
    if character:
        sentences.append(character)

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
