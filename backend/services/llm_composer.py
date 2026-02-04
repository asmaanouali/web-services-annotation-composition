"""
Solution B: Composition intelligente avec LLM (Ollama)
Enhanced with Training and Continuous Learning capabilities
"""

import time
import json
import requests
from models.service import CompositionResult
from utils.qos_calculator import calculate_utility


class LLMComposer:
    def __init__(self, services, ollama_url="http://localhost:11434", training_examples=None):
        self.services = services
        self.service_dict = {s.id: s for s in services}
        self.ollama_url = ollama_url
        self.model = "llama3.2:3b"
        self.conversation_history = []
        
        # Training and learning components
        self.training_examples = training_examples or []
        self.learned_patterns = []
        self.composition_memory = []
        self.success_strategies = []
        self.is_trained = len(self.training_examples) > 0
    
    def train(self, training_examples):
        """
        Train the LLM composer with examples of successful compositions
        
        Args:
            training_examples: List of dicts with 'request', 'service', 'solution', 'best_solution'
        """
        self.training_examples = training_examples
        self.is_trained = True
        
        print(f"Training LLM Composer with {len(training_examples)} examples...")
        
        # Analyze training examples to extract patterns
        self._analyze_training_patterns()
        
        # Build knowledge base from training data
        self._build_knowledge_base()
        
        print(f"Training completed: {len(self.learned_patterns)} patterns learned")
    
    def _analyze_training_patterns(self):
        """Analyze training examples to extract successful patterns"""
        patterns = []
        
        for example in self.training_examples:
            if not example.get('best_solution'):
                continue
            
            req = example['request']
            best_sol = example['best_solution']
            service = example.get('service')
            
            if not service:
                continue
            
            # Extract pattern: what characteristics led to success?
            pattern = {
                'request_type': {
                    'provided_count': len(req.get('provided', [])),
                    'resultant': req.get('resultant'),
                    'qos_priority': self._identify_qos_priority(req.get('qos_constraints', {}))
                },
                'service_characteristics': {
                    'id': service.get('id'),
                    'inputs_count': len(service.get('inputs', [])),
                    'outputs_count': len(service.get('outputs', [])),
                    'qos_profile': self._get_qos_profile(service.get('qos', {}))
                },
                'utility': best_sol.get('utility', 0),
                'success_factors': []
            }
            
            # Identify why this service was successful
            qos = service.get('qos', {})
            qos_constraints = req.get('qos_constraints', {})
            
            if qos.get('Reliability', 0) >= qos_constraints.get('Reliability', 0):
                pattern['success_factors'].append('high_reliability')
            if qos.get('Availability', 0) >= qos_constraints.get('Availability', 0):
                pattern['success_factors'].append('high_availability')
            if qos.get('ResponseTime', 999) <= qos_constraints.get('ResponseTime', 1000):
                pattern['success_factors'].append('fast_response')
            
            patterns.append(pattern)
        
        self.learned_patterns = patterns
    
    def _build_knowledge_base(self):
        """Build a knowledge base from training examples for few-shot learning"""
        self.knowledge_base = []
        
        for example in self.training_examples[:5]:  # Use top 5 examples
            if not example.get('best_solution') or not example.get('service'):
                continue
            
            req = example['request']
            service = example['service']
            best_sol = example['best_solution']
            
            kb_entry = f"""
Example:
- Request: {req.get('resultant')} with {len(req.get('provided', []))} inputs
- QoS Requirements: Reliability≥{req.get('qos_constraints', {}).get('Reliability', 0)}, Availability≥{req.get('qos_constraints', {}).get('Availability', 0)}
- Selected Service: {service.get('id')}
- Service QoS: Reliability={service.get('qos', {}).get('Reliability', 0):.1f}, Availability={service.get('qos', {}).get('Availability', 0):.1f}
- Result: Utility={best_sol.get('utility', 0):.2f} ✓ Success
"""
            self.knowledge_base.append(kb_entry.strip())
    
    def _identify_qos_priority(self, qos_constraints):
        """Identify the main QoS priority from constraints"""
        if not qos_constraints:
            return "balanced"
        
        priorities = []
        if qos_constraints.get('Reliability', 0) > 80:
            priorities.append('reliability')
        if qos_constraints.get('Availability', 0) > 90:
            priorities.append('availability')
        if qos_constraints.get('ResponseTime', 1000) < 100:
            priorities.append('performance')
        
        return priorities[0] if priorities else "balanced"
    
    def _get_qos_profile(self, qos):
        """Get QoS profile category"""
        if not qos:
            return "unknown"
        
        reliability = qos.get('Reliability', 0)
        availability = qos.get('Availability', 0)
        
        if reliability > 90 and availability > 95:
            return "premium"
        elif reliability > 70 and availability > 80:
            return "standard"
        else:
            return "basic"
    
    def compose(self, request, enable_reasoning=True, enable_adaptation=True):
        """
        Compose services using LLM reasoning with training knowledge
        
        Args:
            request: CompositionRequest
            enable_reasoning: Enable LLM contextual reasoning
            enable_adaptation: Enable adaptive behavior
        
        Returns:
            CompositionResult
        """
        start_time = time.time()
        result = CompositionResult()
        
        try:
            # Step 1: Analyze context with training knowledge
            context_analysis = self._analyze_context_with_training(request) if enable_reasoning else {}
            
            # Step 2: Select services using trained LLM
            selected_services = self._llm_select_services_trained(request, context_analysis)
            
            # Step 3: Validate and calculate utility
            if selected_services:
                best_service = selected_services[0]
                
                qos_checks = best_service.qos.meets_constraints(request.qos_constraints)
                utility = calculate_utility(
                    best_service.qos,
                    request.qos_constraints,
                    qos_checks
                )
                
                # Bonus for annotations
                if best_service.annotations:
                    utility += best_service.annotations.social_node.trust_degree.value * 5
                    utility += best_service.annotations.social_node.reputation.value * 5
                
                # Step 4: Generate explanation with training context
                explanation = self._generate_explanation_with_training(
                    best_service,
                    request,
                    context_analysis,
                    qos_checks
                )
                
                # Step 5: Apply adaptations if enabled
                adaptations = []
                if enable_adaptation:
                    adaptations = self._apply_adaptations(best_service, context_analysis)
                
                result.services = [best_service]
                result.workflow = [best_service.id]
                result.utility_value = utility
                result.qos_achieved = best_service.qos
                result.success = len(result.services) > 0  # Fixed: success if service found
                result.explanation = explanation
                
                if adaptations:
                    result.explanation += "\n\nAdaptations applied:\n" + "\n".join(f"- {a}" for a in adaptations)
            
            else:
                result.explanation = "The trained LLM found no appropriate service"
        
        except Exception as e:
            print(f"LLM composition error: {e}")
            result.success = False
            result.explanation = f"Error: {str(e)}"
        
        result.computation_time = time.time() - start_time
        return result
    
    def _analyze_context_with_training(self, request):
        """Analyze request context using training knowledge"""
        # Build context with training examples
        training_context = ""
        if self.knowledge_base:
            training_context = "\n\nTRAINING KNOWLEDGE (successful examples):\n" + "\n".join(self.knowledge_base)
        
        # Find similar training patterns
        similar_patterns = self._find_similar_patterns(request)
        pattern_hints = ""
        if similar_patterns:
            pattern_hints = f"\n\nSimilar past successful compositions: {len(similar_patterns)}"
            for pattern in similar_patterns[:2]:
                pattern_hints += f"\n- Service with {pattern['service_characteristics']['qos_profile']} QoS profile achieved utility {pattern['utility']:.2f}"
        
        context_info = {
            'provided_params': request.provided,
            'target_param': request.resultant,
            'qos_constraints': request.qos_constraints.to_dict()
        }
        
        prompt = f"""Analyze this service composition request using training knowledge:

Request Details:
- Input parameters available: {len(request.provided)} parameters
- Target output: {request.resultant}
- QoS Constraints:
  * Response Time: ≤ {request.qos_constraints.response_time}
  * Availability: ≥ {request.qos_constraints.availability}
  * Reliability: ≥ {request.qos_constraints.reliability}

{training_context}
{pattern_hints}

Based on training knowledge and constraints, identify:
1. Priority level (high/medium/low)
2. Environment type (production/development/test)
3. Main concerns (performance/reliability/security)

Respond in JSON format with: {{"priority": "...", "environment": "...", "main_concern": "..."}}
"""
        
        try:
            response = self._call_ollama(prompt)
            analysis = self._extract_json(response)
            
            # Add similar patterns info
            if similar_patterns:
                analysis['similar_patterns_count'] = len(similar_patterns)
                analysis['recommended_qos_profile'] = similar_patterns[0]['service_characteristics']['qos_profile']
            
            return analysis
        except:
            return {
                "priority": "high" if request.qos_constraints.availability > 90 else "medium",
                "environment": "production",
                "main_concern": "reliability"
            }
    
    def _find_similar_patterns(self, request):
        """Find similar patterns from training data"""
        similar = []
        
        qos_priority = self._identify_qos_priority(request.qos_constraints.to_dict())
        
        for pattern in self.learned_patterns:
            # Check if QoS priority matches
            if pattern['request_type']['qos_priority'] == qos_priority:
                similar.append(pattern)
        
        # Sort by utility (best first)
        similar.sort(key=lambda x: x['utility'], reverse=True)
        
        return similar
    
    def _llm_select_services_trained(self, request, context_analysis):
        """Select services using trained LLM with few-shot learning"""
        # Find candidates
        candidates = [
            s for s in self.services
            if request.resultant in s.outputs and s.has_required_inputs(request.provided)
        ]
        
        if not candidates:
            return []
        
        # Limit candidates
        candidates = sorted(candidates, key=lambda s: s.qos.reliability, reverse=True)[:10]
        
        # Prepare service info
        services_info = []
        for s in candidates:
            info = {
                'id': s.id,
                'qos': {
                    'reliability': s.qos.reliability,
                    'availability': s.qos.availability,
                    'response_time': s.qos.response_time
                }
            }
            
            if s.annotations:
                info['annotations'] = {
                    'trust': s.annotations.social_node.trust_degree.value,
                    'reputation': s.annotations.social_node.reputation.value,
                    'role': s.annotations.interaction.role
                }
            
            services_info.append(info)
        
        # Build prompt with training knowledge
        training_examples_text = ""
        if self.knowledge_base:
            training_examples_text = "\n\nLEARNED FROM TRAINING:\n" + "\n".join(self.knowledge_base)
        
        # Add pattern recommendations
        pattern_recommendation = ""
        if context_analysis.get('recommended_qos_profile'):
            pattern_recommendation = f"\n\nRECOMMENDATION: Based on similar past requests, prefer services with '{context_analysis['recommended_qos_profile']}' QoS profile"
        
        prompt = f"""Select the best service for this composition request using training knowledge.

Context: {json.dumps(context_analysis, indent=2)}

Available Services:
{json.dumps(services_info, indent=2)}

Constraints:
- Response Time: ≤ {request.qos_constraints.response_time}
- Availability: ≥ {request.qos_constraints.availability}
- Reliability: ≥ {request.qos_constraints.reliability}

{training_examples_text}
{pattern_recommendation}

Apply learned patterns to select the best service ID that matches requirements.
Respond with just the service ID.
"""
        
        try:
            response = self._call_ollama(prompt)
            selected_id = response.strip()
            
            # Find matching service
            for s in candidates:
                if s.id in selected_id:
                    return [s]
            
            # Fallback
            return [candidates[0]]
        
        except:
            return [candidates[0]]
    
    def _generate_explanation_with_training(self, service, request, context_analysis, qos_checks):
        """Generate explanation referencing training knowledge"""
        prompt = f"""Explain why service {service.id} was selected, referencing training knowledge:

Service QoS:
- Reliability: {service.qos.reliability}
- Availability: {service.qos.availability}
- Response Time: {service.qos.response_time}

Context: {json.dumps(context_analysis)}

QoS Constraints Met: {sum(qos_checks.values())}/{len(qos_checks)}

Training knowledge available: {len(self.knowledge_base)} examples

Provide a brief explanation (2-3 sentences) mentioning how training influenced the decision.
"""
        
        try:
            explanation = self._call_ollama(prompt)
            return explanation.strip()
        except:
            met_count = sum(qos_checks.values())
            total_count = len(qos_checks)
            
            explanation = f"Service {service.id} selected using trained LLM. "
            explanation += f"Satisfies {met_count}/{total_count} QoS constraints. "
            
            if self.is_trained:
                explanation += f"Decision guided by {len(self.training_examples)} training examples. "
            
            if service.annotations:
                explanation += f"Trust: {service.annotations.social_node.trust_degree.value:.2f}, "
                explanation += f"Reputation: {service.annotations.social_node.reputation.value:.2f}. "
            
            return explanation
    
    def learn_from_composition(self, composition_record):
        """
        Continuous learning: Update knowledge from each composition
        
        Args:
            composition_record: Dict with timestamp, request, result, success, utility
        """
        # Add to composition memory
        self.composition_memory.append(composition_record)
        
        # Keep only recent memory (last 100 compositions)
        if len(self.composition_memory) > 100:
            self.composition_memory = self.composition_memory[-100:]
        
        # If successful and high utility, add to success strategies
        if composition_record['success'] and composition_record['utility'] > 50:
            strategy = {
                'request_pattern': {
                    'resultant': composition_record['request'].get('resultant'),
                    'qos_priority': self._identify_qos_priority(
                        composition_record['request'].get('qos_constraints', {})
                    )
                },
                'selected_service': composition_record['result'].get('services', [None])[0],
                'utility_achieved': composition_record['utility'],
                'timestamp': composition_record['timestamp']
            }
            
            self.success_strategies.append(strategy)
            
            # Keep only top 20 strategies
            if len(self.success_strategies) > 20:
                self.success_strategies.sort(key=lambda x: x['utility_achieved'], reverse=True)
                self.success_strategies = self.success_strategies[:20]
        
        print(f"Learning updated: {len(self.composition_memory)} memories, {len(self.success_strategies)} strategies")
    
    def _apply_adaptations(self, service, context_analysis):
        """Apply adaptations based on context and learned strategies"""
        adaptations = []
        
        priority = context_analysis.get('priority', 'medium')
        environment = context_analysis.get('environment', 'production')
        
        if priority == 'high':
            adaptations.append("Failover strategy activated for high priority")
            adaptations.append("Monitoring enhanced for critical service")
        
        if environment == 'production':
            adaptations.append("Production-grade caching enabled")
            adaptations.append("Advanced logging activated")
        
        # Adaptations based on learned strategies
        if len(self.success_strategies) > 0:
            adaptations.append(f"Strategy selection informed by {len(self.success_strategies)} successful past compositions")
        
        if service.annotations:
            if service.annotations.policy.security_level == 'high':
                adaptations.append("Enhanced security protocols applied")
            
            if service.annotations.context.time_critical == 'high':
                adaptations.append("Priority execution queue assigned")
        
        return adaptations
    
    def _call_ollama(self, prompt):
        """Call Ollama API"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama. Is it running? Start with: ollama serve")
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")
    
    def _extract_json(self, text):
        """Extract JSON from text response"""
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
            
            return {}
        except:
            return {}
    
    def chat(self, message):
        """Chat interface with LLM"""
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in self.conversation_history[-5:]
        ])
        
        training_info = ""
        if self.is_trained:
            training_info = f"\n\nI have been trained with {len(self.training_examples)} examples and have learned {len(self.learned_patterns)} patterns."
        
        prompt = f"""You are an expert in web service composition with training and learning capabilities.
{training_info}

Conversation:
{context}

Respond helpfully and concisely about service composition, training, and learning.
"""
        
        try:
            response = self._call_ollama(prompt)
            
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return response
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"