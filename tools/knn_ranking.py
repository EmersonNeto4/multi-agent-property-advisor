import numpy as np
from typing import List, Dict
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler

def calculate_knn_scores(properties: List[Dict], user_budget: float, k: int = 5) -> List[Dict]:
    """
    KNN aprimorado com:
    - normalização robusta
    - pesos ajustáveis
    - melhor engenharia de features
    - score sempre > 0
    """

    if not properties:
        print("Lista de propriedades está vazia no KNN.")
        return []

    print(f"\n KNN: calculando scores para {len(properties)} imóveis...")

    # ===============================
    # FEATURE ENGINEERING
    # ===============================
    features = []
    for p in properties:
        price = p.get("price", 0)
        area = p.get("area_m2", 1)
        csp = p.get("csp_score", 0.5)
        loc = p.get("location_score", 0.5)
        dist = p.get("distance_real_km", 0)

        price_dev = abs(price - user_budget) / max(user_budget, 1)
        price_m2 = price / max(area, 1)

        features.append([
            price_dev,          # 0 - diferença relativa ao budget
            price_m2,           # 1 - preço por m²
            dist,               # 2 - distância (ou 0 se não houver)
            1.0 - csp,          # 3 - inverter CSP (quanto menor melhor)
            1.0 - loc           # 4 - inverter location score
        ])

    X = np.array(features)

    # ===============================
    # NORMALIZAÇÃO ROBUSTA
    # ===============================
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # ===============================
    # PESOS
    # ===============================
    weights = np.array([
        0.35,   # preço relativo ao budget
        0.20,   # preço por m²
        0.15,   # distância real
        0.20,   # CSP
        0.10,   # location_score
    ])

    X_weighted = X_scaled * weights

    # ===============================
    # PONTO IDEAL
    # ===============================
    ideal = np.zeros((1, X_weighted.shape[1])) 

    # ===============================
    # KNN DISTANCES
    # ===============================
    knn = NearestNeighbors(
        n_neighbors=min(k, len(properties)),
        metric="euclidean"
    )
    knn.fit(X_weighted)

    distances, indices = knn.kneighbors(ideal)

    max_dist = max(distances[0].max(), 0.0001)

    # ===============================
    # SCORE CALIBRADO (EXPONENCIAL)
    # ===============================
    results = []
    for rank, (idx, dist) in enumerate(zip(indices[0], distances[0]), 1):
        prop = properties[idx].copy()

        # score suave e nunca zero
        score = np.exp(-3 * (dist / max_dist))
        score = float(max(0.05, min(score, 1.0)))

        prop["knn_rank"] = rank
        prop["knn_distance"] = float(dist)
        prop["knn_score"] = round(score, 4)

        results.append(prop)

        print(f"   #{rank} score={score:.4f} – {prop.get('title')}")

    print("\nKNN concluído.")
    return results
