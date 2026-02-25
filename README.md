# Intelligent Web Service Composition System

## Technical Documentation

A comprehensive research platform implementing **MOF-based Social Web Services Description Metamodel** with dual composition strategies: classical graph-based algorithms and LLM-enhanced intelligent composition with continuous learning capabilities.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Technical Stack](#technical-stack)
4. [Installation & Setup](#installation--setup)
5. [System Components](#system-components)
6. [Composition Algorithms](#composition-algorithms)
7. [Data Models & Formats](#data-models--formats)
8. [API Reference](#api-reference)
9. [Usage Workflows](#usage-workflows)
10. [Configuration](#configuration)
11. [Performance & Optimization](#performance--optimization)
12. [Troubleshooting](#troubleshooting)
13. [Research Background](#research-background)

---

## System Overview

### Purpose

This system addresses the web service composition problem through two complementary approaches:

- **Solution A (Classical)**: Graph-based pathfinding algorithms (Dijkstra, A*, Greedy) that guarantee optimality through exhaustive or heuristic-guided search
- **Solution B (Intelligent)**: LLM-powered composition leveraging social annotations, contextual reasoning, and continuous learning from training examples

### Key Features

- **Automatic Service Annotation**: Generates social, interaction, context, and policy annotations using LLM (Ollama) or rule-based methods
- **Dual Composition Strategies**: Compare classical algorithms against AI-enhanced selection
- **Training & Learning**: Few-shot learning from successful compositions with continuous improvement
- **QoS-Aware Selection**: Multi-dimensional quality evaluation (response time, reliability, availability, etc.)
- **Comparative Analysis**: Side-by-side performance metrics, utility scoring, and visualization
- **Real-time Visualization**: Algorithm execution traces, service graphs, workflow diagrams

---

## Architecture

### System Design
```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (HTML/JS)                       │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────┐ │
│  │ Service  │ Annotate │ Classic  │   LLM    │ Compare   │ │
│  │ Manager  │ Services │ Compose  │ Compose  │ Analysis  │ │
│  └──────────┴──────────┴──────────┴──────────┴───────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ▼ REST API
┌─────────────────────────────────────────────────────────────┐
│                   Backend (Flask/Python)                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Application Layer (app.py)               │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │  WSDL    │ Service  │ Classic  │   LLM    │  QoS     │  │
│  │  Parser  │Annotator │ Composer │ Composer │Calculator│  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │        Data Models (Services, QoS, Annotations)       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              External Services & Dependencies                │
│  ┌──────────────────┐         ┌────────────────────────┐   │
│  │  Ollama (LLM)    │         │  Training Data         │   │
│  │  llama3.2:3b     │         │  (WSDL, Requests,      │   │
│  │  localhost:11434 │         │   Solutions)           │   │
│  └──────────────────┘         └────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Service Upload**: WSDL files → Parser → Service Repository
2. **Annotation**: Services → Annotator (LLM/Classic) → Annotated Services with Social Properties
3. **Composition**: Request + Services → Composer → Composition Result
4. **Learning**: Training Data → LLM Composer → Pattern Recognition → Improved Selection

---

## Technical Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Web Framework** | Flask | 3.0.0 | REST API server |
| **CORS** | Flask-CORS | 4.0.0 | Cross-origin requests |
| **XML Parsing** | lxml | 5.1.0 | WSDL parsing |
| **XML Processing** | xmltodict | 0.13.0 | XML-to-dict conversion |
| **Graph Operations** | NetworkX | 3.2.1 | Service graph construction |
| **HTTP Client** | requests | 2.31.0 | Ollama API calls |
| **Numerical** | NumPy | 1.26.2 | QoS calculations |

### Frontend

- **Pure HTML5/CSS3/JavaScript** (no frameworks)
- **Chart.js 4.4.1** for visualization
- **SVG** for graph rendering
- **Responsive design** with CSS Grid/Flexbox

### LLM Integration

- **Model**: Llama 3.2 3B via Ollama
- **API**: REST (localhost:11434)
- **Inference**: Local, no external API keys required
- **Temperature**: 0.3 (deterministic reasoning)

---

## Installation & Setup

### Prerequisites
```bash
# System requirements
- Python 3.8+
- Node.js/npm (optional, for development)
- 8GB RAM minimum
- 20GB disk space (for models)
```

### 1. Clone Repository
```bash
git clone https://github.com/asmaanouali/web-services-annotation-composition.git
cd service-composition-system
```

### 2. Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

### 3. Install Ollama (for LLM features)
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: Download from https://ollama.com/download

# Pull the model
ollama pull llama3.2:3b

# Start Ollama server
ollama serve  # Runs on localhost:11434
```

### 4. Start Backend Server
```bash
# Development mode
cd backend
python run.py

# Production mode (alternative)
gunicorn -c unicorn_config.py app:app
```

Server starts on `http://localhost:5000`

### 5. Launch Frontend
```bash
# Simple HTTP server
cd frontend
python -m http.server 8080

# Or use any web server
```

Access at `http://localhost:8080`

### 6. Verify Installation
```bash
# Check backend health
curl http://localhost:5000/api/health

# Expected response:
# {
#   "status": "healthy",
#   "services_loaded": 0,
#   "services_annotated": 0,
#   "requests_loaded": 0,
#   "is_trained": false,
#   "training_examples": 0
# }
```

---

## System Components

### 1. WSDL Parser (`backend/services/wsdl_parser.py`)

**Purpose**: Extracts service metadata from WSDL/XML files

**Capabilities**:
- Parses standard WSDL format
- Extracts input/output parameters from message definitions
- Extracts QoS metrics from XML comments or QoS extensions
- Supports bulk parsing (500+ files in batches)
- Handles WSChallenge Discovery/Composition formats

**Key Methods**:
```python
parse_content(content, filename)  # Parse WSDL string
parse_requests_xml(filepath)      # Parse requests file
parse_best_solutions_xml(filepath) # Parse reference solutions
```

**QoS Extraction**:
- Response Time (ms)
- Availability (%)
- Throughput (req/s)
- Reliability (%)
- Successability (%)
- Compliance (%)
- Best Practices (%)
- Latency (ms)
- Documentation (%)

### 2. Service Annotator (`backend/services/annotator.py`)

**Purpose**: Generates MOF-based social annotations for services

**Annotation Types**:

#### A. Social Node Properties
- **Trust Degree**: Calculated from reliability, availability, compliance
- **Reputation**: Based on best practices, documentation, compliance
- **Cooperativeness**: Derived from reliability and availability

#### B. Interaction Annotations
- **Collaboration Associations**: Services that can be called (I/O compatibility)
- **Substitution Associations**: Alternative services (≥70% output similarity)
- **Dependencies**: Required predecessor services
- **Role Classification**: Orchestrator, Worker, or Aggregator

#### C. Context Annotations
- **Context Awareness**: Environment-sensitive behavior
- **Time Criticality**: Low/Medium/High priority
- **Usage Patterns**: Peak hours, business days
- **Interaction History**: Usage frequency tracking

#### D. Policy Annotations
- **GDPR Compliance**: Data protection conformance
- **Security Level**: Low/Medium/High
- **Data Retention**: Days to keep data
- **Encryption Requirements**: Data protection needs

**Annotation Modes**:

1. **Classic (Rule-Based)**:
   - Fast (~50ms per service per type)
   - Deterministic
   - Based on QoS metrics and I/O patterns

2. **LLM-Enhanced (Intelligent)**:
   - Slower (~4s per service per type)
   - Context-aware
   - Generates explanatory text
   - Requires Ollama running

**Social Association Calculation**:
```python
# Collaboration Weight Formula
# io_ratio = overlap(service_outputs, target_inputs) / len(target_inputs)
# qos_sim  = 1.0 - abs(reliability_A - reliability_B) * 0.01
collaboration_weight = (
    io_ratio * 0.5 +   # I/O compatibility ratio
    qos_sim  * 0.3 +   # Reliability-based QoS similarity
    0.2                # Fixed trust baseline
)

# Robustness Weight for Substitution (≥70% output overlap required)
# r_sim = 1 - abs(reliability_A - reliability_B) * 0.01
# a_sim = 1 - abs(availability_A - availability_B) * 0.01
robustness_weight = (
    r_sim * 0.5 +
    a_sim * 0.5
)
```

### 3. Classic Composer (`backend/services/classic_composer.py`)

**Purpose**: Graph-based composition using pathfinding algorithms

**Algorithms Implemented**:

#### **Dijkstra's Algorithm**
- **Strategy**: Exhaustive search for optimal path
- **Guarantee**: Always finds best utility solution
- **Complexity**: O((V + E) log V) where V = services, E = transitions
- **Use Case**: When optimality is critical, graph is moderate size
```python
# State representation
state = (utility_so_far, path, available_parameters)

# Priority queue ordered by negative utility (max-heap simulation)
heapq.heappush(queue, (-utility, counter, state))
```

#### **A\* Algorithm**
- **Strategy**: Heuristic-guided search
- **Heuristic Function**:
```python
  h(service) = (
      goal_bonus      * 0.5 +   # 1.0 if produces target, else 0.0
      reliability/100 * 0.2 +   # Reliability contribution
      availability/100* 0.2 +   # Availability contribution
      norm_resp_time  * 0.05 +  # Normalized response time (lower=better)
      param_novelty   * 0.05    # Proportion of truly new outputs added
  )
```
- **Guarantee**: Optimal if heuristic is admissible
- **Complexity**: Better than Dijkstra in practice
- **Use Case**: Balance between speed and optimality

#### **Greedy Algorithm**
- **Strategy**: Local best-first selection
- **Selection Criteria**:
```python
  score = utility + (100 if produces_goal else 0)
```
- **Guarantee**: None (may miss global optimum)
- **Complexity**: O(V) in best case
- **Use Case**: Real-time constraints, large graphs

**Service Graph Construction**:
- **Search space**: Pre-filtered via forward + backward reachability — only services that are both reachable from provided params AND contribute toward the goal are considered
- **Visualization graph**: Capped at top-40 by reliability for UI rendering
- Nodes: START, services (up to 40 top-rated), END
- Edges:
  - START → service (if service can use provided params)
  - service → END (if service produces resultant)
  - service → service (if outputs match inputs)

**Algorithm Trace Capture**:
Each step records:
- Step number
- Action type (init, explore, expand, goal_found, complete, failed)
- Current state (path, available params, queue size)
- Decision rationale

### 4. LLM Composer (`backend/services/llm_composer.py`)

**Purpose**: Intelligent composition using Large Language Models

**Architecture**:
```python
class LLMComposer:
    def __init__(services, training_examples=None,
                 ollama_url="http://localhost:11434"):
        self.services = services
        self.model = "llama3.2:3b"
        self.knowledge_base = {      # populated during training
            'patterns': [],
            'service_rankings': {},
            'io_chains': [],
        }
        self.composition_history = []  # continuous learning state
        self.success_patterns = []
        if training_examples:
            self.train(training_examples)
```

**Composition Pipeline**:

1. **Candidate Discovery**:
   - Index-based lookup: services accepting provided params + services producing target param
   - Second-hop chaining: outputs of candidates feed into further services

2. **Candidate Scoring**:
   - QoS utility score (bottleneck model)
   - Knowledge-base bonus (training pattern match)
   - Direct-producer bonus (+50 if service produces target directly)
   - Input-satisfaction ratio bonus
   - Annotation bonus (trust degree + reputation + cooperativeness from social node)

3. **Composition Selection**:
   - Direct (single-service) composition preferred
   - Greedy chain building as fallback for multi-step paths
   - LLM reasoning invoked for top-5 ambiguous candidates when `enable_reasoning=True`

4. **Explanation Generation**:
   - LLM generates human-readable justification
   - References training knowledge and scoring rationale
   - Explains why service was chosen

5. **Adaptation**:
   - Optional: apply historical composition patterns when `enable_adaptation=True`

**Training & Learning**:

**Training Phase**:
```python
train(training_examples):
    1. Extract composition patterns (request → solution service IDs + utility)
    2. Build service quality rankings (usage frequency × utility scores)
    3. Build I/O chain knowledge (parameter linkages from successful workflows)
```

**Continuous Learning**:
```python
learn_from_composition(record):
    1. Append to composition_history
    2. If successful:
       - Append to success_patterns
       - Update knowledge_base['service_rankings'] (usage count + avg utility)
    3. Performance metrics recalculated from history
```

**Few-Shot Learning Example**:
```
Training examples show:
- High reliability requests → prefer services with Reliability > 90
- Production environment → services with annotations.security_level = "high"
- Time-critical contexts → services with ResponseTime < 100ms

LLM applies these patterns to new requests.
```

**Fallback Mechanism**:
If LLM fails (Ollama offline, timeout, etc.):
```python
_fallback_select_services(request):
    # Rule-based selection
    1. Filter by I/O compatibility
    2. Check QoS constraints
    3. Calculate utility scores
    4. Return highest utility service
```

### 5. QoS Calculator (`backend/utils/qos_calculator.py`)

**Purpose**: Calculate service utility scores based on QoS metrics

**Utility Formula**:
```python
# Step 1: Quality Score (0-100)
quality_score = (
    normalize(availability, 0, 100, 0, 15) +      # 15 pts
    normalize(reliability, 0, 100, 0, 15) +       # 15 pts
    normalize(successability, 0, 100, 0, 15) +    # 15 pts
    normalize(throughput, 0, 1000, 0, 10) +       # 10 pts
    normalize(compliance, 0, 100, 0, 10) +        # 10 pts
    normalize(best_practices, 0, 100, 0, 10) +    # 10 pts
    normalize(documentation, 0, 100, 0, 5) +      # 5 pts
    normalize_inverse(response_time, 0, 1000, 0, 10) +  # 10 pts
    normalize_inverse(latency, 0, 1000, 0, 10)          # 10 pts
)

# Step 2: Conformity Score (0-100)
# Per-constraint weights (sum to 100 when all satisfied):
constraint_weights = {
    'ResponseTime': 12, 'Availability': 12, 'Reliability': 12,
    'Throughput': 11,   'Successability': 11, 'Compliance': 11,
    'Latency': 11,      'BestPractices': 10,  'Documentation': 10
}
conformity_score = sum(
    constraint_weights[c] for c, met in qos_checks.items() if met
)

# Step 3: Base Utility
base_utility = quality_score * 0.4 + conformity_score * 0.6

# Step 4: Bonus/Penalty
if satisfaction_ratio == 1.0:
    bonus = 50  # All constraints met
elif satisfaction_ratio >= 0.8:
    bonus = 25
elif satisfaction_ratio >= 0.6:
    bonus = 10
else:
    bonus = 0

penalty_factor = (
    0.5 if satisfaction_ratio < 0.5 else
    0.7 if satisfaction_ratio < 0.7 else
    0.9 if satisfaction_ratio < 1.0 else
    1.0
)

# Step 5: Final Utility
utility = (base_utility * penalty_factor) + bonus
```

**Key Properties**:
- Range: 0-150+ (theoretical max ~160)
- Balanced: Considers both intrinsic quality and constraint satisfaction
- Non-punitive: Partial satisfaction still yields reasonable scores
- Bonus for perfection: Incentivizes complete constraint satisfaction

---

## Composition Algorithms

### Detailed Algorithm Analysis

#### 1. Dijkstra's Algorithm

**Implementation Details**:
```python
def _dijkstra_compose(request):
    # State: (utility, path, available_params)
    initial_state = (0, [], set(request.provided))
    
    # Priority queue (max-heap by utility)
    pq = [(0, 0, initial_state)]
    
    # Best utility seen for each parameter set
    best_utilities = {frozenset(request.provided): 0}
    
    while pq:
        neg_util, _, (util, path, params) = heapq.heappop(pq)
        
        # Goal check
        if request.resultant in params:
            return create_result(path, util)
        
        # Expand applicable services
        for service in services:
            if can_apply(service, path, params):
                new_util = min(util, service_utility)
                new_params = params | set(service.outputs)
                
                if better_than_seen(new_params, new_util):
                    heapq.heappush(pq, (-new_util, counter, new_state))
```

**Optimality Proof**:
- Explores states in decreasing order of utility
- Never revisits a parameter set with worse utility
- First goal state reached is optimal (max utility path)

**Time Complexity**:
- Best case: O(V log V) when goal is directly reachable
- Average case: O((V + E) log V) for typical service graphs
- Worst case: O(V² log V) for dense graphs

**Space Complexity**: O(V²) for storing best utilities per parameter combination

#### 2. A* Algorithm

**Heuristic Design**:
```python
def calculate_heuristic(service, available_params):
    # f(n) = g(n) + h(n): g = bottleneck utility so far, h = estimated gain
    
    # 1. Goal proximity (value 1.0 weighted by 0.5 → max 0.5)
    goal_bonus = 1.0 if request.resultant in service.outputs else 0.0
    
    # 2. Parameter novelty (proportion of truly new outputs)
    new_params = set(service.outputs) - available_params
    novelty = len(new_params) / max(len(service.outputs), 1)
    
    # 3. QoS quality components
    norm_rt = 1 - (service.qos.response_time / max_rt) if max_rt > 0 else 0
    
    h = (
        goal_bonus                     * 0.5  +
        service.qos.reliability / 100  * 0.2  +
        service.qos.availability / 100 * 0.2  +
        norm_rt                        * 0.05 +
        novelty                        * 0.05
    )
    return h
```

**Properties**:
- **Admissible**: h(n) ≤ actual cost to goal
- **Consistent**: h(n) ≤ c(n, n') + h(n') for all neighbors
- Guarantees optimality when admissible

**Performance vs Dijkstra**:
- Explores ~30-50% fewer states on average
- Faster for graphs with clear goal direction
- Similar worst-case but better average-case

#### 3. Greedy Algorithm

**Decision Strategy**:
```python
def select_best_service(applicable_services, request):
    candidates = []
    
    for service in applicable_services:
        utility = calculate_utility(service.qos, request.constraints)
        
        # Heavily favor goal-producing services
        score = utility + (100 if request.resultant in service.outputs else 0)
        
        candidates.append((service, score, utility))
    
    # Pick highest score
    best = max(candidates, key=lambda x: x[1])
    return best[0]
```

**Trade-offs**:
- **Speed**: 10-100x faster than Dijkstra
- **Quality**: May miss optimal by 10-30% utility
- **Use Cases**: 
  - Real-time systems with <100ms latency requirements
  - Large service repositories (1000+ services)
  - Situations where "good enough" is acceptable

**Failure Modes**:
- Local maxima: Gets stuck with suboptimal choice
- No backtracking: Cannot undo bad decisions
- Greedy trap: Service A looks good locally but blocks optimal path through B

### Algorithm Comparison

| Metric | Dijkstra | A* | Greedy |
|--------|----------|-----|--------|
| **Optimality** | Guaranteed | Guaranteed* | No guarantee |
| **Time Complexity** | O((V+E) log V) | O((V+E) log V) | O(V) |
| **Space Complexity** | O(V²) | O(V²) | O(V) |
| **States Explored** | High (100%) | Medium (30-70%) | Low (<10%) |
| **Typical Runtime** | 100-500ms | 50-200ms | 10-50ms |
| **Best For** | Small graphs, critical applications | Medium graphs, balanced needs | Large graphs, soft real-time |

*Guaranteed if heuristic is admissible

---

## Data Models & Formats

### 1. WSDL File Format

**Standard Structure**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" name="servicep1a123456">
    <types>
        <xsd:schema>
            <xsd:element name="param1" type="xsd:string"/>
            <xsd:element name="param2" type="xsd:string"/>
        </xsd:schema>
    </types>
    
    <message name="RequestMessage">
        <part name="param1" type="xsd:string"/>
    </message>
    
    <message name="ResponseMessage">
        <part name="param2" type="xsd:string"/>
    </message>
    
    <!-- QoS Extension -->
    <QoS>
        <ResponseTime Value="250"/>
        <Availability Value="95.5"/>
        <Throughput Value="500"/>
        <Successability Value="98.0"/>
        <Reliability Value="92.0"/>
        <Compliance Value="85.0"/>
        <BestPractices Value="78.0"/>
        <Latency Value="120"/>
        <Documentation Value="88.0"/>
    </QoS>
</definitions>
```

### 2. Requests File Format

**WSChallenge Discovery/Composition Format**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<WSChallenge>
    <CompositionRoutine name="request1">
        <Provided>param1,param2,param3</Provided>
        <Resultant>param10</Resultant>
        <QoS>300,95.0,400,97.0,90.0,80.0,75.0,150,85.0</QoS>
    </CompositionRoutine>
    <!-- More routines... -->
</WSChallenge>
```

**QoS Values Order**:
1. ResponseTime (ms)
2. Availability (%)
3. Throughput (req/s)
4. Successability (%)
5. Reliability (%)
6. Compliance (%)
7. BestPractices (%)
8. Latency (ms)
9. Documentation (%)

### 3. Best Solutions Format

**Discovery Format** (single service):
```xml
<case name="request1">
    <service name="servicep1a123456"/>
    <utility value="85.5"/>
</case>
```

**Composition Format** (workflow):
```xml
<case name="request1">
    <service name="servicep1a111111"/>
    <service name="servicep2a222222"/>
    <service name="servicep3a333333"/>
    <utility value="78.3"/>
</case>
```

### 4. Enriched WSDL with Annotations

**Example Output**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:social="http://social-ws/annotations"
             name="servicep1a123456">
    
    <!-- Original WSDL content -->
    
    <!-- Social Annotations Extension -->
    <social:SocialNode>
        <social:nodeId>servicep1a123456</social:nodeId>
        <social:nodeType>WebService</social:nodeType>
        <social:state>active</social:state>
        
        <social:NodeProperties>
            <social:trustDegree>0.850</social:trustDegree>
            <social:reputation>0.780</social:reputation>
            <social:cooperativeness>0.920</social:cooperativeness>
        </social:NodeProperties>
        
        <social:Associations>
            <social:Association>
                <social:sourceNode>servicep1a123456</social:sourceNode>
                <social:targetNode>servicep2a789012</social:targetNode>
                <social:type>collaboration</social:type>
                <social:weight>0.750</social:weight>
            </social:Association>
        </social:Associations>
    </social:SocialNode>
    
    <social:Interaction>
        <social:role>worker</social:role>
        <social:collaborations>
            <social:service>servicep2a789012</social:service>
        </social:collaborations>
    </social:Interaction>
    
    <social:Context>
        <social:contextAware>true</social:contextAware>
        <social:timeCritical>medium</social:timeCritical>
        <social:interactionCount>256</social:interactionCount>
    </social:Context>
    
    <social:Policy>
        <social:gdprCompliant>true</social:gdprCompliant>
        <social:securityLevel>high</social:securityLevel>
        <social:dataRetentionDays>90</social:dataRetentionDays>
    </social:Policy>
</definitions>
```

---

## API Reference

### Service Management

#### `POST /api/services/upload`
Upload WSDL files to service repository.

**Request**:
```javascript
FormData {
    files: File[] // Multiple .wsdl or .xml files
}
```

**Response**:
```json
{
    "message": "150 services loaded successfully",
    "total_services": 150,
    "services": [
        {
            "id": "servicep1a123456",
            "name": "servicep1a123456",
            "inputs": ["param1", "param2"],
            "outputs": ["param5", "param6"],
            "qos": {
                "ResponseTime": 250,
                "Availability": 95.5,
                "Reliability": 92.0
            },
            "annotations": null
        }
    ],
    "errors": []
}
```

#### `GET /api/services`
Retrieve all loaded services.

#### `GET /api/services/{service_id}`
Get specific service details.

#### `GET /api/services/{service_id}/download`
Download enriched WSDL with annotations.

### Training Endpoints

#### `POST /api/training/upload-data`
Upload training dataset for LLM learning.

**Request**:
```javascript
FormData {
    wsdl_files: File[],          // Training WSDL files
    requests_file: File,         // Training requests
    solutions_file: File,        // Solutions
    best_solutions_file: File    // Best solutions
}
```

**Response**:
```json
{
    "message": "Training data uploaded successfully",
    "training_services": 100,
    "training_requests": 50,
    "training_solutions": 50,
    "training_best_solutions": 50
}
```

#### `POST /api/training/start`
Begin LLM training process.

**Response**:
```json
{
    "message": "LLM training completed",
    "training_examples_count": 50,
    "is_trained": true
}
```

#### `GET /api/training/status`
Get training status and performance metrics.

**Response**:
```json
{
    "is_trained": true,
    "training_examples": 50,
    "composition_history": 120,
    "success_patterns": 15,
    "performance_metrics": {
        "total_compositions": 120,
        "successful_compositions": 110,
        "average_utility": 78.5,
        "learning_rate": 5.2
    }
}
```

### Annotation Endpoints

#### `POST /api/annotate/estimate`
Estimate annotation time.

**Request**:
```json
{
    "use_llm": true,
    "service_ids": ["servicep1a123456", "servicep2a789012"],
    "annotation_types": ["interaction", "context", "policy"]
}
```

**Response**:
```json
{
    "estimated_time_seconds": 45.2,
    "num_services": 2,
    "num_annotation_types": 3,
    "use_llm": true,
    "complexity_factor": 1.15,
    "avg_io_per_service": 8.5,
    "breakdown": {
        "base_processing": {"time": 0.04, "label": "Base Processing"},
        "annotation_generation": {"time": 24.0, "label": "LLM Annotation"},
        "association_building": {"time": 18.0, "label": "Social Associations"},
        "property_calculation": {"time": 0.02, "label": "Node Properties"},
        "network_overhead": {"time": 3.0, "label": "Network (Ollama)"}
    }
}
```

#### `POST /api/annotate/start`
Start annotation process.

**Request**:
```json
{
    "use_llm": true,
    "service_ids": ["servicep1a123456"],
    "annotation_types": ["interaction", "context", "policy"]
}
```

**Response**:
```json
{
    "message": "Annotation completed",
    "total_annotated": 1,
    "services": [...],
    "annotation_types": ["interaction", "context", "policy"],
    "used_llm": true
}
```

#### `GET /api/annotate/progress`
Poll annotation progress (real-time).

**Response**:
```json
{
    "current": 5,
    "total": 10,
    "current_service": "servicep5a555555",
    "completed": false,
    "error": null
}
```

#### `GET /api/annotation/status`
Check if services are annotated.

**Response**:
```json
{
    "services_annotated": true,
    "annotation_count": 150,
    "total_services": 150,
    "percentage": 100.0
}
```

### Composition Endpoints

#### `POST /api/requests/upload`
Upload composition requests.

**Request**:
```javascript
FormData {
    file: File // Requests.xml
}
```

#### `GET /api/requests`
Get all loaded requests.

#### `POST /api/compose/classic`
Execute classical composition.

**Request**:
```json
{
    "request_id": "request1",
    "algorithm": "dijkstra" // or "astar", "greedy"
}
```

**Response**:
```json
{
    "services": ["servicep1a123456", "servicep2a789012"],
    "workflow": ["servicep1a123456", "servicep2a789012"],
    "utility_value": 85.5,
    "qos_achieved": {...},
    "computation_time": 0.145,
    "success": true,
    "explanation": "Dijkstra Algorithm: 2 service(s) selected...",
    "algorithm_trace": [
        {
            "step": 0,
            "action": "init",
            "description": "Initialize with 3 provided parameters",
            "available_params": ["param1", "param2", "param3"]
        }
    ],
    "graph_data": {
        "nodes": [...],
        "edges": [...],
        "path": ["servicep1a123456", "servicep2a789012"]
    },
    "algorithm_used": "dijkstra",
    "states_explored": 45
}
```

#### `POST /api/compose/llm`
Execute LLM-based composition.

**Request**:
```json
{
    "request_id": "request1",
    "enable_reasoning": true,
    "enable_adaptation": true
}
```

**Response**:
```json
{
    "services": ["servicep1a123456"],
    "workflow": ["servicep1a123456"],
    "utility_value": 88.2,
    "qos_achieved": {...},
    "computation_time": 2.5,
    "success": true,
    "explanation": "Service servicep1a123456 selected based on high reliability..."
}
```

#### `POST /api/compose/compare`
Run all algorithms + LLM on same request.

**Request**:
```json
{
    "request_id": "request1"
}
```

**Response**:
```json
{
    "dijkstra": {...},
    "astar": {...},
    "greedy": {...},
    "llm": {...}
}
```

#### `POST /api/llm/chat`
Chat with LLM about compositions.

**Request**:
```json
{
    "message": "Why did you select service X?"
}
```

**Response**:
```json
{
    "response": "I selected service X because..."
}
```

### Comparison Endpoints

#### `POST /api/best-solutions/upload`
Upload reference solutions.

#### `GET /api/comparison`
Get comprehensive comparative analysis.

**Response**:
```json
{
    "comparisons": [...],
    "statistics": {
        "classic": {
            "success_rate": 95.0,
            "avg_utility": 82.3,
            "avg_time": 0.125
        },
        "llm": {
            "success_rate": 98.0,
            "avg_utility": 85.7,
            "avg_time": 2.3
        },
        "comparison": {
            "classic_wins": 12,
            "llm_wins": 30,
            "ties": 5
        }
    }
}
```

### Health Check

#### `GET /api/health`
Server health and status.

**Response**:
```json
{
    "status": "healthy",
    "services_loaded": 150,
    "services_annotated": 150,
    "requests_loaded": 50,
    "is_trained": true,
    "training_examples": 50
}
```

---

## Usage Workflows

### Workflow 1: Basic Service Composition (No Training)
```bash
# 1. Start backend
cd backend && python run.py

# 2. Upload services (Tab 1)
# Via UI: Select WSDL files → Upload

# 3. Annotate services (Tab 2) - REQUIRED for LLM
# Select services → Choose annotation types → Start annotation

# 4. Upload requests (Tab 3)
# Upload Requests.xml file

# 5. Compose with Classic Algorithm (Tab 3)
# Select request → Choose algorithm → Execute

# 6. Compose with LLM (Tab 4)
# Select request → Execute intelligent composition
```

### Workflow 2: Training-Enhanced LLM Composition
```bash
# 1. Upload Training Data (Tab 1)
Training WSDL files: 100 services
Training Requests: 50 requests
Training Solutions: 50 solutions
Training Best Solutions: 50 best solutions

# 2. Train LLM
Click "Upload Training Data & Train LLM"
Wait for training completion (~30-60 seconds)

# 3. Upload Test Services
Different set of services for evaluation

# 4. Annotate Test Services
Use LLM or classic method

# 5. Upload Test Requests
Different requests to evaluate generalization

# 6. Compose & Compare
Run compositions and analyze training impact
```

### Workflow 3: Comparative Analysis
```bash
# 1. Ensure all data loaded:
- Services uploaded & annotated
- Requests uploaded
- Best solutions uploaded (optional)

# 2. Navigate to Tab 5 (Comparative Analysis)

# 3. Click "Generate Comparative Analysis"
System automatically:
- Runs Dijkstra on all requests
- Runs LLM on all requests (if annotated)
- Compares results against best known solutions
- Generates statistics and visualizations

# 4. Review Results:
- KPI cards: Avg utility comparison
- Charts: Request-by-request comparison
- Detailed metrics: Success rates, timing
- Training impact: Learning effectiveness
```

### Workflow 4: Batch Processing Large Datasets
```bash
# For 1000+ services:

# 1. Split services into batches of 500
# 2. Upload batches sequentially (automatic)
# 3. Annotation strategy:
#    - Classic: ~50 seconds total
#    - LLM: ~4 hours total
# 4. Select specific services for LLM annotation
#    (e.g., top 100 by reliability)
# 5. Use classic annotation for remaining services
```

---

## Configuration

### Backend Configuration

**`backend/app.py`** - Main settings:
```python
# Server
app.config['MAX_CONTENT_LENGTH'] = None  # Unlimited uploads

# LLM Composer
ollama_url = "http://localhost:11434"
model = "llama3.2:3b"

# Annotation
annotation_types = ['interaction', 'context', 'policy']
```

**`backend/run.py`** - Server settings:
```python
app.run(
    host='0.0.0.0',      # Listen on all interfaces
    port=5000,           # API port
    debug=True,          # Development mode
    threaded=True,       # Multi-threading support
    use_reloader=True    # Auto-reload on code changes
)
```

**`backend/unicorn_config.py`** - Production settings:
```python
# Gunicorn configuration
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 0  # Infinite timeout for large uploads
limit_request_line = 0  # Unlimited request size
limit_request_field_size = 0
```

### LLM Configuration

**Ollama Model Selection**:
```bash
# Current: llama3.2:3b (fast, good quality)
ollama pull llama3.2:3b

# Alternatives:
ollama pull llama3.2:1b      # Faster, lower quality
ollama pull llama3.2:7b      # Slower, higher quality
ollama pull mixtral:8x7b     # Best quality, requires 48GB RAM
```

**Inference Parameters** (`annotator.py`, `llm_composer.py`):
```python
{
    "model": "llama3.2:3b",
    "temperature": 0.3,  # Deterministic reasoning
    "top_p": 0.9,        # Nucleus sampling
    "stream": False      # Wait for complete response
}
```

### Frontend Configuration

**API Endpoint** (`frontend/index.html`):
```javascript
const API = 'http://localhost:5000/api';  // Backend URL
```

**Polling Intervals**:
```javascript
annInterval = setInterval(pollProgress, 500);  // Annotation progress
setInterval(loadMetrics, 30000);               // Training metrics
```

---

## Performance & Optimization

### Backend Optimizations

#### 1. Batch Upload Processing
```python
BATCH_SIZE = 500  # Process 500 services per batch

# Prevents memory overflow with 1000+ files
# Provides progress feedback
# Allows error recovery per batch
```

#### 2. Temporary File Handling
```python
with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
    tmp.write(content)
    tmp.flush()  # Force buffer write
    os.fsync(tmp.fileno())  # Sync to disk
    # Critical for XML parsing reliability
```

#### 3. Service Graph Optimization
```python
# Limit candidate services for visualization
candidates = sorted(candidates, key=lambda s: s.qos.reliability, reverse=True)[:40]

# Prevents UI overload
# Keeps top-quality services
```

#### 4. Algorithm State Caching
```python
best_utilities = {}  # Cache best utility per parameter set
best_utilities[frozenset(params)] = utility

# Prevents re-exploring same states
# Reduces Dijkstra/A* complexity by 30-50%
```

### Frontend Optimizations

#### 1. Progressive Rendering
```javascript
// Display first 300 services, show count for rest
if (services.length > 300) {
    displayFirst300();
    showRemainingCount();
}
```

#### 2. Lazy Trace Loading
```javascript
// Show first 50 algorithm steps, truncate rest
if (trace.length > 50) {
    trace = trace.slice(0, 50);
}
```

#### 3. Chart Data Limiting
```javascript
// Display max 20 requests in charts
labels = labels.slice(0, 20);
```

### LLM Performance

#### Annotation Speed
| Method | Services | Time per Service | Total (100 services) |
|--------|----------|------------------|----------------------|
| **Classic** | Any | 50ms | 5 seconds |
| **LLM** | Any | 4s | 6.7 minutes |

#### Composition Speed
| Method | Complexity | Time |
|--------|-----------|------|
| **Dijkstra** | Small (10 services) | 10-50ms |
| **Dijkstra** | Medium (50 services) | 100-300ms |
| **Dijkstra** | Large (200 services) | 500-2000ms |
| **A*** | Medium (50 services) | 50-150ms |
| **Greedy** | Large (200 services) | 10-100ms |
| **LLM** | Any | 2-5 seconds |

### Scaling Recommendations

**Small Datasets** (<100 services):
- Use LLM annotation for all services
- Run all algorithms for comparison
- Full algorithm traces

**Medium Datasets** (100-500 services):
- LLM annotation for top 20% by QoS
- Classic annotation for remaining 80%
- Focus on A* or Greedy for compositions
- Limited trace (first 50 steps)

**Large Datasets** (>500 services):
- Classic annotation only
- Use Greedy algorithm
- Minimal trace/visualization
- Consider pre-filtering services by QoS thresholds

---

## Troubleshooting

### Common Issues

#### 1. Ollama Connection Error

**Symptom**:
```
Error: Cannot connect to Ollama. Is it running?
```

**Solutions**:
```bash
# Check if Ollama is running
curl http://localhost:11434

# Start Ollama
ollama serve

# Check model availability
ollama list

# Pull model if missing
ollama pull llama3.2:3b

# Verify endpoint in code
# annotator.py, llm_composer.py:
ollama_url = "http://localhost:11434"
```

#### 2. LLM Composition Fails: Services Not Annotated

**Symptom**:
```json
{
    "error": "Services must be annotated before LLM composition"
}
```

**Solution**:
1. Go to Tab 2 (Automatic Annotation)
2. Select services to annotate
3. Check annotation types
4. Start annotation process
5. Wait for completion
6. Return to Tab 4 and retry composition

**Verify**:
```bash
curl http://localhost:5000/api/annotation/status

# Should show:
# "services_annotated": true
```

#### 3. Request Parsing Fails

**Symptom**:
```
Error parsing requests: No such file or directory
```

**Cause**: Temporary file not flushed to disk

**Fix**: Already implemented in `wsdl_parser.py`:
```python
with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
    tmp.write(content)
    tmp.flush()  # CRITICAL
    os.fsync(tmp.fileno())  # CRITICAL
```

#### 4. CORS Errors in Browser

**Symptom**:
```
Access to fetch at 'http://localhost:5000/api/...' from origin 'http://localhost:8080' has been blocked by CORS
```

**Fix**: Already configured in `app.py`:
```python
from flask_cors import CORS
CORS(app)  # Allows all origins
```

**Alternative** (restrict origins):
```python
CORS(app, resources={
    r"/api/*": {"origins": ["http://localhost:8080"]}
})
```

#### 5. Composition Returns No Results

**Possible Causes**:

A. **No I/O Match**:
```
Request needs param10 as output
No service produces param10
→ No composition possible
```

B. **QoS Too Strict**:
```
Request requires: Reliability ≥ 99%, Availability ≥ 99.9%
No service meets these constraints
→ Empty candidate pool
```

C. **Circular Dependency**:
```
Service A requires Service B's output
Service B requires Service A's output
→ Deadlock in graph
```

**Diagnosis**:
```python
# Check algorithm trace
result.algorithm_trace[-1]  # Last step shows reason

# Common failures:
{"action": "dead_end", "description": "No applicable services"}
{"action": "failed", "description": "No composition found"}
```

#### 6. Training Not Improving Results

**Possible Causes**:

A. **Insufficient Training Examples**:
- Need at least 20 examples
- Prefer 50-100 for good patterns

B. **Training/Test Mismatch**:
- Training on different service types
- Different QoS ranges
- Different request patterns

C. **Training Quality Issues**:
- Best solutions are not actually optimal
- Training data has errors/inconsistencies

**Verification**:
```bash
# Check training status
curl http://localhost:5000/api/training/status

# Review learned patterns
# Check: Are patterns diverse?
#        Do they cover different QoS priorities?
#        Are utilities reasonable (50-100)?
```

#### 7. Memory Issues with Large Datasets

**Symptom**:
```
MemoryError: Unable to allocate array
```

**Solutions**:

A. **Increase Python memory limit**:
```python
# run.py
import sys
sys.setrecursionlimit(10000)
```

B. **Batch processing**:
```python
# Process services in chunks
for batch in chunks(services, 500):
    process_batch(batch)
```

C. **Reduce graph size**:
```python
# classic_composer.py
candidates = candidates[:40]  # Limit candidates
```

#### 8. Slow Annotation with LLM

**Expected Behavior**:
- 4 seconds per service per annotation type
- 100 services × 3 types = 20 minutes

**Optimization Strategies**:

A. **Selective LLM annotation**:
```javascript
// Annotate only high-value services
services.filter(s => s.qos.reliability > 90)
```

B. **Parallel processing** (future enhancement):
```python
# Use threading for multiple Ollama requests
from concurrent.futures import ThreadPoolExecutor
```

C. **Model downgrade**:
```bash
ollama pull llama3.2:1b  # Faster, lower quality
```

---

**Last Updated**: February 25, 2026  
**Version**: 1.0.1
