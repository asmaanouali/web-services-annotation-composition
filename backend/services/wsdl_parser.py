"""
PARSER COMPLET CORRIGÉ pour Discovery & Composition
====================================================

Remplace TOUT le contenu de backend/services/wsdl_parser.py
avec ce fichier complet.
"""

import xml.etree.ElementTree as ET
import xmltodict
import re
from models.service import WebService, QoS


class WSDLParser:
    def __init__(self):
        self.services = []
    
    def parse_file(self, filepath):
        """Parse un fichier WSDL"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_content(content, filepath)
        except Exception as e:
            print(f"Erreur lors du parsing de {filepath}: {e}")
            return None
    
    def parse_content(self, content, filename="unknown"):
        """Parse le contenu WSDL"""
        try:
            # Extraire l'ID du service depuis le nom du fichier
            service_id = self._extract_service_id(filename)
            
            service = WebService(service_id)
            service.wsdl_content = content
            
            # Parser XML
            root = ET.fromstring(content)
            
            # Extraire inputs et outputs
            service.inputs, service.outputs = self._extract_parameters(root)
            
            # Extraire QoS depuis les commentaires ou extensions
            service.qos = self._extract_qos(root, content)
            
            return service
        except Exception as e:
            print(f"Erreur lors du parsing du contenu: {e}")
            return None
    
    def _extract_service_id(self, filename):
        """Extrait l'ID du service depuis le nom de fichier"""
        # Format: servicepXXaYYYYYYY.wsdl
        match = re.search(r'service(p\d+a\d+)', filename)
        if match:
            return match.group(1)
        return filename.replace('.wsdl', '')
    
    def _extract_parameters(self, root):
        """Extrait les paramètres d'entrée et de sortie"""
        inputs = []
        outputs = []
        
        # Chercher tous les messages (avec et sans namespace)
        messages = []
        
        # Méthode 1: Avec namespace explicite
        for ns in ['http://schemas.xmlsoap.org/wsdl/', '']:
            ns_prefix = f'{{{ns}}}' if ns else ''
            messages.extend(root.findall(f'.//{ns_prefix}message'))
        
        # Méthode 2: Sans considération de namespace
        for elem in root.iter():
            if elem.tag.endswith('message') or elem.tag == 'message':
                if elem not in messages:
                    messages.append(elem)
        
        # Parser les messages
        for msg in messages:
            msg_name = msg.get('name', '').lower()
            
            # Trouver toutes les parts du message
            parts = []
            for part_elem in msg:
                if part_elem.tag.endswith('part') or part_elem.tag == 'part':
                    parts.append(part_elem)
            
            for part in parts:
                param_name = part.get('name') or part.get('element', '').split(':')[-1]
                
                if param_name and param_name.strip():
                    # Déterminer si c'est un input ou output
                    is_input = any(keyword in msg_name for keyword in ['request', 'input', 'in'])
                    is_output = any(keyword in msg_name for keyword in ['response', 'output', 'out', 'result'])
                    
                    # Si le message se termine par 'Request' ou contient 'Request'
                    if 'request' in msg_name and param_name not in inputs:
                        inputs.append(param_name)
                    # Si le message se termine par 'Response' ou contient 'Response'
                    elif 'response' in msg_name and param_name not in outputs:
                        outputs.append(param_name)
                    # Si on ne peut pas déterminer, regarder la structure du portType
                    elif is_input and param_name not in inputs:
                        inputs.append(param_name)
                    elif is_output and param_name not in outputs:
                        outputs.append(param_name)
        
        # Si pas de paramètres trouvés, utiliser une approche générique
        if not inputs and not outputs:
            inputs, outputs = self._extract_generic_parameters(root)
        
        return inputs, outputs
    
    def _extract_generic_parameters(self, root):
        """Extraction générique des paramètres"""
        inputs = []
        outputs = []
        
        # Chercher tous les éléments qui ressemblent à des paramètres
        for elem in root.iter():
            name = elem.get('name', '')
            if name.startswith('p') and 'a' in name:
                # Format pXXaYYYYYYY
                if elem.tag.endswith('input') or 'request' in elem.tag.lower():
                    inputs.append(name)
                elif elem.tag.endswith('output') or 'response' in elem.tag.lower():
                    outputs.append(name)
        
        return inputs, outputs
    
    def _extract_qos(self, root, content):
        """Extrait les QoS depuis le WSDL"""
        qos = QoS()
        qos_found = False
        
        # Méthode 1: Chercher la balise <QoS> dans le XML (avec ou sans namespace)
        qos_element = None
        
        # Essayer sans namespace
        qos_element = root.find('.//QoS')
        
        # Essayer avec différents namespaces possibles
        if qos_element is None:
            for elem in root.iter():
                if elem.tag.endswith('QoS') or elem.tag == 'QoS':
                    qos_element = elem
                    break
        
        if qos_element is not None:
            qos_data = {}
            for child in qos_element:
                # Obtenir le nom du tag sans namespace
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                # Format 1: <ResponseTime Value="409"/>
                value = child.get('Value')
                
                # Format 2: <ResponseTime>409</ResponseTime>
                if not value:
                    value = child.text
                
                if value:
                    try:
                        qos_data[tag_name] = float(value)
                    except:
                        pass
            
            if qos_data:
                qos = QoS(qos_data)
                qos_found = True
        
        # Méthode 2: Chercher les QoS dans les commentaires XML
        if not qos_found:
            qos_pattern = r'<!--\s*QoS:\s*({[^}]+})\s*-->'
            match = re.search(qos_pattern, content)
            
            if match:
                try:
                    qos_str = match.group(1)
                    qos_data = eval(qos_str)
                    qos = QoS(qos_data)
                    qos_found = True
                except:
                    pass
        
        return qos
    
    def parse_directory(self, directory):
        """Parse tous les fichiers WSDL d'un dossier"""
        import os
        services = []
        
        for filename in os.listdir(directory):
            if filename.endswith('.wsdl') or filename.endswith('.xml'):
                filepath = os.path.join(directory, filename)
                service = self.parse_file(filepath)
                if service:
                    services.append(service)
        
        return services


