# File Generation Service - System Documentation

## Overview

The File Generation Service is an AI-powered template management system that enables users to upload document templates (PDF/DOCX), fill them with company data using LLM technology, and retrieve information through RAG-based question answering.

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ ┌───────┐ │
│  │   Templates  │  │ Template Fill│  │ Template Q&A │ │Agent  │ │
│  │   Management │  │   (LLM-based)│  │  (RAG-based) │ │Orch.  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ └───────┘ │
│         │                 │                  │            │      │
├─────────┼─────────────────┼──────────────────┼────────────┼──────┤
│         │                 │                  │            │      │
│  ┌──────▼──────┐  ┌───────▼──────┐  ┌──────▼──────┐ ┌──▼──────┐ │
│  │ PostgreSQL  │  │ Qdrant Vector│  │ LLM Service │ │OpenAI   │ │
│  │  Database   │  │ Database (RAG)│  │ (gpt-4o)    │ │w/ Tools │ │
│  └─────────────┘  └───────────────┘  └─────────────┘ └─────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Template Upload Flow
1. User uploads a PDF/DOCX file
2. File is validated and extracted
3. Document is chunked into sections
4. Chunks are indexed in **Qdrant** for vector search
5. Metadata stored in **PostgreSQL**

### 2. Template Fill Flow
1. User requests template fill with company data
2. System retrieves template structure from PostgreSQL
3. For each section:
   - **RAG Retriever** fetches relevant context from Qdrant
   - **LLM** generates content based on company data + context
4. Filled template saved to PostgreSQL and Qdrant
5. Version management maintained

### 3. Q&A Flow (RAG)
1. User asks a question about a template
2. **RAG Retriever** searches Qdrant for relevant sections
3. **LLM** generates answer based on retrieved context
4. Confidence score calculated and Q&A record saved

### 4. Agent Orchestration Flow (NEW)
1. User requests agent orchestration for template fill + QA
2. **Agent Orchestrator** receives template_id and company_data
3. Agent uses **OpenAI GPT-4o with function calling** to execute workflow:
   - **Tool 1: fill_template** - Fills all placeholders with company data using LLM + RAG
   - **Tool 2: create_and_validate** - Validates quality (completeness, relevance, grammar, consistency, accuracy)
   - **Tool 3: ask_qa_questions** - Asks 7-10 strategic questions and verifies answers
   - **Tool 4: retrieve_vector_context** - Retrieves and verifies context from Qdrant
4. Agent applies **chain-of-thought reasoning** to:
   - Analyze template structure
   - Plan validation strategy
   - Develop strategic QA questions
   - Make final recommendation
5. All results saved to PostgreSQL and Qdrant
6. Returns comprehensive report with:
   - Quality scores
   - QA results
   - Final recommendation (APPROVED, NEEDS_REVISION, MANUAL_REVIEW, etc.)

**Key Difference**: Instead of user calling fill → validate → QA separately, the agent intelligently orchestrates the entire workflow with reasoning at each step.

### 5. Template Generation Flow (NEW)
1. User requests creation of new template from scratch
2. **Template Generator** receives:
   - Template name (e.g., "Sales Proposal Template")
   - Template type (proposal, report, contract, invoice, etc.)
   - Company type (SaaS, Manufacturing, Finance, etc.)
   - Number of sections and additional context
3. **LLM generates** template structure with:
   - Section names and descriptions
   - Content templates with [PLACEHOLDER] markers
   - Placeholder definitions (type, description, required)
   - Tips for filling each section
4. **System creates** HTML/DOCX file with:
   - Professional formatting
   - Clear section organization
   - Placeholder highlighting
5. **Saves to both databases**:
   - PostgreSQL: Template metadata, sections, placeholders
   - Qdrant: Embeddings for semantic search
6. Returns:
   - template_id and file_path
   - Sections count and placeholders count
   - Ready to use immediately

## Flow Comparison: Before vs After Agent Orchestration

