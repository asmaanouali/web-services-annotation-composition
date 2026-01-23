"""
API Flask pour le système de composition de services intelligents
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
import tempfile
from datetime import datetime

from services.wsdl_parser import WSDLParser, parse_requests_xml, parse_best_solutions_xml
from services.annotator import ServiceAnnotator
from services.classic_composer import ClassicComposer
from services.llm_composer import LLMComposer

app = Flask(__name__)
CORS(app)

# Augmenter la limite de taille pour les uploads massifs
app.config['MAX_CONTENT_LENGTH'] = None

# État global de l'application
app_state = {
    'services': [],
    'annotated_services': [],
    'requests': [],
    'best_solutions': {},
    'results_classic': {},
    'results_llm': {},
    'parser': WSDLParser(),
    'annotator': None,
    'classic_composer': None,
    'llm_composer': None
}


@app.route('/api/health', methods=['GET'])
def health_check():
    """Vérification de santé de l'API"""
    return jsonify({
        'status': 'healthy',
        'services_loaded': len(app_state['services']),
        'services_annotated': len(app_state['annotated_services']),
        'requests_loaded': len(app_state['requests'])
    })


@app.route('/api/services/upload', methods=['POST'])
def upload_services():
    """Charge des fichiers WSDL"""
    try:
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        services = []
        errors = []
        
        for idx, file in enumerate(files):
            if idx % 100 == 0:  # Log tous les 100 fichiers
                print(f"Progression: {idx}/{len(files)} fichiers traités")
            
            if file.filename.endswith('.wsdl') or file.filename.endswith('.xml'):
                try:
                    content = file.read().decode('utf-8')
                    service = app_state['parser'].parse_content(content, file.filename)
                    
                    if service:
                        services.append(service)
                    else:
                        errors.append(f"{file.filename}: Parse failed")
                except Exception as e:
                    errors.append(f"{file.filename}: {str(e)}")
        
        print(f"Traitement terminé: {len(services)} services chargés, {len(errors)} erreurs")
        
        if services:
            app_state['services'].extend(services)
            
            # Réinitialiser les composers
            app_state['annotator'] = ServiceAnnotator(app_state['services'])
            app_state['classic_composer'] = ClassicComposer(app_state['services'])
            app_state['llm_composer'] = LLMComposer(app_state['services'])
            
            message = f'{len(services)} services loaded successfully'
            if errors:
                message += f' ({len(errors)} errors)'
            
            return jsonify({
                'message': message,
                'total_services': len(app_state['services']),
                'services': [s.to_dict() for s in services],
                'errors': errors if errors else None
            })
        else:
            return jsonify({
                'error': 'No valid services found',
                'errors': errors[:10],  # Limiter les erreurs affichées
                'total_errors': len(errors)
            }), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/services', methods=['GET'])
def get_services():
    """Récupère la liste des services"""
    return jsonify({
        'services': [s.to_dict() for s in app_state['services']],
        'total': len(app_state['services'])
    })


@app.route('/api/services/<service_id>', methods=['GET'])
def get_service(service_id):
    """Récupère un service spécifique"""
    service = next((s for s in app_state['services'] if s.id == service_id), None)
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    return jsonify(service.to_dict())


