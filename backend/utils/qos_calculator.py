"""
Utilitaires pour le calcul de la QoS et de l'utilité
FIXED VERSION - Corrects utility calculation to give meaningful values
"""


def calculate_utility(qos_achieved, qos_constraints, qos_checks):
    """
    FIXED: Calcule la valeur d'utilité d'un service avec une formule plus équilibrée
    
    Args:
        qos_achieved: QoS réelles du service
        qos_constraints: Contraintes QoS de la requête
        qos_checks: Dict des vérifications QoS
    
    Returns:
        float: Valeur d'utilité (0-150+)
    
    CHANGEMENTS:
    - Formule plus équilibrée qui ne pénalise pas trop les services partiellement conformes
    - Bonus pour satisfaction complète des contraintes
    - Score de qualité intrinsèque du service
    """
    
    # Nombre de contraintes satisfaites
    met_constraints = sum(qos_checks.values())
    total_constraints = len(qos_checks)
    
    # Ratio de satisfaction (0 à 1)
    satisfaction_ratio = met_constraints / total_constraints if total_constraints > 0 else 0
    
    # ============================================================
    # PARTIE 1: Score de Qualité Intrinsèque (0-100)
    # ============================================================
    # Ce score évalue la qualité générale du service indépendamment des contraintes
    
    quality_score = (
        normalize(qos_achieved.availability, 0, 100, 0, 15) +      # 15 points max
        normalize(qos_achieved.reliability, 0, 100, 0, 15) +       # 15 points max
        normalize(qos_achieved.successability, 0, 100, 0, 15) +    # 15 points max
        normalize(qos_achieved.throughput, 0, 1000, 0, 10) +       # 10 points max
        normalize(qos_achieved.compliance, 0, 100, 0, 10) +        # 10 points max
        normalize(qos_achieved.best_practices, 0, 100, 0, 10) +    # 10 points max
        normalize(qos_achieved.documentation, 0, 100, 0, 5) +      # 5 points max
        normalize_inverse(qos_achieved.response_time, 0, 1000, 0, 10) +  # 10 points max
        normalize_inverse(qos_achieved.latency, 0, 1000, 0, 10)          # 10 points max
    )
    # Total possible: 100 points
    
    # ============================================================
    # PARTIE 2: Score de Conformité aux Contraintes (0-100)
    # ============================================================
    # Ce score évalue à quel point le service respecte les contraintes spécifiques
    
    conformity_score = 0
    constraint_weights = {
        'ResponseTime': 12,
        'Availability': 12,
        'Throughput': 11,
        'Successability': 11,
        'Reliability': 12,
        'Compliance': 11,
        'BestPractices': 10,
        'Latency': 11,
        'Documentation': 10
    }
    
    for constraint_name, is_met in qos_checks.items():
        if is_met:
            conformity_score += constraint_weights.get(constraint_name, 10)
    
    # Total possible: 100 points (si toutes contraintes satisfaites)
    
    # ============================================================
    # PARTIE 3: Formule Finale d'Utilité
    # ============================================================
    
    # CHANGEMENT PRINCIPAL: Formule plus douce, moins punitive
    # Au lieu de: utility = quality_score * satisfaction_ratio - (1 - satisfaction_ratio) * 100
    # On utilise une combinaison pondérée
    
    # Utilité de base = moyenne pondérée qualité + conformité
    base_utility = (quality_score * 0.4) + (conformity_score * 0.6)
    
    # Bonus pour satisfaction complète (toutes contraintes respectées)
    if satisfaction_ratio == 1.0:
        bonus = 50  # Gros bonus pour satisfaction totale
    elif satisfaction_ratio >= 0.8:
        bonus = 25  # Bonus moyen si presque toutes contraintes OK
    elif satisfaction_ratio >= 0.6:
        bonus = 10  # Petit bonus si majorité des contraintes OK
    else:
        bonus = 0
    
    # Pénalité douce pour non-conformité (moins sévère qu'avant)
    # Au lieu de soustraire directement (1 - satisfaction_ratio) * 100
    # On applique un facteur de réduction
    if satisfaction_ratio < 0.5:
        # Si moins de 50% des contraintes: pénalité plus forte
        penalty_factor = 0.5  # Réduit l'utilité de moitié
    elif satisfaction_ratio < 0.7:
        # Si 50-70% des contraintes: pénalité modérée
        penalty_factor = 0.7
    elif satisfaction_ratio < 1.0:
        # Si 70-100% des contraintes: pénalité légère
        penalty_factor = 0.9
    else:
        # Toutes contraintes: pas de pénalité
        penalty_factor = 1.0
    
    # Calcul final
    utility = (base_utility * penalty_factor) + bonus
    
    # Assurer que l'utilité est positive
    utility = max(utility, 0)
    
    return utility


def normalize(value, min_val, max_val, target_min, target_max):
    """Normalise une valeur dans une nouvelle plage"""
    if max_val == min_val:
        return target_min
    
    # Assurer que value est dans la plage [min_val, max_val]
    value = max(min_val, min(value, max_val))
    
    normalized = (value - min_val) / (max_val - min_val)
    return target_min + normalized * (target_max - target_min)


def normalize_inverse(value, min_val, max_val, target_min, target_max):
    """Normalise une valeur de manière inversée (plus bas = mieux)"""
    if max_val == min_val:
        return target_max
    
    # Assurer que value est dans la plage [min_val, max_val]
    value = max(min_val, min(value, max_val))
    
    normalized = 1 - ((value - min_val) / (max_val - min_val))
    return target_min + normalized * (target_max - target_min)