def parse_requests_xml(filepath):
    """
    Parse le fichier Requests.xml
    Support 3 formats:
    1. Format standard: <Requests><Request id="...">...</Request></Requests>
    2. Format WSChallenge Discovery: <WSChallenge><DiscoveryRoutine>...</DiscoveryRoutine></WSChallenge>
    3. Format WSChallenge Composition: <WSChallenge><CompositionRoutine>...</CompositionRoutine></WSChallenge>
    """
    from models.service import CompositionRequest
    
    requests = []
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Détecter le format du fichier
        if root.tag == 'WSChallenge':
            # Format WSChallenge - chercher DiscoveryRoutine OU CompositionRoutine
            routines = root.findall('.//DiscoveryRoutine')
            routine_type = 'Discovery'
            
            if not routines:  # Si pas de DiscoveryRoutine, chercher CompositionRoutine
                routines = root.findall('.//CompositionRoutine')
                routine_type = 'Composition'
            
            print(f"📋 Found {len(routines)} {routine_type}Routine(s) in file")
            
            for routine in routines:
                request_name = routine.get('name', 'unknown')
                comp_req = CompositionRequest(request_name)
                
                # Provided parameters
                provided = routine.find('Provided')
                if provided is not None and provided.text:
                    comp_req.provided = [p.strip() for p in provided.text.split(',') if p.strip()]
                
                # Resultant parameter
                resultant = routine.find('Resultant')
                if resultant is not None and resultant.text:
                    comp_req.resultant = resultant.text.strip()
                else:
                    print(f"⚠️ Warning: Request '{request_name}' has no Resultant element — skipping (composition would always fail)")
                    continue
                
                # QoS Constraints (format: valeur1,valeur2,valeur3,...)
                qos_elem = routine.find('QoS')
                if qos_elem is not None and qos_elem.text:
                    qos_values = [float(v.strip()) for v in qos_elem.text.split(',') if v.strip()]
                    
                    # Mapper les valeurs QoS selon l'ordre standard
                    # Format attendu: ResponseTime, Availability, Throughput, Successability, 
                    #                 Reliability, Compliance, BestPractices, Latency, Documentation
                    qos_keys = [
                        'ResponseTime', 'Availability', 'Throughput', 'Successability',
                        'Reliability', 'Compliance', 'BestPractices', 'Latency', 'Documentation'
                    ]
                    
                    qos_data = {}
                    for i, key in enumerate(qos_keys):
                        if i < len(qos_values):
                            qos_data[key] = qos_values[i]
                        else:
                            qos_data[key] = 0
                    
                    comp_req.qos_constraints = QoS(qos_data)
                
                requests.append(comp_req)
        
        else:
            # Format standard (ancien format)
            for req in root.findall('.//Request'):
                request_id = req.get('id') or req.get('name', 'unknown')
                comp_req = CompositionRequest(request_id)
                
                # Provided parameters
                provided = req.find('Provided')
                if provided is not None:
                    comp_req.provided = [p.strip() for p in provided.text.split(';') if p.strip()]
                
                # Resultant parameter
                resultant = req.find('Resultant')
                if resultant is not None and resultant.text:
                    comp_req.resultant = resultant.text.strip()
                else:
                    print(f"⚠️ Warning: Request '{request_id}' has no Resultant element — skipping")
                    continue
                
                # QoS Constraints
                qos_elem = req.find('QoS')
                if qos_elem is not None:
                    qos_data = {}
                    for qos_child in qos_elem:
                        try:
                            qos_data[qos_child.tag] = float(qos_child.text)
                        except:
                            qos_data[qos_child.tag] = 0
                    comp_req.qos_constraints = QoS(qos_data)
                
                requests.append(comp_req)
    
    except Exception as e:
        print(f"❌ Erreur lors du parsing des requêtes: {e}")
        import traceback
        traceback.print_exc()
    
    return requests


def parse_best_solutions_xml(filepath):
    """
    Parse le fichier BestSolutions.xml
    Support 2 formats:
    1. Discovery: 1 service unique par case
    2. Composition: LISTE de services par case (workflow/chaîne)
    """
    solutions = {}
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        for case in root.findall('.//case'):
            request_id = case.get('name', 'unknown')
            
            # Trouver TOUS les services dans ce case
            services = case.findall('.//service')
            service_ids = [s.get('name', '').strip() for s in services if s.get('name')]
            
            # Trouver l'utility
            utility_elem = case.find('.//utility')
            utility_value = 0
            if utility_elem is not None:
                utility_str = utility_elem.get('value', '0')
                try:
                    utility_value = float(utility_str)
                except:
                    utility_value = 0
            
            # CORRECTION MAJEURE:
            # - Discovery: service_ids aura 1 élément
            # - Composition: service_ids aura plusieurs éléments (workflow)
            solutions[request_id] = {
                'service_id': service_ids[0] if len(service_ids) == 1 else None,  # Pour compatibilité Discovery
                'service_ids': service_ids,  # NOUVEAU: Liste complète pour Composition
                'utility': utility_value,
                'is_workflow': len(service_ids) > 1  # Flag pour identifier Composition
            }
            
            print(f"  • {request_id}: {len(service_ids)} service(s), utility={utility_value:.2f}")
    
    except Exception as e:
        print(f"❌ Erreur lors du parsing des best solutions: {e}")
        import traceback
        traceback.print_exc()
    
    return solutions