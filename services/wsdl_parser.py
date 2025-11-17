"""
Parser WSDL - Extraction des informations d'un fichier WSDL
"""
from lxml import etree
import os

class WSDLParser:
    """Classe pour parser et extraire les informations d'un fichier WSDL"""
    
    # Namespaces couramment utilisés dans WSDL
    NAMESPACES = {
        'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
        'soap': 'http://schemas.xmlsoap.org/wsdl/soap/',
        'xsd': 'http://www.w3.org/2001/XMLSchema',
        'soap12': 'http://schemas.xmlsoap.org/wsdl/soap12/'
    }
    
    def __init__(self, wsdl_path):
        """
        Initialise le parser avec le chemin du fichier WSDL
        
        Args:
            wsdl_path (str): Chemin vers le fichier WSDL
        """
        self.wsdl_path = wsdl_path
        self.tree = None
        self.root = None
        self.service_info = {}
        
    def parse(self):
        """
        Parse le fichier WSDL et extrait toutes les informations
        
        Returns:
            dict: Informations structurées du service
        """
        if not os.path.exists(self.wsdl_path):
            raise FileNotFoundError(f"Fichier WSDL non trouvé : {self.wsdl_path}")
        
        # Parser le XML
        self.tree = etree.parse(self.wsdl_path)
        self.root = self.tree.getroot()
        
        # Extraire les informations
        self.service_info = {
            'service_name': self._extract_service_name(),
            'target_namespace': self._extract_target_namespace(),
            'operations': self._extract_operations(),
            'messages': self._extract_messages(),
            'types': self._extract_types(),
            'endpoint': self._extract_endpoint(),
            'raw_wsdl': self._get_raw_wsdl()
        }
        
        return self.service_info
    
    def _extract_service_name(self):
        """Extrait le nom du service"""
        service = self.root.find('.//wsdl:service', self.NAMESPACES)
        if service is not None:
            return service.get('name', 'UnknownService')
        
        # Fallback sur l'attribut name de definitions
        return self.root.get('name', 'UnknownService')
    
    def _extract_target_namespace(self):
        """Extrait le namespace cible"""
        return self.root.get('targetNamespace', '')
    
    def _extract_operations(self):
        """Extrait toutes les opérations disponibles"""
        operations = []
        
        # Chercher dans portType
        port_types = self.root.findall('.//wsdl:portType', self.NAMESPACES)
        
        for port_type in port_types:
            ops = port_type.findall('.//wsdl:operation', self.NAMESPACES)
            
            for op in ops:
                op_name = op.get('name', '')
                
                # Input
                input_elem = op.find('wsdl:input', self.NAMESPACES)
                input_msg = input_elem.get('message', '').split(':')[-1] if input_elem is not None else ''
                
                # Output
                output_elem = op.find('wsdl:output', self.NAMESPACES)
                output_msg = output_elem.get('message', '').split(':')[-1] if output_elem is not None else ''
                
                operations.append({
                    'name': op_name,
                    'input_message': input_msg,
                    'output_message': output_msg
                })
        
        return operations
    
    def _extract_messages(self):
        """Extrait les définitions des messages"""
        messages = {}
        
        msg_elements = self.root.findall('.//wsdl:message', self.NAMESPACES)
        
        for msg in msg_elements:
            msg_name = msg.get('name', '')
            parts = []
            
            for part in msg.findall('wsdl:part', self.NAMESPACES):
                part_info = {
                    'name': part.get('name', ''),
                    'element': part.get('element', '').split(':')[-1],
                    'type': part.get('type', '').split(':')[-1]
                }
                parts.append(part_info)
            
            messages[msg_name] = {
                'parts': parts
            }
        
        return messages
    
    def _extract_types(self):
        """Extrait les types de données définis dans le schéma"""
        types_info = []
        
        # Chercher tous les éléments dans le schéma
        elements = self.root.findall('.//xsd:element', self.NAMESPACES)
        
        for elem in elements:
            elem_name = elem.get('name', '')
            elem_type = elem.get('type', '')
            
            # Si c'est un complexType, extraire ses champs
            complex_type = elem.find('.//xsd:complexType', self.NAMESPACES)
            fields = []
            
            if complex_type is not None:
                sequence = complex_type.find('.//xsd:sequence', self.NAMESPACES)
                if sequence is not None:
                    for field in sequence.findall('xsd:element', self.NAMESPACES):
                        fields.append({
                            'name': field.get('name', ''),
                            'type': field.get('type', '').split(':')[-1]
                        })
            
            types_info.append({
                'name': elem_name,
                'type': elem_type.split(':')[-1] if elem_type else 'complexType',
                'fields': fields
            })
        
        return types_info
    
    def _extract_endpoint(self):
        """Extrait l'URL de l'endpoint du service"""
        # SOAP 1.1
        soap_address = self.root.find('.//soap:address', self.NAMESPACES)
        if soap_address is not None:
            return soap_address.get('location', '')
        
        # SOAP 1.2
        soap12_address = self.root.find('.//soap12:address', self.NAMESPACES)
        if soap12_address is not None:
            return soap12_address.get('location', '')
        
        return ''
    
    def _get_raw_wsdl(self):
        """Retourne le contenu brut du WSDL en string"""
        with open(self.wsdl_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def get_summary(self):
        """
        Génère un résumé textuel du service pour le LLM
        
        Returns:
            str: Résumé formaté
        """
        if not self.service_info:
            self.parse()
        
        summary = f"# Service SOAP: {self.service_info['service_name']}\n\n"
        summary += f"Namespace: {self.service_info['target_namespace']}\n"
        summary += f"Endpoint: {self.service_info['endpoint']}\n\n"
        
        summary += "## Opérations disponibles:\n"
        for op in self.service_info['operations']:
            summary += f"- {op['name']}\n"
            summary += f"  Input: {op['input_message']}\n"
            summary += f"  Output: {op['output_message']}\n"
        
        summary += "\n## Types de données:\n"
        for type_def in self.service_info['types']:
            summary += f"- {type_def['name']}\n"
            if type_def['fields']:
                for field in type_def['fields']:
                    summary += f"  - {field['name']}: {field['type']}\n"
        
        return summary
    
    def to_dict(self):
        """Retourne les informations sous forme de dictionnaire"""
        if not self.service_info:
            self.parse()
        return self.service_info