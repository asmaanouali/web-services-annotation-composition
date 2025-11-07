"""
WSDLParser - Extraction et analyse de fichiers WSDL
"""

from zeep import Client
from typing import Dict, List, Any
import hashlib
import logging

logger = logging.getLogger(__name__)


class WSDLParser:
    """Parse les fichiers WSDL et extrait les métadonnées"""
    
    def __init__(self, wsdl_url: str):
        self.wsdl_url = wsdl_url
        self.client = Client(wsdl_url)
        self.wsdl_doc = self.client.wsdl
        
    def extract_service_info(self) -> Dict[str, Any]:
        """Extrait toutes les informations du WSDL"""
        return {
            "service_name": self.get_service_name(),
            "target_namespace": self.get_target_namespace(),
            "endpoint_url": self.get_endpoint_url(),
            "operations": self.extract_operations(),
            "types": self.extract_types(),
            "documentation": self.extract_documentation()
        }
    
    def get_service_name(self) -> str:
        """Récupère le nom du service"""
        return list(self.wsdl_doc.services.keys())[0] if self.wsdl_doc.services else "Unknown"
    
    def get_target_namespace(self) -> str:
        """Récupère le namespace cible"""
        return self.wsdl_doc.target_namespace
    
    def get_endpoint_url(self) -> str:
        """Récupère l'URL de l'endpoint"""
        service_name = self.get_service_name()
        service = self.wsdl_doc.services.get(service_name)
        if service and service.ports:
            port = list(service.ports.values())[0]
            return port.binding_options['address']
        return ""
    
    def extract_operations(self) -> List[Dict[str, Any]]:
        """Extrait toutes les opérations avec leurs signatures"""
        operations = []
        
        for service in self.wsdl_doc.services.values():
            for port in service.ports.values():
                binding = port.binding
                
                for operation in binding.all():
                    op_info = {
                        "name": operation.name,
                        "input": self.extract_message_parts(operation.input),
                        "output": self.extract_message_parts(operation.output),
                        "documentation": operation.abstract.documentation if hasattr(operation.abstract, 'documentation') else "",
                        "soap_action": operation.soapaction if hasattr(operation, 'soapaction') else ""
                    }
                    operations.append(op_info)
        
        return operations
    
    def extract_message_parts(self, message) -> List[Dict[str, Any]]:
        """Extrait les parties d'un message (paramètres)"""
        if not message or not message.body:
            return []
        
        parts = []
        for element in message.body.type.elements:
            part_info = {
                "name": element[0],
                "type": str(element[1].type.name) if hasattr(element[1].type, 'name') else "complex",
                "required": not element[1].is_optional,
                "default": element[1].default,
                "min_occurs": element[1].min_occurs,
                "max_occurs": element[1].max_occurs
            }
            parts.append(part_info)
        
        return parts
    
    def extract_types(self) -> Dict[str, Any]:
        """Extrait les types complexes définis"""
        types_info = {}
        
        for type_name, type_def in self.wsdl_doc.types.types.items():
            if hasattr(type_def, 'elements'):
                types_info[str(type_name)] = {
                    "elements": [
                        {
                            "name": elem[0],
                            "type": str(elem[1].type.name) if hasattr(elem[1].type, 'name') else "complex"
                        }
                        for elem in type_def.elements
                    ]
                }
        
        return types_info
    
    def extract_documentation(self) -> str:
        """Extrait la documentation du service"""
        service_name = self.get_service_name()
        service = self.wsdl_doc.services.get(service_name)
        
        if service and hasattr(service, 'documentation'):
            return service.documentation
        return ""
    
    def generate_functional_annotations(self) -> Dict[str, Any]:
        """Génère les annotations fonctionnelles à partir du WSDL"""
        service_info = self.extract_service_info()
        
        annotations = {
            "service_id": self.generate_service_id(service_info['service_name']),
            "service_name": service_info['service_name'],
            "wsdl_url": self.wsdl_url,
            "endpoint_url": service_info['endpoint_url'],
            "namespace": service_info['target_namespace'],
            "description": service_info['documentation'],
            
            "functional_annotations": {
                "operations": [
                    {
                        "name": op['name'],
                        "description": op['documentation'],
                        "soap_action": op['soap_action'],
                        "inputs": op['input'],
                        "outputs": op['output'],
                        "input_types": self.infer_types(op['input']),
                        "output_types": self.infer_types(op['output'])
                    }
                    for op in service_info['operations']
                ],
                "complex_types": service_info['types']
            }
        }
        
        return annotations
    
    def infer_types(self, parts: List[Dict[str, Any]]) -> Dict[str, str]:
        """Infère les types pour chaque paramètre"""
        return {part['name']: part['type'] for part in parts}
    
    def generate_service_id(self, service_name: str) -> str:
        """Génère un ID unique pour le service"""
        unique_str = f"{service_name}_{self.wsdl_url}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:16]