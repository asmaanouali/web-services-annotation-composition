from zeep import Client
from zeep.wsdl import wsdl
import json
from typing import Dict, List, Any

class WSDLParser:
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
        if self.wsdl_doc.services:
            return list(self.wsdl_doc.services.keys())[0]
        return "Unknown"
    
    def get_target_namespace(self) -> str:
        """Récupère le namespace cible"""
        # ✅ Utiliser hasattr pour vérifier l'existence
        if hasattr(self.wsdl_doc, 'target_namespace'):
            return self.wsdl_doc.target_namespace  # type: ignore
        return ""
    
    def get_endpoint_url(self) -> str:
        """Récupère l'URL de l'endpoint"""
        service_name = self.get_service_name()
        service = self.wsdl_doc.services.get(service_name)
        if service and service.ports:
            port = list(service.ports.values())[0]
            # ✅ Vérifier que binding_options existe
            if hasattr(port, 'binding_options') and 'address' in port.binding_options:
                return port.binding_options['address']  # type: ignore
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
                        "documentation": getattr(operation.abstract, 'documentation', '') if hasattr(operation, 'abstract') else "",
                        "soap_action": getattr(operation, 'soapaction', '')
                    }
                    operations.append(op_info)
        
        return operations
    
    def extract_message_parts(self, message) -> List[Dict[str, Any]]:
        """Extrait les parties d'un message (paramètres)"""
        if not message or not hasattr(message, 'body') or not message.body:
            return []
        
        parts = []
        # ✅ Vérifier que body.type existe et a des éléments
        if hasattr(message.body, 'type') and hasattr(message.body.type, 'elements'):
            for element in message.body.type.elements:
                part_info = {
                    "name": element[0],  # Nom du paramètre
                    "type": str(element[1].type.name) if hasattr(element[1].type, 'name') else "complex",
                    "required": not element[1].is_optional if hasattr(element[1], 'is_optional') else True,
                    "default": getattr(element[1], 'default', None),
                    "min_occurs": getattr(element[1], 'min_occurs', None),
                    "max_occurs": getattr(element[1], 'max_occurs', None)
                }
                parts.append(part_info)
        
        return parts
    
    def extract_types(self) -> Dict[str, Any]:
        """Extrait les types complexes définis"""
        types_info = {}
        
        # ✅ Vérifier que types existe
        if not hasattr(self.wsdl_doc, 'types'):
            return types_info
            
        types_dict = dict(self.wsdl_doc.types.types)  # type: ignore
        for type_name, type_def in types_dict.items():
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
        
        # ✅ Utiliser hasattr pour vérifier
        if service and hasattr(service, 'documentation'):
            return service.documentation  # type: ignore
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
        import hashlib
        unique_str = f"{service_name}_{self.wsdl_url}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:16]


# Exemple d'utilisation
if __name__ == "__main__":
    # Exemple avec un service SOAP public
    wsdl_url = "http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso?WSDL"
    
    parser = WSDLParser(wsdl_url)
    annotations = parser.generate_functional_annotations()
    
    print(json.dumps(annotations, indent=2))