### OLD FLOW (Manual Sequential Steps)
```
User makes multiple API calls:
  1. POST /api/v1/templates/{id}/fill
  2. Wait for response
  3. POST /api/v1/templates/{id}/ask (repeat multiple times)
  4. Wait for each response
  5. Manual quality assessment
  
Problems:
  ✗ Multiple API calls needed
  ✗ Manual decision-making at each step
  ✗ No intelligent orchestration
  ✗ No automatic quality validation
  ✗ User must decide what to do next
```

### NEW FLOW (Agent-Orchestrated)
```
User makes single API call:
  POST /api/v1/agent/{id}/orchestrate-fill-and-qa
        ↓
  ┌────────────────────────────────────────────────┐
  │  Agent (OpenAI GPT-4o with Function Calling)   │
  ├────────────────────────────────────────────────┤
  │                                                 │
  │  [PLAN] Chain-of-thought reasoning             │
  │  └─→ Analyze template & plan strategy          │
  │                                                 │
  │  [FILL] Execute: fill_template()               │
  │  └─→ Use LLMFiller + RAG context               │
  │  └─→ Save to PostgreSQL + Qdrant               │
  │                                                 │
  │  [VALIDATE] Execute: create_and_validate()     │
  │  └─→ Check completeness, relevance, grammar,   │
  │      consistency, accuracy                     │
  │  └─→ Calculate quality score                   │
  │                                                 │
  │  [QA] Execute: ask_qa_questions()              │
  │  └─→ Ask 7-10 strategic questions              │
  │  └─→ Retrieve from Qdrant                      │
  │  └─→ Verify accuracy with similarity scores    │
  │                                                 │
  │  [VERIFY] Execute: retrieve_vector_context()   │
  │  └─→ Double-check critical information         │
  │                                                 │
  │  [DECIDE] Make Final Recommendation            │
  │  └─→ APPROVED                                  │
  │  └─→ APPROVED_WITH_NOTES                       │
  │  └─→ NEEDS_REVISION                            │
  │  └─→ NEEDS_REFILL                              │
  │  └─→ MANUAL_REVIEW                             │
  │                                                 │
  └────────────────────────────────────────────────┘
        ↓
  Returns comprehensive report with:
  ├─ Quality scores (completeness, relevance, etc.)
  ├─ QA results (pass rate, findings)
  ├─ Validation details
  ├─ Final recommendation
  └─ Agent reasoning explanation

Benefits:
  ✓ Single API call for complete workflow
  ✓ Intelligent decision-making at each step
  ✓ Automatic quality validation
  ✓ Strategic QA generation
  ✓ Chain-of-thought reasoning
  ✓ Clear recommendation
  ✓ No manual intervention
  ✓ Comprehensive report
```

## File Structure

### Routes (`app/routes/`)
- **health.py** - Health check and service info endpoints
- **templates.py** - Template CRUD operations (upload, list, get, delete)
- **template_fill.py** - Template filling endpoints (fill, preview, history, versioning)
- **template_qa.py** - Q&A endpoints (ask, history, search, delete)
- **agent_orchestration.py** (NEW) - Agent-driven orchestration endpoints (fill + QA + validate)
- **template_generation.py** (NEW) - Template generation endpoints (create new templates from scratch)

### Services (`app/services/`)
- **template_manager.py** - Manages template storage and retrieval
- **vector_db_service.py** - Handles Qdrant vector database operations
- **embedding_service.py** - Generates embeddings for chunks
- **llm_filler.py** - Fills templates using LLM + context
- **rag_retriever.py** - Retrieves context from Qdrant for RAG
- **agent_orchestrator.py** (NEW) - Orchestrates fill + validation + QA using OpenAI with function calling
- **template_generator.py** (NEW) - Generates new templates from scratch using LLM

### Utilities
- **collection_recovery.py** - Auto-recovery mechanism for Qdrant collection
- **llm_client.py** - LLM API client interface

