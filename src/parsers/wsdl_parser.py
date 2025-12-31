"""
WSDLParser avec détection LLM libre + Normalisation
1. Détection libre des fonctionnalités (sans limitation)
2. Normalisation en catégories génériques
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
import requests
import json

class WSDLParser:
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama2"):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = 30
    
    def is_ollama_available(self) -> bool:
        """Vérifie si Ollama est disponible"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def detect_functionalities_with_llm(self, service_name: str, operations: List[str]) -> List[str]:
        """
        Étape 1: Détection libre des fonctionnalités avec le LLM
        Aucune limitation de domaine ou de mots-clés
        """
        
        prompt = f"""Analyze this web service and identify ALL the functionalities it provides.

Service Name: {service_name}
Operations: {', '.join(operations)}

Your task:
- Identify what this service does based on its name and operations
- List ALL functionalities in clear, simple terms
- Be specific and comprehensive
- Think freely - don't limit yourself to common categories
- Return ONLY a JSON array of functionality names

Examples of possible functionalities (but don't limit yourself to these):
- stripe payment processing, paypal payment, credit card payment
- hotel booking, flight booking, restaurant reservation
- user authentication, oauth login, token validation
- email notification, SMS sending, push notification
- etc.

Return format (JSON array only):
["functionality1", "functionality2", "functionality3"]

Be creative and accurate based on the service name and operations."""

        try:
            if not self.is_ollama_available():
                return self._fallback_detection(service_name, operations)
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                text = response.json().get('response', '')
                
                # Extraire le JSON array
                start = text.find('[')
                end = text.rfind(']') + 1
                
                if start >= 0 and end > start:
                    functionalities = json.loads(text[start:end])
                    # Nettoyer et valider
                    if isinstance(functionalities, list) and functionalities:
                        return [str(f).strip().lower() for f in functionalities if f]
        except Exception as e:
            print(f"Erreur LLM détection: {e}")
        
        # Fallback si échec
        return self._fallback_detection(service_name, operations)
    
    def normalize_functionalities_with_llm(self, functionalities: List[str]) -> List[str]:
        """
        Étape 2: Normalisation des fonctionnalités en catégories génériques
        Exemple: "stripe payment", "paypal payment" → "payment"
        """
        
        if not functionalities:
            return ["general"]
        
        prompt = f"""Normalize these functionalities into generic categories.

Detected functionalities: {', '.join(functionalities)}

Your task:
- Group similar functionalities into generic categories
- Remove vendor-specific names (stripe, paypal, etc.)
- Remove platform-specific details (android, ios, etc.)
- Keep only the core function

Examples:
- "stripe payment", "paypal payment", "credit card payment" → "payment"
- "hotel booking", "flight booking" → "booking"
- "email notification", "SMS sending" → "notification"
- "oauth login", "token authentication" → "authentication"

Return ONLY a JSON array of normalized generic categories:
["category1", "category2"]

Keep it simple and generic."""

        try:
            if not self.is_ollama_available():
                return self._fallback_normalization(functionalities)
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                text = response.json().get('response', '')
                
                # Extraire le JSON array
                start = text.find('[')
                end = text.rfind(']') + 1
                
                if start >= 0 and end > start:
                    normalized = json.loads(text[start:end])
                    # Nettoyer et valider
                    if isinstance(normalized, list) and normalized:
                        result = list(set([str(f).strip().lower() for f in normalized if f]))
                        return result if result else ["general"]
        except Exception as e:
            print(f"Erreur LLM normalisation: {e}")
        
        # Fallback si échec
        return self._fallback_normalization(functionalities)
    
    def _fallback_normalization(self, functionalities: List[str]) -> List[str]:
        """
        Normalisation de fallback sans LLM
        Utilise des règles simples pour normaliser
        """
        normalized = set()
        
        # Dictionnaire de normalisation basique
        normalization_map = {
            'payment': ['payment', 'pay', 'billing', 'invoice', 'transaction', 'stripe', 'paypal', 'credit'],
            'booking': ['booking', 'reservation', 'reserve', 'book', 'hotel', 'flight', 'ticket'],
            'authentication': ['auth', 'login', 'signin', 'credential', 'token', 'oauth', 'sso'],
            'notification': ['notification', 'notify', 'email', 'sms', 'alert', 'message', 'push'],
            'user': ['user', 'account', 'profile', 'customer'],
            'search': ['search', 'find', 'query', 'lookup', 'filter'],
            'order': ['order', 'purchase', 'cart', 'checkout'],
            'inventory': ['inventory', 'stock', 'product', 'item', 'catalog'],
            'shipping': ['shipping', 'delivery', 'transport', 'logistics'],
            'report': ['report', 'analytics', 'statistics', 'dashboard'],
            'file': ['file', 'document', 'upload', 'download', 'storage'],
            'data': ['data', 'database', 'record', 'sync']
        }
        
        for func in functionalities:
            func_lower = func.lower()
            matched = False
            
            # Chercher dans la map
            for category, keywords in normalization_map.items():
                for keyword in keywords:
                    if keyword in func_lower:
                        normalized.add(category)
                        matched = True
                        break
                if matched:
                    break
            
            # Si pas de match, garder tel quel mais nettoyé
            if not matched:
                # Supprimer les vendors communs
                cleaned = func_lower
                vendors = ['stripe', 'paypal', 'square', 'android', 'ios', 'google', 'facebook', 'twitter']
                for vendor in vendors:
                    cleaned = cleaned.replace(vendor, '').strip()
                
                if cleaned:
                    normalized.add(cleaned)
        
        return list(normalized) if normalized else ["general"]
    
    def _fallback_detection(self, service_name: str, operations: List[str]) -> List[str]:
        """
        Détection de fallback intelligente sans LLM
        """
        functionalities = []
        text = (service_name + ' ' + ' '.join(operations)).lower()
        
        # Analyse du nom du service
        service_words = service_name.lower().replace('service', '').replace('webservice', '').replace('api', '')
        if service_words.strip():
            functionalities.append(service_words.strip())
        
        # Analyse des opérations
        operation_concepts = set()
        for op in operations:
            cleaned = op.lower()
            for prefix in ['get', 'set', 'create', 'update', 'delete', 'add', 'remove', 'fetch', 'retrieve']:
                if cleaned.startswith(prefix):
                    concept = cleaned[len(prefix):].strip()
                    if concept:
                        operation_concepts.add(concept)
                    break
            else:
                if cleaned:
                    operation_concepts.add(cleaned)
        
        functionalities.extend(list(operation_concepts)[:3])
        
        if not functionalities:
            functionalities = ["general"]
        
        return functionalities
    
    @staticmethod
    def parse(content: str, filename: str, ollama_url: str = "http://localhost:11434", model: str = "llama2") -> Optional[Dict[str, Any]]:
        """
        Parse un fichier WSDL avec détection + normalisation LLM
        """
        parser_instance = WSDLParser(ollama_url, model)
        
        try:
            root = ET.fromstring(content)
            ns = {
                'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
                'soap': 'http://schemas.xmlsoap.org/wsdl/soap/'
            }
            
            # Extraire les opérations
            operations = []
            for op in root.findall('.//wsdl:portType/wsdl:operation', ns):
                name = op.get('name')
                if name:
                    operations.append(name)
            
            if not operations:
                for op in root.findall('.//wsdl:binding/wsdl:operation', ns):
                    name = op.get('name')
                    if name:
                        operations.append(name)
            
            # Extraire l'endpoint
            endpoint = None
            for addr in root.findall('.//soap:address', ns):
                endpoint = addr.get('location')
                break
            
            # Nom du service
            service_name = filename.replace('.wsdl', '').replace('.xml', '')
            for svc in root.findall('.//wsdl:service', ns):
                name = svc.get('name')
                if name:
                    service_name = name
                    break
            
            if not endpoint:
                endpoint = f"http://localhost:8080/services/{service_name}"
            
            if not operations:
                operations = ['execute', 'process', 'handle']
            
            # ÉTAPE 1: Détection libre avec LLM
            print(f"🤖 Détection LLM des fonctionnalités pour {service_name}...")
            raw_functionalities = parser_instance.detect_functionalities_with_llm(service_name, operations)
            print(f"📋 Détectées: {', '.join(raw_functionalities)}")
            
            # ÉTAPE 2: Normalisation en catégories génériques
            print(f"🔄 Normalisation en catégories génériques...")
            normalized_functionalities = parser_instance.normalize_functionalities_with_llm(raw_functionalities)
            print(f"✅ Catégories: {', '.join(normalized_functionalities)}")
            
            return {
                'name': service_name,
                'filename': filename,
                'operations': list(set(operations)),
                'endpoint': endpoint,
                'functionalities': normalized_functionalities
            }
        except Exception as e:
            print(f"⚠️ Erreur parsing {filename}: {e}")
            # Fallback complet
            service_name = filename.replace('.wsdl', '').replace('.xml', '')
            operations = ['execute', 'process']
            raw_func = parser_instance._fallback_detection(service_name, operations)
            functionalities = parser_instance._fallback_normalization(raw_func)
            
            return {
                'name': service_name,
                'filename': filename,
                'operations': operations,
                'endpoint': f"http://localhost:8080/services/{service_name}",
                'functionalities': functionalities
            }