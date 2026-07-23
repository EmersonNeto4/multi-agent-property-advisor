from typing import List, Dict, Optional, Tuple
from models import UserPreferences


class PropertyCSP:
    """
    Constraint Satisfaction Problem para filtragem de imóveis.
    
    Suporta:
    - Hard constraints (obrigatórias) - eliminam imóveis
    - Soft constraints (preferências com pesos) - dão pontos
    - Scoring para ranking
    """
    
    def __init__(self, preferences: UserPreferences):
        self.preferences = preferences
        self.hard_constraints = []
        self.soft_constraints = []
        self._build_constraints()
    
    def _build_constraints(self):
        """Constrói lista de restrições baseadas nas preferências."""
        prefs = self.preferences
        
        # ============================================
        # HARD CONSTRAINTS (obrigatórias)
        # Imóveis que não satisfazem são ELIMINADOS
        # ============================================
        
        # ========================================
        # FILTROS DE QUALIDADE (sempre aplicados)
        # ========================================
        
        # 1. TIPO DE PROPRIEDADE (apartamentos E moradias)
        self.hard_constraints.append({
            'name': 'property_type',
            'check': lambda p: p.get('property_type', '') in [
                'flat', 'apartment', 'penthouse', 'duplex', 'studio',
                'chalet', 'independantHouse', 'semidetachedHouse', 
                'terracedHouse', 'countryHouse'
            ],
            'message': "Deve ser apartamento ou moradia (não terreno/garagem)"
        })
        
        def check_min_price(p):
            """Preço mínimo baseado na operação."""
            price = p.get('price', 0)
            
            # Detectar operação
            operation = p.get('operation', 'sale')
            
            # Se preferências especificam operação, usar essa
            if hasattr(prefs, 'operation') and prefs.operation:
                operation = prefs.operation
            
            # Aplicar limites apropriados
            if operation == 'rent':
                return 150 <= price <= 15000  # €300-15k/mês
            else:
                return price >= 50000  # ≥€50k venda
        
        self.hard_constraints.append({
            'name': 'min_price',
            'check': check_min_price,
            'message': "Preço dentro de limites razoáveis"
        })
        
        # 3. ÁREA MÍNIMA (eliminar muito pequenos)
        self.hard_constraints.append({
            'name': 'min_area',
            'check': lambda p: p.get('area_m2', 0) == 0 or p.get('area_m2', 0) >= 30,
            'message': "Área deve ser ≥ 30m²"
        })
        
        # 4. ESTADO (eliminar ruínas e terrenos)
        def check_not_ruin(p):
            """Verifica se não é ruína/terreno pela descrição."""
            description = p.get('description', '').lower()
            
            bad_keywords = [
                'ruína', 'ruina', 'demolir', 'demolição',
                'terreno para construir', 'lote para construção',
                'terreno urbano', 'para construir', 'recuperar urgente'
            ]
            
            return not any(keyword in description for keyword in bad_keywords)
        
        self.hard_constraints.append({
            'name': 'not_ruin',
            'check': check_not_ruin,
            'message': "Não pode estar em ruínas ou ser terreno"
        })
        
        # 5. ESTADO HABITÁVEL
        self.hard_constraints.append({
            'name': 'habitable',
            'check': lambda p: p.get('status', '') in [
                'good', 'renew', 'newdevelopment', ''
            ],
            'message': "Deve estar em condições habitáveis"
        })
        
        # ========================================
        # FILTROS BASEADOS NAS PREFERÊNCIAS DO UTILIZADOR
        # ========================================
        
        if prefs.budget:
            self.hard_constraints.append({
                'name': 'budget',
                'check': lambda p: p.get('price', float('inf')) <= prefs.budget,
                'message': f"Preço deve ser ≤ €{prefs.budget}"
            })
        
        if prefs.rooms:
            self.hard_constraints.append({
                'name': 'rooms',
                'check': lambda p: p.get('rooms', 0) >= prefs.rooms,
                'message': f"Deve ter ≥ {prefs.rooms} quartos"
            })
        
        if prefs.bathrooms:
            self.hard_constraints.append({
                'name': 'bathrooms',
                'check': lambda p: p.get('bathrooms', 0) >= prefs.bathrooms,
                'message': f"Deve ter ≥ {prefs.bathrooms} casas de banho"
            })
        
        if prefs.area_m2:
            self.hard_constraints.append({
                'name': 'area',
                'check': lambda p: p.get('area_m2', 0) >= prefs.area_m2,
                'message': f"Área deve ser ≥ {prefs.area_m2}m²"
            })
        
        if prefs.parking:
            self.hard_constraints.append({
                'name': 'parking',
                'check': lambda p: p.get('parking') is True or p.get('has_parking') is True,
                'message': "Deve ter estacionamento/garagem"
            })
        
        if getattr(prefs, 'pool', False): 
            self.hard_constraints.append({
                'name': 'pool',
                # Verifica a flag 'has_pool' que vem do parser
                'check': lambda p: p.get('has_pool') is True,
                'message': "Deve ter piscina"
            })
        
        if prefs.outdoor_space:
            self.hard_constraints.append({
                'name': 'outdoor',
                'check': lambda p: p.get('has_terrace', False) or p.get('has_garden', False),
                'message': "Deve ter terraço ou jardim"
            })
        
        # ============================================
        # SOFT CONSTRAINTS (preferências com pesos)
        # Dão pontos mas NÃO eliminam imóveis
        # ============================================
        
        # Preferência por elevador (peso: 0.1)
        self.soft_constraints.append({
            'name': 'elevator',
            'check': lambda p: p.get('has_lift', False),
            'weight': 0.1,
            'message': "Tem elevador"
        })
        
        # Preferência por ar condicionado (peso: 0.15)
        self.soft_constraints.append({
            'name': 'air_conditioning',
            'check': lambda p: p.get('has_air_conditioning', False),
            'weight': 0.15,
            'message': "Tem ar condicionado"
        })
        
        # Preferência por imóvel em bom estado (peso: 0.2)
        self.soft_constraints.append({
            'name': 'good_condition',
            'check': lambda p: p.get('status', '') == 'good',
            'weight': 0.2,
            'message': "Em bom estado"
        })
        
        # Preferência por andar não térreo (peso: 0.1)
        self.soft_constraints.append({
            'name': 'not_ground_floor',
            'check': lambda p: p.get('floor', 'bj') not in ['bj', 'en', 'ss', '0'],
            'weight': 0.1,
            'message': "Não é rés-do-chão"
        })
        
        # Preferência por imóvel com foto (peso: 0.1)
        self.soft_constraints.append({
            'name': 'has_photo',
            'check': lambda p: p.get('thumbnail') is not None,
            'weight': 0.1,
            'message': "Tem fotografias"
        })
        
        # Se especificou tipo de imóvel, dar peso extra (peso: 0.1)
        if prefs.property_type:
            self.soft_constraints.append({
                'name': 'property_type_match',
                'check': lambda p: prefs.property_type.lower() in p.get('property_type', '').lower(),
                'weight': 0.1,
                'message': f"Tipo correto ({prefs.property_type})"
            })

    def satisfies_hard_constraints(self, property: Dict) -> Tuple[bool, List[str]]:
        """
        Verifica se o imóvel satisfaz TODAS as restrições obrigatórias.
        
        Args:
            property: Imóvel a verificar
            
        Returns:
            (satisfies, violated_constraints)
            - satisfies: True se satisfaz todas
            - violated_constraints: Lista de mensagens das restrições violadas
        """
        violated = []
        
        for constraint in self.hard_constraints:
            try:
                if not constraint['check'](property):
                    violated.append(constraint['message'])
            except Exception as e:
                # Se houver erro ao verificar (ex: campo não existe), considerar violado
                violated.append(f"{constraint['message']} (erro: {e})")
        
        return (len(violated) == 0, violated)
    
    def calculate_soft_score(self, property: Dict) -> Tuple[float, List[str]]:
        """
        Calcula score baseado em soft constraints (0.0 a 1.0).
        
        Args:
            property: Imóvel a avaliar
            
        Returns:
            (score, satisfied_preferences)
            - score: Score normalizado (0.0 a 1.0)
            - satisfied_preferences: Lista de preferências satisfeitas
        """
        if not self.soft_constraints:
            return (0.5, [])  # Score neutro se não há preferências
        
        total_weight = sum(c['weight'] for c in self.soft_constraints)
        earned_score = 0.0
        satisfied = []
        
        for constraint in self.soft_constraints:
            try:
                if constraint['check'](property):
                    earned_score += constraint['weight']
                    satisfied.append(constraint['message'])
            except Exception:
                # Se erro, não conta
                pass
        
        normalized_score = earned_score / total_weight if total_weight > 0 else 0.5
        return normalized_score, satisfied
    
    def filter_and_score(self, properties: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        Filtra imóveis e adiciona scores.
        
        Args:
            properties: Lista de imóveis para filtrar
            
        Returns:
            (filtered_properties, statistics)
            - filtered_properties: Imóveis que passam + scores
            - statistics: Estatísticas sobre o processo
        """
        filtered = []
        rejected = []
        
        for prop in properties:
            satisfies, violations = self.satisfies_hard_constraints(prop)
            
            if satisfies:
                # Calcular score de soft constraints
                soft_score, satisfied_prefs = self.calculate_soft_score(prop)
                
                # Adicionar informações ao imóvel
                prop_copy = prop.copy()
                prop_copy['csp_score'] = round(soft_score, 3)
                prop_copy['satisfies_all_requirements'] = True
                prop_copy['satisfied_preferences'] = satisfied_prefs
                
                filtered.append(prop_copy)
            else:
                rejected.append({
                    'property': prop,
                    'violations': violations
                })

        stats = {
            'total_properties': len(properties),
            'passed': len(filtered),
            'rejected': len(rejected),
            'hard_constraints_count': len(self.hard_constraints),
            'soft_constraints_count': len(self.soft_constraints)
        }
        
        return (filtered,stats)

async def filter_properties_csp(
    properties: List[Dict],
    preferences: UserPreferences
) -> List[Dict]:
    """
    Filtra imóveis usando CSP avançado.
    
    Process:
    1. Aplica hard constraints (eliminam imóveis)
    2. Calcula soft scores (preferências com pesos)
    3. Ordena por CSP score
    
    Args:
        properties: Lista de imóveis
        preferences: Preferências do utilizador
        
    Returns:
        Lista de imóveis que satisfazem restrições obrigatórias,
        ordenados por score de preferências
    """
    print(f"\n CSP Solver:")
    print(f"   Input: {len(properties)} imóveis")
    
    csp = PropertyCSP(preferences)
    
    filtered = []
    
    for prop in properties:
        # 1. Verificar hard constraints
        if not csp.satisfies_hard_constraints(prop):
            continue  # Eliminar
        
        # 2. Calcular soft score
        score, satisfied_prefs = csp.calculate_soft_score(prop)  # ← MUDANÇA
        
        # 3. Adicionar ao imóvel
        prop['csp_score'] = score  # ← Agora é float!
        prop['satisfied_preferences'] = satisfied_prefs  # ← Lista de strings
        
        filtered.append(prop)
    
    print(f" CSP: {len(filtered)} imóveis passaram")
    
    # Debug
    for i, prop in enumerate(filtered[:3], 1):
        score = prop.get('csp_score', 0)
        prefs = prop.get('satisfied_preferences', [])
        print(f"   #{i} {prop['id']}: Score={score:.2f}, Prefs={len(prefs)}")
    
    return filtered