### Database
- **PostgreSQL** - Stores templates, versions, Q&A records, metadata
- **Qdrant** - Vector database for semantic search and RAG context

## Key Features

### 1. Template Management
- Upload and store document templates
- Extract sections and placeholders automatically
- Organize by company and category
- Version control for templates

### 2. Intelligent Filling
- LLM-powered content generation
- Context-aware using RAG retrieval
- Configurable temperature for creativity
- Preview generation before save
- Version history tracking

### 3. RAG-Based Q&A
- Semantic search on template content
- Context-aware answers using LLM
- Confidence scoring
- Q&A history and search
- Multi-user support

### 4. Automatic Recovery
- Auto-recovery of Qdrant collections
- Retry logic for failed operations
- Duplicate template detection
- Error handling with graceful fallbacks

### 5. Agent-Driven Orchestration (NEW)
- OpenAI GPT-4o with function calling
- Intelligent workflow orchestration
- Chain-of-thought reasoning for better decisions
- Atomic tools: fill, validate, QA, retrieve context
- Automatic quality assessment and recommendations
- Strategic QA question generation
- Single endpoint for complete fill + QA workflow

### 6. Template Generation (NEW)
- Generate new templates from scratch using LLM
- Supports 14+ template types (proposal, report, contract, invoice, etc.)
- Supports 14+ industry types (SaaS, Manufacturing, Finance, etc.)
- Configurable number of sections
- Automatic placeholder generation with descriptions
- Saves to PostgreSQL and Qdrant immediately
- Generated templates ready to use instantly

## API Endpoints Summary

| Category | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| Health | GET | `/api/v1/health` | Check service status |
| Health | GET | `/api/v1/info` | Get service information |
| Templates | POST | `/api/v1/templates/upload` | Upload new template |
| Templates | GET | `/api/v1/templates/list` | List all templates |
| Templates | GET | `/api/v1/templates/{template_id}` | Get template details |
| Templates | DELETE | `/api/v1/templates/{template_id}` | Delete template |
| Fill | POST | `/api/v1/templates/{template_id}/fill` | Fill template with data |
| Fill | POST | `/api/v1/templates/{template_id}/fill-preview` | Preview filled template |
| Fill | GET | `/api/v1/templates/{template_id}/fill-history` | Get fill versions |
| Fill | GET | `/api/v1/templates/{template_id}/versions/{version_id}` | Get specific version |
| Fill | DELETE | `/api/v1/templates/{template_id}/versions/{version_id}` | Delete version |
| Q&A | POST | `/api/v1/templates/{template_id}/ask` | Ask about template |
| Q&A | GET | `/api/v1/templates/{template_id}/qa-history` | Get Q&A history |
| Q&A | POST | `/api/v1/templates/{template_id}/qa-search` | Search Q&A |
| Q&A | DELETE | `/api/v1/templates/{template_id}/qa-history/{qa_id}` | Delete Q&A entry |
| Agent | POST | `/api/v1/agent/{template_id}/orchestrate-fill-and-qa` | Agent-driven fill + QA + validation |
| Generation | POST | `/api/v1/templates/generate` | Generate new template from scratch |
| Generation | GET | `/api/v1/templates/generation-types` | Get supported template and company types |

## Technology Stack

- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL (relational database)
- **Vector DB**: Qdrant (vector similarity search)
- **LLM**: Language Model Service (LLM API integration)
- **Embeddings**: Multi-lingual embeddings
- **Server**: Uvicorn (ASGI server)
- **Containerization**: Docker

## Environment Variables

```
DATABASE_HOST=postgresql://localhost
DATABASE_PORT=5432
DATABASE_NAME=file_gen_db
QDRANT_URL=http://localhost:6333
LLM_MODEL=your-llm-model-name
EMBEDDING_MODEL=multi-lingual-model
CORS_ORIGINS=["http://localhost:3000"]
MAX_FILE_SIZE_MB=50
```

