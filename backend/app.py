"""
Flask API for intelligent service composition system
Enhanced version with annotation requirement for LLM composition
MODIFICATION: LLM composition requires annotated services
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
import tempfile
import threading
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
    'annotation_thread': None,  # Background thread for annotation
    'annotation_progress': {
        'current': 0,
        'total': 0,
        'current_service': '',
        'completed': False,
        'error': None
    },
    # NEW: Track annotation status
    'annotation_status': {
        'services_annotated': False,
        'annotation_count': 0,
        'total_services': 0
    },
    # Training data and learning state
    'training_data': {
        'services': [],
        'requests': [],
        'solutions': {},
        'best_solutions': {}
    },
    'learning_state': {
        'is_trained': False,
        'training_examples': [],
        'composition_history': [],
        'success_patterns': [],
        'error_patterns': [],
        'performance_metrics': {
            'total_compositions': 0,
            'successful_compositions': 0,
            'average_utility': 0,
            'learning_rate': 0
        }
    }
}

# Thread-safety lock for shared mutable state (#4)
state_lock = threading.Lock()


def _compute_annotation_status():
    """Single source of truth for annotation status (#10)"""
    annotated_count = sum(1 for s in app_state['services'] if hasattr(s, 'annotations') and s.annotations is not None)
    total_count = len(app_state['services'])
    return {
        'services_annotated': annotated_count > 0,
        'annotation_count': annotated_count,
        'total_services': total_count,
        'percentage': (annotated_count / total_count * 100) if total_count > 0 else 0
    }


@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        'status': 'healthy',
        'services_loaded': len(app_state['services']),
        'services_annotated': len(app_state['annotated_services']),
        'requests_loaded': len(app_state['requests']),
        'is_trained': app_state['learning_state']['is_trained'],
        'training_examples': len(app_state['learning_state']['training_examples']),
        'annotation_status': _compute_annotation_status()
    })


# NEW: Endpoint to check if services are annotated
@app.route('/api/annotation/status', methods=['GET'])
def get_annotation_status():
    """Get current annotation status"""
    status = _compute_annotation_status()
    app_state['annotation_status'] = status
    return jsonify(status)


# ============== TRAINING ENDPOINTS ==============

