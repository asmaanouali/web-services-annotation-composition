"""
Flask API for intelligent service composition system
Enhanced version with time estimation and real-time progress
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

# Increase limit for massive uploads
app.config['MAX_CONTENT_LENGTH'] = None

# Global application state
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
    'llm_composer': None,
    'annotation_progress': {
        'current': 0,
        'total': 0,
        'current_service': '',
        'completed': False,
        'error': None
    }
}


@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        'status': 'healthy',
        'services_loaded': len(app_state['services']),
        'services_annotated': len(app_state['annotated_services']),
        'requests_loaded': len(app_state['requests'])
    })


@app.route('/api/services/upload', methods=['POST'])
def upload_services():
    """Load WSDL files"""
    try:
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        services = []
        errors = []
        
        for idx, file in enumerate(files):
            if idx % 100 == 0:  # Log every 100 files
                print(f"Progress: {idx}/{len(files)} files processed")
            
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
        
        print(f"Processing completed: {len(services)} services loaded, {len(errors)} errors")
        
        if services:
            app_state['services'].extend(services)
            
            # Reset composers
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
                'errors': errors[:10],  # Limit displayed errors
                'total_errors': len(errors)
            }), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/services', methods=['GET'])
def get_services():
    """Retrieve service list"""
    return jsonify({
        'services': [s.to_dict() for s in app_state['services']],
        'total': len(app_state['services'])
    })


@app.route('/api/services/<service_id>', methods=['GET'])
def get_service(service_id):
    """Retrieve a specific service"""
    service = next((s for s in app_state['services'] if s.id == service_id), None)
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    return jsonify(service.to_dict())


@app.route('/api/services/<service_id>/download', methods=['GET'])
def download_annotated_service(service_id):
    """Download an annotated service in enriched WSDL format"""
    try:
        # Find the service
        service = next((s for s in app_state['services'] if s.id == service_id), None)
        
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Generate enriched WSDL
        xml_content = generate_enriched_wsdl(service)
        
        # Create response with file
        response = Response(xml_content, mimetype='application/xml')
        response.headers['Content-Disposition'] = f'attachment; filename={service_id}_enriched.xml'
        
        return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_enriched_wsdl(service):
    """
    Generates an enriched WSDL with social annotations
    Takes the original WSDL content and enriches it with annotations
    """
    # Start with original WSDL if available
    if service.wsdl_content:
        # Parse original content to enrich it
        original_lines = service.wsdl_content.split('\n')
        
        # Find the closing </definitions> tag
        definitions_closing_index = -1
        for i in range(len(original_lines) - 1, -1, -1):
            if '</definitions>' in original_lines[i]:
                definitions_closing_index = i
                break
        
        if definitions_closing_index > 0:
            # Insert annotations before closing tag
            xml_lines = original_lines[:definitions_closing_index]
            xml_lines.append('')
            xml_lines.append('  <!-- ========== Social Annotations Extension ========== -->')
        else:
            # Fallback: create basic structure
            xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml_lines.append(f'<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"')
            xml_lines.append('             xmlns:social="http://social-ws/annotations"')
            xml_lines.append(f'             name="{service.id}">')
    else:
        # Create basic WSDL structure
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append(f'<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"')
        xml_lines.append('             xmlns:social="http://social-ws/annotations"')
        xml_lines.append(f'             name="{service.id}">')
        xml_lines.append('')
        xml_lines.append('  <!-- ========== Basic Service Description ========== -->')
        
        # Add basic types
        xml_lines.append('  <types>')
        xml_lines.append('    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">')
        for inp in service.inputs:
            xml_lines.append(f'      <xsd:element name="{inp}" type="xsd:string"/>')
        for out in service.outputs:
            xml_lines.append(f'      <xsd:element name="{out}" type="xsd:string"/>')
        xml_lines.append('    </xsd:schema>')
        xml_lines.append('  </types>')
    
    # Add QoS extension
    xml_lines.append('')
    xml_lines.append('  <!-- ========== QoS Properties ========== -->')
    xml_lines.append('  <social:QoS>')
    qos_dict = service.qos if isinstance(service.qos, dict) else vars(service.qos)
    for key, value in qos_dict.items():
        xml_key = key.replace('_', '')
        xml_key = xml_key[0].upper() + xml_key[1:]
        xml_lines.append(f'    <social:{xml_key}>{value:.2f}</social:{xml_key}>')
    xml_lines.append('  </social:QoS>')
    xml_lines.append('')
    
    # Add social annotations if available
    if hasattr(service, 'annotations') and service.annotations:
        xml_lines.append('  <!-- ========== Social Annotations ========== -->')
        annotations = service.annotations
        social_node = annotations.social_node
        
        # Social Node
        xml_lines.append('  <social:SocialNode>')
        xml_lines.append(f'    <social:nodeId>{social_node.node_id}</social:nodeId>')
        xml_lines.append(f'    <social:nodeType>{social_node.node_type}</social:nodeType>')
        xml_lines.append(f'    <social:state>{social_node.state}</social:state>')
        xml_lines.append('')
        
        # Node properties
        xml_lines.append('    <social:NodeProperties>')
        xml_lines.append(f'      <social:trustDegree>{social_node.trust_degree.value:.3f}</social:trustDegree>')
        xml_lines.append(f'      <social:reputation>{social_node.reputation.value:.3f}</social:reputation>')
        xml_lines.append(f'      <social:cooperativeness>{social_node.cooperativeness.value:.3f}</social:cooperativeness>')
        
        for prop in social_node.properties:
            xml_lines.append(f'      <social:property name="{prop.prop_name}" value="{prop.value:.3f}"/>')
        
        xml_lines.append('    </social:NodeProperties>')
        xml_lines.append('')
        
        # Social associations
        if social_node.associations:
            xml_lines.append('    <social:Associations>')
            
            for assoc in social_node.associations:
                xml_lines.append('      <social:Association>')
                xml_lines.append(f'        <social:sourceNode>{assoc.source_node}</social:sourceNode>')
                xml_lines.append(f'        <social:targetNode>{assoc.target_node}</social:targetNode>')
                xml_lines.append(f'        <social:type>{assoc.association_type.type_name}</social:type>')
                xml_lines.append(f'        <social:weight>{assoc.association_weight.value:.3f}</social:weight>')
                xml_lines.append('      </social:Association>')
            
            xml_lines.append('    </social:Associations>')
        
        xml_lines.append('  </social:SocialNode>')
        xml_lines.append('')
        
        # Interaction annotations
        xml_lines.append('  <social:Interaction>')
        inter = annotations.interaction
        inter_dict = inter if isinstance(inter, dict) else vars(inter)
        xml_lines.append(f'    <social:role>{inter_dict.get("role", "worker")}</social:role>')
        
        if inter_dict.get('collaboration_associations'):
            xml_lines.append('    <social:collaborations>')
            for svc_id in inter_dict['collaboration_associations'][:5]:  # Limit to 5
                xml_lines.append(f'      <social:service>{svc_id}</social:service>')
            xml_lines.append('    </social:collaborations>')
        
        xml_lines.append('  </social:Interaction>')
        xml_lines.append('')
        
        # Context annotations
        xml_lines.append('  <social:Context>')
        ctx = annotations.context
        ctx_dict = ctx if isinstance(ctx, dict) else vars(ctx)
        xml_lines.append(f'    <social:contextAware>{str(ctx_dict.get("context_aware", False)).lower()}</social:contextAware>')
        xml_lines.append(f'    <social:timeCritical>{ctx_dict.get("time_critical", "low")}</social:timeCritical>')
        xml_lines.append(f'    <social:interactionCount>{ctx_dict.get("interaction_count", 0)}</social:interactionCount>')
        xml_lines.append('  </social:Context>')
        xml_lines.append('')
        
        # Policy annotations
        xml_lines.append('  <social:Policy>')
        pol = annotations.policy
        pol_dict = pol if isinstance(pol, dict) else vars(pol)
        xml_lines.append(f'    <social:gdprCompliant>{str(pol_dict.get("gdpr_compliant", True)).lower()}</social:gdprCompliant>')
        xml_lines.append(f'    <social:securityLevel>{pol_dict.get("security_level", "medium")}</social:securityLevel>')
        xml_lines.append(f'    <social:dataRetentionDays>{pol_dict.get("data_retention_days", 30)}</social:dataRetentionDays>')
        xml_lines.append('  </social:Policy>')
    
    xml_lines.append('')
    xml_lines.append('</definitions>')
    
    return '\n'.join(xml_lines)


@app.route('/api/annotate/estimate', methods=['POST'])
def estimate_annotation_time():
    """Estimate time needed for annotation"""
    try:
        data = request.json or {}
        use_llm = data.get('use_llm', False)
        service_ids = data.get('service_ids', None)
        annotation_types = data.get('annotation_types', ['interaction', 'context', 'policy'])
        
        # Calculate number of services
        if service_ids:
            num_services = len(service_ids)
        else:
            num_services = len(app_state['services'])
        
        # Estimate time per service (in seconds)
        if use_llm:
            # With LLM: approximately 8-12 seconds per service per annotation type
            # (LLM inference time + processing overhead)
            time_per_service = len(annotation_types) * 10  # 10 seconds per type
        else:
            # Without LLM: very fast, approximately 0.5 second per service
            time_per_service = 0.5
        
        total_time = num_services * time_per_service
        
        return jsonify({
            'estimated_time_seconds': total_time,
            'num_services': num_services,
            'time_per_service': time_per_service,
            'use_llm': use_llm,
            'annotation_types': annotation_types
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/annotate/start', methods=['POST'])
def start_annotation():
    """Start automatic service annotation with real-time updates"""
    try:
        data = request.json or {}
        use_llm = data.get('use_llm', False)
        service_ids = data.get('service_ids', None)
        annotation_types = data.get('annotation_types', ['interaction', 'context', 'policy'])
        
        if not app_state['services']:
            return jsonify({'error': 'No services loaded'}), 400
        
        if not app_state['annotator']:
            app_state['annotator'] = ServiceAnnotator(app_state['services'])
        
        # Reset progress state
        app_state['annotation_progress'] = {
            'current': 0,
            'total': len(service_ids) if service_ids else len(app_state['services']),
            'current_service': '',
            'completed': False,
            'error': None
        }
        
        # Annotate selected services with progress callback
        def progress_callback(current, total, service_id):
            app_state['annotation_progress'] = {
                'current': current,
                'total': total,
                'current_service': service_id,
                'completed': False,
                'error': None
            }
            print(f"Annotation progress: {current}/{total} - Service: {service_id}")
        
        annotated = app_state['annotator'].annotate_all(
            service_ids=service_ids,
            use_llm=use_llm,
            annotation_types=annotation_types,
            progress_callback=progress_callback
        )
        
        # Update annotated services list
        for service in annotated:
            idx = next((i for i, s in enumerate(app_state['services']) if s.id == service.id), None)
            if idx is not None:
                app_state['services'][idx] = service
        
        app_state['annotated_services'] = app_state['services']
        
        # Update composers
        app_state['classic_composer'] = ClassicComposer(app_state['services'])
        app_state['llm_composer'] = LLMComposer(app_state['services'])
        
        # Mark as completed
        app_state['annotation_progress']['completed'] = True
        
        return jsonify({
            'message': 'Annotation completed',
            'total_annotated': len(annotated),
            'services': [s.to_dict() for s in annotated],
            'annotation_types': annotation_types,
            'used_llm': use_llm
        })
    
    except Exception as e:
        app_state['annotation_progress']['error'] = str(e)
        app_state['annotation_progress']['completed'] = True
        return jsonify({'error': str(e)}), 500


@app.route('/api/annotate/progress', methods=['GET'])
def get_annotation_progress():
    """Retrieve annotation progress in real-time"""
    progress = app_state.get('annotation_progress', {
        'current': 0,
        'total': 0,
        'current_service': '',
        'completed': False,
        'error': None
    })
    
    return jsonify(progress)


@app.route('/api/requests/upload', methods=['POST'])
def upload_requests():
    """Load requests file"""
    try:
        file = request.files.get('file')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Use cross-platform compatible temporary file
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
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Retrieve requests list"""
    return jsonify({
        'requests': [r.to_dict() for r in app_state['requests']],
        'total': len(app_state['requests'])
    })


@app.route('/api/compose/classic', methods=['POST'])
def compose_classic():
    """Classic composition (Solution A)"""
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
    """Intelligent composition with LLM (Solution B)"""
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
    """Chat with LLM"""
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
    """Load best solutions file"""
    try:
        file = request.files.get('file')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Use cross-platform compatible temporary file
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
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/comparison', methods=['GET'])
def get_comparison():
    """Compare results Solution A vs B vs Best Solutions"""
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
    """Calculate global statistics"""
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