def aggregate_qos(services):
    """
    Agrège les QoS de plusieurs services dans une composition séquentielle
    
    Args:
        services: Liste de WebService
    
    Returns:
        QoS: QoS agrégées
    """
    from models.service import QoS
    
    if not services:
        return QoS()
    
    if len(services) == 1:
        return services[0].qos
    
    # Compute aggregated values for sequential composition
    # Times: sum
    total_response_time = sum(s.qos.response_time for s in services)
    total_latency = sum(s.qos.latency for s in services)
    
    # Probabilities: product (availability, reliability, successability are percentages)
    agg_availability = 1.0
    agg_reliability = 1.0
    agg_successability = 1.0
    for s in services:
        agg_availability *= (s.qos.availability / 100)
        agg_reliability *= (s.qos.reliability / 100)
        agg_successability *= (s.qos.successability / 100)
    agg_availability *= 100
    agg_reliability *= 100
    agg_successability *= 100
    
    # Others: minimum (most restrictive)
    min_throughput = min(s.qos.throughput for s in services)
    min_compliance = min(s.qos.compliance for s in services)
    min_best_practices = min(s.qos.best_practices for s in services)
    min_documentation = min(s.qos.documentation for s in services)
    
    # Construct via the QoS kwargs constructor (goes through float() validation)
    return QoS(
        response_time=total_response_time,
        availability=agg_availability,
        throughput=min_throughput,
        successability=agg_successability,
        reliability=agg_reliability,
        compliance=min_compliance,
        best_practices=min_best_practices,
        latency=total_latency,
        documentation=min_documentation
    )


def compare_qos(qos1, qos2):
    """
    Compare deux QoS
    
    Returns:
        dict: Comparaison détaillée
    """
    comparison = {}
    
    metrics = [
        ('response_time', False),  # False = plus bas = mieux
        ('availability', True),    # True = plus haut = mieux
        ('throughput', True),
        ('successability', True),
        ('reliability', True),
        ('compliance', True),
        ('best_practices', True),
        ('latency', False),
        ('documentation', True)
    ]
    
    for metric, higher_is_better in metrics:
        val1 = getattr(qos1, metric)
        val2 = getattr(qos2, metric)
        
        if higher_is_better:
            comparison[metric] = {
                'qos1': val1,
                'qos2': val2,
                'winner': 'qos1' if val1 > val2 else ('qos2' if val2 > val1 else 'tie'),
                'difference': val1 - val2
            }
        else:
            comparison[metric] = {
                'qos1': val1,
                'qos2': val2,
                'winner': 'qos1' if val1 < val2 else ('qos2' if val2 < val1 else 'tie'),
                'difference': val2 - val1
            }
    
    return comparison


def calculate_utility_detailed(qos_achieved, qos_constraints, qos_checks):
    """
    Version détaillée du calcul d'utilité pour debug
    Retourne un dictionnaire avec tous les détails du calcul
    """
    met_constraints = sum(qos_checks.values())
    total_constraints = len(qos_checks)
    satisfaction_ratio = met_constraints / total_constraints if total_constraints > 0 else 0
    
    # Score de qualité
    quality_components = {
        'availability': normalize(qos_achieved.availability, 0, 100, 0, 15),
        'reliability': normalize(qos_achieved.reliability, 0, 100, 0, 15),
        'successability': normalize(qos_achieved.successability, 0, 100, 0, 15),
        'throughput': normalize(qos_achieved.throughput, 0, 1000, 0, 10),
        'compliance': normalize(qos_achieved.compliance, 0, 100, 0, 10),
        'best_practices': normalize(qos_achieved.best_practices, 0, 100, 0, 10),
        'documentation': normalize(qos_achieved.documentation, 0, 100, 0, 5),
        'response_time': normalize_inverse(qos_achieved.response_time, 0, 1000, 0, 10),
        'latency': normalize_inverse(qos_achieved.latency, 0, 1000, 0, 10)
    }
    
    quality_score = sum(quality_components.values())
    
    # Score de conformité
    conformity_score = 0
    constraint_weights = {
        'ResponseTime': 12, 'Availability': 12, 'Throughput': 11,
        'Successability': 11, 'Reliability': 12, 'Compliance': 11,
        'BestPractices': 10, 'Latency': 11, 'Documentation': 10
    }
    
    for constraint_name, is_met in qos_checks.items():
        if is_met:
            conformity_score += constraint_weights.get(constraint_name, 10)
    
    # Calcul bonus/pénalité
    if satisfaction_ratio == 1.0:
        bonus = 50
    elif satisfaction_ratio >= 0.8:
        bonus = 25
    elif satisfaction_ratio >= 0.6:
        bonus = 10
    else:
        bonus = 0
    
    if satisfaction_ratio < 0.5:
        penalty_factor = 0.5
    elif satisfaction_ratio < 0.7:
        penalty_factor = 0.7
    elif satisfaction_ratio < 1.0:
        penalty_factor = 0.9
    else:
        penalty_factor = 1.0
    
    base_utility = (quality_score * 0.4) + (conformity_score * 0.6)
    utility = (base_utility * penalty_factor) + bonus
    utility = max(utility, 0)
    
    return {
        'utility': utility,
        'quality_score': quality_score,
        'quality_components': quality_components,
        'conformity_score': conformity_score,
        'satisfaction_ratio': satisfaction_ratio,
        'met_constraints': met_constraints,
        'total_constraints': total_constraints,
        'bonus': bonus,
        'penalty_factor': penalty_factor,
        'base_utility': base_utility
    }