@app.route('/api/services/<service_id>/download', methods=['GET'])
def download_annotated_service(service_id):
    """Télécharge un service annoté en format S-WSDL (MOF-based)"""
    try:
        # Trouver le service
        service = next((s for s in app_state['services'] if s.id == service_id), None)
        
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Générer le S-WSDL (Social WSDL selon le modèle MOF)
        xml_content = generate_s_wsdl(service)
        
        # Créer la réponse avec le fichier
        response = Response(xml_content, mimetype='application/xml')
        response.headers['Content-Disposition'] = f'attachment; filename={service_id}_S-WSDL.xml'
        
        return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_s_wsdl(service):
    """
    Génère un S-WSDL (Social WSDL) selon le modèle MOF-based
    Référence: Benna, A., Maamar, Z., & Nacer, M. A. (2016)
    """
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<!-- S-WSDL: Social Web Service Description Language -->')
    xml_lines.append('<!-- Based on MOF-based Social Web Services Description Metamodel -->')
    xml_lines.append('<!-- Reference: Benna et al., MODELSWARD 2016 -->')
    xml_lines.append('')
    
    # Namespace déclaration
    xml_lines.append('<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"')
    xml_lines.append('             xmlns:social="http://cerist.dz/social-ws/2016"')
    xml_lines.append('             xmlns:xsd="http://www.w3.org/2001/XMLSchema"')
    xml_lines.append(f'             name="{service.id}"')
    xml_lines.append(f'             targetNamespace="http://example.com/services/{service.id}">')
    xml_lines.append('')
    
    # 1. WSDL classique (partie standard)
    xml_lines.append('  <!-- ========== WSDL Standard Description ========== -->')
    xml_lines.append('  <types>')
    xml_lines.append('    <xsd:schema targetNamespace="http://example.com/services">')
    
    # Types pour inputs
    for inp in service.inputs:
        xml_lines.append(f'      <xsd:element name="{inp}" type="xsd:string"/>')
    
    # Types pour outputs
    for out in service.outputs:
        xml_lines.append(f'      <xsd:element name="{out}" type="xsd:string"/>')
    
    xml_lines.append('    </xsd:schema>')
    xml_lines.append('  </types>')
    xml_lines.append('')
    
    # Messages
    xml_lines.append('  <message name="InputMessage">')
    for inp in service.inputs:
        xml_lines.append(f'    <part name="{inp}" element="tns:{inp}"/>')
    xml_lines.append('  </message>')
    xml_lines.append('')
    
    xml_lines.append('  <message name="OutputMessage">')
    for out in service.outputs:
        xml_lines.append(f'    <part name="{out}" element="tns:{out}"/>')
    xml_lines.append('  </message>')
    xml_lines.append('')
    
    # PortType
    xml_lines.append('  <portType name="ServicePortType">')
    xml_lines.append(f'    <operation name="execute">')
    xml_lines.append('      <input message="tns:InputMessage"/>')
    xml_lines.append('      <output message="tns:OutputMessage"/>')
    xml_lines.append('    </operation>')
    xml_lines.append('  </portType>')
    xml_lines.append('')
    
    # QoS (dans extensibility element)
    xml_lines.append('  <!-- ========== QoS Properties ========== -->')
    xml_lines.append('  <social:QoS>')
    qos_dict = service.qos if isinstance(service.qos, dict) else vars(service.qos)
    for key, value in qos_dict.items():
        xml_key = key.replace('_', '')
        xml_key = xml_key[0].upper() + xml_key[1:]  # Capitalize
        xml_lines.append(f'    <social:{xml_key}>{value:.2f}</social:{xml_key}>')
    xml_lines.append('  </social:QoS>')
    xml_lines.append('')
    
    # 2. Extension sociale (S-WSDL selon MOF)
    if hasattr(service, 'annotations') and service.annotations:
        xml_lines.append('  <!-- ========== Social Dimension (S-WSDL Extension) ========== -->')
        xml_lines.append('  <!-- Based on MOF-based Social Web Services Metamodel -->')
        xml_lines.append('')
        
        annotations = service.annotations
        social_node = annotations.social_node
        
        # SNNode (Nœud Social)
        xml_lines.append('  <social:SocialNode>')
        xml_lines.append(f'    <social:nodeId>{social_node.node_id}</social:nodeId>')
        xml_lines.append(f'    <social:nodeType>{social_node.node_type}</social:nodeType>')
        xml_lines.append(f'    <social:state>{social_node.state}</social:state>')
        xml_lines.append('')
        
        # Node Degree (Propriétés sociales)
        xml_lines.append('    <!-- Node Degree Properties -->')
        xml_lines.append('    <social:NodeDegree>')
        xml_lines.append(f'      <social:trustDegree value="{social_node.trust_degree.value:.3f}"/>')
        xml_lines.append(f'      <social:reputation value="{social_node.reputation.value:.3f}"/>')
        xml_lines.append(f'      <social:cooperativeness value="{social_node.cooperativeness.value:.3f}"/>')
        
        # Propriétés supplémentaires
        for prop in social_node.properties:
            xml_lines.append(f'      <social:property name="{prop.prop_name}" value="{prop.value:.3f}"/>')
        
        xml_lines.append('    </social:NodeDegree>')
        xml_lines.append('')
        
        # SNAssociations (Relations sociales)
        if social_node.associations:
            xml_lines.append('    <!-- Social Associations -->')
            xml_lines.append('    <social:Associations>')
            
            for assoc in social_node.associations:
                xml_lines.append('      <social:Association>')
                xml_lines.append(f'        <social:sourceNode>{assoc.source_node}</social:sourceNode>')
                xml_lines.append(f'        <social:targetNode>{assoc.target_node}</social:targetNode>')
                
                # Association Type
                xml_lines.append('        <social:AssociationType>')
                xml_lines.append(f'          <social:typeName>{assoc.association_type.type_name}</social:typeName>')
                xml_lines.append(f'          <social:isSymmetric>{str(assoc.association_type.is_symmetric).lower()}</social:isSymmetric>')
                xml_lines.append(f'          <social:supportsTransitivity>{str(assoc.association_type.supports_transitivity).lower()}</social:supportsTransitivity>')
                xml_lines.append(f'          <social:isDependant>{str(assoc.association_type.is_dependent).lower()}</social:isDependant>')
                xml_lines.append(f'          <social:temporalAspect>{assoc.association_type.temporal_aspect}</social:temporalAspect>')
                xml_lines.append('        </social:AssociationType>')
                
                # Association Weight
                xml_lines.append('        <social:AssociationWeight>')
                xml_lines.append(f'          <social:propName>{assoc.association_weight.prop_name}</social:propName>')
                xml_lines.append(f'          <social:value>{assoc.association_weight.value:.3f}</social:value>')
                xml_lines.append(f'          <social:calculationMethod>{assoc.association_weight.calculation_method}</social:calculationMethod>')
                xml_lines.append('        </social:AssociationWeight>')
                
                xml_lines.append('      </social:Association>')
            
            xml_lines.append('    </social:Associations>')
        
        xml_lines.append('  </social:SocialNode>')
        xml_lines.append('')
        
        # Extensions supplémentaires (Interaction, Context, Policy)
        xml_lines.append('  <!-- ========== Extended Annotations ========== -->')
        xml_lines.append('  <social:ExtendedAnnotations>')
        
        # Interaction
        xml_lines.append('    <social:Interaction>')
        inter = annotations.interaction
        inter_dict = inter if isinstance(inter, dict) else vars(inter)
        xml_lines.append(f'      <social:role>{inter_dict.get("role", "worker")}</social:role>')
        
        if inter_dict.get('collaboration_associations'):
            xml_lines.append('      <social:collaborationAssociations>')
            for svc_id in inter_dict['collaboration_associations']:
                xml_lines.append(f'        <social:serviceId>{svc_id}</social:serviceId>')
            xml_lines.append('      </social:collaborationAssociations>')
        
        if inter_dict.get('substitution_associations'):
            xml_lines.append('      <social:substitutionAssociations>')
            for svc_id in inter_dict['substitution_associations']:
                xml_lines.append(f'        <social:serviceId>{svc_id}</social:serviceId>')
            xml_lines.append('      </social:substitutionAssociations>')
        
        if inter_dict.get('depends_on'):
            xml_lines.append('      <social:dependencies>')
            for svc_id in inter_dict['depends_on']:
                xml_lines.append(f'        <social:serviceId>{svc_id}</social:serviceId>')
            xml_lines.append('      </social:dependencies>')
        
        xml_lines.append('    </social:Interaction>')
        xml_lines.append('')
        
        # Context
        xml_lines.append('    <social:Context>')
        ctx = annotations.context
        ctx_dict = ctx if isinstance(ctx, dict) else vars(ctx)
        xml_lines.append(f'      <social:contextAware>{str(ctx_dict.get("context_aware", False)).lower()}</social:contextAware>')
        xml_lines.append(f'      <social:locationSensitive>{str(ctx_dict.get("location_sensitive", False)).lower()}</social:locationSensitive>')
        xml_lines.append(f'      <social:timeCritical>{ctx_dict.get("time_critical", "low")}</social:timeCritical>')
        xml_lines.append(f'      <social:interactionCount>{ctx_dict.get("interaction_count", 0)}</social:interactionCount>')
        
        if ctx_dict.get('last_used'):
            xml_lines.append(f'      <social:lastUsed>{ctx_dict["last_used"]}</social:lastUsed>')
        
        if ctx_dict.get('usage_patterns'):
            xml_lines.append('      <social:usagePatterns>')
            for pattern in ctx_dict['usage_patterns']:
                xml_lines.append(f'        <social:pattern>{pattern}</social:pattern>')
            xml_lines.append('      </social:usagePatterns>')
        
        xml_lines.append('    </social:Context>')
        xml_lines.append('')
        
        # Policy
        xml_lines.append('    <social:Policy>')
        pol = annotations.policy
        pol_dict = pol if isinstance(pol, dict) else vars(pol)
        xml_lines.append(f'      <social:gdprCompliant>{str(pol_dict.get("gdpr_compliant", True)).lower()}</social:gdprCompliant>')
        xml_lines.append(f'      <social:securityLevel>{pol_dict.get("security_level", "medium")}</social:securityLevel>')
        xml_lines.append(f'      <social:dataRetentionDays>{pol_dict.get("data_retention_days", 30)}</social:dataRetentionDays>')
        xml_lines.append(f'      <social:dataClassification>{pol_dict.get("data_classification", "internal")}</social:dataClassification>')
        xml_lines.append(f'      <social:encryptionRequired>{str(pol_dict.get("encryption_required", False)).lower()}</social:encryptionRequired>')
        
        if pol_dict.get('compliance_standards'):
            xml_lines.append('      <social:complianceStandards>')
            for standard in pol_dict['compliance_standards']:
                xml_lines.append(f'        <social:standard>{standard}</social:standard>')
            xml_lines.append('      </social:complianceStandards>')
        
        xml_lines.append('    </social:Policy>')
        
        xml_lines.append('  </social:ExtendedAnnotations>')
    
    xml_lines.append('')
    xml_lines.append('</definitions>')
    
    return '\n'.join(xml_lines)