@app.route('/api/training/upload-data', methods=['POST'])
def upload_training_data():
    """Upload training data (WSDL files + requests + solutions) - FIXED VERSION"""
    try:
        # Get training WSDL files
        wsdl_files = request.files.getlist('wsdl_files')
        requests_file = request.files.get('requests_file')
        solutions_file = request.files.get('solutions_file')
        best_solutions_file = request.files.get('best_solutions_file')
        
        training_services = []
        training_requests = []
        training_solutions = {}
        training_best_solutions = {}
        
        # Parse WSDL files
        if wsdl_files:
            print(f"Processing {len(wsdl_files)} WSDL files...")
            for file in wsdl_files:
                if file.filename.endswith('.wsdl') or file.filename.endswith('.xml'):
                    try:
                        content = file.read().decode('utf-8')
                        service = app_state['parser'].parse_content(content, file.filename)
                        if service:
                            training_services.append(service)
                    except Exception as e:
                        print(f"Error parsing {file.filename}: {e}")
        
        # Parse requests - FIXED VERSION
        if requests_file:
            print(f"Processing requests file: {requests_file.filename}")
            
            # Create temporary file with proper handling
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                # Read and write content
                content = requests_file.read()
                tmp.write(content)
                tmp.flush()  # IMPORTANT: Force write to buffer
                os.fsync(tmp.fileno())  # IMPORTANT: Sync with disk
                tmp_path = tmp.name
            
            try:
                print(f"Parsing requests from: {tmp_path}")
                print(f"File size: {os.path.getsize(tmp_path)} bytes")
                
                # Parse the file
                training_requests = parse_requests_xml(tmp_path)
                print(f"✓ Parsed {len(training_requests)} requests")
                
            except Exception as e:
                print(f"✗ Error parsing requests: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    print(f"Cleaned up temp file: {tmp_path}")
        
        # Parse solutions - FIXED VERSION
        if solutions_file:
            print(f"Processing solutions file: {solutions_file.filename}")
            
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                content = solutions_file.read()
                tmp.write(content)
                tmp.flush()  # IMPORTANT
                os.fsync(tmp.fileno())  # IMPORTANT
                tmp_path = tmp.name
            
            try:
                print(f"Parsing solutions from: {tmp_path}")
                print(f"File size: {os.path.getsize(tmp_path)} bytes")
                
                training_solutions = parse_best_solutions_xml(tmp_path)
                print(f"✓ Parsed {len(training_solutions)} solutions")
                
            except Exception as e:
                print(f"✗ Error parsing solutions: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    print(f"Cleaned up temp file: {tmp_path}")
        
        # Parse best solutions - FIXED VERSION
        if best_solutions_file:
            print(f"Processing best solutions file: {best_solutions_file.filename}")
            
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                content = best_solutions_file.read()
                tmp.write(content)
                tmp.flush()  # IMPORTANT
                os.fsync(tmp.fileno())  # IMPORTANT
                tmp_path = tmp.name
            
            try:
                print(f"Parsing best solutions from: {tmp_path}")
                print(f"File size: {os.path.getsize(tmp_path)} bytes")
                
                training_best_solutions = parse_best_solutions_xml(tmp_path)
                print(f"✓ Parsed {len(training_best_solutions)} best solutions")
                
            except Exception as e:
                print(f"✗ Error parsing best solutions: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    print(f"Cleaned up temp file: {tmp_path}")
        
        # Store training data
        app_state['training_data']['services'] = training_services
        app_state['training_data']['requests'] = training_requests
        app_state['training_data']['solutions'] = training_solutions
        app_state['training_data']['best_solutions'] = training_best_solutions
        
        # Log final results
        print("\n" + "=" * 60)
        print("TRAINING DATA UPLOAD SUMMARY")
        print("=" * 60)
        print(f"Training Services: {len(training_services)}")
        print(f"Training Requests: {len(training_requests)}")
        print(f"Training Solutions: {len(training_solutions)}")
        print(f"Training Best Solutions: {len(training_best_solutions)}")
        print("=" * 60 + "\n")
        
        return jsonify({
            'message': 'Training data uploaded successfully',
            'training_services': len(training_services),
            'training_requests': len(training_requests),
            'training_solutions': len(training_solutions),
            'training_best_solutions': len(training_best_solutions)
        })
    
    except Exception as e:
        print(f"\n✗ UPLOAD ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/upload-wsdl-batch', methods=['POST'])
def upload_training_wsdl_batch():
    """Upload WSDL de training par batch"""
    try:
        wsdl_files = request.files.getlist('wsdl_files')
        batch_num = request.form.get('batch_num', 0)
        
        services = []
        for file in wsdl_files:
            if file.filename.endswith('.wsdl') or file.filename.endswith('.xml'):
                try:
                    content = file.read().decode('utf-8')
                    service = app_state['parser'].parse_content(content, file.filename)
                    if service:
                        services.append(service)
                except Exception as e:
                    print(f"Error parsing {file.filename}: {e}")
        
        # Ajouter au training data existant (ne pas écraser)
        app_state['training_data']['services'].extend(services)
        
        print(f"Batch {batch_num}: {len(services)} training services added (total: {len(app_state['training_data']['services'])})")
        
        return jsonify({
            'message': f'Batch {batch_num}: {len(services)} services added',
            'batch_services': len(services),
            'total_training_services': len(app_state['training_data']['services'])
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/upload-xml-files', methods=['POST'])
def upload_training_xml_files():
    """Upload les fichiers XML de training (requests, solutions, best solutions)"""
    try:
        requests_file = request.files.get('requests_file')
        solutions_file = request.files.get('solutions_file')
        best_solutions_file = request.files.get('best_solutions_file')
        
        training_requests = []
        training_solutions = {}
        training_best_solutions = {}
        
        if requests_file:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                content = requests_file.read()
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            try:
                training_requests = parse_requests_xml(tmp_path)
                print(f"✓ Parsed {len(training_requests)} training requests")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        if solutions_file:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                content = solutions_file.read()
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            try:
                training_solutions = parse_best_solutions_xml(tmp_path)
                print(f"✓ Parsed {len(training_solutions)} solutions")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        if best_solutions_file:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                content = best_solutions_file.read()
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            try:
                training_best_solutions = parse_best_solutions_xml(tmp_path)
                print(f"✓ Parsed {len(training_best_solutions)} best solutions")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        # Stocker les données XML
        app_state['training_data']['requests'] = training_requests
        app_state['training_data']['solutions'] = training_solutions
        app_state['training_data']['best_solutions'] = training_best_solutions
        
        return jsonify({
            'message': 'XML files uploaded successfully',
            'training_requests': len(training_requests),
            'training_solutions': len(training_solutions),
            'training_best_solutions': len(training_best_solutions),
            'total_training_services': len(app_state['training_data']['services'])
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/reset-wsdl', methods=['POST'])
def reset_training_wsdl():
    """Réinitialise les WSDL de training (avant un nouvel upload batch)"""
    app_state['training_data']['services'] = []
    return jsonify({'message': 'Training WSDL reset'})
    
@app.route('/api/training/start', methods=['POST'])
def start_training():
    """Train the LLM with the uploaded training data"""
    try:
        if not app_state['training_data']['services']:
            return jsonify({'error': 'No training data available'}), 400
        
        # Always (re)create LLM composer with current services to ensure training applies (#12)
        services = app_state['annotated_services'] or app_state['services']
        app_state['llm_composer'] = LLMComposer(services)
        
        # Build training examples from training data
        training_examples = []
        
        for req in app_state['training_data']['requests']:
            example = {
                'request': req.to_dict(),
                'solution': app_state['training_data']['solutions'].get(req.id),
                'best_solution': app_state['training_data']['best_solutions'].get(req.id)
            }
            
            # Find the service used in the solution
            if example['best_solution']:
                service_id = example['best_solution'].get('service_id')
                service = next(
                    (s for s in app_state['training_data']['services'] if s.id == service_id),
                    None
                )
                if service:
                    example['service'] = service.to_dict()
            
            training_examples.append(example)
        
        # Train the LLM composer
        training_quality = app_state['llm_composer'].train(training_examples)
        
        # Update learning state
        app_state['learning_state']['is_trained'] = True
        app_state['learning_state']['training_examples'] = training_examples
        
        # Compute real metrics from training data so the UI shows non-zero values
        total_examples = len(training_examples)
        examples_with_solutions = sum(
            1 for e in training_examples if e.get('best_solution')
        )
        total_utility = sum(
            (e.get('best_solution') or {}).get('utility', 0)
            for e in training_examples
            if e.get('best_solution')
        )
        avg_utility = total_utility / max(examples_with_solutions, 1)
        coverage = (examples_with_solutions / total_examples * 100) if total_examples > 0 else 0

        app_state['learning_state']['performance_metrics'] = {
            'total_compositions': total_examples,
            'successful_compositions': examples_with_solutions,
            'average_utility': avg_utility,
            'learning_rate': coverage,
        }
        app_state['learning_state']['training_quality'] = training_quality
        
        return jsonify({
            'message': 'LLM training completed',
            'training_examples_count': total_examples,
            'is_trained': True,
            'training_quality': training_quality,
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/status', methods=['GET'])
def get_training_status():
    """Get current training status and metrics including training quality"""
    return jsonify({
        'is_trained': app_state['learning_state']['is_trained'],
        'training_examples': len(app_state['learning_state']['training_examples']),
        'composition_history': len(app_state['learning_state']['composition_history']),
        'success_patterns': len(app_state['learning_state']['success_patterns']),
        'performance_metrics': app_state['learning_state']['performance_metrics'],
        'training_quality': app_state['learning_state'].get('training_quality', {})
    })


# ============== SERVICE MANAGEMENT ENDPOINTS ==============

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
            
            # Reset composers with learning capability
            app_state['annotator'] = ServiceAnnotator(
                app_state['services'],
                training_examples=app_state['learning_state'].get('training_examples')
            )
            app_state['classic_composer'] = ClassicComposer(app_state['services'])
            
            # Initialize LLM composer with training data if available
            if app_state['learning_state']['is_trained']:
                app_state['llm_composer'] = LLMComposer(
                    app_state['services'],
                    training_examples=app_state['learning_state']['training_examples']
                )
            else:
                app_state['llm_composer'] = LLMComposer(app_state['services'])
            
            # NEW: Reset annotation status when new services are uploaded
            app_state['annotation_status'] = {
                'services_annotated': False,
                'annotation_count': 0,
                'total_services': len(app_state['services'])
            }
            
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
    # Use to_dict() which provides correct CamelCase keys (ResponseTime, etc.)
    qos_dict = service.qos.to_dict() if hasattr(service.qos, 'to_dict') else (service.qos if isinstance(service.qos, dict) else vars(service.qos))
    for key, value in qos_dict.items():
        xml_lines.append(f'    <social:{key}>{value:.2f}</social:{key}>')
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


# ============== ANNOTATION ENDPOINTS ==============

@app.route('/api/annotate/estimate', methods=['POST'])
def estimate_annotation_time():
    """Estimate annotation time with detailed breakdown based on real parameters"""
    try:
        data = request.json or {}
        use_llm = data.get('use_llm', False)
        service_ids = data.get('service_ids', None)
        annotation_types = data.get('annotation_types', ['interaction', 'context', 'policy'])
        
        # Get target services
        if service_ids:
            target_services = [s for s in app_state['services'] if s.id in service_ids]
        else:
            target_services = app_state['services']
        
        num_services = len(target_services)
        num_types = len(annotation_types)
        total_services = len(app_state['services'])
        
        # ---- Complexity analysis ----
        if target_services:
            avg_inputs = sum(len(s.inputs) for s in target_services) / num_services
            avg_outputs = sum(len(s.outputs) for s in target_services) / num_services
            avg_io = avg_inputs + avg_outputs
        else:
            avg_inputs = 0
            avg_outputs = 0
            avg_io = 0
        
        # Complexity factor: more I/O = more processing
        complexity_factor = 1.0 + (avg_io / 15.0)
        
        # ---- Time breakdown ----
        breakdown = {}
        
        # 1. Base processing time per service
        base_time_per_service = 0.005  # 5ms per service (init, property calc)
        breakdown['base_processing'] = {
            'label': 'Base Processing',
            'time': num_services * base_time_per_service,
            'detail': f'{num_services} services × {base_time_per_service*1000:.0f}ms'
        }
        
        # 2. Annotation generation per type
        if use_llm:
            # LLM inference: ~3-5s per call, one call per type per service
            llm_latency = 4.0  # avg seconds per LLM call
            annotation_time = num_services * num_types * llm_latency * complexity_factor
            breakdown['annotation_generation'] = {
                'label': 'LLM Annotation Generation',
                'time': annotation_time,
                'detail': f'{num_services} × {num_types} types × ~{llm_latency}s per LLM call × {complexity_factor:.1f}x complexity'
            }
        else:
            # Classic: context/policy are O(1) ~1ms, interaction uses index ~5ms
            classic_time_per_type = 0.005  # 5ms per type per service (index-based)
            annotation_time = num_services * num_types * classic_time_per_type * complexity_factor
            breakdown['annotation_generation'] = {
                'label': 'Classic Annotation Generation',
                'time': annotation_time,
                'detail': f'{num_services} × {num_types} types × {classic_time_per_type*1000:.0f}ms × {complexity_factor:.1f}x complexity'
            }
        
        # 3. Social association building (index-based, O(n * avg_degree))
        # Estimate avg I/O fanout: each param connects to ~sqrt(N) services
        avg_degree = min(avg_io * max(int(total_services ** 0.4), 1), total_services)
        estimated_lookups = num_services * avg_degree
        association_time_per_lookup = 0.00005  # 50μs per indexed lookup
        association_time = estimated_lookups * association_time_per_lookup
        breakdown['association_building'] = {
            'label': 'Social Association Building',
            'time': association_time,
            'detail': f'{num_services} × ~{int(avg_degree)} avg connections × 50μs'
        }
        
        # 4. Social node property calculation
        property_time = num_services * 0.002  # 2ms per service
        breakdown['property_calculation'] = {
            'label': 'Social Node Properties',
            'time': property_time,
            'detail': f'{num_services} services × 2ms'
        }
        
        # 5. Network overhead (if LLM)
        if use_llm:
            network_overhead = num_services * num_types * 0.5  # 500ms network per call
            breakdown['network_overhead'] = {
                'label': 'Network Overhead (Ollama)',
                'time': network_overhead,
                'detail': f'{num_services * num_types} API calls × ~500ms'
            }
        
        # Total time
        total_time = sum(item['time'] for item in breakdown.values())
        
        # Add 10% safety margin
        total_time_with_margin = total_time * 1.1
        
        return jsonify({
            'estimated_time_seconds': total_time_with_margin,
            'num_services': num_services,
            'num_annotation_types': num_types,
            'use_llm': use_llm,
            'annotation_types': annotation_types,
            'complexity_factor': round(complexity_factor, 2),
            'avg_io_per_service': round(avg_io, 1),
            'avg_inputs': round(avg_inputs, 1),
            'avg_outputs': round(avg_outputs, 1),
            'total_services_in_repo': total_services,
            'breakdown': breakdown,
            'safety_margin': '10%'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/annotate/start', methods=['POST'])
def start_annotation():
    """Start automatic service annotation in a background thread.
    Returns 202 immediately; poll /api/annotate/progress for status."""
    try:
        data = request.json or {}
        use_llm = data.get('use_llm', False)
        service_ids = data.get('service_ids', None)
        annotation_types = data.get('annotation_types', ['interaction', 'context', 'policy'])

        if not app_state['services']:
            return jsonify({'error': 'No services loaded'}), 400

        # Prevent starting a second annotation while one is running
        thread = app_state.get('annotation_thread')
        if thread and thread.is_alive():
            return jsonify({'error': 'Annotation already in progress'}), 409

        if not app_state['annotator']:
            app_state['annotator'] = ServiceAnnotator(
                app_state['services'],
                training_examples=app_state['learning_state'].get('training_examples')
            )

        total = len(service_ids) if service_ids else len(app_state['services'])

        # Reset progress state
        with state_lock:
            app_state['annotation_progress'] = {
                'current': 0,
                'total': total,
                'current_service': '',
                'completed': False,
                'error': None,
                'result': None  # will hold final result dict
            }

        # --------------- background worker ---------------
        def _annotation_worker():
            try:
                log_every = max(total // 200, 1)  # log ~200 times max

                def progress_callback(current, _total, service_id):
                    with state_lock:
                        p = app_state['annotation_progress']
                        p['current'] = current
                        p['total'] = _total
                        p['current_service'] = service_id
                    if current % log_every == 0 or current == _total:
                        print(f"Annotation progress: {current}/{_total} - {service_id}")

                annotated = app_state['annotator'].annotate_all(
                    service_ids=service_ids,
                    use_llm=use_llm,
                    annotation_types=annotation_types,
                    progress_callback=progress_callback
                )

                # Update services list
                svc_by_id = {s.id: s for s in annotated}
                for i, s in enumerate(app_state['services']):
                    if s.id in svc_by_id:
                        app_state['services'][i] = svc_by_id[s.id]

                app_state['annotated_services'] = app_state['services']

                # Rebuild composers
                app_state['classic_composer'] = ClassicComposer(app_state['services'])
                if app_state['learning_state']['is_trained']:
                    app_state['llm_composer'] = LLMComposer(
                        app_state['services'],
                        training_examples=app_state['learning_state']['training_examples']
                    )
                else:
                    app_state['llm_composer'] = LLMComposer(app_state['services'])

                app_state['annotation_status'] = _compute_annotation_status()

                with state_lock:
                    app_state['annotation_progress']['completed'] = True
                    app_state['annotation_progress']['result'] = {
                        'message': 'Annotation completed',
                        'total_annotated': len(annotated),
                        'services': [s.to_dict() for s in annotated],
                        'annotation_types': annotation_types,
                        'used_llm': use_llm
                    }
                print(f"Annotation finished: {len(annotated)} services annotated.")

            except Exception as exc:
                import traceback
                traceback.print_exc()
                with state_lock:
                    app_state['annotation_progress']['error'] = str(exc)
                    app_state['annotation_progress']['completed'] = True
        # -------------------------------------------------

        t = threading.Thread(target=_annotation_worker, daemon=True)
        app_state['annotation_thread'] = t
        t.start()

        return jsonify({
            'message': 'Annotation started in background',
            'total': total
        }), 202   # Accepted

    except Exception as e:
        with state_lock:
            app_state['annotation_progress']['error'] = str(e)
            app_state['annotation_progress']['completed'] = True
        return jsonify({'error': str(e)}), 500


@app.route('/api/annotate/progress', methods=['GET'])
def get_annotation_progress():
    """Retrieve annotation progress in real-time.
    When completed, the 'result' field contains the full annotation result."""
    with state_lock:
        progress = app_state.get('annotation_progress', {
            'current': 0,
            'total': 0,
            'current_service': '',
            'completed': False,
            'error': None,
            'result': None
        }).copy()

    return jsonify(progress)


# ============== COMPOSITION REQUEST ENDPOINTS ==============

@app.route('/api/requests/upload', methods=['POST'])
def upload_requests():
    """Load requests file - FIXED VERSION"""
    try:
        file = request.files.get('file')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Use cross-platform compatible temporary file with proper flush
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
            content = file.read()
            tmp.write(content)
            tmp.flush()  # IMPORTANT
            os.fsync(tmp.fileno())  # IMPORTANT
            tmp_path = tmp.name
        
        try:
            print(f"Parsing requests from: {tmp_path}")
            print(f"File size: {os.path.getsize(tmp_path)} bytes")
            
            requests_list = parse_requests_xml(tmp_path)
            app_state['requests'] = requests_list
            
            print(f"✓ Parsed {len(requests_list)} requests")
            
            return jsonify({
                'message': f'{len(requests_list)} requests loaded',
                'requests': [r.to_dict() for r in requests_list]
            })
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                print(f"Cleaned up temp file: {tmp_path}")
    
    except Exception as e:
        print(f"✗ Error uploading requests: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Retrieve requests list"""
    return jsonify({
        'requests': [r.to_dict() for r in app_state['requests']],
        'total': len(app_state['requests'])
    })


# ============== COMPOSITION ENDPOINTS ==============

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
    """
    Intelligent composition with LLM (Solution B) - Enhanced with learning
    MODIFICATION: Requires services to be annotated first
    """
    try:
        # NEW: Check if services are annotated
        annotated_count = sum(1 for s in app_state['services'] if hasattr(s, 'annotations') and s.annotations is not None)
        
        if annotated_count == 0:
            return jsonify({
                'error': 'Services must be annotated before LLM composition',
                'message': 'Please annotate the services first in Tab 2 (Automatic Annotation) before using intelligent composition.',
                'services_annotated': False,
                'annotation_count': 0,
                'total_services': len(app_state['services'])
            }), 400
        
        data = request.json
        request_id = data.get('request_id')
        enable_reasoning = data.get('enable_reasoning', True)
        enable_adaptation = data.get('enable_adaptation', True)
        
        comp_request = next((r for r in app_state['requests'] if r.id == request_id), None)
        
        if not comp_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if not app_state['llm_composer']:
            services = app_state['annotated_services'] or app_state['services']
            app_state['llm_composer'] = LLMComposer(
                services,
                training_examples=app_state['learning_state']['training_examples']
            )
        
        # Perform composition
        result = app_state['llm_composer'].compose(
            comp_request,
            enable_reasoning=enable_reasoning,
            enable_adaptation=enable_adaptation
        )
        
        app_state['results_llm'][request_id] = result
        
        # CONTINUOUS LEARNING: Record this composition for learning
        composition_record = {
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id,
            'request': comp_request.to_dict(),
            'result': result.to_dict(),
            'success': result.success,
            'utility': result.utility_value
        }
        
        app_state['learning_state']['composition_history'].append(composition_record)
        
        # Update performance metrics
        metrics = app_state['learning_state']['performance_metrics']
        metrics['total_compositions'] += 1
        if result.success:
            metrics['successful_compositions'] += 1
        
        # Calculate average utility
        total_utility = sum(
            record['utility'] for record in app_state['learning_state']['composition_history']
        )
        metrics['average_utility'] = total_utility / len(app_state['learning_state']['composition_history'])
        
        # Calculate learning rate (improvement over time)
        if len(app_state['learning_state']['composition_history']) >= 10:
            recent_avg = sum(
                record['utility'] for record in app_state['learning_state']['composition_history'][-10:]
            ) / 10
            overall_avg = metrics['average_utility']
            metrics['learning_rate'] = ((recent_avg - overall_avg) / overall_avg * 100) if overall_avg > 0 else 0
        
        # Learn from this composition
        app_state['llm_composer'].learn_from_composition(composition_record)
        
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


# ============== COMPARISON ENDPOINTS ==============

@app.route('/api/best-solutions/upload', methods=['POST'])
def upload_best_solutions():
    """Load best solutions file - FIXED VERSION"""
    try:
        file = request.files.get('file')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Use cross-platform compatible temporary file with proper flush
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
            content = file.read()
            tmp.write(content)
            tmp.flush()  # IMPORTANT
            os.fsync(tmp.fileno())  # IMPORTANT
            tmp_path = tmp.name
        
        try:
            print(f"Parsing best solutions from: {tmp_path}")
            print(f"File size: {os.path.getsize(tmp_path)} bytes")
            
            solutions = parse_best_solutions_xml(tmp_path)
            app_state['best_solutions'] = solutions
            
            print(f"✓ Parsed {len(solutions)} best solutions")
            
            return jsonify({
                'message': f'{len(solutions)} best solutions loaded',
                'solutions': solutions
            })
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                print(f"Cleaned up temp file: {tmp_path}")
    
    except Exception as e:
        print(f"✗ Error uploading best solutions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/compose/compare', methods=['POST'])
def compose_compare():
    """Run all three classic algorithms + LLM on the same request for comparison"""
    try:
        data = request.json
        request_id = data.get('request_id')
        
        comp_request = next((r for r in app_state['requests'] if r.id == request_id), None)
        if not comp_request:
            return jsonify({'error': 'Request not found'}), 404
        
        results = {}
        
        # Run all classic algorithms
        if app_state['classic_composer']:
            for algo in ['dijkstra', 'astar', 'greedy']:
                try:
                    result = app_state['classic_composer'].compose(comp_request, algo)
                    results[algo] = result.to_dict()
                    app_state['results_classic'][f"{request_id}_{algo}"] = result
                except Exception as e:
                    results[algo] = {'success': False, 'error': str(e), 'utility_value': 0, 'computation_time': 0}
        
        # Run LLM composition if available
        annotated_count = sum(1 for s in app_state['services'] if hasattr(s, 'annotations') and s.annotations is not None)
        if app_state['llm_composer'] and annotated_count > 0:
            try:
                llm_result = app_state['llm_composer'].compose(comp_request)
                results['llm'] = llm_result.to_dict()
                app_state['results_llm'][request_id] = llm_result
            except Exception as e:
                results['llm'] = {'success': False, 'error': str(e), 'utility_value': 0, 'computation_time': 0}
        else:
            results['llm'] = {'success': False, 'error': 'LLM not available or services not annotated', 'utility_value': 0, 'computation_time': 0}
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compose/batch', methods=['POST'])
def compose_batch():
    """Batch compose all requests with classic + LLM in one call (#15)"""
    try:
        data = request.json or {}
        algorithm = data.get('algorithm', 'dijkstra')
        request_ids = data.get('request_ids', [r.id for r in app_state['requests']])
        
        results = {}
        annotated_count = sum(1 for s in app_state['services'] if hasattr(s, 'annotations') and s.annotations is not None)
        
        for req_id in request_ids:
            comp_request = next((r for r in app_state['requests'] if r.id == req_id), None)
            if not comp_request:
                continue
            
            entry = {'classic': None, 'llm': None}
            
            # Classic composition
            if app_state['classic_composer']:
                try:
                    result = app_state['classic_composer'].compose(comp_request, algorithm)
                    app_state['results_classic'][req_id] = result
                    entry['classic'] = result.to_dict()
                except Exception as e:
                    entry['classic'] = {'success': False, 'error': str(e), 'utility_value': 0, 'computation_time': 0}
            
            # LLM composition
            if app_state['llm_composer'] and annotated_count > 0:
                try:
                    llm_result = app_state['llm_composer'].compose(comp_request)
                    app_state['results_llm'][req_id] = llm_result
                    entry['llm'] = llm_result.to_dict()
                except Exception as e:
                    entry['llm'] = {'success': False, 'error': str(e), 'utility_value': 0, 'computation_time': 0}
            
            results[req_id] = entry
        
        return jsonify({'results': results, 'total': len(results)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/comparison', methods=['GET'])
def get_comparison():
    """Enhanced comparison: Solution A vs B vs Best Solutions with rich metrics"""
    try:
        comparisons = []
        
        for req in app_state['requests']:
            req_id = req.id
            
            comparison = {
                'request_id': req_id,
                'best_known': app_state['best_solutions'].get(req_id),
                'classic': None,
                'llm': None
            }
            
            # Get classic result (any algorithm)
            classic_result = app_state['results_classic'].get(req_id)
            if classic_result:
                comparison['classic'] = classic_result.to_dict() if hasattr(classic_result, 'to_dict') else classic_result
            
            # Get LLM result
            llm_result = app_state['results_llm'].get(req_id)
            if llm_result:
                comparison['llm'] = llm_result.to_dict() if hasattr(llm_result, 'to_dict') else llm_result
            
            comparisons.append(comparison)
        
        stats = calculate_statistics(comparisons)
        
        # Add training impact info
        training_impact = {
            'is_trained': app_state['learning_state']['is_trained'],
            'training_examples': len(app_state['learning_state']['training_examples']),
            'composition_history': len(app_state['learning_state']['composition_history']),
            'performance_metrics': app_state['learning_state']['performance_metrics']
        }
        
        return jsonify({
            'comparisons': comparisons,
            'statistics': stats,
            'training_impact': training_impact,
            'total_requests': len(app_state['requests']),
            'total_services': len(app_state['services']),
            'annotated_services': sum(1 for s in app_state['services'] if hasattr(s, 'annotations') and s.annotations is not None)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def calculate_statistics(comparisons):
    """Calculate rich global statistics for comparison"""
    stats = {
        'classic': {
            'success_rate': 0, 'avg_utility': 0, 'avg_time': 0,
            'max_utility': 0, 'min_utility': 0,
            'total_composed': 0, 'avg_services_used': 0, 'avg_states_explored': 0
        },
        'llm': {
            'success_rate': 0, 'avg_utility': 0, 'avg_time': 0,
            'max_utility': 0, 'min_utility': 0,
            'total_composed': 0, 'avg_services_used': 0
        },
        'comparison': {
            'classic_wins': 0, 'llm_wins': 0, 'ties': 0,
            'avg_utility_gap': 0, 'avg_time_ratio': 0
        }
    }
    
    classic_results = [c['classic'] for c in comparisons if c['classic'] and c['classic'].get('success')]
    llm_results = [c['llm'] for c in comparisons if c['llm'] and c['llm'].get('success')]
    
    if classic_results:
        utilities = [r['utility_value'] for r in classic_results]
        stats['classic']['success_rate'] = len(classic_results) / max(len(comparisons), 1) * 100
        stats['classic']['avg_utility'] = sum(utilities) / len(utilities)
        stats['classic']['max_utility'] = max(utilities)
        stats['classic']['min_utility'] = min(utilities)
        stats['classic']['avg_time'] = sum(r['computation_time'] for r in classic_results) / len(classic_results)
        stats['classic']['total_composed'] = len(classic_results)
        stats['classic']['avg_services_used'] = sum(len(r.get('services', [])) for r in classic_results) / len(classic_results)
        stats['classic']['avg_states_explored'] = sum(r.get('states_explored', 0) for r in classic_results) / len(classic_results)
    
    if llm_results:
        utilities = [r['utility_value'] for r in llm_results]
        stats['llm']['success_rate'] = len(llm_results) / max(len(comparisons), 1) * 100
        stats['llm']['avg_utility'] = sum(utilities) / len(utilities)
        stats['llm']['max_utility'] = max(utilities)
        stats['llm']['min_utility'] = min(utilities)
        stats['llm']['avg_time'] = sum(r['computation_time'] for r in llm_results) / len(llm_results)
        stats['llm']['total_composed'] = len(llm_results)
        stats['llm']['avg_services_used'] = sum(len(r.get('services', [])) for r in llm_results) / len(llm_results)
    
    # Head-to-head comparison
    for comp in comparisons:
        if comp['classic'] and comp['llm'] and comp['classic'].get('success') and comp['llm'].get('success'):
            cu = comp['classic']['utility_value']
            lu = comp['llm']['utility_value']
            if cu > lu:
                stats['comparison']['classic_wins'] += 1
            elif lu > cu:
                stats['comparison']['llm_wins'] += 1
            else:
                stats['comparison']['ties'] += 1
    
    # Utility gap
    if stats['classic']['avg_utility'] > 0 and stats['llm']['avg_utility'] > 0:
        stats['comparison']['avg_utility_gap'] = stats['llm']['avg_utility'] - stats['classic']['avg_utility']
    
    # Time ratio
    if stats['classic']['avg_time'] > 0 and stats['llm']['avg_time'] > 0:
        stats['comparison']['avg_time_ratio'] = stats['llm']['avg_time'] / stats['classic']['avg_time']
    
    return stats


if __name__ == '__main__':
    app.run(debug=True, port=5000)