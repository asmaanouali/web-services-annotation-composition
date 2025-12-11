"""
composition_system/classic_wsdl_parser.py
Parser WSDL simple pour la composition classique (sans annotations LLM)
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os
import re


@dataclass
class ServiceOperation:
    """Opération d'un service"""
    name: str
    input_params: List[str]
    output_params: List[str]
    documentation: str = ""


@dataclass
class ServiceInfo:
    """Informations basiques extraites du WSDL"""
    name: str
    endpoint: str
    operations: List[ServiceOperation]
    documentation: str = ""
    
    def get_category(self) -> str:
        """Détermine la catégorie du service par analyse du nom et opérations"""
        name_lower = self.name.lower()
        ops_str = " ".join([op.name.lower() for op in self.operations])
        
        # Détection basique par mots-clés
        if "flight" in name_lower or "flight" in ops_str:
            return "flight"
        elif "hotel" in name_lower or "accommodation" in name_lower or "hotel" in ops_str:
            return "hotel"
        elif "payment" in name_lower or "pay" in ops_str:
            return "payment"
        elif "weather" in name_lower:
            return "weather"
        else:
            return "unknown"


class ClassicWSDLParser:
    """Parser WSDL minimaliste pour composition classique"""
    
    NAMESPACES = {
        'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
        'soap': 'http://schemas.xmlsoap.org/wsdl/soap/',
        'xsd': 'http://www.w3.org/2001/XMLSchema'
    }
    
    def __init__(self, wsdl_path: str):
        self.wsdl_path = wsdl_path
        self.tree = None
        self.root = None
    
    def parse(self) -> ServiceInfo:
        """Parse le WSDL et retourne les infos basiques"""
        try:
            self.tree = ET.parse(self.wsdl_path)
            self.root = self.tree.getroot()
            
            # Extraire les infos basiques
            service_name = self._get_service_name()
            endpoint = self._get_endpoint()
            operations = self._get_operations()
            documentation = self._get_service_documentation()
            
            return ServiceInfo(
                name=service_name,
                endpoint=endpoint,
                operations=operations,
                documentation=documentation
            )
        except Exception as e:
            raise ValueError(f"Erreur parsing WSDL {self.wsdl_path}: {e}")
    
    def _get_service_name(self) -> str:
        """Récupère le nom du service"""
        service = self.root.find('.//wsdl:service', self.NAMESPACES)
        if service is not None:
            return service.get('name', 'UnknownService')
        return 'UnknownService'
    
    def _get_endpoint(self) -> str:
        """Récupère l'endpoint SOAP"""
        address = self.root.find('.//soap:address', self.NAMESPACES)
        if address is not None:
            return address.get('location', '')
        return ''
    
    def _get_service_documentation(self) -> str:
        """Récupère la documentation du service"""
        service = self.root.find('.//wsdl:service', self.NAMESPACES)
        if service is not None:
            doc = service.find('wsdl:documentation', self.NAMESPACES)
            if doc is not None and doc.text:
                return doc.text.strip()
        return ''
    
    def _get_operations(self) -> List[ServiceOperation]:
        """Récupère toutes les opérations"""
        operations = []
        port_type = self.root.find('.//wsdl:portType', self.NAMESPACES)
        
        if port_type is None:
            return operations
        
        for op_elem in port_type.findall('wsdl:operation', self.NAMESPACES):
            op_name = op_elem.get('name', '')
            
            # Documentation
            doc_elem = op_elem.find('wsdl:documentation', self.NAMESPACES)
            doc = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else ""
            
            # Paramètres d'entrée
            input_params = self._extract_params_from_message(op_elem, 'input')
            
            # Paramètres de sortie
            output_params = self._extract_params_from_message(op_elem, 'output')
            
            operations.append(ServiceOperation(
                name=op_name,
                input_params=input_params,
                output_params=output_params,
                documentation=doc
            ))
        
        return operations
    
    def _extract_params_from_message(self, op_elem, msg_type: str) -> List[str]:
        """Extrait les paramètres d'un message (input ou output)"""
        params = []
        
        msg_elem = op_elem.find(f'wsdl:{msg_type}', self.NAMESPACES)
        if msg_elem is None:
            return params
        
        msg_name = msg_elem.get('message', '')
        if ':' in msg_name:
            msg_name = msg_name.split(':')[-1]
        
        # Trouver le message
        message = self.root.find(f".//wsdl:message[@name='{msg_name}']", self.NAMESPACES)
        if message is None:
            return params
        
        # Récupérer les parts
        for part in message.findall('wsdl:part', self.NAMESPACES):
            part_type = part.get('type', '') or part.get('element', '')
            if ':' in part_type:
                part_type = part_type.split(':')[-1]
            
            # Récupérer les éléments du type complexe
            complex_params = self._extract_complex_type_elements(part_type)
            params.extend(complex_params)
        
        return params
    
    def _extract_complex_type_elements(self, type_name: str) -> List[str]:
        """Extrait les éléments d'un type complexe"""
        elements = []
        
        schema = self.root.find('.//xsd:schema', self.NAMESPACES)
        if schema is None:
            return elements
        
        complex_type = schema.find(f".//xsd:complexType[@name='{type_name}']", self.NAMESPACES)
        if complex_type is None:
            return elements
        
        sequence = complex_type.find('.//xsd:sequence', self.NAMESPACES)
        if sequence is not None:
            for elem in sequence.findall('xsd:element', self.NAMESPACES):
                elem_name = elem.get('name', '')
                if elem_name:
                    elements.append(elem_name)
        
        return elements


