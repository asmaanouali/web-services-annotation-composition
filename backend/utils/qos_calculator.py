"""
Utilitaires pour le calcul de la QoS et de l'utilité
"""


def calculate_utility(qos_achieved, qos_constraints, qos_checks):
    """
    Calcule la valeur d'utilité d'un service
    
    Args:
        qos_achieved: QoS réelles du service
        qos_constraints: Contraintes QoS de la requête
        qos_checks: Dict des vérifications QoS
    
    Returns:
        float: Valeur d'utilité
    """
    # Nombre de contraintes satisfaites
    met_constraints = sum(qos_checks.values())
    total_constraints = len(qos_checks)
    
    # Ratio de satisfaction (0 à 1)
    satisfaction_ratio = met_constraints / total_constraints if total_constraints > 0 else 0
    
    # Score de qualité normalisé (0 à 100)
    quality_score = (
        normalize(qos_achieved.availability, 0, 100, 0, 100) * 0.15 +
        normalize(qos_achieved.reliability, 0, 100, 0, 100) * 0.15 +
        normalize(qos_achieved.successability, 0, 100, 0, 100) * 0.15 +
        normalize(qos_achieved.throughput, 0, 1000, 0, 100) * 0.10 +
        normalize(qos_achieved.compliance, 0, 100, 0, 100) * 0.10 +
        normalize(qos_achieved.best_practices, 0, 100, 0, 100) * 0.10 +
        normalize(qos_achieved.documentation, 0, 100, 0, 100) * 0.05 +
        normalize_inverse(qos_achieved.response_time, 0, 1000, 0, 100) * 0.10 +
        normalize_inverse(qos_achieved.latency, 0, 1000, 0, 100) * 0.10
    )
    
    # Formule d'utilité finale
    # Pénalité si contraintes non satisfaites
    penalty = (1 - satisfaction_ratio) * 100
    
    utility = quality_score * satisfaction_ratio - penalty
    
    # Bonus si toutes les contraintes sont satisfaites
    if satisfaction_ratio == 1.0:
        utility += 50
    
    return max(utility, 0)  # Minimum 0


def normalize(value, min_val, max_val, target_min, target_max):
    """Normalise une valeur dans une nouvelle plage"""
    if max_val == min_val:
        return target_min
    
    normalized = (value - min_val) / (max_val - min_val)
    return target_min + normalized * (target_max - target_min)


def normalize_inverse(value, min_val, max_val, target_min, target_max):
    """Normalise une valeur de manière inversée (plus bas = mieux)"""
    if max_val == min_val:
        return target_max
    
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
    
    aggregated = QoS()
    
    # Pour les temps: somme
    aggregated.response_time = sum(s.qos.response_time for s in services)
    aggregated.latency = sum(s.qos.latency for s in services)
    
    # Pour la disponibilité et fiabilité: produit (probabilités)
    aggregated.availability = 1.0
    aggregated.reliability = 1.0
    aggregated.successability = 1.0
    
    for s in services:
        aggregated.availability *= (s.qos.availability / 100)
        aggregated.reliability *= (s.qos.reliability / 100)
        aggregated.successability *= (s.qos.successability / 100)
    
    aggregated.availability *= 100
    aggregated.reliability *= 100
    aggregated.successability *= 100
    
    # Pour les autres: minimum (le plus restrictif)
    aggregated.throughput = min(s.qos.throughput for s in services)
    aggregated.compliance = min(s.qos.compliance for s in services)
    aggregated.best_practices = min(s.qos.best_practices for s in services)
    aggregated.documentation = min(s.qos.documentation for s in services)
    
    return aggregated


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