@app.route('/api/annotate/start', methods=['POST'])
def start_annotation():
    """Lance l'annotation automatique des services"""
    try:
        data = request.json or {}
        use_llm = data.get('use_llm', False)
        service_ids = data.get('service_ids', None)
        annotation_types = data.get('annotation_types', ['interaction', 'context', 'policy'])
        
        if not app_state['services']:
            return jsonify({'error': 'No services loaded'}), 400
        
        if not app_state['annotator']:
            app_state['annotator'] = ServiceAnnotator(app_state['services'])
        
        # Annoter les services sélectionnés
        annotated = app_state['annotator'].annotate_all(
            service_ids=service_ids,
            use_llm=use_llm,
            annotation_types=annotation_types
        )
        
        # Mettre à jour la liste des services annotés
        for service in annotated:
            idx = next((i for i, s in enumerate(app_state['services']) if s.id == service.id), None)
            if idx is not None:
                app_state['services'][idx] = service
        
        app_state['annotated_services'] = app_state['services']
        
        # Mettre à jour les composers
        app_state['classic_composer'] = ClassicComposer(app_state['services'])
        app_state['llm_composer'] = LLMComposer(app_state['services'])
        
        return jsonify({
            'message': 'Annotation completed',
            'total_annotated': len(annotated),
            'services': [s.to_dict() for s in annotated],
            'annotation_types': annotation_types,
            'used_llm': use_llm
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/annotate/progress', methods=['GET'])
def get_annotation_progress():
    """Récupère la progression de l'annotation"""
    total = len(app_state['services'])
    annotated = len(app_state['annotated_services'])
    
    return jsonify({
        'total': total,
        'annotated': annotated,
        'progress': (annotated / total * 100) if total > 0 else 0
    })


@app.route('/api/requests/upload', methods=['POST'])
def upload_requests():
    """Charge le fichier de requêtes"""
    try:
        file = request.files.get('file')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Utiliser un fichier temporaire compatible multiplateforme
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            requests_list = parse_requests_xml(tmp_path)
            app_state['requests'] = requests_list
            
            return jsonify({
                'message': f'{len(requests_list)} requests loaded',
                'requests': [r.to_dict() for r in requests_list]
            })
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Récupère la liste des requêtes"""
    return jsonify({
        'requests': [r.to_dict() for r in app_state['requests']],
        'total': len(app_state['requests'])
    })


@app.route('/api/compose/classic', methods=['POST'])
def compose_classic():
    """Composition classique (Solution A)"""
    try:
        data = request.json
        request_id = data.get('request_id')
        algorithm = data.get('algorithm', 'dijkstra')
        
        comp_request = next((r for r in app_state['requests'] if r.id == request_id), None)
        
        if not comp_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if not app_state['classic_composer']:
            services = app_state['annotated_services'] or app_state['services']
            app_state['classic_composer'] = ClassicComposer(services)
        
        result = app_state['classic_composer'].compose(comp_request, algorithm)
        app_state['results_classic'][request_id] = result
        
        return jsonify(result.to_dict())
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compose/llm', methods=['POST'])
def compose_llm():
    """Composition intelligente avec LLM (Solution B)"""
    try:
        data = request.json
        request_id = data.get('request_id')
        enable_reasoning = data.get('enable_reasoning', True)
        enable_adaptation = data.get('enable_adaptation', True)
        
        comp_request = next((r for r in app_state['requests'] if r.id == request_id), None)
        
        if not comp_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if not app_state['llm_composer']:
            services = app_state['annotated_services'] or app_state['services']
            app_state['llm_composer'] = LLMComposer(services)
        
        result = app_state['llm_composer'].compose(
            comp_request,
            enable_reasoning=enable_reasoning,
            enable_adaptation=enable_adaptation
        )
        
        app_state['results_llm'][request_id] = result
        
        return jsonify(result.to_dict())
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/llm/chat', methods=['POST'])
def llm_chat():
    """Chat avec le LLM"""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not app_state['llm_composer']:
            services = app_state['annotated_services'] or app_state['services']
            app_state['llm_composer'] = LLMComposer(services)
        
        response = app_state['llm_composer'].chat(message)
        
        return jsonify({'response': response})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/best-solutions/upload', methods=['POST'])
def upload_best_solutions():
    """Charge le fichier des meilleures solutions"""
    try:
        file = request.files.get('file')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Utiliser un fichier temporaire compatible multiplateforme
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            solutions = parse_best_solutions_xml(tmp_path)
            app_state['best_solutions'] = solutions
            
            return jsonify({
                'message': f'{len(solutions)} best solutions loaded',
                'solutions': solutions
            })
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/comparison', methods=['GET'])
def get_comparison():
    """Compare les résultats Solution A vs B vs Best Solutions"""
    try:
        comparisons = []
        
        for request_id in app_state['requests']:
            req_id = request_id.id
            
            comparison = {
                'request_id': req_id,
                'best_known': app_state['best_solutions'].get(req_id),
                'classic': app_state['results_classic'].get(req_id),
                'llm': app_state['results_llm'].get(req_id)
            }
            
            if comparison['classic']:
                comparison['classic'] = comparison['classic'].to_dict()
            if comparison['llm']:
                comparison['llm'] = comparison['llm'].to_dict()
            
            comparisons.append(comparison)
        
        stats = calculate_statistics(comparisons)
        
        return jsonify({
            'comparisons': comparisons,
            'statistics': stats
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def calculate_statistics(comparisons):
    """Calcule les statistiques globales"""
    stats = {
        'classic': {
            'success_rate': 0,
            'avg_utility': 0,
            'avg_time': 0,
            'better_than_best': 0
        },
        'llm': {
            'success_rate': 0,
            'avg_utility': 0,
            'avg_time': 0,
            'better_than_best': 0
        }
    }
    
    classic_results = [c['classic'] for c in comparisons if c['classic']]
    llm_results = [c['llm'] for c in comparisons if c['llm']]
    
    if classic_results:
        stats['classic']['success_rate'] = sum(1 for r in classic_results if r['success']) / len(classic_results) * 100
        stats['classic']['avg_utility'] = sum(r['utility_value'] for r in classic_results) / len(classic_results)
        stats['classic']['avg_time'] = sum(r['computation_time'] for r in classic_results) / len(classic_results)
    
    if llm_results:
        stats['llm']['success_rate'] = sum(1 for r in llm_results if r['success']) / len(llm_results) * 100
        stats['llm']['avg_utility'] = sum(r['utility_value'] for r in llm_results) / len(llm_results)
        stats['llm']['avg_time'] = sum(r['computation_time'] for r in llm_results) / len(llm_results)
    
    return stats


if __name__ == '__main__':
    app.run(debug=True, port=5000)