class ClassicServiceRegistry:
    """Registre simple basé uniquement sur les WSDL"""
    
    def __init__(self, wsdl_dir: str = "services/wsdl/original"):
        self.wsdl_dir = wsdl_dir
        self.services: Dict[str, ServiceInfo] = {}
        self.load_services()
    
    def load_services(self):
        """Charge tous les services depuis les WSDL"""
        print(f"Chargement des services depuis {self.wsdl_dir}...")
        
        if not os.path.exists(self.wsdl_dir):
            print(f"❌ Répertoire non trouvé: {self.wsdl_dir}")
            return
        
        wsdl_files = [f for f in os.listdir(self.wsdl_dir) if f.endswith('.wsdl')]
        
        for filename in wsdl_files:
            filepath = os.path.join(self.wsdl_dir, filename)
            try:
                parser = ClassicWSDLParser(filepath)
                service_info = parser.parse()
                self.services[service_info.name] = service_info
                print(f"   {service_info.name} (catégorie: {service_info.get_category()})")
            except Exception as e:
                print(f"   ❌ Erreur avec {filename}: {e}")
        
        print(f"\n{len(self.services)} services chargés\n")
    
    def find_by_category(self, category: str) -> List[ServiceInfo]:
        """Trouve les services d'une catégorie"""
        results = []
        for service in self.services.values():
            if service.get_category() == category:
                results.append(service)
        return results
    
    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Récupère un service par nom"""
        return self.services.get(name)
    
    def list_all(self) -> List[str]:
        """Liste tous les services"""
        return list(self.services.keys())


# Test
if __name__ == "__main__":
    print("Test du Classic WSDL Parser\n")
    
    # Test parsing d'un WSDL
    wsdl_file = "services/wsdl/original/AmadeusFlightService.wsdl"
    
    if os.path.exists(wsdl_file):
        print("Test de parsing d'un WSDL:")
        print(f"Fichier: {wsdl_file}\n")
        
        parser = ClassicWSDLParser(wsdl_file)
        service = parser.parse()
        
        print(f"Service: {service.name}")
        print(f"Endpoint: {service.endpoint}")
        print(f"Catégorie détectée: {service.get_category()}")
        print(f"Nombre d'opérations: {len(service.operations)}\n")
        
        for op in service.operations:
            print(f"  Opération: {op.name}")
            print(f"    Entrées: {op.input_params}")
            print(f"    Sorties: {op.output_params}")
            print()
    
    # Test du registre
    print("\nTest du registre de services:\n")
    registry = ClassicServiceRegistry()
    
    if registry.services:
        print("\nRecherche par catégorie 'flight':")
        flight_services = registry.find_by_category("flight")
        for service in flight_services:
            print(f"   - {service.name}")