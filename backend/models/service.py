"""
Modèles de données pour les services web
"""

class QoS:
    def __init__(self, data=None, **kwargs):
        """
        Initialize QoS with either:
        1. A dictionary with keys like 'ResponseTime', 'Availability', etc.
        2. Named parameters like response_time=, availability=, etc.
        
        Args:
            data: Dictionary with QoS values (optional)
            **kwargs: Named parameters (response_time, availability, etc.)
        """
        # Si des kwargs sont fournis, on les utilise en priorité
        if kwargs:
            self.response_time = float(kwargs.get('response_time', 0))
            self.availability = float(kwargs.get('availability', 0))
            self.throughput = float(kwargs.get('throughput', 0))
            self.successability = float(kwargs.get('successability', 0))
            self.reliability = float(kwargs.get('reliability', 0))
            self.compliance = float(kwargs.get('compliance', 0))
            self.best_practices = float(kwargs.get('best_practices', 0))
            self.latency = float(kwargs.get('latency', 0))
            self.documentation = float(kwargs.get('documentation', 0))
        else:
            # Sinon, on utilise le format dict (compatibilité avec l'ancien code)
            if data is None:
                data = {}
            self.response_time = float(data.get('ResponseTime', 0))
            self.availability = float(data.get('Availability', 0))
            self.throughput = float(data.get('Throughput', 0))
            self.successability = float(data.get('Successability', 0))
            self.reliability = float(data.get('Reliability', 0))
            self.compliance = float(data.get('Compliance', 0))
            self.best_practices = float(data.get('BestPractices', 0))
            self.latency = float(data.get('Latency', 0))
            self.documentation = float(data.get('Documentation', 0))
    
    def to_dict(self):
        return {
            'ResponseTime': self.response_time,
            'Availability': self.availability,
            'Throughput': self.throughput,
            'Successability': self.successability,
            'Reliability': self.reliability,
            'Compliance': self.compliance,
            'BestPractices': self.best_practices,
            'Latency': self.latency,
            'Documentation': self.documentation
        }
    
    def meets_constraints(self, constraints):
        """Vérifie si les QoS respectent les contraintes"""
        checks = {
            'ResponseTime': self.response_time <= constraints.response_time,
            'Availability': self.availability >= constraints.availability,
            'Throughput': self.throughput >= constraints.throughput,
            'Successability': self.successability >= constraints.successability,
            'Reliability': self.reliability >= constraints.reliability,
            'Compliance': self.compliance >= constraints.compliance,
            'BestPractices': self.best_practices >= constraints.best_practices,
            'Latency': self.latency <= constraints.latency,
            'Documentation': self.documentation >= constraints.documentation
        }
        return checks


class WebService:
    def __init__(self, service_id, name=None):
        self.id = service_id
        self.name = name or service_id
        self.inputs = []
        self.outputs = []
        self.qos = QoS()
        self.annotations = None
        self.wsdl_content = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'qos': self.qos.to_dict(),
            'annotations': self.annotations.to_dict() if self.annotations else None
        }
    
    def can_produce(self, parameter):
        """Vérifie si le service peut produire un paramètre"""
        return parameter in self.outputs
    
    def has_required_inputs(self, available_params):
        """Vérifie si tous les inputs requis sont disponibles"""
        return all(inp in available_params for inp in self.inputs)


class CompositionRequest:
    def __init__(self, request_id):
        self.id = request_id
        self.provided = []  # Paramètres d'entrée disponibles
        self.resultant = None  # Paramètre de sortie désiré
        self.qos_constraints = QoS()
    
    def to_dict(self):
        return {
            'id': self.id,
            'provided': self.provided,
            'resultant': self.resultant,
            'qos_constraints': self.qos_constraints.to_dict()
        }


class CompositionResult:
    def __init__(self):
        self.services = []  # Liste des services utilisés
        self.workflow = []  # Séquence d'exécution
        self.utility_value = 0.0
        self.qos_achieved = QoS()
        self.computation_time = 0.0
        self.success = False
        self.explanation = ""
    
    def to_dict(self):
        return {
            'services': [s.id if hasattr(s, 'id') else s for s in self.services],
            'workflow': self.workflow,
            'utility_value': self.utility_value,
            'qos_achieved': self.qos_achieved.to_dict(),
            'computation_time': self.computation_time,
            'success': self.success,
            'explanation': self.explanation
        }