"""
Utilities for QoS and utility calculation
FIXED VERSION - Corrects utility calculation to give meaningful values
"""


def calculate_utility(qos_achieved, qos_constraints, qos_checks):
    """
    FIXED: Calculates the utility value of a service with a more balanced formula
    
    Args:
        qos_achieved: Actual QoS of the service
        qos_constraints: QoS constraints of the request
        qos_checks: Dict of QoS checks
    
    Returns:
        float: Utility value (0-150+)
    
    CHANGES:
    - More balanced formula that doesn't penalize partially-conforming services too much
    - Bonus for complete constraint satisfaction
    - Intrinsic quality score of the service
    """
    
    # Number of satisfied constraints
    met_constraints = sum(qos_checks.values())
    total_constraints = len(qos_checks)
    
    # Satisfaction ratio (0 to 1)
    satisfaction_ratio = met_constraints / total_constraints if total_constraints > 0 else 0
    
    # ============================================================
    # PART 1: Intrinsic Quality Score (0-100)
    # ============================================================
    # This score evaluates the overall quality of the service independently of constraints
    
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
    # PART 2: Constraint Conformity Score (0-100)
    # ============================================================
    # This score evaluates how well the service meets specific constraints
    
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
    
    # Total possible: 100 points (if all constraints satisfied)
    
    # ============================================================
    # PART 3: Final Utility Formula
    # ============================================================
    
    # MAIN CHANGE: Softer formula, less punitive
    # Instead of: utility = quality_score * satisfaction_ratio - (1 - satisfaction_ratio) * 100
    # We use a weighted combination
    
    # Base utility = weighted average of quality + conformity
    base_utility = (quality_score * 0.4) + (conformity_score * 0.6)
    
    # Bonus for complete satisfaction (all constraints met)
    if satisfaction_ratio == 1.0:
        bonus = 50  # Large bonus for total satisfaction
    elif satisfaction_ratio >= 0.8:
        bonus = 25  # Medium bonus if almost all constraints OK
    elif satisfaction_ratio >= 0.6:
        bonus = 10  # Small bonus if majority of constraints OK
    else:
        bonus = 0
    
    # Soft penalty for non-conformity (less severe than before)
    # Instead of directly subtracting (1 - satisfaction_ratio) * 100
    # We apply a reduction factor
    if satisfaction_ratio < 0.5:
        # If less than 50% of constraints: stronger penalty
        penalty_factor = 0.5  # Reduces utility by half
    elif satisfaction_ratio < 0.7:
        # If 50-70% of constraints: moderate penalty
        penalty_factor = 0.7
    elif satisfaction_ratio < 1.0:
        # If 70-100% of constraints: light penalty
        penalty_factor = 0.9
    else:
        # All constraints met: no penalty
        penalty_factor = 1.0
    
    # Final calculation
    utility = (base_utility * penalty_factor) + bonus
    
    # Ensure utility is positive
    utility = max(utility, 0)
    
    return utility


def normalize(value, min_val, max_val, target_min, target_max):
    """Normalize a value into a new range"""
    if max_val == min_val:
        return target_min
    
    # Ensure value is within [min_val, max_val]
    value = max(min_val, min(value, max_val))
    
    normalized = (value - min_val) / (max_val - min_val)
    return target_min + normalized * (target_max - target_min)


def normalize_inverse(value, min_val, max_val, target_min, target_max):
    """Normalize a value inversely (lower = better)"""
    if max_val == min_val:
        return target_max
    
    # Ensure value is within [min_val, max_val]
    value = max(min_val, min(value, max_val))
    
    normalized = 1 - ((value - min_val) / (max_val - min_val))
    return target_min + normalized * (target_max - target_min)


def aggregate_qos(services):
    """
    Aggregate QoS of multiple services in a sequential composition
    
    Args:
        services: List of WebService
    
    Returns:
        QoS: Aggregated QoS
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
    Compare two QoS
    
    Returns:
        dict: Detailed comparison
    """
    comparison = {}
    
    metrics = [
        ('response_time', False),  # False = lower is better
        ('availability', True),    # True = higher is better
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
    Detailed version of utility calculation for debugging.
    Returns a dictionary with all calculation details.
    """
    met_constraints = sum(qos_checks.values())
    total_constraints = len(qos_checks)
    satisfaction_ratio = met_constraints / total_constraints if total_constraints > 0 else 0
    
    # Quality score
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
    
    # Conformity score
    conformity_score = 0
    constraint_weights = {
        'ResponseTime': 12, 'Availability': 12, 'Throughput': 11,
        'Successability': 11, 'Reliability': 12, 'Compliance': 11,
        'BestPractices': 10, 'Latency': 11, 'Documentation': 10
    }
    
    for constraint_name, is_met in qos_checks.items():
        if is_met:
            conformity_score += constraint_weights.get(constraint_name, 10)
    
    # Calculate bonus/penalty
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