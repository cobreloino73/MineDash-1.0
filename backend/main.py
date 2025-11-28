"""
MineDash AI - Backend API
Sistema Experto de Operaciones Mineras con Análisis Causal
División Salvador - Codelco Chile
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

# Services
from services.lightrag_setup import get_rag_instance
from services.ranking_analytics import get_ranking_analytics
from services.causal_analytics import get_causal_analytics
from services.insights import get_insights_system
from services.intelligent_extractor import get_intelligent_extractor
from services.feedback_system import get_feedback_system
from services.plan_comparison import get_plan_comparison_service
from config import Config

# Wrappers
def get_rag_service():
    return get_rag_instance()

def get_rankings_service():
    return get_ranking_analytics()

# ==================== SERVICIOS GLOBALES ====================
_rag_service = None
_rankings_service = None

def get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = get_rag_instance()  # ✅ CORRECTO
    return _rag_service

def get_rankings_service():
    global _rankings_service
    if _rankings_service is None:
        _rankings_service = get_ranking_analytics()  # ✅ CORRECTO
    return _rankings_service

# ==================== FASTAPI APP ====================
app = FastAPI(
    title="MineDash AI API",
    version="2.0.0",
    description="Sistema Experto de Operaciones Mineras con Análisis Causal",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELS ====================
class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"

# ==================== ENDPOINTS ====================

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz"""
    return {
        "service": "MineDash AI",
        "version": "2.0.0",
        "status": "online",
        "division": "Salvador - Codelco Chile"
    }

