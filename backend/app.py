"""
API Flask pour le système de composition de services intelligents
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
from datetime import datetime

from services.wsdl_parser import WSDLParser, parse_requests_xml, parse_best_solutions_xml
from services.annotator import ServiceAnnotator
from services.classic_composer import ClassicComposer
from services.llm_composer import LLMComposer

app = Flask(__name__)
CORS(app)

# Augmenter la limite de taille pour les uploads massifs
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

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
        
        for file in files:
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
                'errors': errors
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
    """Télécharge un service annoté en format XML"""
    try:
        # Trouver le service
        service = next((s for s in app_state['services'] if s.id == service_id), None)
        
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Générer le XML annoté
        xml_content = generate_annotated_xml(service)
        
        # Créer la réponse avec le fichier
        response = Response(xml_content, mimetype='application/xml')
        response.headers['Content-Disposition'] = f'attachment; filename={service_id}_annotated.xml'
        
        return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_annotated_xml(service):
    """Génère le XML annoté pour un service"""
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<annotatedService>')
    xml_lines.append(f'  <serviceId>{service.id}</serviceId>')
    
    # Informations de base
    xml_lines.append('  <basicInfo>')
    xml_lines.append(f'    <inputs>')
    for inp in service.inputs:
        xml_lines.append(f'      <input>{inp}</input>')
    xml_lines.append(f'    </inputs>')
    xml_lines.append(f'    <outputs>')
    for out in service.outputs:
        xml_lines.append(f'      <output>{out}</output>')
    xml_lines.append(f'    </outputs>')
    xml_lines.append('  </basicInfo>')
    
    # QoS
    xml_lines.append('  <qos>')
    # Convertir l'objet QoS en dictionnaire
    qos_dict = service.qos if isinstance(service.qos, dict) else vars(service.qos)
    for key, value in qos_dict.items():
        xml_lines.append(f'    <{key}>{value}</{key}>')
    xml_lines.append('  </qos>')
    
    # Annotations si elles existent
    if hasattr(service, 'annotations') and service.annotations:
        # Convertir l'objet annotations en dictionnaire
        annotations_dict = service.annotations if isinstance(service.annotations, dict) else vars(service.annotations)
        
        xml_lines.append('  <annotations>')
        
        # Annotations d'interaction
        if 'interaction' in annotations_dict:
            xml_lines.append('    <interaction>')
            inter = annotations_dict['interaction']
            # Convertir inter en dict si nécessaire
            inter_dict = inter if isinstance(inter, dict) else vars(inter)
            xml_lines.append(f'      <role>{inter_dict.get("role", "")}</role>')
            xml_lines.append('      <canCall>')
            for s in inter_dict.get('can_call', []):
                xml_lines.append(f'        <service>{s}</service>')
            xml_lines.append('      </canCall>')
            xml_lines.append('      <dependsOn>')
            for s in inter_dict.get('depends_on', []):
                xml_lines.append(f'        <service>{s}</service>')
            xml_lines.append('      </dependsOn>')
            xml_lines.append('      <substitutes>')
            for s in inter_dict.get('substitutes', []):
                xml_lines.append(f'        <service>{s}</service>')
            xml_lines.append('      </substitutes>')
            xml_lines.append('    </interaction>')
        
        # Annotations de contexte
        if 'context' in annotations_dict:
            xml_lines.append('    <context>')
            ctx = annotations_dict['context']
            # Convertir ctx en dict si nécessaire
            ctx_dict = ctx if isinstance(ctx, dict) else vars(ctx)
            xml_lines.append(f'      <contextAware>{str(ctx_dict.get("context_aware", False)).lower()}</contextAware>')
            xml_lines.append(f'      <locationSensitive>{str(ctx_dict.get("location_sensitive", False)).lower()}</locationSensitive>')
            xml_lines.append(f'      <timeCritical>{ctx_dict.get("time_critical", "low")}</timeCritical>')
            xml_lines.append(f'      <interactionCount>{ctx_dict.get("interaction_count", 0)}</interactionCount>')
            xml_lines.append('    </context>')
        
        # Annotations de politiques
        if 'policy' in annotations_dict:
            xml_lines.append('    <policy>')
            pol = annotations_dict['policy']
            # Convertir pol en dict si nécessaire
            pol_dict = pol if isinstance(pol, dict) else vars(pol)
            xml_lines.append(f'      <gdprCompliant>{str(pol_dict.get("gdpr_compliant", False)).lower()}</gdprCompliant>')
            xml_lines.append(f'      <securityLevel>{pol_dict.get("security_level", "standard")}</securityLevel>')
            xml_lines.append(f'      <dataRetentionDays>{pol_dict.get("data_retention_days", 30)}</dataRetentionDays>')
            xml_lines.append(f'      <dataClassification>{pol_dict.get("data_classification", "public")}</dataClassification>')
            xml_lines.append('    </policy>')
        
        # Propriétés sociales
        xml_lines.append('    <socialProperties>')
        xml_lines.append(f'      <trustDegree>{annotations_dict.get("trust_degree", 0.5)}</trustDegree>')
        xml_lines.append(f'      <reputation>{annotations_dict.get("reputation", 0.5)}</reputation>')
        xml_lines.append(f'      <robustnessScore>{annotations_dict.get("robustness_score", 0.5)}</robustnessScore>')
        xml_lines.append('    </socialProperties>')
        
        xml_lines.append('  </annotations>')
    
    xml_lines.append('</annotatedService>')
    
    return '\n'.join(xml_lines)


@app.route('/api/annotate/start', methods=['POST'])
def start_annotation():
    """Lance l'annotation automatique des services"""
    try:
        data = request.json or {}
        use_llm = data.get('use_llm', False)
        service_ids = data.get('service_ids', None)  # None = tous les services
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
            # Remplacer dans la liste principale
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
            'services': [s.to_dict() for s in annotated],  # Retourner tous les services annotés
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
        
        # Sauvegarder temporairement
        temp_path = '/tmp/requests.xml'
        file.save(temp_path)
        
        # Parser
        requests_list = parse_requests_xml(temp_path)
        app_state['requests'] = requests_list
        
        return jsonify({
            'message': f'{len(requests_list)} requests loaded',
            'requests': [r.to_dict() for r in requests_list]
        })
    
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
        
        # Trouver la requête
        comp_request = next((r for r in app_state['requests'] if r.id == request_id), None)
        
        if not comp_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if not app_state['classic_composer']:
            services = app_state['annotated_services'] or app_state['services']
            app_state['classic_composer'] = ClassicComposer(services)
        
        # Composer
        result = app_state['classic_composer'].compose(comp_request, algorithm)
        
        # Sauvegarder
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
        
        # Trouver la requête
        comp_request = next((r for r in app_state['requests'] if r.id == request_id), None)
        
        if not comp_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if not app_state['llm_composer']:
            services = app_state['annotated_services'] or app_state['services']
            app_state['llm_composer'] = LLMComposer(services)
        
        # Composer
        result = app_state['llm_composer'].compose(
            comp_request,
            enable_reasoning=enable_reasoning,
            enable_adaptation=enable_adaptation
        )
        
        # Sauvegarder
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
        
        # Sauvegarder temporairement
        temp_path = '/tmp/best_solutions.xml'
        file.save(temp_path)
        
        # Parser
        solutions = parse_best_solutions_xml(temp_path)
        app_state['best_solutions'] = solutions
        
        return jsonify({
            'message': f'{len(solutions)} best solutions loaded',
            'solutions': solutions
        })
    
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
            
            # Convertir en dict
            if comparison['classic']:
                comparison['classic'] = comparison['classic'].to_dict()
            if comparison['llm']:
                comparison['llm'] = comparison['llm'].to_dict()
            
            comparisons.append(comparison)
        
        # Statistiques globales
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