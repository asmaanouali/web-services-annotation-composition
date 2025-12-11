"""
annotation_system/wsdl_parser.py
Parser WSDL pour extraire les informations nécessaires à l'annotation
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class WSDLOperation:
    """Représente une opération WSDL"""
    name: str
    documentation: str
    input_message: str
    output_message: str
    soap_action: str


@dataclass
class WSDLMessage:
    """Représente un message WSDL"""
    name: str
    parts: List[Tuple[str, str]]  # [(part_name, part_type)]


@dataclass
class WSDLType:
    """Représente un type complexe WSDL"""
    name: str
    elements: List[Tuple[str, str, bool]]  # [(element_name, element_type, is_required)]


@dataclass
class WSDLService:
    """Représente un service WSDL complet"""
    name: str
    documentation: str
    endpoint: str
    namespace: str
    operations: List[WSDLOperation]
    messages: Dict[str, WSDLMessage]
    types: Dict[str, WSDLType]


class WSDLParser:
    """Parser pour extraire les informations des fichiers WSDL"""
    
    # Namespaces XML communs
    NAMESPACES = {
        'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
        'soap': 'http://schemas.xmlsoap.org/wsdl/soap/',
        'xsd': 'http://www.w3.org/2001/XMLSchema'
    }
    
    def __init__(self, wsdl_path: str):
        self.wsdl_path = wsdl_path
        self.tree = None
        self.root = None
        self.target_namespace = None
        
    def parse(self) -> WSDLService:
        """Parse le fichier WSDL et retourne un objet WSDLService"""
        try:
            self.tree = ET.parse(self.wsdl_path)
            self.root = self.tree.getroot()
            
            # Extraire le target namespace
            self.target_namespace = self.root.get('targetNamespace', '')
            
            # Parser les différentes parties
            service_info = self._parse_service()
            operations = self._parse_operations()
            messages = self._parse_messages()
            types = self._parse_types()
            
            return WSDLService(
                name=service_info['name'],
                documentation=service_info['documentation'],
                endpoint=service_info['endpoint'],
                namespace=self.target_namespace,
                operations=operations,
                messages=messages,
                types=types
            )
            
        except ET.ParseError as e:
            raise ValueError(f"Erreur de parsing XML: {e}")
        except Exception as e:
            raise ValueError(f"Erreur lors du parsing WSDL: {e}")
    
    def _parse_service(self) -> Dict:
        """Extrait les informations du service"""
        service_elem = self.root.find('.//wsdl:service', self.NAMESPACES)
        
        if service_elem is None:
            raise ValueError("Aucun élément <service> trouvé dans le WSDL")
        
        name = service_elem.get('name', 'UnknownService')
        
        # Documentation
        doc_elem = service_elem.find('wsdl:documentation', self.NAMESPACES)
        documentation = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else ""
        
        # Endpoint SOAP
        address_elem = service_elem.find('.//soap:address', self.NAMESPACES)
        endpoint = address_elem.get('location', '') if address_elem is not None else ""
        
        return {
            'name': name,
            'documentation': documentation,
            'endpoint': endpoint
        }
    
    def _parse_operations(self) -> List[WSDLOperation]:
        """Extrait toutes les opérations du portType"""
        operations = []
        
        # Trouver le portType
        port_type = self.root.find('.//wsdl:portType', self.NAMESPACES)
        if port_type is None:
            return operations
        
        # Parser chaque opération
        for op_elem in port_type.findall('wsdl:operation', self.NAMESPACES):
            name = op_elem.get('name', '')
            
            # Documentation
            doc_elem = op_elem.find('wsdl:documentation', self.NAMESPACES)
            documentation = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else ""
            
            # Input et output messages
            input_elem = op_elem.find('wsdl:input', self.NAMESPACES)
            output_elem = op_elem.find('wsdl:output', self.NAMESPACES)
            
            input_msg = self._extract_message_name(input_elem.get('message', '')) if input_elem is not None else ""
            output_msg = self._extract_message_name(output_elem.get('message', '')) if output_elem is not None else ""
            
            # SOAP Action depuis le binding
            soap_action = self._get_soap_action(name)
            
            operations.append(WSDLOperation(
                name=name,
                documentation=documentation,
                input_message=input_msg,
                output_message=output_msg,
                soap_action=soap_action
            ))
        
        return operations
    
    def _parse_messages(self) -> Dict[str, WSDLMessage]:
        """Extrait tous les messages"""
        messages = {}
        
        for msg_elem in self.root.findall('.//wsdl:message', self.NAMESPACES):
            name = msg_elem.get('name', '')
            parts = []
            
            for part_elem in msg_elem.findall('wsdl:part', self.NAMESPACES):
                part_name = part_elem.get('name', '')
                part_type = part_elem.get('type', '') or part_elem.get('element', '')
                part_type = self._extract_type_name(part_type)
                parts.append((part_name, part_type))
            
            messages[name] = WSDLMessage(name=name, parts=parts)
        
        return messages
    
    def _parse_types(self) -> Dict[str, WSDLType]:
        """Extrait tous les types complexes"""
        types = {}
        
        # Trouver la section types/schema
        schema = self.root.find('.//xsd:schema', self.NAMESPACES)
        if schema is None:
            return types
        
        # Parser les complexTypes
        for complex_type in schema.findall('.//xsd:complexType', self.NAMESPACES):
            type_name = complex_type.get('name', '')
            elements = []
            
            # Trouver la sequence
            sequence = complex_type.find('.//xsd:sequence', self.NAMESPACES)
            if sequence is not None:
                for elem in sequence.findall('xsd:element', self.NAMESPACES):
                    elem_name = elem.get('name', '')
                    elem_type = elem.get('type', '')
                    elem_type = self._extract_type_name(elem_type)
                    
                    # Vérifier si obligatoire
                    min_occurs = elem.get('minOccurs', '1')
                    is_required = min_occurs != '0'
                    
                    elements.append((elem_name, elem_type, is_required))
            
            types[type_name] = WSDLType(name=type_name, elements=elements)
        
        return types
    
    def _get_soap_action(self, operation_name: str) -> str:
        """Récupère le SOAP action pour une opération"""
        # Chercher dans le binding
        binding = self.root.find('.//wsdl:binding', self.NAMESPACES)
        if binding is None:
            return ""
        
        for op in binding.findall('wsdl:operation', self.NAMESPACES):
            if op.get('name') == operation_name:
                soap_op = op.find('soap:operation', self.NAMESPACES)
                if soap_op is not None:
                    return soap_op.get('soapAction', '')
        
        return ""
    
    def _extract_message_name(self, full_name: str) -> str:
        """Extrait le nom du message depuis un nom qualifié (tns:MessageName)"""
        if ':' in full_name:
            return full_name.split(':')[-1]
        return full_name
    
    def _extract_type_name(self, full_type: str) -> str:
        """Extrait le nom du type depuis un type qualifié"""
        if ':' in full_type:
            return full_type.split(':')[-1]
        return full_type
    
    def extract_for_llm(self) -> Dict:
        """
        Extrait les informations pertinentes pour le LLM
        Format simplifié et structuré
        """
        service = self.parse()
        
        llm_data = {
            "service_name": service.name,
            "service_description": service.documentation,
            "endpoint": service.endpoint,
            "namespace": service.namespace,
            "operations": []
        }
        
        for operation in service.operations:
            op_data = {
                "name": operation.name,
                "description": operation.documentation,
                "soap_action": operation.soap_action,
                "input_parameters": [],
                "output_parameters": []
            }
            
            # Extraire les paramètres d'entrée
            if operation.input_message in service.messages:
                input_msg = service.messages[operation.input_message]
                for part_name, part_type in input_msg.parts:
                    if part_type in service.types:
                        type_def = service.types[part_type]
                        for elem_name, elem_type, is_required in type_def.elements:
                            op_data["input_parameters"].append({
                                "name": elem_name,
                                "type": elem_type,
                                "required": is_required
                            })
            
            # Extraire les paramètres de sortie
            if operation.output_message in service.messages:
                output_msg = service.messages[operation.output_message]
                for part_name, part_type in output_msg.parts:
                    if part_type in service.types:
                        type_def = service.types[part_type]
                        for elem_name, elem_type, is_required in type_def.elements:
                            op_data["output_parameters"].append({
                                "name": elem_name,
                                "type": elem_type
                            })
            
            llm_data["operations"].append(op_data)
        
        return llm_data


# Test du parser
if __name__ == "__main__":
    import json
    
    # Tester avec un fichier WSDL
    wsdl_file = "services/wsdl/original/AmadeusFlightService.wsdl"
    
    try:
        parser = WSDLParser(wsdl_file)
        llm_data = parser.extract_for_llm()
        
        print("Parsing WSDL réussi!")
        print(f"\nService: {llm_data['service_name']}")
        print(f"Operations: {len(llm_data['operations'])}")
        
        print("\nDonnées extraites (format JSON):")
        print(json.dumps(llm_data, indent=2))
        
    except Exception as e:
        print(f"Erreur: {e}")