## Running the Service

### Using Docker
```bash
docker-compose up --build
```

### Locally
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Access
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/api/v1/health

## Agent Orchestration Implementation

### Files Created
1. **`app/services/agent_orchestrator.py`** (~500 lines)
   - Main agent orchestration engine
   - Uses OpenAI GPT-4o with function calling
   - Defines 4 atomic tools: fill, validate, QA, retrieve context
   - Applies chain-of-thought reasoning

2. **`app/routes/agent_orchestration.py`** (~50 lines)
   - FastAPI endpoint: `POST /api/v1/agent/{template_id}/orchestrate-fill-and-qa`
   - Handles orchestration requests
   - Returns comprehensive results

3. **`docs/AGENT_SYSTEM_PROMPT.md`** (~400 lines)
   - System prompt for agent
   - Detailed chain-of-thought reasoning
   - Tool usage rules and constraints
   - Success metrics and validation criteria

### Files Modified
1. **`app/main.py`**
   - Added agent_orchestration router import
   - Registered agent routes
   - Added agent status to startup logs

2. **`docs/README.md`** (this file)
   - Updated architecture diagram
   - Added agent flow documentation
   - Updated technology stack

### Database Integration

#### PostgreSQL
- **Reads**: Template structure, version details
- **Writes**: Filled versions, QA records
- **Operations**: 4-6 queries per orchestration

#### Qdrant
- **Reads**: RAG context retrieval, similarity search
- **Writes**: Indexed embeddings for filled content
- **Operations**: 10-15 queries per orchestration

### Template Generation Integration

#### Files Created
1. **`app/services/template_generator.py`** (~400 lines)
   - Generates template structure using LLM
   - Creates HTML files from template structure
   - Saves to PostgreSQL (template, sections, placeholders)
   - Saves embeddings to Qdrant

2. **`app/routes/template_generation.py`** (~100 lines)
   - `POST /api/v1/templates/generate` - Generate new template
   - `GET /api/v1/templates/generation-types` - List supported types

#### Agent Tool
- **generate_template()** - Can be called by agent during orchestration
  - Parameters: template_name, template_type, company_type, num_sections
  - Returns: template_id, file_path, sections_count

#### Example Usage

**Direct Endpoint:**
```bash
POST /api/v1/templates/generate

{
  "template_name": "Sales Proposal",
  "template_type": "proposal",
  "company_type": "SaaS",
  "num_sections": 7,
  "additional_context": "Focus on enterprise clients"
}
```

**Via Agent:**
The agent can call `generate_template()` tool to create templates as part of orchestration workflow.

### Agent Tools

#### 1. fill_template()
- **Input**: template_id, company_data, additional_context
- **Output**: version_id, sections_filled, placeholders_filled
- **Uses**: LLMFiller, RAGRetriever
- **Saves**: PostgreSQL (version), Qdrant (embeddings)

#### 2. create_and_validate()
- **Input**: template_id, version_id
- **Output**: Quality scores (completeness, relevance, grammar, consistency, accuracy)
- **Validation**: 5 dimensions checked
- **Saves**: Not saved (computed in memory)

#### 3. ask_qa_questions()
- **Input**: template_id, questions (7-10 list)
- **Output**: QA results, pass rate, similarity scores
- **Uses**: RAGRetriever for context retrieval
- **Saves**: QA records to PostgreSQL

#### 4. retrieve_vector_context()
- **Input**: template_id, query
- **Output**: Context chunks, similarity scores
- **Uses**: Direct Qdrant queries
- **Saves**: Not saved (read-only)

### Performance Metrics

- **Typical Duration**: 20-45 seconds per orchestration
- **API Calls to OpenAI**: 15-25 calls
- **Database Queries**: 14-21 total (PostgreSQL + Qdrant)
- **Estimated Cost**: $0.10-0.20 per orchestration (GPT-4o)