@app.get("/api/info", tags=["Info"])
async def get_info():
    """Obtiene información del sistema"""
    try:
        rag = get_rag_service()
        
        return {
            "service": "MineDash AI",
            "version": "2.0.0",
            "division": "Salvador",
            "company": "Codelco Chile",
            "description": "Sistema Experto de Operaciones Mineras con Análisis Causal",
            "features": [
                "Análisis de datos Hexagon MineOPS",
                "Códigos ASARCO para clasificación de demoras",
                "Análisis causal operador-equipo-estados",
                "Rankings dinámicos de operadores",
                "Análisis de utilización y disponibilidad",
                "Embeddings Gemini para alta calidad",
                "LLM Claude Sonnet 4 para análisis experto"
            ],
            "endpoints": [
                "/api/query",
                "/api/ranking/operadores-produccion",
                "/api/ranking/operadores-dumps", 
                "/api/ranking/operadores-eficiencia",
                "/api/analytics/operador-causal",
                "/api/insights",
                "/api/debug/equipos",
                "/api/debug/operadores"
            ],
            "data_sources": [
                "Hexagon MineOPS (ciclos, dumps, estados)",
                "Control de Gestión (KPIs, producción)",
                "Seguridad (incidentes, dotación, ausentismo)",
                "Planificación (planes mensuales)",
                "Perforación y Tronadura (diseño, ejecución)"
            ],
            "rag_status": {
                "working_dir": str(Config.LIGHTRAG_DIR),
                "embeddings_model": "gemini-1.5-flash",
                "llm_model": "claude-sonnet-4-20250514"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query", tags=["RAG"])
async def query_rag(request: QueryRequest):
    """
    Consulta al sistema RAG
    
    Modos disponibles:
    - local: Búsqueda local en el grafo de conocimiento
    - global: Búsqueda global con contexto amplio
    - hybrid: Combinación de ambos (recomendado)
    """
    try:
        rag = get_rag_service()
        
        response = rag.query(
            query=request.query,
            search_mode=request.mode
        )
        
        return {
            "success": True,
            "query": request.query,
            "mode": request.mode,
            "response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ranking/operadores-produccion", tags=["Rankings"])
async def get_ranking_produccion(
    year: int = 2024,
    top_n: int = 10,
    tipo: str = ""
):
    """
    Ranking de operadores por producción (toneladas)
    
    Args:
        year: Año de análisis
        top_n: Número de operadores a retornar
        tipo: Filtro por tipo de equipo (opcional)
    """
    try:
        rankings = get_rankings_service()
        result = rankings.ranking_operadores_produccion(year, top_n, tipo)
        return result
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@app.get("/api/ranking/operadores-dumps", tags=["Rankings"])
async def get_ranking_dumps(
    year: int = 2024,
    top_n: int = 10
):
    """
    Ranking de operadores por número de dumps
    
    Args:
        year: Año de análisis
        top_n: Número de operadores a retornar
    """
    try:
        rankings = get_rankings_service()
        result = rankings.ranking_operadores_dumps(year, top_n)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ranking/operadores-eficiencia", tags=["Rankings"])
async def get_ranking_eficiencia(
    year: int = 2024,
    top_n: int = 10,
    tipo: str = ""
):
    """
    Ranking de operadores por eficiencia (ton/dump)
    
    Args:
        year: Año de análisis
        top_n: Número de operadores a retornar
        tipo: Filtro por tipo de equipo (opcional)
    """
    try:
        rankings = get_rankings_service()
        result = rankings.ranking_operadores_eficiencia(year, top_n, tipo)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/operador-causal", tags=["Análisis Causal"])
async def get_operador_causal(
    apellido: str,
    year: int = 2024,
    mes_inicio: int = 1,
    mes_fin: int = 12
):
    """
    Análisis causal de utilización de un operador
    
    Correlaciona:
    1. Dumps del operador (qué equipos usó)
    2. Estados de esos equipos (códigos ASARCO)
    3. Horas de esos equipos (utilización)
    
    Args:
        apellido: Apellido del operador
        year: Año de análisis
        mes_inicio: Mes de inicio del período
        mes_fin: Mes de fin del período
    """
    try:
        causal = get_causal_analytics()
        result = causal.analisis_operador_utilizacion(
            operador_apellido=apellido,
            year=year,
            mes_inicio=mes_inicio,
            mes_fin=mes_fin
        )
        return result
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@app.get("/api/insights", tags=["Insights"])
async def get_insights(
    year: int = 2024,
    plan: str = 'P0'
):
    """
    Obtiene insights inteligentes del sistema
    
    Genera alertas, recomendaciones y predicciones basadas en:
    - Cumplimiento de plan (P0, PND, Plan Mensual)
    - KPIs operacionales (Disponibilidad, Utilización)
    - Códigos ASARCO críticos
    - Tendencias y proyecciones
    
    Args:
        year: Año de análisis
        plan: Tipo de plan (P0, PND, MENSUAL)
        
    Returns:
        Dict con:
        - plan_referencia: Datos del plan seleccionado
        - kpis_actuales: Métricas actuales del sistema
        - cumplimiento: Análisis de cumplimiento vs plan
        - alertas: Problemas que requieren atención
        - recomendaciones: Acciones sugeridas
        - predicciones: Proyecciones y tendencias
    """
    try:
        # Validar plan
        plan_upper = plan.upper()
        if plan_upper not in ['P0', 'PND', 'MENSUAL']:
            raise HTTPException(
                status_code=400,
                detail=f"Plan inválido. Debe ser: P0, PND o MENSUAL. Recibido: {plan}"
            )
        
        insights_sys = get_insights_system()
        insights = insights_sys.generar_insights(year, plan_upper)
        
        return insights
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@app.get("/api/debug/equipos", tags=["Debug"])
async def debug_equipos(year: int = 2024):
    """Debug - Lista de equipos únicos"""
    try:
        rankings = get_rankings_service()
        result = rankings.debug_equipos_unicos(year)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/operadores", tags=["Debug"])
async def debug_operadores(year: int = 2024):
    """Debug - Lista de operadores únicos"""
    try:
        rankings = get_rankings_service()
        result = rankings.debug_operadores_unicos(year)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/compare/real-vs-plans", tags=["Comparaciones"])
async def compare_real_vs_plans(
    mes: int,
    year: int = 2024,
    incluir_acumulado: bool = True
):
    """
    Compara producción real vs todos los planes (P0, PND, PM)
    
    Ejemplo: /api/compare/real-vs-plans?mes=7&year=2025&incluir_acumulado=true
    
    Responde: "Dame resultado real julio 2025 vs planes"
    """
    try:
        comparison = get_plan_comparison_service()
        result = await comparison.compare_real_vs_plans(mes, year, incluir_acumulado)
        return result
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@app.post("/api/feedback/validate", tags=["Feedback"])
async def validate_insight(request: dict):
    """
    Registra validación del usuario sobre un insight
    
    Body:
    {
        "insight_type": "alerta | recomendacion | prediccion | plan_extraction",
        "insight_data": {...},
        "user_validation": true/false,
        "corrections": {...},
        "user_comment": "string"
    }
    """
    try:
        feedback = get_feedback_system()
        result = await feedback.record_feedback(
            insight_type=request.get("insight_type"),
            insight_data=request.get("insight_data"),
            user_validation=request.get("user_validation"),
            corrections=request.get("corrections"),
            user_comment=request.get("user_comment")
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/feedback/stats", tags=["Feedback"])
async def get_learning_stats():
    """Obtiene estadísticas de aprendizaje del sistema"""
    try:
        feedback = get_feedback_system()
        stats = await feedback.get_learning_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/plans/extract-all", tags=["Planes"])
async def extract_all_plans():
    """
    Extrae todos los planes disponibles usando IA
    El sistema lee los Excel y aprende automáticamente
    """
    try:
        extractor = get_intelligent_extractor()
        planes = await extractor.extract_all_plans()
        return {
            "success": True,
            "planes": planes,
            "total": len(planes)
        }
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

# ==================== MAIN ====================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 MineDash AI - Backend API")
    print("="*60)
    print(f"📍 División Salvador - Codelco Chile")
    print(f"📊 Análisis Causal de Operaciones Mineras")
    print(f"🔗 Docs: http://localhost:8000/docs")
    print("="*60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )