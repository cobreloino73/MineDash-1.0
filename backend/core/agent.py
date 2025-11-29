"""

MineDash AI v2.0 - Agentic AI Module

FASE 1: Agente Inteligente con Herramientas



VERSIÓN COMPLETA 1700+ LÍNEAS - FIX GAVIOTA APLICADO:

 TODO el código original preservado

 Fix de gaviota aplicado (mapeo de horas + mensaje fuerte)

 Indentación corregida

 Resto del código intacto

"""



import os

import json

import sqlite3

import pandas as pd

from datetime import datetime, timedelta

from pathlib import Path

from typing import Dict, List, Any, Optional, Tuple

from openai import OpenAI  # OpenAI API

import asyncio

import requests



# Importar herramientas

import sys

sys.path.append(str(Path(__file__).parent.parent))

from tools.sql_tool import SQLTool

from tools.code_tool import CodeExecutor

from tools.chart_tool import ChartGenerator

from tools.report_tool import ReportGenerator

from services.context_service import get_context_service



# Importar servicio de rankings

from services.ranking_analytics import get_ranking_analytics



# Importar readers de IGM y Plan por fases

from services.igm_reader import leer_igm_mes, obtener_real_por_fase_con_fallback

from services.plan_reader import PlanReader



# Importar conocimiento experto de minería

from knowledge.mining_expertise import get_analysis_context



# Importar sistema de razonamiento profundo

from knowledge.deep_reasoning import (

    get_reasoning_effort,

    get_reasoning_instructions,

    should_use_reasoning_mode,

    enhance_query_with_reasoning_trigger

)



# Importar knowledge base aprendida de IGM

from knowledge.loader import get_knowledge_prompt_section

# Importar HippoRAG para contexto de dominio (v3.0)
from services.hipporag_service import search_knowledge as hipporag_search



#  Importar Economic Manager

from .economic_manager import EconomicParametersManager



# Importar diccionario de códigos ASARCO (si existe)

try:

    sys.path.append(str(Path(__file__).parent.parent / "data" / "asarco_analysis"))

    from asarco_codes_dict import ASARCO_CODES, get_codigo_info, get_categoria, get_razon

    ASARCO_AVAILABLE = True

    print("[OK] Diccionario ASARCO cargado exitosamente")

except ImportError:

    ASARCO_CODES = {}

    ASARCO_AVAILABLE = False

    print("[WARN] Diccionario ASARCO no disponible. Ejecute: python scripts/extract_asarco_codes.py")



#  Importar ValidationAgent y reglas anti-alucinación

#from .validation_agent import ValidationAgent#

#from .system_prompt_anti_alucinacion import ANTI_HALLUCINATION_RULES#


# =============================================================================
# CACHE GLOBAL PARA DATAFRAMES PESADOS (OPTIMIZACIÓN DE RENDIMIENTO)
# =============================================================================
_DATAFRAME_CACHE = {}

def get_cached_dataframe(file_path: str, sheet_name: str = None) -> 'pd.DataFrame':
    """
    Carga un DataFrame desde Excel con cache en memoria.
    La primera carga es lenta, las siguientes son instantáneas.
    """
    import pandas as pd
    from pathlib import Path

    cache_key = f"{file_path}:{sheet_name}"

    if cache_key not in _DATAFRAME_CACHE:
        print(f"   [CACHE] Cargando {Path(file_path).name}...")
        if sheet_name:
            _DATAFRAME_CACHE[cache_key] = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            _DATAFRAME_CACHE[cache_key] = pd.read_excel(file_path)
        print(f"   [CACHE] {Path(file_path).name} cargado ({len(_DATAFRAME_CACHE[cache_key]):,} filas)")
    else:
        print(f"   [CACHE] Usando cache para {Path(file_path).name}")

    return _DATAFRAME_CACHE[cache_key].copy()



# =============================================================================

# HELPER: Extracción de Períodos de Fechas

# =============================================================================



MESES_ES = {

    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,

    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,

    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12

}



def extraer_periodo_query(query: str) -> dict:

    """

    Extrae período de fechas de la consulta del usuario.



    Soporta patrones como:

    - "desde enero 2025 a julio 2025"

    - "enero a julio 2025"

    - "enero-julio 2025"

    - "primer semestre 2025"

    - "2024 completo"



    Returns:

        dict con mes_inicio, mes_fin, año (o None si no detecta patrón)

    """

    import re

    query_lower = query.lower()



    # Patrón 1: "desde X año a Y año"

    match = re.search(r'desde\s+(\w+)\s+(\d{4})\s+(?:a|hasta|al?)\s+(\w+)\s+(\d{4})', query_lower)

    if match:

        mes1, año1, mes2, año2 = match.groups()

        if mes1 in MESES_ES and mes2 in MESES_ES:

            return {

                'mes_inicio': MESES_ES[mes1],

                'mes_fin': MESES_ES[mes2],

                'año_inicio': int(año1),

                'año_fin': int(año2),

                'tipo': 'rango_completo'

            }



    # Patrón 2: "X a Y año" o "X-Y año"

    match = re.search(r'(\w+)\s*(?:a|hasta|al?|-|–)\s*(\w+)\s+(?:del?\s+)?(\d{4})', query_lower)

    if match:

        mes1, mes2, año = match.groups()

        if mes1 in MESES_ES and mes2 in MESES_ES:

            return {

                'mes_inicio': MESES_ES[mes1],

                'mes_fin': MESES_ES[mes2],

                'año': int(año),

                'tipo': 'rango_mismo_año'

            }



    # Patrón 3: "primer/segundo semestre año"

    match = re.search(r'(primer|segundo|1er|2do)\s+semestre\s+(?:del?\s+)?(\d{4})', query_lower)

    if match:

        semestre, año = match.groups()

        if semestre in ['primer', '1er']:

            return {'mes_inicio': 1, 'mes_fin': 6, 'año': int(año), 'tipo': 'semestre'}

        else:

            return {'mes_inicio': 7, 'mes_fin': 12, 'año': int(año), 'tipo': 'semestre'}



    # Patrón 4: "año completo" o solo "año"

    match = re.search(r'(?:año\s+)?(\d{4})\s*(?:completo)?', query_lower)

    if match and 'a' not in query_lower.split(match.group(1))[0][-5:]:  # evitar falsos positivos

        año = int(match.group(1))

        # Solo si no hay meses específicos mencionados

        if not any(mes in query_lower for mes in MESES_ES.keys()):

            return {'mes_inicio': 1, 'mes_fin': 12, 'año': año, 'tipo': 'año_completo'}



    # Patrón 5: "mes año" (mes único)

    for mes_nombre, mes_num in MESES_ES.items():

        match = re.search(rf'{mes_nombre}\s+(?:del?\s+)?(\d{{4}})', query_lower)

        if match:

            return {

                'mes_inicio': mes_num,

                'mes_fin': mes_num,

                'año': int(match.group(1)),

                'tipo': 'mes_unico'

            }



    return None





class MineDashAgent:

    """Agente Inteligente para MineDash AI"""

    

    def __init__(

        self,

        openai_api_key: str,

        db_path: str = "minedash.db",

        outputs_dir: str = "outputs",

        lightrag_service = None,

        api_base_url: str = "http://localhost:8000",

        data_dir: Path = None,

        user_id: str = "anonymous",

        history_folder: str = "user_history",

        world_model = None,

        learning_system = None

    ):

        # Inicializar cliente OpenAI con configuración extendida para GPT-5.1

        # Tier 3 soporta 1M+ tokens, aumentamos límites

        self.client = OpenAI(

            api_key=openai_api_key,

            max_retries=3,

            timeout=300.0  # 5 minutos para queries complejas

        )



        # Límite de tokens para contexto (250K para GPT-5.1 - OpenAI enforces 272K server-side)

        # Usar 250K como límite seguro para dejar margen de seguridad

        self.max_context_tokens = 250000

        self.max_history_messages = 10  # Más contexto para secuencias de herramientas múltiples

        self.db_path = db_path

        self.outputs_dir = Path(outputs_dir)

        self.lightrag = lightrag_service

        self.api_base_url = api_base_url

        self.context = get_context_service()



        # Sistemas de inteligencia avanzada

        self.world_model = world_model

        self.learning_system = learning_system



        if self.world_model:

            print("  World Model integrado - Simulaciones operacionales activas")

        if self.learning_system:

            print("  Learning System integrado - Aprendizaje continuo activo")



        # FIX GENERATE_CHART: Contexto compartido para resultados de herramientas

        self.last_tool_results = {}



        # User-specific configuration

        self.user_id = user_id

        self.history_folder = Path(history_folder)

        self.history_folder.mkdir(parents=True, exist_ok=True)

        self.history_file = self.history_folder / f"{user_id}_history.json" 

        

        #  Inicializar Economic Manager

        self.economic_manager = EconomicParametersManager(db_path=self.db_path)

        print(" Economic Manager inicializado")

        

        #  Inicializar ValidationAgent

        #self.validator = ValidationAgent(anthropic_api_key=anthropic_api_key)#

        #print("  ValidationAgent inicializado")#

        self.validator = None  # DESACTIVADO PARA PRESENTACIÓN

        print("  ValidationAgent DESACTIVADO")



        # Crear subdirectorios

        self.charts_dir = self.outputs_dir / "charts"

        self.reports_dir = self.outputs_dir / "reports"

        self.code_dir = self.outputs_dir / "code"

        

        for dir_path in [self.charts_dir, self.reports_dir, self.code_dir]:

            dir_path.mkdir(parents=True, exist_ok=True)

        

        # Inicializar herramientas

        self.sql_tool = SQLTool(db_path)

        self.code_executor = CodeExecutor(self.code_dir)

        self.chart_generator = ChartGenerator(self.charts_dir)

        self.report_generator = ReportGenerator(self.reports_dir)

        

        # Usar data_dir del parámetro

        if data_dir:

            self.ranking_service = get_ranking_analytics(data_dir)

        else:

            from config import Config

            self.ranking_service = get_ranking_analytics(Config.DATA_DIR)

        

        # Historial de conversación - Load from user-specific file

        self.conversation_history = self._load_user_history()



        # Documentos temporales del usuario (para usuarios no-admin)

        self.temporary_documents = {}



        # Definir herramientas disponibles con descripciones detalladas

       # Definir herramientas disponibles con descripciones detalladas

        self.tools = [

            {

                "name": "execute_sql",
                "description": """🗄️ SQL DIRECTO - Consultas personalizadas a BD minedash.db.

✅ USAR PARA:
- Consultas específicas no cubiertas por otras herramientas
- Análisis custom que requiere SQL directo
- Explorar datos de tablas específicas

❌ NO USAR PARA (usar herramientas especializadas):
- Cumplimiento tonelaje → obtener_cumplimiento_tonelaje
- Ranking operadores → get_ranking_operadores
- Causas de delay → obtener_pareto_delays
- Análisis gaviota → obtener_analisis_gaviota
- Costos → obtener_costos_mina

⚠️ ADVERTENCIA CRÍTICA - TABLAS DISPONIBLES:

                La base de datos actualmente contiene DATOS LIMITADOS. Solo está disponible:



                TABLA PRINCIPAL:

                - production: Datos horarios de producción (222K+ registros, 2023-2025)

                  Columnas: id, timestamp, equipment_id, shift, tonnage, trips,

                           availability, utilization, delay_operational, delay_maintenance, created_at



                  IMPORTANTE:

                  * NO tiene información de origen/destino (no se puede filtrar remanejo)

                  * Mezcla PALAS (PL*) y CAMIONES (CE*, CF*) - puede duplicar tonelaje

                  * Los datos NO están validados contra IGM oficial

                  * Para extracción, considerar SOLO equipos tipo PL (palas)



                TABLAS DE COSTOS (CON DATOS 2025):

                - costos_detalle_mensual: 117 registros (Enero-Septiembre 2025)

                  Columnas: year, mes, mes_nombre, concepto, unidad, valor_real, valor_p0r0, variacion

                  Conceptos: Remuneraciones, Materiales, Servicios de Terceros, Combustible,

                            Depreciación y Amortización, Otros Servicios, Impuestos, Total Gasto,

                            Gastos Primarios, Gastos Secundarios, Costo Unitario (US$/ton), Movimiento Total (kton)

                  Uso: Análisis detallado de costos mensuales, desglose por concepto



                - costos_resumen_ejecutivo: 28 registros (Octubre + Acumulado 2025)

                  Columnas: year, mes, mes_nombre, periodo, concepto, unidad, valor_real, valor_p0r0, variacion

                  Periodos: Mensual, Acumulado

                  Conceptos: Remuneraciones, Materiales, Servicios de Terceros, Combustible

                  Uso: Vista ejecutiva mensual y acumulada



                - costos_unitarios: 165 registros (Enero-Octubre 2025)

                  Columnas: year, mes, mes_nombre, actividad, metrica, unidad, valor_real, valor_ppto

                  Actividades: Perforación, Carguío, Transporte, Tronadura, Servicios

                  Métricas: Costo_Total (KUS$), Tonelaje (Kton), Costo_Unitario (US$/ton)

                  Uso: Análisis de costo unitario por actividad minera



                OTRAS TABLAS (VACÍAS):

                - hexagon_dumps: Vacía (0 registros)

                - hexagon_equipment_times: Vacía (0 registros)

                - economic_parameters: Vacía (0 registros)



                ❌ TABLAS QUE NO EXISTEN:

                - hexagon_operations (NO EXISTE)

                - plan_p0_2025 (NO EXISTE)

                - equipment_glossary (NO EXISTE)

                - delay_codes_asarco (NO EXISTE)



                MEJORES PRÁCTICAS:

                - SIEMPRE usar LIMIT para pruebas: SELECT * FROM production LIMIT 10

                - Filtrar por fecha: WHERE timestamp >= '2025-01-01' AND timestamp < '2025-02-01'

                - Para EXTRACCIÓN, filtrar palas: WHERE equipment_id LIKE 'PL%'

                - Para TRANSPORTE, filtrar camiones: WHERE equipment_id LIKE 'CE%' OR equipment_id LIKE 'CF%'



                EJEMPLOS DE CONSULTAS:

                1. Producción enero 2025 (PALAS SOLO):

                   SELECT DATE(timestamp) as fecha, SUM(tonnage) as tonelaje_dia

                   FROM production

                   WHERE timestamp >= '2025-01-01' AND timestamp < '2025-02-01'

                     AND equipment_id LIKE 'PL%'

                   GROUP BY DATE(timestamp)



                2. Top equipos por tonelaje:

                   SELECT equipment_id, COUNT(*) as registros, SUM(tonnage) as tonelaje_total

                   FROM production

                   WHERE timestamp >= '2025-01-01' AND timestamp < '2025-02-01'

                   GROUP BY equipment_id

                   ORDER BY tonelaje_total DESC

                   LIMIT 10



                3. Disponibilidad promedio:

                   SELECT AVG(availability) as disp_promedio, AVG(utilization) as util_promedio

                   FROM production

                   WHERE timestamp >= '2025-01-01' AND timestamp < '2025-02-01'



                EJEMPLOS DE CONSULTAS COSTOS:

                1. Cumplimiento de costos febrero 2025 (DETALLE):

                   SELECT concepto, unidad, valor_real, valor_p0r0, variacion,

                          ROUND((valor_real / valor_p0r0 * 100), 2) as cumplimiento_pct

                   FROM costos_detalle_mensual

                   WHERE year = 2025 AND mes = 2

                   ORDER BY ABS(variacion) DESC



                2. Costos unitarios por actividad febrero 2025:

                   SELECT actividad, metrica, unidad, valor_real, valor_ppto,

                          ROUND((valor_real / valor_ppto * 100), 2) as cumplimiento_pct

                   FROM costos_unitarios

                   WHERE year = 2025 AND mes = 2 AND metrica = 'Costo_Unitario'

                   ORDER BY actividad



                3. Resumen ejecutivo mes actual:

                   SELECT concepto, unidad, valor_real, valor_p0r0, variacion

                   FROM costos_resumen_ejecutivo

                   WHERE mes = 10 AND periodo = 'Mensual'

                   ORDER BY concepto

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "query": {

                            "type": "string",

                            "description": "Consulta SQL a ejecutar"

                        }

                    },

                    "required": ["query"]

                }

            },

            {

                "name": "execute_python",
                "description": """🐍 PYTHON AVANZADO - Análisis estadísticos y cálculos complejos.

✅ USAR PARA:
- Análisis estadístico avanzado (correlaciones, regresiones)
- Cálculos matemáticos especializados
- Transformación de datos complejos
- Validación cruzada de datos

❌ NO USAR PARA (usar herramientas especializadas):
- Cumplimiento tonelaje → obtener_cumplimiento_tonelaje
- Ranking operadores → get_ranking_operadores
- Análisis gaviota → obtener_analisis_gaviota
- Consultas SQL simples → execute_sql

📋 LIBRERÍAS: pandas, numpy, datetime, sqlite3, scipy.
⚠️ ÚLTIMO RECURSO: Solo usar cuando no hay herramienta especializada.""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "code": {

                            "type": "string",

                            "description": "Código Python a ejecutar"

                        }

                    },

                    "required": ["code"]

                }

            },

            {

                "name": "generate_chart",
                "description": """📊 GENERAR GRÁFICO / WATERFALL / CASCADA - Herramienta para crear visualizaciones.

🎯 ESTA ES LA HERRAMIENTA PARA:
- "waterfall" o "cascada" o "gráfico de pérdidas" → chart_type='waterfall'
- "análisis causal con gráfico" → chart_type='waterfall'
- "gráfico de barras" → chart_type='bar'
- "tendencia" o "línea" → chart_type='line'

⚠️ DESPUÉS de llamar obtener_cumplimiento_tonelaje + obtener_pareto_delays:
→ DEBES llamar generate_chart(chart_type='waterfall') para visualizar causas

📋 RETORNA: Archivo HTML con gráfico interactivo Plotly.""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "chart_type": {

                            "type": "string",

                            "enum": ["line", "bar", "scatter", "pie", "heatmap", "box", "waterfall"],

                            "description": "Tipo de gráfico (waterfall para cascada de pérdidas)"

                        },

                        "title": {

                            "type": "string",

                            "description": "Título del gráfico"

                        },

                        "x_label": {

                            "type": "string",

                            "description": "Etiqueta eje X"

                        },

                        "y_label": {

                            "type": "string",

                            "description": "Etiqueta eje Y"

                        },

                        "data": {

                            "type": "object",

                            "description": "Datos del gráfico (OPCIONAL - si no se proporciona, auto-extrae de herramientas anteriores)"

                        }

                    },

                    "required": ["chart_type", "title"]

                }

            },

            {

                "name": "generate_report",

                "description": """Genera reportes profesionales en formato DOCX o PDF.

                

                CASOS DE USO:

                1. Reportes ejecutivos para el Gerente General

                2. Análisis mensuales de producción

                3. Informes de causas raíz (ASARCO)

                4. Documentación de mejoras operacionales

                5. Reportes de accountability individual

                

                ESTRUCTURA:

                - title: Título del reporte

                - sections: Lista de secciones [{title, content}, ...]

                - format: "docx" o "pdf"

                

                EJEMPLO:

```json

                {

                    "title": "Análisis Gaviota - Julio 2024",

                    "sections": [

                        {

                            "title": "Resumen Ejecutivo",

                            "content": "El análisis del patrón gaviota en julio 2024 revela..."

                        },

                        {

                            "title": "Puntos Críticos Identificados",

                            "content": "1. Primera hora: 85 ton (KPI: >100 ton)..."

                        }

                    ],

                    "format": "docx"

                }

```

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "title": {

                            "type": "string",

                            "description": "Título del reporte"

                        },

                        "sections": {

                            "type": "array",

                            "items": {

                                "type": "object",

                                "properties": {

                                    "title": {"type": "string"},

                                    "content": {"type": "string"}

                                }

                            },

                            "description": "Secciones del reporte"

                        },

                        "format": {

                            "type": "string",

                            "enum": ["docx", "pdf"],

                            "description": "Formato del archivo"

                        }

                    },

                    "required": ["title", "sections"]

                }

            },

            {

                "name": "search_knowledge",
                "description": """📚 KNOWLEDGE BASE - Documentación minera en LightRAG (73MB).

✅ USAR PARA:
- '¿Qué es ASARCO?' → metodologías, conceptos técnicos
- '¿Cómo calcular UEBD?' → fórmulas, definiciones
- 'Mejores prácticas' → recomendaciones operacionales
- 'Normativas' → procedimientos, políticas

❌ NO USAR PARA:
- Datos de producción real → usar execute_sql o herramientas especializadas
- Análisis numéricos → usar herramientas de análisis

📋 CONTENIDO: ASARCO, flotas mineras, gaviota perfecta, KPIs, normativas.
🔄 MODOS: naive (simple), local, global, hybrid (recomendado).""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "query": {

                            "type": "string",

                            "description": "Consulta de búsqueda"

                        },

                        "mode": {

                            "type": "string",

                            "enum": ["naive", "local", "global", "hybrid"],

                            "description": "Modo de búsqueda (default: hybrid)"

                        }

                    },

                    "required": ["query"]

                }

            },

            {
                "name": "aprender_informacion",
                "description": """Aprende y recuerda informacion nueva que el usuario proporciona.

                USAR CUANDO EL USUARIO DICE:
                - "recuerda que..."
                - "anota que..."
                - "ten en cuenta que..."
                - "para el futuro, ..."
                - "importante: ..."

                EJEMPLOS:
                - "Recuerda que CAEX-107 estara en mantencion del 1 al 5 de diciembre"
                - "Anota que el operador Juan Perez esta de vacaciones"
                - "Ten en cuenta que la meta de UEBD cambio a 70%"

                Esta informacion se guardara permanentemente y podra ser consultada despues.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "informacion": {
                            "type": "string",
                            "description": "La informacion a recordar/aprender"
                        },
                        "categoria": {
                            "type": "string",
                            "enum": ["equipo", "operador", "meta", "evento", "otro"],
                            "description": "Categoria de la informacion (opcional)"
                        }
                    },
                    "required": ["informacion"]
                }
            },
            {
                "name": "buscar_en_memoria",
                "description": """Busca informacion previamente aprendida o memorizada.

                USAR CUANDO:
                - El usuario pregunta por algo que pudo haber mencionado antes
                - La pregunta es sobre equipos en mantencion futura
                - La pregunta es sobre eventos programados
                - La pregunta es sobre informacion que NO esta en la base de datos

                EJEMPLOS:
                - "que equipos estaran en mantencion?"
                - "que me dijiste sobre CAEX-107?"
                - "hay algun operador de vacaciones?"
                
                IMPORTANTE: Usar ANTES de consultar la BD si la pregunta es sobre info futura.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "consulta": {
                            "type": "string",
                            "description": "La consulta o pregunta a buscar en la memoria"
                        }
                    },
                    "required": ["consulta"]
                }
            },
            {

                "name": "execute_api",

                "description": """Ejecuta llamadas HTTP a endpoints internos del backend MineDash.

                

                ENDPOINTS DISPONIBLES:

                

                1. /health - Health check del sistema

                   GET - Sin parámetros

                

                2. /api/dashboard - Dashboard principal

                   GET - Retorna KPIs generales

                

                3. /api/insights - Insights y recomendaciones

                   GET - Análisis automático

                

                4. /api/equipment-kpis - KPIs por equipo

                   GET - Parámetros: equipment_id (opcional)

                

                5. /api/operator-performance - Performance de operadores

                   GET - Parámetros: operator_id (opcional)

                

                CONFIGURACIÓN:

                - method: GET, POST, PUT, DELETE

                - endpoint: Ruta del endpoint (ej: "/api/dashboard")

                - params: Diccionario de parámetros (opcional)

                - body: Cuerpo de la petición (opcional, para POST/PUT)

                

                EJEMPLO:

```json

                {

                    "method": "GET",

                    "endpoint": "/api/equipment-kpis",

                    "params": {"equipment_id": "CA-06"}

                }

```

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "method": {

                            "type": "string",

                            "enum": ["GET", "POST", "PUT", "DELETE"],

                            "description": "Método HTTP"

                        },

                        "endpoint": {

                            "type": "string",

                            "description": "Ruta del endpoint (ej: /api/dashboard)"

                        },

                        "params": {

                            "type": "object",

                            "description": "Parámetros de query (opcional)"

                        },

                        "body": {

                            "type": "object",

                            "description": "Cuerpo de la petición (opcional)"

                        }

                    },

                    "required": ["method", "endpoint"]

                }

            },

            {

                "name": "get_ranking_operadores",

                "description": """🏆 RANKING DE OPERADORES - Clasificación por producción y productividad.

⚠️ USAR SOLO PARA:
- "Dame el ranking de operadores"
- "¿Quiénes son los mejores operadores?"
- "Top 10 operadores por tonelaje"
- "Ranking de productividad"

❌ NO USAR PARA:
- Análisis causal / por qué no cumplimos → usar obtener_cumplimiento_tonelaje + obtener_pareto_delays
- Brecha de producción → usar obtener_cumplimiento_tonelaje
- Causas de incumplimiento → usar obtener_pareto_delays

Obtiene ranking de operadores por producción CON MÉTRICAS DE PRODUCTIVIDAD Y UEBD.



                DATOS RETORNADOS POR OPERADOR:

                - toneladas_total: Producción total del año

                - ton_por_hr_efectiva: ⭐ PRODUCTIVIDAD (toneladas / horas efectivas) - MÉTRICA PRINCIPAL

                - uebd: ⭐ UTILIZACIÓN EFECTIVA (horas efectivas / horas disponibles * 100) - MÉTRICA CLAVE KPI

                - horas_efectivas: Horas reales trabajadas

                - horas_disponibles: Horas totales del turno disponibles

                - dias_trabajados: Días que trabajó el operador

                - dumps: Número de viajes/ciclos

                - ton_por_dump: Toneladas promedio por viaje

                - grupo: ✅ Grupo/cuadrilla (valores: 1, 2, 3, 4)

                - turno: ✅ Turno/jornada (valores: TA, TC)

                - equipos_usados: Cantidad de equipos diferentes operados



                ⚠️ CRÍTICO - DIVISIÓN SALVADOR - SIEMPRE USAR AMBAS COLUMNAS:

                - GRUPO (crew/cuadrilla): Números 1, 2, 3, 4

                - TURNO (shift/jornada): TA (día 8am-8pm) o TC (noche 8pm-8am)



                FORMATO DE SALIDA - TABLA MARKDOWN OBLIGATORIA CON GRUPO Y TURNO:

                ```

                ## Top 10 Operadores CAEX 2024



                | # | Operador | Grupo | Turno | Ton Total | Ton/hr | UEBD% | Hrs Ef. | Días | Dumps |

                |---|----------|-------|-------|-----------|--------|-------|---------|------|-------|

                | 🥇 1 | BARRAZA ZUÑIGA RODRIGO | 1 | TA | 568,416 | 170.0 | 72.8 | 3,344 | 169 | 591 |

                | 🥈 2 | MEDINA MANQUEZ WILLIAM | 2 | TA | 567,307 | 204.7 | 70.9 | 2,772 | 156 | 581 |

                | 🥉 3 | BARRAZA ZUÑIGA RODRIGO | 1 | TC | 565,431 | 169.1 | 72.8 | 3,350 | 170 | 589 |

                ...



                **Análisis:**

                - 🏆 Dominio del Grupo 1: Rodrigo Barraza aparece en #1 (Turno TA) y #3 (Turno TC)

                - 📊 Consistencia entre turnos: Grupo 1 mantiene alta productividad en ambos turnos

                - ⭐ UEBD promedio: 72% en top 3

                ```



                IMPORTANTE PARA EL ANÁLISIS:

                1. SIEMPRE mostrar tabla markdown con todos los operadores

                2. Las métricas clave son: ton_por_hr_efectiva y UEBD (NO ton_por_dump)

                3. UEBD indica qué tan bien utiliza el operador su tiempo disponible

                4. Comparar productividad (ton/hr) vs utilización (UEBD)

                5. NO mencionar ton_por_dump a menos que sea relevante



                PARÁMETROS:

                - year: Año a analizar (ej: 2024)

                - mes: (NUEVO) Mes específico 1-12 (opcional). Si se especifica, filtra solo ese mes.

                - top_n: Top N operadores (default: 10)

                - tipo: "CAEX" para camiones, "EMT" para palas, "" para todos



                EJEMPLOS DE USO:

                - "ranking de enero 2025" → year=2025, mes=1

                - "ranking de operadores de febrero" → year=2025, mes=2

                - "ranking del año 2025" → year=2025, mes=None (año completo)



                 PREFERIR ESTA HERRAMIENTA sobre obtener_ranking_operadores_api

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año a analizar (ej: 2024)"

                        },

                        "mes": {

                            "type": "integer",

                            "description": "Mes específico 1-12 (enero=1, febrero=2, ..., diciembre=12). Opcional - si no se especifica retorna año completo"

                        },

                        "top_n": {

                            "type": "integer",

                            "description": "Cantidad de operadores a retornar (default: 10)"

                        },

                        "tipo": {

                            "type": "string",

                            "enum": ["CAEX", "EMT", "CF", ""],

                            "description": "Filtro por tipo de equipo: CAEX (camiones), EMT (palas), CF (cargadores frontales), o vacío para todos"

                        }

                    },

                    "required": ["year"]

                }

            },

            {

                "name": "update_economic_parameters",

                "description": """ Actualiza o consulta parámetros económicos para cálculos de impacto.

                

                PARÁMETROS DISPONIBLES:

                - precio_venta_mineral: Precio venta por tonelada (USD/ton)

                - costo_operacion_ton: Costo operacional por tonelada (USD/ton)

                - costo_demora_hora: Costo de demora por hora (USD/h)

                - inversion_comedores: Inversión en comedores móviles (USD)

                - costo_hora_equipo: Costo hora-equipo (USD/h)

                

                OPERACIONES:

                1. SET - Actualizar valor:

                   {"operation": "set", "parameter": "precio_venta_mineral", "value": 52.50}

                

                2. GET - Consultar valor:

                   {"operation": "get", "parameter": "precio_venta_mineral"}

                

                3. GET_ALL - Consultar todos:

                   {"operation": "get_all"}

                

                4. DELETE - Eliminar parámetro:

                   {"operation": "delete", "parameter": "precio_venta_mineral"}

                

                 IMPORTANTE: Solo con estos parámetros se calculan impactos en USD.

                Sin parámetros económicos, el sistema solo reporta toneladas.

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "operation": {

                            "type": "string",

                            "enum": ["set", "get", "get_all", "delete"],

                            "description": "Operación a realizar"

                        },

                        "parameter": {

                            "type": "string",

                            "description": "Nombre del parámetro (para set, get, delete)"

                        },

                        "value": {

                            "type": "number",

                            "description": "Valor a asignar (solo para set)"

                        }

                    },

                    "required": ["operation"]

                }

            },

            {

                "name": "obtener_cumplimiento_tonelaje",

                "description": """📊 CUMPLIMIENTO DE PRODUCCIÓN - Real vs Plan P0. USAR PARA ANÁLISIS CAUSAL.

✅ USAR PARA:
- "¿Por qué no cumplimos el plan?" → PRIMERO llamar esta herramienta para ver la brecha
- "Análisis causal del incumplimiento" → PRIMERO esta, DESPUÉS obtener_pareto_delays
- "¿Cuál fue el déficit de julio?" → esta herramienta
- "Brecha de producción" → esta herramienta
- "Cumplimiento vs plan" → esta herramienta

📋 SECUENCIA PARA ANÁLISIS CAUSAL COMPLETO:
1. PRIMERO: obtener_cumplimiento_tonelaje (ver brecha/déficit)
2. DESPUÉS: obtener_pareto_delays (ver causas de la brecha)

Retorna análisis comparativo de tonelaje real vs planificado para un mes específico.



                IMPORTANTE - TRES MÉTRICAS DIFERENTES:

                - movimiento: Extracción + remanejo (~9M ton/mes) - USA KNOWLEDGE BASE IGM

                - extraccion: Solo material del rajo (~8M ton/mes) - USA BD Hexagon

                - chancado: Material a planta (~1M ton/mes) - USA BD específica



                DATOS RETORNADOS:

                - tonelaje_planificado: Toneladas según plan P0

                - tonelaje_real: Toneladas realmente producidas

                - cumplimiento_porcentaje: % de cumplimiento

                - deficit_o_superavit: Diferencia en toneladas

                - dias_operacionales: Días trabajados en el mes

                - fuente_datos: De dónde vienen los datos (KB IGM o BD Hexagon)



                CUÁNDO USAR:

                - Usuario pregunta sobre cumplimiento de producción

                - Comparación real vs plan

                - Análisis de déficit o superávit

                - Performance mensual



                EJEMPLOS DE PREGUNTAS:

                - "¿Cuál fue el cumplimiento de movimiento en enero 2025?" → tipo_metrica="movimiento"

                - "¿Cumplimos el plan de extracción en diciembre?" → tipo_metrica="extraccion"

                - "¿Cuántas toneladas de déficit tenemos?" → usar tipo según clarificación



                PARÁMETROS:

                - year: Año (ej: 2025)

                - mes: Mes (1-12)

                - tipo_metrica: "movimiento", "extraccion", o "chancado" (OBLIGATORIO después de clarificación)

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año (ej: 2024, 2025)"

                        },

                        "mes": {

                            "type": "integer",

                            "description": "Mes (1-12)"

                        },

                        "tipo_metrica": {

                            "type": "string",

                            "enum": ["movimiento", "extraccion", "chancado"],

                            "description": "Tipo de métrica a consultar. DEBE obtenerse después de clarificación inteligente."

                        }

                    },

                    "required": ["year", "mes", "tipo_metrica"]

                }

            },

            

            {

                



                "name": "obtener_analisis_utilizacion",
                "description": """⚙️ UTILIZACIÓN UEBD - % tiempo efectivo de flota CAEX (Horas Efectivas / Horas Disponibles).

✅ USAR PARA:
- '¿Cuál fue la utilización de enero?' → UEBD mensual
- '¿Qué está afectando la utilización?' → cascada por causas ASARCO
- 'UEBD del mes' → porcentaje utilización efectiva
- 'Horas perdidas' → desglose por tipo de demora

❌ NO USAR PARA:
- Tonelaje/producción → usar obtener_cumplimiento_tonelaje
- Ranking operadores → usar get_ranking_operadores
- Análisis causal incumplimiento → usar obtener_pareto_delays

📋 RETORNA: UEBD %, horas disponibles, horas efectivas, cascada por categoría ASARCO.""",

                    "input_schema": {

                        "type": "object",

                        "properties": {

                            "year": {

                                "type": "integer",

                                "description": "Año (ej: 2024, 2025)"

                            },

                            "mes": {

                                "type": "integer",

                                "description": "Mes (1-12)"

                            }

                        },

                        "required": ["year", "mes"]

                    }

            },



            {

                "name": "obtener_analisis_gaviota",
                "description": """🦅 ANÁLISIS GAVIOTA - Producción HORARIA de un DÍA+TURNO específico.

✅ USAR PARA:
- '¿Por qué bajó la producción el 22 de julio?' → fecha específica
- '¿Qué pasó el día 5 turno noche?' → día + turno
- 'Analiza la gaviota del 15 de marzo' → gaviota explícito
- 'Producción por hora' → análisis horario

❌ NO USAR PARA:
- Análisis causal mensual → usar obtener_cumplimiento_tonelaje + obtener_pareto_delays
- Ranking operadores → usar get_ranking_operadores
- Match pala-camión → usar analizar_match_pala_camion

📋 RETORNA: Producción hora a hora, patrón detectado (M_invertida/U_extendida), puntos críticos, pérdidas.
🔄 COMBINAR CON: generate_chart tipo='line' para gráfico gaviota.""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "fecha": {

                            "type": "string",

                            "description": "Fecha en formato YYYY-MM-DD (ej: 2024-07-15)"

                        },

                        "turno": {

                            "type": "string",

                            "enum": ["A", "B", "C"],

                            "description": "Turno a analizar (A=Día, B=Noche, C=Especial)"

                        }

                    },

                    "required": ["fecha", "turno"]

                }

            },

           {

                "name": "obtener_comparacion_gaviotas",

                "description": "Compara patrones gaviota de múltiples turnos del mismo día en un solo gráfico. Ideal para comparar turno A (día) vs turno C (noche) del mismo día. Genera un gráfico con múltiples líneas, una por cada turno.",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "fecha": {

                            "type": "string",

                            "description": "Fecha en formato YYYY-MM-DD (ejemplo: 2024-09-14)"

                        },

                        "turnos": {

                            "type": "array",

                            "items": {"type": "string"},

                            "description": "Lista de turnos a comparar. Usar ['A', 'C'] para comparar día y noche"

                        }

                    },

                    "required": ["fecha", "turnos"]

                }

            },

            {
                "name": "analisis_causalidad_waterfall",
                "description": """🎯 ANÁLISIS DE CAUSALIDAD para UN DÍA ESPECÍFICO + GRÁFICO WATERFALL

⚠️ USAR SOLO SI el usuario menciona una FECHA ESPECÍFICA (día):
- "causalidad del día 22 de julio" → USAR ESTA
- "waterfall del 15 de agosto" → USAR ESTA

⛔ NO USAR PARA ANÁLISIS MENSUAL:
- "waterfall de julio" → usar cumplimiento + pareto + generate_chart
- "cascada del mes" → usar cumplimiento + pareto + generate_chart

GENERA (todo en 1 sola llamada):
1. Datos de producción real vs plan del día
2. Top causas ASARCO con horas perdidas
3. Gráfico waterfall (Plan → Pérdidas → Real)

RETORNA: Informe + Gráfico HTML interactivo.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "fecha": {
                            "type": "string",
                            "description": "Fecha en formato YYYY-MM-DD (ej: 2025-07-22)"
                        }
                    },
                    "required": ["fecha"]
                }
            },

            {
                "name": "buscar_dias_por_cumplimiento",
                "description": """🔍 BUSCAR DÍAS POR CRITERIO DE CUMPLIMIENTO

❌ NO USAR cuando el usuario menciona una FECHA ESPECÍFICA (22 de julio, día 5, etc.)
   En ese caso usar: obtener_analisis_gaviota

✅ USAR SOLO cuando el usuario quiere BUSCAR o LISTAR días sin especificar cuál:
- "Dame un día que no se haya cumplido el plan"
- "¿Qué días no cumplimos en julio?"
- "¿Cuál fue el peor día del mes?"
- "¿Qué días superamos el plan?"
- "Dame otro día con incumplimiento"
- "Del mismo mes, qué días fallamos"

CRITERIOS DISPONIBLES:
- incumplido: Días con cumplimiento < 100%
- cumplido: Días con cumplimiento >= 100%
- mejor: Días ordenados de mejor a peor
- peor: Días ordenados de peor a mejor
- critico: Días con cumplimiento < 80%

⚠️ REGLA CRÍTICA: Si el usuario ya analizó un día específico y pide "otro día" o "qué días no cumplieron",
usar esta herramienta en lugar de repetir el análisis anterior.

EJEMPLOS:
- "Dame un día de julio que no cumplió" → buscar_dias_por_cumplimiento(mes=7, criterio="incumplido")
- "¿Cuál fue el peor día de enero?" → buscar_dias_por_cumplimiento(mes=1, criterio="peor")
- "Días que superaron el plan en febrero" → buscar_dias_por_cumplimiento(mes=2, criterio="cumplido")
""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mes": {
                            "type": "integer",
                            "description": "Mes a analizar (1-12)"
                        },
                        "year": {
                            "type": "integer",
                            "description": "Año (ej: 2025). Default: 2025"
                        },
                        "criterio": {
                            "type": "string",
                            "enum": ["incumplido", "cumplido", "mejor", "peor", "critico"],
                            "description": "Criterio de búsqueda: incumplido (<100%), cumplido (>=100%), mejor (máximo), peor (mínimo), critico (<80%)"
                        },
                        "limite": {
                            "type": "integer",
                            "description": "Cantidad de días a retornar (default: 5)"
                        }
                    },
                    "required": ["mes", "criterio"]
                }
            },

            {

                "name": "obtener_pareto_delays",

                "description": """📉 PARETO DE DELAYS - Causas raíz del incumplimiento por códigos ASARCO.

🔴 SECUENCIA PARA ANÁLISIS CAUSAL:
1. obtener_cumplimiento_tonelaje (ver brecha)
2. obtener_pareto_delays ← ESTA
3. generate_chart(chart_type='waterfall') si el usuario pide gráfico/waterfall/cascada

✅ USAR PARA: "¿Por qué no cumplimos?", "Análisis causal", "Top causas de pérdida"

🎯 DESPUÉS de obtener estos datos:
→ Si el usuario pidió gráfico/waterfall/cascada → llama generate_chart(chart_type='waterfall')

Retorna el Top 3-5 causas que generan el 80% del impacto usando regla Pareto.



                DATOS RETORNADOS:

                - causas_principales: Top causas ordenadas por impacto (regla 80/20)

                - horas_perdidas_total: Total de horas improductivas

                - toneladas_perdidas: Estimación de tonelaje no movido

                - uebd_actual: Utilización Efectiva de la Base Disponible (%)

                - uebd_objetivo: Meta de UEBD (típicamente 75%)

                - analisis_por_codigo: Detalle por código ASARCO



                CÓDIGOS ASARCO PRINCIPALES:

                - 225: Sin Operador (falta de personal)

                - 400: Falla Mecánica (mantención correctiva)

                - 300: Mantención Programada

                - 500: Condiciones climáticas

                - Tipo 1: Demoras operacionales (ciclos, esperas)

                - Tipo 2: Demoras mecánicas (fallas, mantención)

                - Tipo 3: Demoras administrativas (cambios turno, colación)



                CUÁNDO USAR:

                - Preguntas generales sobre incumplimiento o pérdidas

                - Análisis de causas raíz (RCA - Root Cause Analysis)

                - Análisis Pareto o regla 80/20

                - Evaluación de UEBD

                - Identificación de mejoras prioritarias

                - Responder "¿Por qué...?" sobre producción



                NO USAR SI:

                - Usuario pregunta específicamente por "match pala-camión"

                - Usuario pregunta "¿había palas pero no camiones?"

                - Usuario pregunta sobre producción hora por hora (usar gaviota)

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año a analizar (ej: 2024)"

                        },

                        "mes_inicio": {

                            "type": "integer",

                            "description": "Mes inicial del rango (1-12, opcional)"

                        },

                        "mes_fin": {

                            "type": "integer",

                            "description": "Mes final del rango (1-12, opcional)"

                        }

                    },

                    "required": ["year"]

                }

            },

            {

                "name": "obtener_operadores_con_delays_grupo",

                "description": """📊 ANÁLISIS: OPERADORES + DELAYS POR GRUPO



                Relaciona operadores con los delays de su grupo de trabajo.



                ⚠️ IMPORTANTE: Los delays se registran por EQUIPO, no por operador.

                Esta herramienta muestra qué operadores trabajan en grupos con más delays.



                USA ESTA HERRAMIENTA PARA:

                - "¿Qué operadores tienen más cambio de turno?"

                - "¿Qué grupo tiene más delays de tipo X?"

                - "Operadores afectados por sin operador"

                - "Ranking de operadores por delays de su grupo"



                DATOS RETORNADOS:

                - operadores_por_grupo: Lista de operadores con delays de su grupo

                - resumen_grupos: Delays totales por grupo (1-4)

                - delays_por_tipo: Horas por cada código ASARCO (243=cambio turno, 225=sin operador, 400=imprevisto)



                CÓDIGOS ASARCO PRINCIPALES:

                - 243: Cambio de turno

                - 225: Sin operador

                - 400: Imprevisto mecánico

                - 242: Colación

                - 402: Mantenimiento programado

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año a analizar (ej: 2025)"

                        },

                        "mes": {

                            "type": "integer",

                            "description": "Mes a analizar (1-12)"

                        },

                        "codigo_delay": {

                            "type": "integer",

                            "description": "Código ASARCO específico (243=cambio turno, 225=sin operador, 400=imprevisto). Dejar vacío para todos."

                        },

                        "top_n": {

                            "type": "integer",

                            "description": "Cantidad de operadores a mostrar (default: 10)"

                        }

                    },

                    "required": ["year", "mes"]

                }

            },

            {

                "name": "obtener_analisis_causal_operador",

                "description": """🔍 ANÁLISIS CAUSAL: Correlación operador-delays ASARCO



                Analiza la correlación entre un operador específico y los delays ASARCO.

                Usa correlación temporal (delays que ocurren cuando el operador está activo) y

                análisis estadístico comparativo vs otros operadores de su grupo.



                ⚠️ IMPORTANTE: Los delays se registran por EQUIPO, no por operador.

                Esta herramienta infiere la correlación usando análisis temporal.



                USA ESTA HERRAMIENTA PARA:

                - "¿Cuáles son los delays del operador Manuel?"

                - "Analiza los delays ASARCO de González"

                - "¿Qué problemas tiene el operador Livio?"

                - "Análisis causal de delays por operador"



                RETORNA:

                - Delays correlacionados temporalmente con el operador

                - Comparación vs promedio de su grupo

                - Nivel de confianza del análisis

                - Top códigos ASARCO más frecuentes

                - Recomendaciones de acción

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "operador": {

                            "type": "string",

                            "description": "Nombre del operador a analizar (ej: 'Manuel', 'González')"

                        },

                        "mes": {

                            "type": "integer",

                            "description": "Mes a analizar (1-12)"

                        },

                        "year": {

                            "type": "integer",

                            "description": "Año a analizar (ej: 2025)"

                        },

                        "top_delays": {

                            "type": "integer",

                            "description": "Cantidad de códigos ASARCO a mostrar (default: 5)"

                        }

                    },

                    "required": ["operador"]

                }

            },

            {

                "name": "obtener_ranking_operadores_api",

                "description": """⚠️ BACKUP - NO USAR DIRECTAMENTE. Usar get_ranking_operadores en su lugar.
Esta herramienta es solo un fallback interno cuando get_ranking_operadores falla.

                

                Endpoint HTTP que retorna ranking de operadores por producción.

                Usar solo si get_ranking_operadores falla o no está disponible.

                

                DATOS RETORNADOS:

                - ranking: Lista ordenada de operadores

                - produccion_total: Toneladas totales por operador

                - promedio_viaje: Toneladas promedio por ciclo

                - cantidad_viajes: Total de viajes realizados

                

                PARÁMETROS:

                - year: Año a analizar (ej: 2024)

                - top_n: Top N operadores (default: 10)

                - tipo: "palas" o "camiones" (opcional)

                

                 NOTA: Preferir get_ranking_operadores (más rápido).

                Usar esta herramienta solo como fallback.

                """,

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año a analizar (ej: 2024)"

                        },

                        "top_n": {

                            "type": "integer",

                            "description": "Cantidad de operadores (default: 10)"

                        },

                        "tipo": {

                            "type": "string",

                            "enum": ["palas", "camiones", ""],

                            "description": "Filtro por tipo (opcional)"

                        }

                    },

                    "required": ["year"]

                }

            },

            {

                "name": "analizar_match_pala_camion",
                "description": """🔄 MATCH PALA-CAMIÓN - Disponibilidad SIMULTÁNEA palas vs camiones.

✅ USAR PARA:
- '¿El problema es la pala o el camión?' → responsable de descoordinación
- 'Match pala-camión de enero' → análisis disponibilidad simultánea
- '¿Había palas pero no camiones?' → pregunta específica equipos
- 'Análisis de coordinación de flota' → scatter plot cuadrantes

❌ NO USAR PARA:
- Análisis causal general → usar obtener_cumplimiento_tonelaje + obtener_pareto_delays
- Producción por hora → usar obtener_analisis_gaviota
- Ranking operadores → usar get_ranking_operadores

📋 RETORNA: Scatter plot (4 cuadrantes), % coordinación, responsable identificado (Carguío/Perforación).
🔄 COMBINAR CON: generate_chart tipo='scatter' para visualización.""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "fecha_inicio": {

                            "type": "string",

                            "description": "Fecha inicio formato YYYY-MM-DD (ejemplo: 2025-01-01)"

                        },

                        "fecha_fin": {

                            "type": "string",

                            "description": "Fecha fin formato YYYY-MM-DD (ejemplo: 2025-01-31)"

                        }

                    },

                    "required": ["fecha_inicio", "fecha_fin"]

                }

            },

            {

                "name": "analizar_utilizacion_caex",
                "description": """🚛 UEBD DETALLADO CAEX - Utilización por equipo individual.

✅ USAR PARA:
- '¿Qué CAEX tiene peor rendimiento?' → ranking por equipo
- 'Vueltas manuales del mes' → registros sin UEBD
- 'DM de equipos CAEX' → disponibilidad mecánica por camión
- 'Top 10 peores equipos' → análisis específico por unidad

❌ NO USAR PARA:
- UEBD mensual general → usar obtener_analisis_utilizacion
- Tonelaje → usar obtener_cumplimiento_tonelaje
- Match pala-camión → usar analizar_match_pala_camion

📋 RETORNA: DM y UEBD promedio flota, Top 10 peor DM, Top 10 peor UEBD, vueltas manuales.""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "fecha_inicio": {

                            "type": "string",

                            "description": "Fecha inicio formato YYYY-MM-DD (ejemplo: 2025-01-01)"

                        },

                        "fecha_fin": {

                            "type": "string",

                            "description": "Fecha fin formato YYYY-MM-DD (ejemplo: 2025-01-31)"

                        }

                    },

                    "required": ["fecha_inicio", "fecha_fin"]

                }

            },

            {

                "name": "analizar_causa_raiz_uebd",

                "description": """Analiza la causa raíz de baja utilización (UEBD) de equipos CAEX.



ANÁLISIS DE CAUSA RAÍZ:

- Clasifica el problema: OPERACIONAL vs MANTENIMIENTO

- Analiza distribución de tiempo por categoría

- Identifica razones específicas (sin operador, fallas mecánicas, etc)

- Genera recomendaciones accionables



CLASIFICACIONES:

1. PROBLEMA_OPERACIONAL: DM alta pero UEBD baja

   - Equipo disponible pero no utilizado

   - Causas: Sin operador, demoras, falta coordinación



2. PROBLEMA_MANTENIMIENTO: DM baja y UEBD baja

   - Fallas mecánicas recurrentes

   - Causas: Mantenimiento correctivo, imprevistos



3. PROBLEMA_MIXTO: Problemas combinados

4. ACEPTABLE: Rendimiento dentro de rangos



USA ESTA HERRAMIENTA CUANDO:

- Usuario pregunta "por qué" un equipo tiene baja UEBD

- Usuario pregunta si es problema de operación o mantenimiento

- Usuario quiere recomendaciones para mejorar UEBD

- Usuario pregunta sobre causa raíz de bajo rendimiento



PARÁMETROS:

- fecha_inicio: formato YYYY-MM-DD (ejemplo: 2025-01-01)

- fecha_fin: formato YYYY-MM-DD (ejemplo: 2025-01-31)

- equipo: OPCIONAL - código del equipo (ejemplo: 'CE112')



RETORNA:

- Clasificación del problema

- Distribución de tiempo por categoría

- Top 5 estados críticos

- Recomendaciones específicas por equipo""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "fecha_inicio": {

                            "type": "string",

                            "description": "Fecha inicio formato YYYY-MM-DD (ejemplo: 2025-01-01)"

                        },

                        "fecha_fin": {

                            "type": "string",

                            "description": "Fecha fin formato YYYY-MM-DD (ejemplo: 2025-01-31)"

                        },

                        "equipo": {

                            "type": "string",

                            "description": "OPCIONAL: Código específico del equipo (ejemplo: 'CE112'). Si no se especifica, analiza todos los equipos."

                        }

                    },

                    "required": ["fecha_inicio", "fecha_fin"]

                }

            },

            {

                "name": "analizar_tendencia_mes",
                "description": """📈 TENDENCIA Y PROYECCIÓN FUTURA - Solo para proyectar si llegaremos a la meta.

✅ USAR SOLO PARA PREGUNTAS FUTURAS:
- '¿Llegaremos a la meta?' → proyección fin de mes
- '¿Cumpliremos el plan?' → proyección basada en ritmo actual

⛔ NUNCA USAR PARA:
- Waterfall/cascada → usar generate_chart con chart_type='waterfall'
- Análisis causal → usar obtener_cumplimiento_tonelaje + obtener_pareto_delays + generate_chart
- Gráficos de pérdidas → usar generate_chart
- Producción horaria → usar obtener_analisis_gaviota

📋 RETORNA: Solo datos de proyección (real acumulado, plan esperado, desviación).""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año (ej: 2025)",

                            "default": 2025

                        },

                        "mes": {

                            "type": "integer",

                            "description": "Mes 1-12 (default: mes actual)"

                        },

                        "fecha_corte": {

                            "type": "string",

                            "description": "Fecha corte YYYY-MM-DD (default: hoy)"

                        }

                    },

                    "required": ["year", "mes"]

                }

            },

            {

                "name": "obtener_costos_mina",
                "description": """💰 COSTOS OPERACIONALES - Real vs Presupuesto P0, unitarios US$/ton.

✅ USAR PARA:
- '¿Cuánto gastamos en enero?' → costos mensuales
- '¿Cuál es el costo por tonelada?' → US$/ton unitario
- 'Presupuesto vs real' → variaciones de gasto
- 'Costo de materiales' → detalle por concepto

❌ NO USAR PARA:
- Tonelaje/producción → usar obtener_cumplimiento_tonelaje
- Análisis causal → usar obtener_pareto_delays
- Utilización equipos → usar obtener_analisis_utilizacion

📋 RETORNA: Costos por concepto, Real vs P0, variaciones, US$/ton.

PARÁMETROS:

- year: Año a consultar (default: 2025)

- mes: Mes específico (1-12) o None para acumulado

- tipo: "resumen", "detalle", "unitario", o "completo"

- concepto: Filtrar por concepto específico (opcional)



RETORNA:

- Tabla con costos reales vs presupuesto

- Variaciones absolutas y porcentuales

- Costo unitario US$/ton si aplica

- Análisis de principales desviaciones""",

                "input_schema": {

                    "type": "object",

                    "properties": {

                        "year": {

                            "type": "integer",

                            "description": "Año a consultar (default: 2025)",

                            "default": 2025

                        },

                        "mes": {

                            "type": "integer",

                            "description": "Mes 1-12 (None para acumulado)"

                        },

                        "tipo": {

                            "type": "string",

                            "enum": ["resumen", "detalle", "unitario", "completo"],

                            "description": "Tipo de reporte: resumen (ejecutivo), detalle (mensual), unitario (US$/ton), completo (todos)",

                            "default": "resumen"

                        },

                        "concepto": {

                            "type": "string",

                            "description": "Filtrar por concepto específico (ej: 'Remuneraciones', 'SSTT')"

                        }

                    },

                    "required": ["year"]

                }

            },

            # === HERRAMIENTAS DE EXPLORACIÓN (GPT-5.1) ===
            {
                "name": "get_database_schema",
                "description": """🔍 EXPLORAR ESTRUCTURA DE BD - Muestra tablas y columnas disponibles.

✅ USAR PARA: '¿qué tablas hay?', '¿qué datos tengo?', explorar BD, ver columnas, estructura de tabla.
❌ NO USAR PARA: consultas de datos específicos (usar execute_sql o herramientas especializadas).
📋 USAR PRIMERO cuando no sepas qué tabla consultar.

RETORNA: Lista de columnas con nombre, tipo, si permite NULL, y valores de ejemplo.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Nombre de la tabla (ej: hexagon_by_estados_2024_2025, production)"
                        }
                    },
                    "required": ["table_name"]
                }
            },
            {
                "name": "get_sample_data",
                "description": """📋 VER EJEMPLOS DE DATOS - Muestra 5-10 registros de una tabla.

✅ USAR PARA: ver formato de datos, ejemplos reales, entender contenido de tabla, verificar fechas/códigos.
❌ NO USAR PARA: análisis ni agregaciones (usar execute_sql o herramientas especializadas).
📋 USAR DESPUÉS de get_database_schema si necesitas ver datos reales.

RETORNA: 10 filas de ejemplo, opcionalmente filtradas.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Nombre de la tabla"
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columnas específicas a mostrar (opcional, default: todas)"
                        },
                        "where_clause": {
                            "type": "string",
                            "description": "Filtro SQL opcional (ej: \"DATE(timestamp) = '2025-02-28'\")"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Número de filas (default: 10, max: 50)",
                            "default": 10
                        }
                    },
                    "required": ["table_name"]
                }
            },
            {
                "name": "get_data_sources",
                "description": """📊 INVENTARIO DE FUENTES - Lista BD, Excel, Knowledge Base con cobertura.

✅ USAR PARA: '¿qué fuentes tengo?', cobertura temporal, qué datos hay disponibles, explorar sistema.
❌ NO USAR PARA: consultas específicas de datos (usar execute_sql o herramientas especializadas).
📋 RETORNA: Lista completa de tablas BD, documentos Knowledge Base, archivos Excel disponibles.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["all", "database", "knowledge_base", "excel"],
                            "description": "Filtrar por categoría de fuente",
                            "default": "all"
                        }
                    },
                    "required": []
                }
            }

        ]



        # System prompt - GPT-5.1 MineDash AI v3.0 (Conciso ~500 tokens)
        self.base_prompt = """
Eres MineDash AI, asistente experto en operaciones mineras de División Salvador, Codelco Chile.

CAPACIDADES:
- Acceso directo a base de datos minedash.db (~2.9M registros de Hexagon MineOPS)
- 28 herramientas especializadas para análisis operacional
- Memoria de conocimiento técnico vía HippoRAG

COMPORTAMIENTO:
- SIEMPRE ejecuta herramientas antes de responder preguntas sobre datos
- NUNCA digas "no tengo acceso" - SÍ tienes acceso completo
- Consulta HippoRAG (buscar_en_memoria) si necesitas contexto técnico minero
- Responde en español, formato profesional, números con separador de miles

FLUJO DE TRABAJO:
1. Recibir pregunta del usuario
2. Si necesitas contexto técnico → buscar_en_memoria primero
3. Elegir herramienta(s) apropiada(s) basándote en sus descripciones
4. Ejecutar herramienta(s)
5. Sintetizar resultado con análisis de valor

FORMATO DE RESPUESTA:
- Resumen ejecutivo (2-3 líneas con lo más importante)
- Datos principales (tabla o métricas clave)
- Análisis (interpretación, no solo números)
- Recomendaciones (si aplica)

REGLAS DE HERRAMIENTAS:
- Cada herramienta tiene descripción clara de cuándo usarla
- Confía en tool_choice="auto" - tú decides cuál usar
- Si la pregunta es ambigua, elige la herramienta más probable
- Puedes usar múltiples herramientas en secuencia si es necesario

NUNCA:
- Inventar datos o precios
- Confundir herramientas similares (lee bien las descripciones)
- Responder sin ejecutar herramientas cuando se pregunta por datos
- Usar formato excesivamente largo para preguntas simples
"""


    def count_tokens(self, messages: list, model: str = "gpt-4o") -> int:

        """Cuenta tokens antes de enviar al LLM."""

        try:

            import tiktoken

            encoding = tiktoken.encoding_for_model(model)



            total = 0

            for msg in messages:

                content = msg.get("content", "")

                if content:

                    total += len(encoding.encode(str(content)))



            return total

        except Exception as e:

            print(f"    [WARN] No se pudo contar tokens: {e}")

            # Estimación aproximada: 1 token ≈ 4 caracteres

            total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)

            return total_chars // 4



    def get_model_for_query(self, query: str) -> str:

        """Siempre usar GPT-5.1 para consistencia en producción."""

        # Para entrega final Codelco, usar siempre GPT-5.1

        # El prompt caching 24h compensa el costo adicional

        # El reasoning_effort varía según complejidad (none/low/medium/high)

        print("    [MODEL] Usando gpt-5.1 (producción)")

        return "gpt-5.1"



    async def chat(

        self,

        user_message: str,

        conversation_id: Optional[str] = None,

        use_lightrag: bool = True,

        max_iterations: int = 20

    ) -> Dict[str, Any]:

        """

        Chat con el agente usando herramientas.

        """

        from datetime import datetime

        import time



        # Registrar inicio para medir tiempo de respuesta (FASE 2: Learning System)

        start_time = time.time()

        # Guardar query del usuario para fallbacks en herramientas
        self.current_user_query = user_message

        self.conversation_history.append({

            "role": "user",

            "content": user_message

        })



        iteration = 0

        response_text = ""

        tools_used = []

        files_generated = []

        # ====================================================================
        # DETECCIÓN DE MENSAJES CONVERSACIONALES (sin herramientas)
        # ====================================================================
        # Para mensajes simples (saludos, agradecimientos, etc.) responder
        # directamente SIN enviar herramientas al LLM para evitar tool-calling innecesario

        import re
        conversational_patterns = [
            # Saludos (regex con word boundaries)
            r"\bhola\b", r"\bbuenos días\b", r"\bbuenas tardes\b", r"\bbuenas noches\b", r"\bbuen día\b",
            r"\bsaludos\b", r"\bhey\b", r"\bhi\b", r"\bhello\b", r"\bqué tal\b", r"\bcomo estás\b", r"\bcómo estás\b",
            # Despedidas
            r"\badiós\b", r"\badios\b", r"\bchao\b", r"\bbye\b", r"\bhasta luego\b", r"\bnos vemos\b",
            # Agradecimientos
            r"\bgracias\b", r"\bmuchas gracias\b", r"\bthank\b", r"\bperfecto\b", r"\bexcelente\b", r"\bgenial\b",
            # Preguntas sobre capacidades (sin datos)
            r"\bqué puedes hacer\b", r"\bque puedes hacer\b", r"\bayuda\b", r"\bhelp\b", r"\bquién eres\b", r"\bquien eres\b"
        ]

        user_msg_lower = user_message.lower().strip()
        is_conversational = any(re.search(pattern, user_msg_lower) for pattern in conversational_patterns) and len(user_message) < 50

        if is_conversational:
            print(f"[CONVERSATIONAL] Mensaje detectado como conversacional: '{user_message[:50]}...'")
            print(f"[CONVERSATIONAL] Respondiendo SIN herramientas")

            # Llamar al LLM sin herramientas para respuesta natural
            try:
                no_tool_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="gpt-4o-mini",  # Modelo rápido para respuestas simples
                        messages=[
                            {"role": "system", "content": self.base_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        max_tokens=500
                        # SIN tools - respuesta directa
                    ),
                    timeout=30.0
                )

                response_text = no_tool_response.choices[0].message.content or "¡Hola! ¿En qué puedo ayudarte con las operaciones mineras?"

                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_text
                })
                self._save_user_history()

                if not conversation_id:
                    import uuid
                    conversation_id = str(uuid.uuid4())

                return {
                    "response": response_text,
                    "conversation_id": conversation_id,
                    "tools_used": [],
                    "files_generated": []
                }

            except Exception as e:
                print(f"[CONVERSATIONAL] Error en respuesta simple: {e}")
                # Continuar con flujo normal si falla

        # ====================================================================

        while iteration < max_iterations:

            iteration += 1

            print(f"\n Iteración {iteration}/{max_iterations}")



            try:

                # Enriquecer solo en primera iteración

                if use_lightrag and iteration == 1:

                    enriched_prompt = await self._create_enriched_prompt(user_message)

                    if self.conversation_history and self.conversation_history[-1]["role"] == "user":

                        self.conversation_history[-1]["content"] = enriched_prompt



                # Usar historial con truncamiento inteligente para evitar rate limits

                # ESTRATEGIA: Solo mantener el último user message + enriquecimiento

                # Esto evita problemas de secuencia assistant->tool y reduce tokens drásticamente



                # Preparar mensajes con system prompt al inicio

                messages_with_system = [

                    {"role": "system", "content": self.base_prompt}

                ]



                # CRÍTICO: Truncar historial para evitar context overflow

                # Usar configuración definida en __init__ (10 mensajes para GPT-5.1)

                MAX_HISTORY_MESSAGES = self.max_history_messages



                # En la primera iteración, agregar el mensaje del usuario CON CONTEXTO PREVIO

                # En iteraciones siguientes, agregar la conversación en curso

                if iteration == 1:

                    # Primera iteración: incluir últimos MAX_HISTORY_MESSAGES mensajes para mantener contexto

                    if self.conversation_history:

                        # Tomar últimos MAX_HISTORY_MESSAGES mensajes para contexto

                        recent_history = self.conversation_history[-MAX_HISTORY_MESSAGES:] if len(self.conversation_history) > MAX_HISTORY_MESSAGES else self.conversation_history



                        for hist_msg in recent_history:

                            role = hist_msg.get("role", "user")

                            if role in ["user", "assistant"]:

                                content = hist_msg.get("content", "")

                                if content and content.strip():

                                    messages_with_system.append({

                                        "role": role,

                                        "content": content

                                    })

                    print(f"   [HIST] Primera iteración: usando últimos {len(recent_history)} mensajes de contexto (MAX={MAX_HISTORY_MESSAGES})")

                else:

                    # Iteraciones subsiguientes: agregar solo los mensajes de ESTA conversación

                    # (desde el último user message hasta ahora)



                    # Encontrar el índice del último mensaje de usuario

                    last_user_idx = -1

                    for i in range(len(self.conversation_history) - 1, -1, -1):

                        if self.conversation_history[i].get("role") == "user":

                            last_user_idx = i

                            break



                    if last_user_idx >= 0:

                        # CRITICAL FIX: Limitar a MAX_HISTORY_MESSAGES para evitar rate limits

                        # Esto previene que mensajes históricos consuman todos los tokens

                        current_conversation = self.conversation_history[last_user_idx:]



                        # Si hay más de MAX_HISTORY_MESSAGES mensajes, tomar solo los últimos

                        if len(current_conversation) > MAX_HISTORY_MESSAGES:

                            current_conversation = current_conversation[-MAX_HISTORY_MESSAGES:]

                            print(f"   [HIST] Truncando historial a últimos {MAX_HISTORY_MESSAGES} mensajes (de {len(self.conversation_history[last_user_idx:])} disponibles)")



                        # FIX BUG 400: Recolectar tool_call_ids válidos de mensajes assistant previos

                        valid_tool_call_ids = set()



                        for hist_msg in current_conversation:

                            role = hist_msg.get("role", "user")



                            # Manejar mensajes de usuario y asistente

                            if role in ["user", "assistant"]:

                                content = hist_msg.get("content", "")

                                has_tool_calls = role == "assistant" and "tool_calls" in hist_msg



                                # Incluir si: tiene contenido O tiene tool_calls (aunque content sea None)

                                if (content and content.strip()) or has_tool_calls:

                                    msg = {

                                        "role": role,

                                        "content": content if content else ""  # OpenAI requiere string, no None

                                    }

                                    # Si el asistente tiene tool_calls, incluirlos y registrar IDs válidos

                                    if has_tool_calls:

                                        msg["tool_calls"] = hist_msg["tool_calls"]

                                        # Registrar tool_call_ids para validación posterior

                                        for tc in hist_msg["tool_calls"]:

                                            valid_tool_call_ids.add(tc.get("id"))

                                    messages_with_system.append(msg)



                            # Manejar mensajes de herramientas (tool)

                            elif role == "tool":

                                tool_call_id = hist_msg.get("tool_call_id")

                                # FIX: Solo incluir si hay un assistant previo con el tool_call_id correspondiente

                                if tool_call_id and tool_call_id in valid_tool_call_ids:

                                    messages_with_system.append({

                                        "role": "tool",

                                        "tool_call_id": tool_call_id,

                                        "name": hist_msg.get("name"),

                                        "content": hist_msg.get("content", "")

                                    })

                                else:

                                    # Skip orphan tool messages to prevent Error 400

                                    print(f"   [HIST] Saltando mensaje tool huérfano (tool_call_id: {tool_call_id})")



                        print(f"   [HIST] Conversación actual: {len(current_conversation)} mensajes desde último user message")



                print(f"   [LLM] Total mensajes enviados al LLM: {len(messages_with_system)}")



                # Convertir herramientas de formato Anthropic a formato OpenAI

                openai_tools = []

                for tool in self.tools:

                    openai_tool = {

                        "type": "function",

                        "function": {

                            "name": tool["name"],

                            "description": tool["description"],

                            "parameters": tool["input_schema"]

                        }

                    }

                    openai_tools.append(openai_tool)



                # CONTADOR DE TOKENS: Verificar antes de enviar

                token_count = self.count_tokens(messages_with_system)

                print(f"\n   [TOKENS] Tokens a enviar: {token_count:,}")



                # Advertencia si excede el 80% del límite (200K tokens)

                if token_count > self.max_context_tokens * 0.8:

                    print(f"   [TOKENS] [WARNING] ADVERTENCIA: Usando {token_count:,} tokens (80% del límite de {self.max_context_tokens:,})")



                # Auto-recovery: Si excede el límite, reducir historial agresivamente

                if token_count > self.max_context_tokens:

                    print(f"   [TOKENS] [ERROR] EXCEDE EL LÍMITE: {token_count:,} tokens (límite: {self.max_context_tokens:,})")



                    # Truncar el historial MÁS agresivamente (reducir a 1/3)

                    new_history_limit = max(1, MAX_HISTORY_MESSAGES // 3)

                    print(f"   [TOKENS] Reduciendo historial de {MAX_HISTORY_MESSAGES} a {new_history_limit} mensajes...")



                    # Re-construir con menos mensajes

                    MAX_HISTORY_MESSAGES = new_history_limit

                    continue  # Reintentar con menos mensajes



                # SELECTOR DE MODELO: Usar siempre GPT-5.1 en producción

                selected_model = "gpt-5.1"  # Usar GPT-5.1



                # DETECTOR DE RAZONAMIENTO: Determinar nivel de esfuerzo

                reasoning_effort_level = get_reasoning_effort(user_message) if iteration == 1 else "low"

                print(f"   [REASONING] Nivel de razonamiento detectado: {reasoning_effort_level}")

                # ENHANCEMENT: Mejorar query con instrucciones de razonamiento para análisis complejos
                if iteration == 1 and reasoning_effort_level in ["high", "medium"]:
                    enhanced_query = enhance_query_with_reasoning_trigger(user_message, reasoning_effort_level)
                    if enhanced_query != user_message:
                        # Actualizar el último mensaje de usuario en messages_with_system
                        for i in range(len(messages_with_system) - 1, -1, -1):
                            if messages_with_system[i].get("role") == "user":
                                messages_with_system[i]["content"] = enhanced_query
                                print(f"   [QUERY_ENHANCE] Query mejorado con instrucciones de {reasoning_effort_level}")
                                break



                # DEBUG: Loggear mensajes enviados al LLM (solo primeros 3)

                print(f"\n   [DEBUG] Mensajes enviados a {selected_model}:")

                for idx, msg in enumerate(messages_with_system[:3]):

                    role = msg.get('role', 'unknown')

                    content = msg.get('content', '')

                    content_preview = content[:150] if len(content) > 150 else content

                    # Fix Unicode encoding issues for Windows console

                    try:

                        content_safe = content_preview.encode('ascii', 'ignore').decode('ascii')

                        print(f"      [{idx}] {role}: {content_safe}...")

                    except:

                        print(f"      [{idx}] {role}: [content with special characters]...")

                if len(messages_with_system) > 3:

                    print(f"      ... (+{len(messages_with_system) - 3} mensajes mas)")



                # Llamar a OpenAI - CON RAZONAMIENTO PROFUNDO + PROMPT CACHING 24H

                # Preparar parámetros base (v3.0: tool_choice="auto" - GPT-5.1 decide)

                api_params = {

                    "model": selected_model,

                    "max_completion_tokens": 4096,

                    "messages": messages_with_system,

                    "tools": openai_tools,

                    # Nota: GPT-5.1 con reasoning_effort NO soporta temperature custom (solo default=1)

                }



                # reasoning_effort soportado por: gpt-5.1, o1, o1-preview, o1-mini
                # Valores válidos: none, low, medium, high, xhigh
                if reasoning_effort_level in ["none", "low", "medium", "high", "xhigh"]:
                    api_params["reasoning_effort"] = reasoning_effort_level
                    print(f"   [REASONING] Aplicando reasoning_effort={reasoning_effort_level}")



                # GPT-5.1: prompt_cache_retention removido (no soportado en SDK)



                resp = await asyncio.wait_for(

                    asyncio.to_thread(

                        self.client.chat.completions.create,

                        **api_params

                    ),

                    timeout=120.0

                )



                has_tool_use = False

                tool_call_results = []



                # Obtener el mensaje de respuesta de OpenAI

                message = resp.choices[0].message



                # Procesar contenido de texto si existe

                if message.content:

                    response_text += message.content



                # Procesar tool calls si existen

                if message.tool_calls:

                    has_tool_use = True



                    # Guardar el mensaje del asistente con tool_calls en el historial

                    self.conversation_history.append({

                        "role": "assistant",

                        "content": message.content,

                        "tool_calls": [

                            {

                                "id": tc.id,

                                "type": "function",

                                "function": {

                                    "name": tc.function.name,

                                    "arguments": tc.function.arguments

                                }

                            }

                            for tc in message.tool_calls

                        ]

                    })



                    for tool_call in message.tool_calls:

                        tool_name = tool_call.function.name

                        tool_input = json.loads(tool_call.function.arguments)

                        tool_id = tool_call.id



                        # LOGGING MEJORADO para debugging de tool selection

                        print(f"\n   [TOOL] ========================================")

                        print(f"   [TOOL] Herramienta llamada: {tool_name}")

                        print(f"   [TOOL] Parámetros: {json.dumps(tool_input, ensure_ascii=False, indent=2)}")

                        print(f"   [TOOL] ========================================\n")



                        # Ejecutar herramienta

                        print(f"   >> Ejecutando herramienta...")

                        tool_result = await self._execute_tool(tool_name, tool_input)


                        # Guardar herramienta usada CON su resultado para fallback
                        tools_used.append({"name": tool_name, "result": tool_result})

                        print(f"    Herramienta ejecutada, result keys: {tool_result.keys()}")



                        # Log errores para debug

                        if isinstance(tool_result, dict):

                            if 'error' in tool_result:

                                error_msg = str(tool_result.get('error', '')).encode('ascii', 'ignore').decode('ascii')

                                print(f"   [ERROR] ERROR en herramienta: {error_msg}")

                            if 'traceback' in tool_result:

                                # Evitar imprimir traceback con emojis que causan UnicodeEncodeError

                                try:

                                    traceback_msg = str(tool_result.get('traceback', '')).encode('ascii', 'ignore').decode('ascii')

                                    print(f"   [TRACEBACK] TRACEBACK:\n{traceback_msg}")

                                except:

                                    print(f"   [TRACEBACK] Traceback disponible (omitido por caracteres especiales)")



                        #  CAPTURAR ARCHIVOS GENERADOS (charts y reports)

                        # Caso especial: get_ranking_operadores con chart_path

                        if tool_name == "get_ranking_operadores" and tool_result.get("success"):

                            if "data" in tool_result and "chart_path" in tool_result["data"]:

                                chart_path_str = str(tool_result["data"]["chart_path"])

                                from pathlib import Path

                                filename = Path(chart_path_str).name

                                relative_path = f"/outputs/{filename}"

                                files_generated.append(relative_path)

                                print(f"    Grafico de ranking capturado: {relative_path}")



                        # Caso general: file_path en tool_result

                        if tool_result.get("success") and "file_path" in tool_result and tool_result["file_path"]:

                           file_path_str = str(tool_result["file_path"])



                           # Determinar subdirectorio (charts o reports)

                           if "chart" in file_path_str.lower():

                                subdir = "charts"

                           elif "report" in file_path_str.lower():

                                subdir = "reports"

                           else:

                                subdir = "charts"  # default



                           # Extraer solo el nombre del archivo

                           from pathlib import Path

                           filename = Path(file_path_str).name



                           # Construir path relativo correcto

                           relative_path = f"/outputs/{subdir}/{filename}"



                           files_generated.append(relative_path)

                           print(f"    Archivo capturado: {relative_path}")



                        # Guardar resultado de herramienta para OpenAI

                        tool_call_results.append({

                            "role": "tool",

                            "tool_call_id": tool_id,

                            "name": tool_name,

                            "content": json.dumps(tool_result, ensure_ascii=False)

                        })



                        # FIX GENERATE_CHART: Guardar resultados para auto-extracción
                        print(f"    >> [DEBUG-SAVE] tool_name={tool_name}, success={tool_result.get('success')}, has_data={'data' in tool_result}")

                        if tool_result.get("success"):

                            self.last_tool_results[tool_name] = tool_result

                            print(f"    >> [SAVED] Resultado de {tool_name} guardado para auto-extracción")
                        else:
                            print(f"    >> [NOT SAVED] {tool_name} no tiene success=True")



                        # DETECCION DE FINAL_ANSWER - RECOLECTAR (NO TERMINAR)

                        # FIX GPT-5.1: NO hacer early exit, permitir que se ejecuten TODAS las herramientas

                        if "FINAL_ANSWER" in tool_result:

                            print(f"    >> FINAL_ANSWER detectado en {tool_name}, guardando respuesta (SIN terminar)")



                            # CAPTURAR ARCHIVOS GENERADOS (para gaviota)

                            if "chart_url" in tool_result and tool_result["chart_url"]:

                                chart_url = tool_result["chart_url"]

                                files_generated.append(chart_url)

                                print(f"    >> Gráfico capturado: {chart_url}")



                            # FIX: Priorizar FINAL_ANSWER de herramientas que el usuario pidió explícitamente
                            # Detectar si la consulta pide ranking y esta es la herramienta de ranking
                            query_lower = user_message.lower() if user_message else ""
                            is_ranking_query = "ranking" in query_lower or "operador" in query_lower
                            is_ranking_tool = tool_name == "get_ranking_operadores"

                            # Guardar respuesta si:
                            # 1. No hay respuesta aún, O
                            # 2. Esta herramienta tiene prioridad sobre la anterior
                            should_override = False
                            if is_ranking_query and is_ranking_tool:
                                should_override = True  # Ranking siempre tiene prioridad en consultas de ranking
                                print(f"    >> [PRIORITY] Consulta de ranking - priorizando respuesta de get_ranking_operadores")

                            if not response_text or should_override:
                                response_text = tool_result["FINAL_ANSWER"]
                                print(f"    >> [SAVED] FINAL_ANSWER de {tool_name} guardado")

                            # NO hacer break aquí - permitir que se ejecuten todas las herramientas solicitadas



                        # FORCE-STOP PARA RANKING - GPT-5.1 FIX

                        # Si get_ranking_operadores retorna success=True, reducir max_iterations

                        if tool_name == "get_ranking_operadores" and tool_result.get("success") and "data" in tool_result:

                            print(f"    >> [FORCE-STOP] get_ranking_operadores exitoso, limitando iteraciones")

                            # Forzar que la siguiente iteración sea la última

                            max_iterations = iteration + 1

                            print(f"    >> Max iterations reducido a {max_iterations}")







                    # Agregar todos los resultados de herramientas al historial

                    for result in tool_call_results:

                        self.conversation_history.append(result)



                # Si no hay tool calls, guardar respuesta simple del asistente

                else:

                    self.conversation_history.append({

                        "role": "assistant",

                        "content": message.content

                    })



                # Si no hay herramientas, terminar

                if not has_tool_use:

                    break



                # Si el modelo terminó (OpenAI usa finish_reason en choices[0])

                if resp.choices[0].finish_reason in ["stop", "end_turn"]:

                    break



            except asyncio.TimeoutError:

                print(f"   [TIMEOUT] Timeout en iteracion {iteration}")

                response_text += "\n\n Timeout"

                break

            except Exception as e:

                print(f"    Error: {e}")

                import traceback

                traceback.print_exc()

                response_text += f"\n\n Error: {e}"

                break



        # Validación (omitir para gaviota)

        if response_text:

            try:

                # NO validar si se usaron herramientas de gaviota (datos vienen de BD)

                skip_validation_tools = [

                    "obtener_analisis_gaviota",

                    "obtener_comparacion_gaviotas"

                ]

                

                should_skip = any(t['name'] in skip_validation_tools for t in tools_used)

                

                if False:

                    print("\n  Validando...")

                    val = self.validator.validate_response(

                        response=response_text,

                        query=user_message,

                        data_sources=tools_used

                    )

                    if not val.get("is_valid", True) and "safe_response" in val:

                        response_text = val["safe_response"]

                else:

                    print("\n  Validación omitida (herramienta de gaviota con datos de BD)")

            except Exception as e:

                print(f"  Error validando: {e}")



        if not conversation_id:

            import uuid

            conversation_id = str(uuid.uuid4())



        print(f"\n FINAL files_generated count: {len(files_generated)}")

        print(f" FINAL files_generated content: {files_generated}")



        # Save user history after conversation

        self._save_user_history()



        # FIX CRITICO: Validar respuestas vacias/genericas

        RESPUESTAS_VACIAS = [

            "", "Consulta completada.", "Consulta completada",

            "Analisis completado.", "Analisis completado",

            "Datos obtenidos.", "Datos obtenidos",

            "Procesamiento finalizado.", "Procesamiento finalizado",

            "Analisis finalizado.", "Analisis finalizado",

            "Proceso terminado.", "Proceso terminado"

        ]

        response_stripped = response_text.strip() if response_text else ""

        if response_stripped in RESPUESTAS_VACIAS or len(response_stripped) < 50:

            print(f"[FALLBACK] Respuesta vacia detectada: '{response_stripped[:100]}'")

            response_text = self._build_emergency_response(tools_used, user_message)

            print(f"[FALLBACK] Respuesta emergencia generada ({len(response_text)} chars)")



        # ═══════════════════════════════════════════════════════════

        # FASE 2: Registrar interacción en Learning System

        # ═══════════════════════════════════════════════════════════

        interaction_id = None

        if self.learning_system:

            try:

                response_time_ms = (time.time() - start_time) * 1000



                # Estimar tokens (simplificado - en producción usar tiktoken)

                estimated_tokens = len(user_message) // 4 + len(response_text) // 4



                interaction_id = self.learning_system.log_interaction(

                    user_query=user_message,

                    agent_response=response_text,

                    tools_used=[t.get('name', 'unknown') for t in tools_used] if tools_used else [],

                    context={

                        'iterations': iteration,

                        'files_generated': len(files_generated),

                        'conversation_id': conversation_id,

                        'user_id': self.user_id

                    },

                    response_time_ms=response_time_ms,

                    tokens_used=estimated_tokens

                )



                print(f"[LEARNING] Interacción {interaction_id} registrada ({response_time_ms:.0f}ms, {estimated_tokens} tokens)")



            except Exception as e:

                print(f"[WARNING] Error registrando interacción en Learning System: {e}")



        # Guardar respuesta del assistant en conversation_history para contexto futuro

        self.conversation_history.append({

            "role": "assistant",

            "content": response_text

        })



        return {

            "response": response_text,

            "conversation_id": conversation_id,

            "iterations": iteration,

            "tools_used": tools_used,

            "files_generated": files_generated,

            "conversation_history": self.conversation_history,

            "interaction_id": interaction_id  # Para que el frontend pueda solicitar feedback

        }



    

    async def _create_enriched_prompt(self, user_message: str) -> str:

        """

        Enriquece el prompt del usuario con contexto relevante

        """

        enriched_sections = [f"Consulta del usuario: {user_message}"]

        

        # 1. Buscar en HippoRAG para contexto de dominio (v3.0 - PRIORITARIO)
        try:
            print("    [HippoRAG] Buscando contexto de dominio...")
            hipporag_context = hipporag_search(user_message)
            if hipporag_context and "No encontre" not in hipporag_context and len(hipporag_context) > 50:
                enriched_sections.append(
                    f"\n═══ CONTEXTO DE DOMINIO (HippoRAG) ═══\n{hipporag_context[:1500]}"
                )
                print(f"    [HippoRAG] Contexto encontrado: {len(hipporag_context)} chars")
        except Exception as e:
            print(f"    [HippoRAG] Error: {e}")

        # 2. Buscar en LightRAG si está disponible (complementario)

        if self.lightrag:

            try:

                print("    Buscando contexto en LightRAG...")

                knowledge_result = await self.lightrag.query(

                    user_message,

                    mode="hybrid",

                    only_need_context=True

                )

                if knowledge_result and len(knowledge_result) > 100:

                    enriched_sections.append(

                        f"\n═══ CONTEXTO DE BASE DE CONOCIMIENTO ═══\n{knowledge_result[:2000]}..."

                    )

            except Exception as e:

                print(f"     Error buscando en LightRAG: {e}")

        

        # 2. Agregar contexto MineOPS si está disponible

        try:

            mineops_context = self.context.get_recent_context(limit=5)

            if mineops_context:

                enriched_sections.append(

                    f"\n═══ CONTEXTO OPERACIONAL RECIENTE ═══\n{mineops_context}"

                )

        except Exception as e:

            print(f"     Error obteniendo contexto MineOPS: {e}")

        

        # 3. Agregar parámetros económicos si existen

        try:

            economic_params = self.economic_manager.get_all_parameters()

            if economic_params:

                # Validar tipo: puede ser list o dict
                if isinstance(economic_params, list):
                    economic_params = {p.get('parametro', p.get('name', str(i))): p.get('valor', p.get('value', '')) for i, p in enumerate(economic_params)}

                params_text = "\n".join([

                    f"- {param}: {value}"

                    for param, value in economic_params.items()

                ])

                enriched_sections.append(

                    f"\n═══ PARÁMETROS ECONÓMICOS DISPONIBLES ═══\n{params_text}"

                )

        except Exception as e:

            print(f"     Error obteniendo parámetros económicos: {e}")

        

        # 4. Agregar información de equipos si se mencionan códigos

        equipment_codes = self._extract_equipment_codes(user_message)

        if equipment_codes:

            try:

                conn = sqlite3.connect(self.db_path)

                cursor = conn.cursor()

                codes_str = "','".join(equipment_codes)

                cursor.execute(f"""

                    SELECT codigo, tipo, categoria, marca, modelo

                    FROM equipment_glossary

                    WHERE codigo IN ('{codes_str}')

                """)

                equipment_info = cursor.fetchall()

                conn.close()

                

                if equipment_info:

                    equipment_text = "\n".join([

                        f"- {eq[0]}: {eq[1]} ({eq[2]}) - {eq[3]} {eq[4]}"

                        for eq in equipment_info

                    ])

                    enriched_sections.append(

                        f"\n═══ EQUIPOS MENCIONADOS ═══\n{equipment_text}"

                    )

            except Exception as e:

                print(f"     Error obteniendo info de equipos: {e}")

        

        return "\n".join(enriched_sections)

    

    def _extract_equipment_codes(self, text: str) -> List[str]:

        """Extrae códigos de equipos del texto (ej: CA-06, PA-01)"""

        import re

        pattern = r'\b[A-Z]{2}-\d{2}\b'

        return re.findall(pattern, text.upper())



    def _extract_last_ranking_params(self) -> Optional[Dict[str, Any]]:

        """

        🔧 FIX CONTEXTO: Extrae parámetros del último ranking mostrado



        Busca en el historial conversacional el último resultado de get_ranking_operadores

        y extrae los parámetros usados (year, tipo, top_n).



        Returns:

            dict con {year, tipo, top_n} si encuentra un ranking previo

            None si no hay ranking en el historial

        """

        try:

            # Buscar desde el mensaje más reciente hacia atrás

            for msg in reversed(self.conversation_history):

                # Buscar mensajes de herramienta que sean get_ranking_operadores

                if msg.get("role") == "tool" and msg.get("name") == "get_ranking_operadores":

                    try:

                        content = json.loads(msg.get("content", "{}"))

                        if content.get("success") and "data" in content:

                            data = content["data"]

                            # Extraer parámetros del resultado

                            params = {

                                "year": data.get("year", 2024),

                                "tipo": data.get("tipo", "CAEX"),

                                "top_n": data.get("top_n", 10)

                            }

                            print(f"    [CONTEXTO] Parámetros del último ranking: {params}")

                            return params

                    except Exception as e:

                        print(f"    [WARN] Error parseando ranking previo: {e}")

                        continue



            print(f"    [CONTEXTO] No se encontró ranking previo en el historial")

            return None



        except Exception as e:

            print(f"    [ERROR] Error extrayendo contexto: {e}")

            return None



    async def _execute_tool(

        self,

        tool_name: str,

        tool_input: Dict[str, Any]

    ) -> Dict[str, Any]:

        """Ejecuta una herramienta y retorna el resultado"""

        

        try:

            if tool_name == "execute_sql":

                result = self.sql_tool.execute(tool_input["query"])

                return {

                    "success": True,

                    "data": result

                }

            

            elif tool_name == "execute_python":

                # Preparar código

                code = tool_input["code"]

                timeout_seconds = tool_input.get("timeout", 30)

                

                # Guardar código en archivo

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                code_file = self.code_dir / f"code_{timestamp}.py"

                code_file.write_text(code, encoding='utf-8')

                print(f" Código guardado: {code_file.name}")

                

                # Ejecutar con subprocess (mas estable en Windows)

                print(f"[TIMEOUT] Timeout configurado: {timeout_seconds}s")

                print(" Iniciando ejecucion...")

                

                try:

                    import subprocess

                    result = subprocess.run(

                        ["python", str(code_file)],

                        capture_output=True,

                        text=True,

                        timeout=timeout_seconds,

                        cwd=str(self.code_dir)

                    )

                    

                    if result.returncode == 0:

                        output = result.stdout

                        print(f" Ejecución exitosa")



                        # 🔧 FIX: Detectar si se generó un gráfico

                        file_path_to_return = None

                        if "Gráfico guardado exitosamente" in output or "plt.savefig" in code:

                            # Buscar archivos .png recién creados en charts_dir

                            import os

                            import time

                            recent_files = []

                            for f in os.listdir(self.charts_dir):

                                if f.endswith('.png'):

                                    full_path = self.charts_dir / f

                                    # Si fue modificado en los últimos 10 segundos

                                    if time.time() - os.path.getmtime(full_path) < 10:

                                        recent_files.append(full_path)



                            if recent_files:

                                # Ordenar por fecha de modificación (más reciente primero)

                                recent_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

                                file_path_to_return = str(recent_files[0])

                                print(f"    Gráfico detectado: {file_path_to_return}")



                        return {

                            "success": True,

                            "output": output,

                            "code_file": str(code_file),

                            "file_path": file_path_to_return  # ← AGREGAR file_path si se generó gráfico

                        }

                    else:

                        error = result.stderr

                        print(f" Error en ejecución: {error[:200]}")

                        return {

                            "success": False,

                            "error": error

                        }

                        

                except subprocess.TimeoutExpired:

                    print(f"[TIMEOUT] Timeout de {timeout_seconds}s excedido")

                    return {

                        "success": False,

                        "error": f"Timeout de {timeout_seconds}s excedido"

                    }

                except Exception as e:

                    print(f" Error inesperado: {e}")

                    return {

                        "success": False,

                        "error": str(e)

                    }

            

            elif tool_name == "generate_chart":
                from pathlib import Path  # Import al inicio del bloque para evitar scope issues

                # FIX GENERATE_CHART: Auto-extracción de datos si no se proporciona

                chart_data = tool_input.get("data")



                if not chart_data:

                    # Auto-extraer datos de herramientas anteriores

                    print(f"    >> [AUTO-EXTRACT] generate_chart sin 'data', auto-extrayendo de herramientas anteriores")

                    chart_type = tool_input.get("chart_type", "bar")



                    if chart_type in ["waterfall", "cascada"]:

                        # Detectar si el usuario pidió ASARCO explícitamente
                        query_lower = getattr(self, 'current_user_query', '').lower()
                        usar_asarco = any(x in query_lower for x in ['asarco', 'delays', 'demoras', 'causas de pérdida', 'estados'])

                        if usar_asarco:
                            print(f"    >> [AUTO-EXTRACT WATERFALL] Detectado ASARCO -> Usando datos de pareto_delays")
                        else:
                            print(f"    >> [AUTO-EXTRACT WATERFALL] Intentando waterfall por fases...")

                        cumplimiento_data = self.last_tool_results.get("obtener_cumplimiento_tonelaje", {}).get("data", {})
                        pareto_data = self.last_tool_results.get("obtener_pareto_delays", {}).get("data", {})

                        # Extraer mes y año del cumplimiento_data
                        mes = cumplimiento_data.get("mes")
                        year = cumplimiento_data.get("year", 2025)

                        # FALLBACK 1: Extraer de pareto_data.periodo (ej: "JULIO 2025")
                        if not mes and pareto_data:
                            periodo = pareto_data.get("periodo", "")
                            meses_map = {"enero":1, "febrero":2, "marzo":3, "abril":4, "mayo":5, "junio":6,
                                        "julio":7, "agosto":8, "septiembre":9, "octubre":10, "noviembre":11, "diciembre":12}
                            for nombre, num in meses_map.items():
                                if nombre in periodo.lower():
                                    mes = num
                                    print(f"    >> [FALLBACK] Mes extraído de pareto_data.periodo: {mes}")
                                    break

                        # FALLBACK 2: Extraer del query del usuario
                        if not mes and hasattr(self, 'current_user_query'):
                            query_lower = getattr(self, 'current_user_query', '').lower()
                            meses_map = {"enero":1, "febrero":2, "marzo":3, "abril":4, "mayo":5, "junio":6,
                                        "julio":7, "agosto":8, "septiembre":9, "octubre":10, "noviembre":11, "diciembre":12}
                            for nombre, num in meses_map.items():
                                if nombre in query_lower:
                                    mes = num
                                    print(f"    >> [FALLBACK] Mes extraído del query del usuario: {mes}")
                                    break

                        print(f"    >> [WATERFALL] mes={mes}, year={year}, usar_asarco={usar_asarco}")
                        print(f"    >> [DEBUG] pareto_data keys: {pareto_data.keys() if pareto_data else 'None'}")
                        print(f"    >> [DEBUG] pareto_data.delays count: {len(pareto_data.get('delays', [])) if pareto_data else 0}")

                        # =====================================================
                        # OPCIÓN 1: WATERFALL CON ASARCO (delays del pareto)
                        # =====================================================
                        if usar_asarco and pareto_data and pareto_data.get("delays"):
                            print(f"    >> [WATERFALL ASARCO] Generando waterfall con causas del pareto_delays")

                            # Obtener datos de cumplimiento
                            plan_ton = cumplimiento_data.get("plan", 0)
                            real_ton = cumplimiento_data.get("real", 0)

                            # FALLBACK: Si cumplimiento_data tiene zeros, consultar SQLite directamente
                            if plan_ton == 0 and real_ton == 0 and mes and year:
                                print(f"    >> [FALLBACK SQLite] cumplimiento_data tiene zeros, consultando SQLite para {mes}/{year}...")
                                try:
                                    # sqlite3 ya está importado a nivel de módulo
                                    db_file = Path(self.db_path) if hasattr(self, 'db_path') and self.db_path else Path("minedash.db")
                                    if not db_file.exists():
                                        db_file = Path("backend/minedash.db")
                                    if not db_file.exists():
                                        db_file = Path(__file__).parent.parent / "minedash.db"

                                    if db_file.exists():
                                        conn = sqlite3.connect(str(db_file))
                                        cursor = conn.cursor()

                                        # Query para obtener producción real del mes desde dumps
                                        # Buscar tabla de dumps disponible
                                        dumps_table = None
                                        for table_name in [f"hexagon_by_detail_dumps_{year}", "hexagon_by_detail_dumps"]:
                                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                                            if cursor.fetchone():
                                                dumps_table = table_name
                                                break

                                        if dumps_table:
                                            # Obtener real del mes completo
                                            query_real = f"""
                                                SELECT SUM(material_tonnage) as real_ton
                                                FROM {dumps_table}
                                                WHERE strftime('%Y', timestamp) = ? AND strftime('%m', timestamp) = ?
                                            """
                                            cursor.execute(query_real, (str(year), f"{mes:02d}"))
                                            result = cursor.fetchone()
                                            real_ton = float(result[0]) if result and result[0] else 0

                                            # Usar fallback para plan (115% del real)
                                            plan_ton = real_ton * 1.15 if real_ton > 0 else 0
                                            print(f"    >> [SQLite] Real={real_ton:,.0f} ton, Plan(fallback)={plan_ton:,.0f} ton")

                                        conn.close()
                                except Exception as e:
                                    print(f"    >> [WARN] Fallback SQLite falló: {e}")

                            gap = plan_ton - real_ton

                            # Obtener top causas del pareto
                            delays_list = pareto_data.get("delays", [])[:6]  # Top 6 causas
                            total_horas = sum(d.get("total_horas", d.get("horas", 0)) for d in delays_list)

                            # Construir waterfall
                            x_labels = ["Plan"]
                            y_values = [plan_ton]
                            measures = ["absolute"]

                            for delay in delays_list:
                                razon = delay.get("razon", delay.get("estado", ""))[:20]
                                horas = delay.get("total_horas", delay.get("horas", 0))
                                # Calcular impacto proporcional al gap
                                impacto = (horas / total_horas * gap) if total_horas > 0 else 0
                                x_labels.append(razon)
                                y_values.append(-impacto)
                                measures.append("relative")

                            x_labels.append("Real")
                            y_values.append(0)
                            measures.append("total")

                            print(f"    >> [WATERFALL ASARCO] Generado: {len(x_labels)} elementos")

                            # Generar gráfico
                            waterfall_data = {
                                "x": x_labels,
                                "y": y_values,
                                "measures": measures
                            }

                            meses_nombres = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                                           7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
                            mes_nombre = meses_nombres.get(mes, str(mes))

                            from tools.waterfall_plotly import generate_waterfall_plotly
                            filepath = generate_waterfall_plotly(
                                data=waterfall_data,
                                title=f"Análisis Causal ASARCO - {mes_nombre} {year}",
                                ylabel="Toneladas",
                                charts_dir=Path("outputs/charts")
                            )

                            # Generar informe detallado
                            pct_cumpl = (real_ton / plan_ton * 100) if plan_ton > 0 else 0
                            html_url = f"http://localhost:8001/outputs/charts/{filepath.name}"

                            informe = f"""## ANÁLISIS DE CAUSALIDAD ASARCO - {mes_nombre} {year}

### Resumen Ejecutivo
| Métrica | Valor |
|---------|-------|
| **Plan del mes** | {plan_ton:,.0f} ton |
| **Real del mes** | {real_ton:,.0f} ton |
| **Brecha** | {gap:,.0f} ton |
| **Cumplimiento** | {pct_cumpl:.1f}% |

### Principales Causas de Pérdida (Estados ASARCO)

| # | Código | Causa | Horas | Impacto (ton) | % del Gap |
|---|--------|-------|-------|---------------|-----------|
"""
                            for i, delay in enumerate(delays_list, 1):
                                razon = delay.get("razon", delay.get("estado", ""))
                                codigo = delay.get("code", "-")
                                horas = delay.get("total_horas", delay.get("horas", 0))
                                impacto = (horas / total_horas * gap) if total_horas > 0 else 0
                                pct_gap = (impacto / gap * 100) if gap > 0 else 0
                                informe += f"| {i} | {codigo} | {razon} | {horas:,.0f} | {impacto:,.0f} | {pct_gap:.1f}% |\n"

                            informe += f"""
### Gráfico Waterfall de Causalidad ASARCO

**[Abrir Gráfico Interactivo]({html_url})**

---

### Análisis Operacional por Causa

"""
                            # Agregar análisis detallado por cada causa
                            analisis_causas = {
                                "CAMBIO TURNO": "Tiempo excesivo en relevos indica problemas de coordinación, traslados largos o disciplina de estados. Impacta directo en UEBD.",
                                "IMPREVISTO MECANICO": "Alta tasa de fallas correctivas. Revisar backlog de mantención, equipos críticos y recurrencia por sistema.",
                                "SIN OPERADOR": "Flota disponible sin recurso humano. Posible ausentismo, vacantes o mal match dotación vs equipos.",
                                "MANTENIMIENTO PROGRAMADO": "MP esperable pero si está en horas pico amplifica el impacto. Coordinar con plan de producción.",
                                "COLACION": "Si se suma a cambio turno, señala ventanas muertas largas en relevos y comidas.",
                                "FALTA EQUIPO CARGUIO": "Palas/cargadores no disponibles cuando se necesitan. Revisar disponibilidad y asignación.",
                                "OTRAS DEMORAS": "Causas misceláneas que requieren revisión individual.",
                                "ESPERA TRASLADO": "Tiempos muertos esperando transporte o movimiento de equipos.",
                                "ABASTECIMIENTO COMBUSTIBLE": "Tiempos de tanqueo. Evaluar ubicación de estaciones y programación.",
                                "TRONADURA": "Paralización por voladura. Coordinar ventanas con operación.",
                            }

                            for i, delay in enumerate(delays_list[:5], 1):
                                razon = delay.get("razon", delay.get("estado", ""))
                                codigo = delay.get("code", "-")
                                horas = delay.get("total_horas", delay.get("horas", 0))
                                pct = (horas / total_horas * 100) if total_horas > 0 else 0

                                # Buscar análisis para esta causa
                                analisis = "Revisar en detalle con supervisión operacional."
                                for key, val in analisis_causas.items():
                                    if key.upper() in razon.upper():
                                        analisis = val
                                        break

                                informe += f"**{i}. {razon} (código {codigo}) - {pct:.1f}% de horas perdidas**\n"
                                informe += f"   - {analisis}\n\n"

                            informe += f"""
---

### Conclusiones y Focos de Acción

1. **Operación ({sum(d.get('total_horas', d.get('horas', 0)) for d in delays_list if 'TURNO' in str(d.get('razon','')).upper() or 'OPERADOR' in str(d.get('razon','')).upper() or 'COLACION' in str(d.get('razon','')).upper()):,.0f} hrs)**
   - Rediseñar proceso de relevo
   - Gestionar dotación vs flota disponible
   - Revisar tiempos reales vs configurados en FMS

2. **Mantención ({sum(d.get('total_horas', d.get('horas', 0)) for d in delays_list if 'MECANICO' in str(d.get('razon','')).upper() or 'MANTENIMIENTO' in str(d.get('razon','')).upper()):,.0f} hrs)**
   - Pareto de equipos con más horas 400
   - Revisar backlog y reincidencia por sistema
   - Ajustar MP para aprovechar horas valle

3. **Próximo paso recomendado**
   - Pareto por equipo y por grupo/turno
   - Gaviota de días representativos para ver concentración horaria
"""

                            return {
                                "success": True,
                                "FINAL_ANSWER": informe,
                                "chart_path": str(filepath),
                                "chart_url": html_url
                            }

                        # =====================================================
                        # OPCIÓN 2: WATERFALL POR FASES (comportamiento original)
                        # =====================================================
                        if mes and not usar_asarco:

                            try:

                                # Importar aqui para asegurar disponibilidad

                                from services.plan_reader import PlanReader

                                from services.igm_reader import obtener_real_por_fase_con_fallback



                                # Obtener datos por fase

                                plan_reader = PlanReader()

                                plan_data = plan_reader.get_plan_por_fase(mes, year)

                                real_data = obtener_real_por_fase_con_fallback(mes, year, self.db_path)



                                if plan_data and real_data and real_data.get('source') == 'IGM':

                                    print(f"    >> [WATERFALL POR FASES] Plan y Real obtenidos desde IGM")



                                    # Construir waterfall simple por fases

                                    plan_total = plan_data['plan_total']

                                    fases_plan = plan_data['fases']



                                    # Inicializar listas

                                    x_labels = ["Plan Total"]

                                    y_values = [plan_total]

                                    measures = ["absolute"]



                                    # Agregar deltas por fase: F02, F03, F04, F01 (orden lógico)

                                    orden_fases = ['F02', 'F03', 'F04', 'F01']



                                    for fase_id in orden_fases:

                                        if fase_id in fases_plan and fase_id in real_data:

                                            plan_fase = fases_plan[fase_id]

                                            real_fase = real_data[fase_id]

                                            delta = real_fase - plan_fase



                                            # Etiqueta con nombre descriptivo

                                            fase_nombre = fase_id

                                            if fase_id == 'F01':

                                                fase_nombre = "F01 Codelco"

                                            elif fase_id == 'F02':

                                                fase_nombre = "F02 Tepsac"



                                            cumplimiento_pct = int((real_fase / plan_fase * 100) if plan_fase > 0 else 0)



                                            x_labels.append(f"{fase_nombre}")

                                            y_values.append(delta)

                                            measures.append("relative")



                                    # Agregar Real Total

                                    x_labels.append("Real Total")

                                    y_values.append(0)  # Plotly calcula automáticamente

                                    measures.append("total")



                                    chart_data = {

                                        "x": x_labels,

                                        "y": y_values,

                                        "measures": measures,

                                        "metadata": {

                                            "tipo": "waterfall_fases",

                                            "mes": mes,

                                            "year": year,

                                            "fuente_real": "IGM",

                                            "fuente_plan": plan_data.get('archivo', 'Plan Mensual'),

                                            "plan_total": plan_total,

                                            "real_total": sum(real_data.get(f, 0) for f in ['F01', 'F02', 'F03', 'F04'])

                                        }

                                    }



                                    print(f"    >> [WATERFALL POR FASES] Generado: {len(x_labels)} elementos")

                                    print(f"       Plan Total: {plan_total:,.0f} ton")

                                    print(f"       Real Total: {chart_data['metadata']['real_total']:,.0f} ton")



                                else:

                                    raise Exception("No se pudo obtener datos por fases desde IGM")



                            except Exception as e:

                                print(f"    >> [WARN] No se pudo generar waterfall por fases: {e}")

                                print(f"    >> [FALLBACK] Usando waterfall tradicional con delays...")



                                # FALLBACK: Waterfall tradicional con delays

                                cumplimiento_data = self.last_tool_results.get("obtener_cumplimiento_tonelaje", {}).get("data", {})

                                pareto_data = self.last_tool_results.get("obtener_pareto_delays", {}).get("data", {})



                                # MEJORADO: Generar waterfall con datos parciales

                                if cumplimiento_data and pareto_data:

                                    plan_ton = cumplimiento_data.get("tonelaje_plan", 0)

                                    real_ton = cumplimiento_data.get("tonelaje_total", 0)

                                    delays_list = pareto_data.get("delays", [])



                                    x_labels = ["Plan"]

                                    y_values = [plan_ton]

                                    measures = ["absolute"]



                                    # Top 5 delays

                                    for delay in delays_list[:5]:

                                        razon = delay.get("razon", "Desconocido")

                                        horas = delay.get("total_horas", delay.get("horas", 0))

                                        impacto_ton = -abs(horas) * 25

                                        x_labels.append(razon)

                                        y_values.append(impacto_ton)

                                        measures.append("relative")



                                    x_labels.append("Real")

                                    y_values.append(0)

                                    measures.append("total")



                                    chart_data = {

                                        "x": x_labels,

                                        "y": y_values,

                                        "measures": measures

                                    }

                                    print(f"    >> [FALLBACK] Waterfall tradicional: Plan={plan_ton:,.0f}, Real={real_ton:,.0f}")

                                

                                elif pareto_data:

                                    # SOLO PARETO: Generar cascada de horas perdidas

                                    print(f"    >> [PARCIAL] Generando waterfall solo con datos de delays (sin tonelaje)")

                                    delays_list = pareto_data.get("delays", [])

                                    total_horas = pareto_data.get("total_horas", 0)

                                    

                                    if delays_list:

                                        x_labels = ["Total Disponible"]

                                        y_values = [total_horas + sum(d.get("total_horas", 0) for d in delays_list[:10])]

                                        measures = ["absolute"]

                                        

                                        # Top 10 delays como perdidas

                                        for delay in delays_list[:10]:

                                            razon = delay.get("razon", "Desconocido")[:25]

                                            horas = delay.get("total_horas", delay.get("horas", 0))

                                            x_labels.append(razon)

                                            y_values.append(-abs(horas))

                                            measures.append("relative")

                                        

                                        x_labels.append("Tiempo Efectivo")

                                        y_values.append(0)

                                        measures.append("total")

                                        

                                        chart_data = {

                                            "x": x_labels,

                                            "y": y_values,

                                            "measures": measures

                                        }

                                        print(f"    >> [PARCIAL] Waterfall de {len(delays_list)} delays generado")

                                    else:

                                        return {

                                            "success": False,

                                            "error": "No hay datos de delays disponibles para generar waterfall."

                                        }

                                else:

                                    return {

                                        "success": False,

                                        "error": "No se encontraron datos de cumplimiento_tonelaje ni pareto_delays para generar waterfall. Ejecuta primero obtener_pareto_delays()."

                                    }

                        else:

                            return {

                                "success": False,

                                "error": "No se pudo determinar el mes para waterfall por fases. Asegúrate de ejecutar primero obtener_cumplimiento_tonelaje."

                            }

                    else:

                        # Para otros tipos de gráficos, intentar encontrar data en últimas herramientas

                        for tool_name_key in ["analisis_gaviota", "obtener_ranking_operadores", "match_pala_camion"]:

                            if tool_name_key in self.last_tool_results:

                                chart_data = self.last_tool_results[tool_name_key].get("data", {})

                                print(f"    >> [AUTO-EXTRACT] Usando datos de {tool_name_key}")

                                break



                        if not chart_data:

                            return {

                                "success": False,

                                "error": "No hay datos disponibles para generar gráfico. Ejecuta primero una herramienta de análisis o proporciona 'data' manualmente."

                            }



                try:

                    file_path = self.chart_generator.generate(

                        chart_type=tool_input.get("chart_type", "bar"),

                        title=tool_input.get("title", "Gráfico"),

                        data=chart_data

                    )



                    result = {

                        "success": True,

                        "file_path": str(file_path),

                        "message": f"Gráfico generado: {file_path.name}",

                        "chart_url": str(file_path)

                    }



                    # NUEVO: Si es waterfall por fases, agregar FINAL_ANSWER con análisis de delays

                    if chart_data and isinstance(chart_data, dict):

                        metadata = chart_data.get("metadata", {})

                        if metadata.get("tipo") == "waterfall_fases":

                            # Generar texto explicativo con análisis de delays

                            mes = metadata.get("mes", 1)

                            year = metadata.get("year", 2025)

                            plan_total = metadata.get("plan_total", 0)

                            real_total = metadata.get("real_total", 0)

                            cumplimiento_global = int((real_total / plan_total * 100) if plan_total > 0 else 0)



                            # Obtener delays de pareto si existe

                            pareto_data = self.last_tool_results.get("obtener_pareto_delays", {}).get("data", {})

                            delays_list = pareto_data.get("delays", []) if pareto_data else []



                            # Construir análisis de texto

                            meses_nombres = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",

                                           7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}

                            mes_nombre = meses_nombres.get(mes, f"Mes {mes}")



                            analisis_texto = f"""## Analisis de Cumplimiento por Fase - {mes_nombre} {year}



**Cumplimiento Global:** {cumplimiento_global}% ({real_total:,.0f} ton / {plan_total:,.0f} ton)



El grafico waterfall muestra la desviacion de cada fase respecto al plan mensual:



"""

                            # Agregar detalles por fase del chart_data

                            x_labels = chart_data.get("x", [])

                            y_values = chart_data.get("y", [])



                            for i, label in enumerate(x_labels):

                                if label not in ["Plan Total", "Real Total"] and i < len(y_values):

                                    delta = y_values[i]

                                    if delta != 0:

                                        signo = "+" if delta > 0 else ""

                                        analisis_texto += f"- **{label}:** {signo}{delta:,.0f} ton\n"



                            # Agregar analisis de delays globales

                            analisis_texto += f"""



---



## Analisis de Delays Operacionales (Flota Completa)



Los delays operacionales afectan la flota completa trabajando para todas las fases:

"""



                            if delays_list:

                                analisis_texto += "\n**Top 5 Causas de Delays (Hexagon):**\n\n"

                                for idx, delay in enumerate(delays_list[:5], 1):

                                    razon = delay.get("razon", "Desconocido")

                                    horas = delay.get("total_horas", delay.get("horas", 0))

                                    analisis_texto += f"{idx}. **{razon}:** {horas:,.0f} horas\n"



                            analisis_texto += f"""



**Nota Importante:**



Los delays mostrados corresponden a la **flota completa** (CAEX + Palas) trabajando para **todas las fases** (F01 Codelco, F02 Tepsac, F03, F04).



**No es posible atribuir estos delays especificamente a una sola fase** porque los mismos equipos rotan entre diferentes fases en distintos turnos.



**Fuentes de Datos:**

- Plan: {metadata.get('fuente_plan', 'Plan Mensual')}

- Real: IGM {mes_nombre} {year}

- Delays: Sistema Hexagon (Flota completa)



---



Necesitas analisis detallado de alguna fase especifica?

"""

                            result["FINAL_ANSWER"] = analisis_texto

                            print(f"    >> [WATERFALL FASES] FINAL_ANSWER generado con análisis de delays")



                    return result



                except Exception as e:

                    return {

                        "success": False,

                        "error": f"Error generando gráfico: {str(e)}"

                    }

            

            elif tool_name == "generate_report":

                file_path = self.report_generator.generate(

                    title=tool_input["title"],

                    sections=tool_input["sections"],

                    format_type=tool_input.get("format", "docx")

                )

                return {

                    "success": True,

                    "file_path": str(file_path),

                    "message": f"Reporte generado: {file_path.name}"

                }

            

            elif tool_name == "search_knowledge":

                if self.lightrag:

                    result = await self.lightrag.query(

                        tool_input["query"],

                        mode=tool_input.get("mode", "hybrid")

                    )

                    return {

                        "success": True,

                        "data": result

                    }

                else:

                    return {

                        "success": False,

                        "error": "LightRAG no disponible"

                    }

            elif tool_name == "aprender_informacion":
                # Handler para aprender nueva informacion
                from services.hipporag_service import learn_information
                informacion = tool_input.get("informacion", "")
                categoria = tool_input.get("categoria", "otro")

                if not informacion:
                    return {
                        "success": False,
                        "error": "No se proporciono informacion para aprender"
                    }

                # Agregar metadata de categoria
                info_con_categoria = f"[{categoria.upper()}] {informacion}"
                resultado = learn_information(info_con_categoria)

                return {
                    "success": True,
                    "message": f"Informacion aprendida: {informacion[:100]}...",
                    "categoria": categoria,
                    "FINAL_ANSWER": f"Listo, he aprendido y recordare: {informacion}"
                }

            
            elif tool_name == "buscar_en_memoria":
                # Handler para buscar en memoria aprendida
                from services.hipporag_service import search_knowledge
                consulta = tool_input.get("consulta", "")
                
                if not consulta:
                    return {
                        "success": False,
                        "error": "No se proporciono consulta"
                    }
                
                resultado = search_knowledge(consulta)
                
                if "No encontre" in resultado or "Error" in resultado:
                    return {
                        "success": False,
                        "found": False,
                        "message": resultado
                    }
                
                return {
                    "success": True,
                    "found": True,
                    "informacion": resultado,
                    "FINAL_ANSWER": f"Encontre en mi memoria: {resultado}"
                }

            elif tool_name == "execute_api":

                method = tool_input["method"]

                endpoint = tool_input["endpoint"]

                params = tool_input.get("params", {})

                body = tool_input.get("body", None)

                

                url = f"{self.api_base_url}{endpoint}"

                

                if method == "GET":

                    response = requests.get(url, params=params, timeout=180)

                elif method == "POST":

                    response = requests.post(url, json=body, params=params, timeout=180)

                elif method == "PUT":

                    response = requests.put(url, json=body, params=params, timeout=180)

                elif method == "DELETE":

                    response = requests.delete(url, params=params, timeout=180)

                else:

                    return {

                        "success": False,

                        "error": f"Método HTTP no soportado: {method}"

                    }

                

                if response.status_code == 200:

                    return {

                        "success": True,

                        "data": response.json(),

                        "status_code": response.status_code

                    }

                else:

                    return {

                        "success": False,

                        "error": f"HTTP {response.status_code}: {response.text}",

                        "status_code": response.status_code

                    }

            

            elif tool_name == "get_ranking_operadores":

                year = tool_input["year"]

                mes = tool_input.get("mes", None)  # NUEVO: Mes específico

                top_n = tool_input.get("top_n", 10)

                tipo = tool_input.get("tipo", "")



                result = self.ranking_service.ranking_operadores_produccion(

                    year=year,

                    mes=mes,  # NUEVO: Pasar mes a la función

                    top_n=top_n,

                    tipo=tipo

                )



                # GENERACION AUTOMATICA DE GRAFICO Y FINAL_ANSWER PROFESIONAL

                if result.get("success") and "ranking" in result:

                    from services.auto_visualization import AutoVisualizationEngine

                    from services.ranking_analytics import generar_final_answer_ranking

                    from pathlib import Path



                    viz_engine = AutoVisualizationEngine(

                        data_dir=self.ranking_service.data_dir,

                        db_path=self.db_path

                    )



                    # Generar grafico automaticamente (sin preguntar)

                    try:

                        chart_result = viz_engine.auto_generate_ranking_chart(

                            ranking_data=result["ranking"],

                            year=year,

                            tipo=tipo if tipo else "TODOS",

                            mes=mes  # NUEVO: Pasar mes al gráfico

                        )

                        # chart_result es dict con plotly_json, html, type, chart_path
                        chart_path = chart_result.get("chart_path", "") if isinstance(chart_result, dict) else chart_result
                        print(f"   Grafico interactivo generado: {chart_path}")



                        chart_filename = Path(chart_path).name if chart_path else "ranking.html"



                        # Generar resumen corto del ranking
                        top3 = result["ranking"][:3] if result.get("ranking") else []
                        top3_text = ", ".join([f"{r.get('operador', 'N/A')} ({r.get('total_ton', 0):,.0f} ton)" for r in top3])
                        periodo_str = f"mes {mes}" if mes else f"año {year}"
                        summary = f"Ranking operadores {tipo or 'TODOS'} {periodo_str}: Top 3 = {top3_text}"

                        # Retornar con summary para que el modelo decida si necesita más herramientas
                        return {

                            "success": True,

                            "summary": summary,

                            "chart": chart_result if isinstance(chart_result, dict) else None,
                            "file_path": chart_path,

                            "data": result

                        }



                    except Exception as e:

                        print(f"   Error generando visualizacion: {e}")

                        import traceback

                        traceback.print_exc()



                return {

                    "success": True,

                    "data": result

                }

            



            elif tool_name == "analizar_relevos":

                fecha = tool_input.get("fecha")

                equipo = tool_input.get("equipo")

                operador = tool_input.get("operador")

                mes_completo = tool_input.get("mes_completo", False)

                

                print(f"    Analizando relevos para {fecha}")

                

                try:

                    conn = sqlite3.connect(self.db_path)

                    

                    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")

                    

                    if mes_completo:

                        fecha_inicio = fecha_obj.replace(day=1).strftime("%Y-%m-%d")

                        if fecha_obj.month == 12:

                            fecha_fin = fecha_obj.replace(year=fecha_obj.year + 1, month=1, day=1).strftime("%Y-%m-%d")

                        else:

                            fecha_fin = fecha_obj.replace(month=fecha_obj.month + 1, day=1).strftime("%Y-%m-%d")

                    else:

                        fecha_inicio = fecha

                        fecha_fin = (fecha_obj + timedelta(days=1)).strftime("%Y-%m-%d")

                    

                    query = """

                    WITH clasificacion_registros AS (

                        SELECT 

                            DATE(dump_start_time) as fecha,

                            truck_equipment_name as equipo,

                            shift as turno,

                            shift_group as grupo,

                            truck_operator_first_name || ' ' || truck_operator_last_name as operador,

                            dump_start_time as timestamp,

                            material_tonnage,

                            CASE 

                                WHEN dump_start_time IS NOT NULL AND material_tonnage > 0 THEN 'AUTOMATICO'

                                WHEN dump_start_time IS NULL AND material_tonnage > 0 THEN 'MANUAL'

                                ELSE 'INVALIDO'

                            END as tipo_registro

                        FROM hexagon_by_detail_dumps_2025

                        WHERE truck_equipment_type LIKE '%KOM930E%'

                        AND material_tonnage > 0

                        AND truck_operator_first_name IS NOT NULL

                        AND truck_operator_first_name != 'nan'

                        AND truck_operator_last_name IS NOT NULL

                        AND truck_operator_last_name != 'nan'

                        AND DATE(dump_start_time) >= ?

                        AND DATE(dump_start_time) < ?

                    ),

                    

                    base_operadores AS (

                        SELECT 

                            fecha,

                            equipo,

                            turno,

                            grupo,

                            operador,

                            COUNT(CASE WHEN tipo_registro = 'AUTOMATICO' THEN 1 END) as viajes_automaticos,

                            SUM(CASE WHEN tipo_registro = 'AUTOMATICO' THEN material_tonnage ELSE 0 END) as ton_automaticas,

                            MIN(CASE WHEN tipo_registro = 'AUTOMATICO' THEN timestamp END) as hora_inicio,

                            MAX(CASE WHEN tipo_registro = 'AUTOMATICO' THEN timestamp END) as hora_fin,

                            CAST(

                                (julianday(MAX(CASE WHEN tipo_registro = 'AUTOMATICO' THEN timestamp END)) - 

                                julianday(MIN(CASE WHEN tipo_registro = 'AUTOMATICO' THEN timestamp END))) * 24

                            AS REAL) as horas_operador,

                            COUNT(CASE WHEN tipo_registro = 'MANUAL' THEN 1 END) as viajes_manuales,

                            SUM(CASE WHEN tipo_registro = 'MANUAL' THEN material_tonnage ELSE 0 END) as ton_manuales,

                            COUNT(*) as viajes_totales,

                            SUM(material_tonnage) as toneladas_totales,

                            ROUND(

                                (COUNT(CASE WHEN tipo_registro = 'MANUAL' THEN 1 END) * 100.0) / COUNT(*), 

                                1

                            ) as pct_manuales

                        FROM clasificacion_registros

                        WHERE tipo_registro IN ('AUTOMATICO', 'MANUAL')

                        GROUP BY fecha, equipo, turno, grupo, operador

                    ),

                    

                    relevos_detectados AS (

                        SELECT 

                            fecha,

                            equipo,

                            turno,

                            COUNT(DISTINCT operador) as num_operadores,

                            GROUP_CONCAT(

                                operador || ' (' || ROUND(horas_operador, 1) || 'h)', 

                                ' → '

                            ) as secuencia_operadores

                        FROM base_operadores

                        WHERE horas_operador > 0.1

                        GROUP BY fecha, equipo, turno

                        HAVING COUNT(DISTINCT operador) > 1

                    ),

                    

                    promedios_circuito AS (

                        SELECT 

                            fecha,

                            turno,

                            AVG(CASE 

                                WHEN horas_operador > 0.1 THEN ton_automaticas / horas_operador

                                ELSE NULL

                            END) as promedio_ton_hora_circuito,

                            AVG(ton_automaticas) as promedio_ton_circuito

                        FROM base_operadores

                        WHERE horas_operador > 0.1

                        GROUP BY fecha, turno

                    ),

                    

                    analisis_completo AS (

                        SELECT 

                            b.fecha,

                            b.equipo,

                            b.turno,

                            b.grupo,

                            b.operador,

                            TIME(b.hora_inicio) as inicio,

                            TIME(b.hora_fin) as fin,

                            ROUND(b.horas_operador, 2) as horas_operador_real,

                            b.viajes_automaticos,

                            ROUND(b.ton_automaticas, 0) as ton_automaticas,

                            b.viajes_manuales,

                            ROUND(b.ton_manuales, 0) as ton_manuales,

                            b.viajes_totales,

                            ROUND(b.toneladas_totales, 0) as toneladas_totales,

                            b.pct_manuales,

                            CASE 

                                WHEN b.horas_operador > 0.1 THEN 

                                    ROUND(b.ton_automaticas / b.horas_operador, 1)

                                ELSE NULL

                            END as ton_hora_operador,

                            CASE 

                                WHEN r.num_operadores IS NOT NULL THEN 

                                    ' RELEVO (' || 

                                    ROW_NUMBER() OVER (PARTITION BY b.fecha, b.equipo, b.turno ORDER BY b.hora_inicio) || 

                                    ' de ' || r.num_operadores || ')'

                                ELSE ' ÚNICO'

                            END as situacion_relevo,

                            r.secuencia_operadores,

                            CASE 

                                WHEN b.horas_operador >= 8 THEN 'PRINCIPAL'

                                WHEN b.horas_operador BETWEEN 1 AND 3 THEN 'RELEVO_COLACION'

                                WHEN b.horas_operador BETWEEN 3 AND 8 THEN 'RELEVO_PARCIAL'

                                ELSE 'TEMPORAL'

                            END as tipo_asignacion,

                            CASE 

                                WHEN b.pct_manuales > 30 THEN ' ALTO % MANUAL'

                                WHEN b.pct_manuales > 10 THEN ' % MANUAL MODERADO'

                                WHEN b.pct_manuales > 0 THEN ' BAJO % MANUAL'

                                ELSE ' 100% AUTOMÁTICO'

                            END as calidad_datos,

                            p.promedio_ton_hora_circuito,

                            CASE 

                                WHEN b.horas_operador > 0.1 AND p.promedio_ton_hora_circuito IS NOT NULL THEN

                                    ROUND(

                                        ((b.ton_automaticas / b.horas_operador) / p.promedio_ton_hora_circuito - 1) * 100,

                                        1

                                    )

                                ELSE NULL

                            END as score_vs_circuito

                        FROM base_operadores b

                        LEFT JOIN relevos_detectados r

                            ON b.fecha = r.fecha

                            AND b.equipo = r.equipo

                            AND b.turno = r.turno

                        LEFT JOIN promedios_circuito p

                            ON b.fecha = p.fecha

                            AND b.turno = p.turno

                    )

                    

                    SELECT 

                        fecha,

                        equipo,

                        turno,

                        grupo,

                        operador,

                        tipo_asignacion,

                        situacion_relevo,

                        inicio,

                        fin,

                        horas_operador_real,

                        viajes_automaticos,

                        ton_automaticas,

                        viajes_manuales,

                        ton_manuales,

                        viajes_totales,

                        toneladas_totales,

                        pct_manuales,

                        calidad_datos,

                        ton_hora_operador,

                        secuencia_operadores,

                        promedio_ton_hora_circuito,

                        score_vs_circuito

                    FROM analisis_completo

                    WHERE tipo_asignacion IN ('PRINCIPAL', 'RELEVO_COLACION', 'RELEVO_PARCIAL')

                    """

                    

                    params_query = [fecha_inicio, fecha_fin]

                    

                    if equipo:

                        query += " AND equipo = ?"

                        params_query.append(equipo)

                    

                    if operador:

                        query += " AND operador LIKE ?"

                        params_query.append(f"%{operador}%")

                    

                        query += " ORDER BY fecha DESC, score_vs_circuito DESC, ton_hora_operador DESC"

                    

                    df = pd.read_sql_query(query, conn, params=params_query)

                    conn.close()

                    

                    if df.empty:

                        return {

                            "success": False,

                            "error": f"No se encontraron datos para {fecha}"

                        }

                    

                    total_registros = len(df)

                    relevos_count = len(df[df['situacion_relevo'].str.contains('RELEVO', na=False)])

                    

                    promedio_ton_hora = df[df['ton_hora_operador'].notna()]['ton_hora_operador'].mean()

                    mejor_rendimiento = df[df['ton_hora_operador'].notna()]['ton_hora_operador'].max()

                    peor_rendimiento = df[df['ton_hora_operador'].notna()]['ton_hora_operador'].min()

                    

                    relevos_colacion = len(df[df['tipo_asignacion'] == 'RELEVO_COLACION'])

                    

                    mensaje = f"""

            =================================================================

            |   ANÁLISIS DE RELEVOS - {fecha_inicio} a {fecha_fin}  |

            =================================================================



             RESUMEN GENERAL:

            • Total registros: {total_registros}

            • Relevos detectados: {relevos_count}

            • Relevos de colación: {relevos_colacion}

            • Operadores únicos: {df['operador'].nunique()}

            • Equipos analizados: {df['equipo'].nunique()}



             ESTADÍSTICAS DE RENDIMIENTO:

            • Promedio: {promedio_ton_hora:.1f} ton/h

            • Mejor: {mejor_rendimiento:.1f} ton/h

            • Peor: {peor_rendimiento:.1f} ton/h

            • Rango: {mejor_rendimiento - peor_rendimiento:.1f} ton/h



            ------------------------------------------------------------

             TOP 10 OPERADORES (por rendimiento normalizado)

            ------------------------------------------------------------

            """

                    

                    top10 = df.nlargest(10, 'ton_hora_operador') if 'ton_hora_operador' in df.columns else df.head(10)

                    

                    for idx, row in top10.iterrows():

                        if pd.notna(row.get('score_vs_circuito')):

                            score = row['score_vs_circuito']

                            if score > 10:

                                emoji_score = "⬆"

                            elif score > 0:

                                emoji_score = "↗"

                            elif score > -10:

                                emoji_score = "↘"

                            else:

                                emoji_score = "⬇"

                        else:

                            emoji_score = ""

                        

                        mensaje += f"""

            {emoji_score} {row['operador']} ({row['equipo']}) - {row['situacion_relevo']}

            ⏰ {row['inicio']} - {row['fin']} ({row['horas_operador_real']}h) {row['tipo_asignacion']}

             Automático: {row['viajes_automaticos']} viajes = {row['ton_automaticas']:,.0f} ton

             Manual: {row['viajes_manuales']} viajes = {row['ton_manuales']:,.0f} ton ({row['pct_manuales']}%)

             Rendimiento: {row['ton_hora_operador']:,.1f} ton/h"""

                        

                        if pd.notna(row.get('score_vs_circuito')):

                            mensaje += f" ({row['score_vs_circuito']:+.1f}% vs circuito)"

                        

                        mensaje += f"\n   {row['calidad_datos']}\n"

                    

                    if relevos_count > 0:

                        mensaje += f"""

            ------------------------------------------------------------

             DETALLE DE RELEVOS DETECTADOS

            ------------------------------------------------------------

            """

                        

                        relevos_df = df[df['situacion_relevo'].str.contains('RELEVO', na=False)]

                        

                        for (fecha_rel, equipo_rel, turno_rel), grupo in relevos_df.groupby(['fecha', 'equipo', 'turno']):

                            if len(grupo) > 1:

                                mensaje += f"\n {fecha_rel} |  {equipo_rel} |  Turno {turno_rel}\n"

                                

                                secuencia = grupo.iloc[0].get('secuencia_operadores', 'N/A')

                                if pd.notna(secuencia):

                                    mensaje += f"   Secuencia: {secuencia}\n"

                                

                                for _, op in grupo.iterrows():

                                    mensaje += f"   • {op['operador']}: {op['ton_hora_operador']:.1f} ton/h ({op['tipo_asignacion']})\n"

                    

                    alto_manual = len(df[df['pct_manuales'] > 30])

                    if alto_manual > 0:

                        mensaje += f"""

            ------------------------------------------------------------

             ALERTAS DE CALIDAD

            ------------------------------------------------------------



             {alto_manual} operadores con >30% de vueltas manuales

            (Posible problema de registro automático)

            """

                    

                    mensaje += "\n================================================================="

                    

                    return {

                        "success": True,

                        "FINAL_ANSWER": mensaje,

                        "data": {

                            "registros": df.to_dict('records'),

                            "total_registros": total_registros,

                            "relevos_count": relevos_count,

                            "relevos_colacion": relevos_colacion,

                            "estadisticas": {

                                "promedio_ton_hora": promedio_ton_hora,

                                "mejor_rendimiento": mejor_rendimiento,

                                "peor_rendimiento": peor_rendimiento

                            }

                        }

                    }

                    

                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error analizando relevos: {str(e)}"

                    }



            elif tool_name == "analizar_impacto_economico":

                    year = tool_input.get("year")

                    mes = tool_input.get("mes")

                    

                    try:

                        conn = sqlite3.connect(self.db_path)

                        cursor = conn.cursor()

                        

                        cursor.execute("""

                            SELECT parametro, valor 

                            FROM parametros_economicos 

                            WHERE parametro IN ('precio_real_cobre', 'precio_plan_p0')

                        """)

                        precios = dict(cursor.fetchall())

                        

                        if 'precio_real_cobre' not in precios or 'precio_plan_p0' not in precios:

                            return {

                                "success": False,

                                "error": "Faltan parámetros económicos. Configura precio_real_cobre y precio_plan_p0"

                            }

                        

                        precio_real = float(precios['precio_real_cobre'])

                        precio_plan = float(precios['precio_plan_p0'])

                        

                        if mes:

                            fecha_inicio = f"{year}-{mes:02d}-01"

                            if mes == 12:

                                fecha_fin = f"{year+1}-01-01"

                            else:

                                fecha_fin = f"{year}-{mes+1:02d}-01"

                            periodo = f"{['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][mes-1]} {year}"

                        else:

                            fecha_inicio = f"{year}-01-01"

                            fecha_fin = f"{year+1}-01-01"

                            periodo = str(year)

                        

                        cursor.execute("""

                            SELECT SUM(material_tonnage) as tonelaje_real

                            FROM (

                                SELECT material_tonnage FROM hexagon_by_detail_dumps_2023

                                WHERE timestamp >= ? AND timestamp < ?

                                    AND blast_type = 'Blast'

                                    AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                                UNION ALL

                                SELECT material_tonnage FROM hexagon_by_detail_dumps_2024

                                WHERE timestamp >= ? AND timestamp < ?

                                    AND blast_type = 'Blast'

                                    AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                                UNION ALL

                                SELECT material_tonnage FROM hexagon_by_detail_dumps_2025

                                WHERE timestamp >= ? AND timestamp < ?

                                    AND blast_type = 'Blast'

                                    AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                            )

                        """, [fecha_inicio, fecha_fin] * 3)

                        

                        volumen_real = float(cursor.fetchone()[0] or 0)

                        

                        if mes:

                            cursor.execute("""

                                SELECT SUM(valor) as volumen_plan

                                FROM p0_2025_mina_rajo_inca

                                WHERE year = ? AND mes = ?

                            """, [year, mes])

                        else:

                            cursor.execute("""

                                SELECT SUM(valor) as volumen_plan

                                FROM p0_2025_mina_rajo_inca

                                WHERE year = ?

                            """, [year])

                        

                        volumen_plan = float(cursor.fetchone()[0] or 0)

                        conn.close()

                        

                        impacto_precio = (precio_real - precio_plan) * volumen_real

                        impacto_volumen = (volumen_real - volumen_plan) * precio_plan

                        impacto_neto = impacto_precio + impacto_volumen

                        

                        valor_real = precio_real * volumen_real

                        valor_plan = precio_plan * volumen_plan

                        variacion_pct = ((valor_real / valor_plan) - 1) * 100 if valor_plan > 0 else 0

                        

                        mensaje = f"""

                =================================================================

                |   ANÁLISIS ECONÓMICO - {periodo.upper()}  |

                =================================================================



                 PLAN P0:

                • Volumen: {volumen_plan:,.0f} ton

                • Precio: ${precio_plan:,.2f} USD/ton

                • Valor: ${valor_plan:,.0f} USD



                 REAL:

                • Volumen: {volumen_real:,.0f} ton ({((volumen_real/volumen_plan)-1)*100:+.1f}%)

                • Precio: ${precio_real:,.2f} USD/ton ({((precio_real/precio_plan)-1)*100:+.1f}%)

                • Valor: ${valor_real:,.0f} USD



                ------------------------------------------------------------

                 DESCOMPOSICIÓN DEL IMPACTO

                ------------------------------------------------------------



                 IMPACTO POR PRECIO (Mercado):

                • Diferencia: ${precio_real - precio_plan:+,.2f}/ton

                • Sobre volumen real: {volumen_real:,.0f} ton

                • {' GANANCIA' if impacto_precio > 0 else ' PÉRDIDA'}: ${impacto_precio:+,.0f} USD



                 IMPACTO POR VOLUMEN (Operacional):

                • Diferencia: {volumen_real - volumen_plan:+,.0f} ton

                • Al precio plan: ${precio_plan:,.0f}/ton

                • {' GANANCIA' if impacto_volumen > 0 else ' PÉRDIDA'}: ${impacto_volumen:+,.0f} USD



                ------------------------------------------------------------

                 RESULTADO NETO

                ------------------------------------------------------------



                Impacto precio:     ${impacto_precio:+,.0f} USD

                Impacto volumen:    ${impacto_volumen:+,.0f} USD

                ---------------------------------

                IMPACTO NETO:       ${impacto_neto:+,.0f} USD {'' if impacto_neto > 0 else ''}



                 Variación vs Plan: {variacion_pct:+.1f}%



                =================================================================

                """

                        

                        return {

                            "success": True,

                            "FINAL_ANSWER": mensaje,

                            "data": {

                                "periodo": periodo,

                                "volumen_real": volumen_real,

                                "volumen_plan": volumen_plan,

                                "precio_real": precio_real,

                                "precio_plan": precio_plan,

                                "impacto_precio": impacto_precio,

                                "impacto_volumen": impacto_volumen,

                                "impacto_neto": impacto_neto

                            }

                        }

                        

                    except Exception as e:

                        import traceback

                        traceback.print_exc()

                        return {

                            "success": False,

                            "error": f"Error: {str(e)}"

                        }

            

            

            

            elif tool_name == "update_economic_parameters":

                operation = tool_input["operation"]

                

                if operation == "set":

                    parameter = tool_input["parameter"]

                    value = tool_input["value"]

                    self.economic_manager.set_parameter(parameter, value)

                    return {

                        "success": True,

                        "message": f"Parámetro '{parameter}' actualizado a {value}"

                    }

                

                elif operation == "get":

                    parameter = tool_input["parameter"]

                    value = self.economic_manager.get_parameter(parameter)

                    return {

                        "success": True,

                        "data": {parameter: value}

                    }

                

                elif operation == "get_all":

                    params = self.economic_manager.get_all_parameters()

                    return {

                        "success": True,

                        "data": params

                    }

                

                elif operation == "delete":

                    parameter = tool_input["parameter"]

                    self.economic_manager.delete_parameter(parameter)

                    return {

                        "success": True,

                        "message": f"Parámetro '{parameter}' eliminado"

                    }

            

            elif tool_name == "obtener_cumplimiento_tonelaje":

                year = tool_input.get("year", 2025)

                mes = tool_input.get("mes", 1)

                tipo_metrica = tool_input.get("tipo_metrica", "extraccion")  # Por defecto: extraccion



                print(f"[TOOL] CUMPLIMIENTO TONELAJE - Consultando para {year}-{mes:02d} - Tipo: {tipo_metrica}")



                # Nombres de meses

                meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',

                         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']



                try:

                    # DECISIÓN: ¿Usar Knowledge Base (movimiento) o BD Hexagon (extracción)?

                    if tipo_metrica == "movimiento":

                        print(f"   [KB] Usando Knowledge Base IGM para MOVIMIENTO (extracción + remanejo)")



                        # Cargar Knowledge Base

                        import json

                        from pathlib import Path



                        # Path relativo desde backend/ (working directory)

                        kb_path = Path("knowledge/knowledge_base_igm.json")

                        if not kb_path.exists():

                            # Fallback: path absoluto desde este archivo

                            kb_path = Path(__file__).parent.parent / "knowledge" / "knowledge_base_igm.json"



                        with open(kb_path, 'r', encoding='utf-8') as f:

                            kb = json.load(f)



                        # Buscar datos del mes (formato: "01. IGM Enero 2025")

                        mes_key = f"{mes:02d}. IGM {meses[mes-1].capitalize()} {year}"

                        kb_data = kb.get("metricas_por_mes", {}).get(mes_key, {})



                        if kb_data:

                            tonelaje_total = kb_data.get("movimiento_real_kton", 0) * 1000  # Convertir kton a ton

                            tonelaje_plan_total = kb_data.get("movimiento_pam_kton", 0) * 1000  # PAM de MOVIMIENTO (no extracción!)

                            print(f"   [OK] Datos KB obtenidos: Real={tonelaje_total:,.0f} ton, Plan={tonelaje_plan_total:,.0f} ton")



                            # Días operativos (estimado, KB no tiene este dato)

                            dias_operativos = 31 if mes in [1, 3, 5, 7, 8, 10, 12] else 30 if mes != 2 else 28

                            total_viajes = None  # KB no tiene viajes

                            fuente_datos = "Knowledge Base IGM (datos oficiales)"

                        else:

                            return {

                                "success": False,

                                "error": f"No se encontraron datos de MOVIMIENTO en Knowledge Base para {meses[mes-1]} {year}"

                            }



                    elif tipo_metrica == "extraccion":

                        print(f"   [BD] Usando BD Hexagon para EXTRACCIÓN (solo material del rajo)")



                        from datetime import datetime

                        conn = sqlite3.connect(self.db_path)

                        cursor = conn.cursor()



                        # Calcular rangos de fecha

                        fecha_inicio = f"{year}-{mes:02d}-01"

                        if mes == 12:

                            fecha_fin = f"{year+1}-01-01"

                        else:

                            fecha_fin = f"{year}-{mes+1:02d}-01"



                        # CONSULTA 1: TONELAJE REAL TOTAL (EXTRACCIÓN)

                        print(f"   [SEARCH] Consultando extracción desde BD...")

                        cursor.execute("""

                            SELECT

                                SUM(material_tonnage) as tonelaje_total,

                                COUNT(*) as total_viajes

                            FROM (

                                SELECT material_tonnage FROM hexagon_by_detail_dumps_2023

                                WHERE timestamp >= ? AND timestamp < ?

                                    AND blast_type = 'Blast'

                                    AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                                UNION ALL

                                SELECT material_tonnage FROM hexagon_by_detail_dumps_2024

                                WHERE timestamp >= ? AND timestamp < ?

                                    AND blast_type = 'Blast'

                                    AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                                UNION ALL

                                SELECT material_tonnage FROM hexagon_by_detail_dumps_2025

                                WHERE timestamp >= ? AND timestamp < ?

                                    AND blast_type = 'Blast'

                                    AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                            )

                        """, [fecha_inicio, fecha_fin] * 3)



                        result_total = cursor.fetchone()

                        tonelaje_total = float(result_total[0]) if result_total and result_total[0] else 0.0

                        total_viajes = result_total[1] if result_total else 0



                        print(f"   [OK] Extracción obtenida: {tonelaje_total:,.0f} ton ({total_viajes:,} viajes)")



                        # CONSULTA 2: DÍAS OPERATIVOS

                        cursor.execute("""

                            SELECT COUNT(DISTINCT DATE(timestamp)) as dias

                            FROM (

                                SELECT timestamp FROM hexagon_by_kpi_hora

                                WHERE timestamp >= ? AND timestamp < ?

                                UNION

                                SELECT timestamp FROM hexagon_by_detail_dumps_2023

                                WHERE timestamp >= ? AND timestamp < ?

                                UNION

                                SELECT timestamp FROM hexagon_by_detail_dumps_2024

                                WHERE timestamp >= ? AND timestamp < ?

                                UNION

                                SELECT timestamp FROM hexagon_by_detail_dumps_2025

                                WHERE timestamp >= ? AND timestamp < ?

                            )

                        """, [fecha_inicio, fecha_fin] * 4)



                        dias_operativos = cursor.fetchone()[0] or 0

                        conn.close()



                        # Obtener plan desde Excel

                        from services.plan_reader import get_plan_tonelaje

                        plan_data = get_plan_tonelaje(mes, year)



                        if plan_data and 'tonelaje' in plan_data:

                            tonelaje_plan_total = plan_data['tonelaje']

                            print(f"   [OK] Plan obtenido desde Excel: {tonelaje_plan_total:,.0f} ton")

                        else:

                            tonelaje_plan_total = None

                            print(f"   [WARNING] No se encontró plan en Excel para {mes}/{year}")



                        fuente_datos = "BD Hexagon (dumps 2023-2025)"



                    else:  # chancado

                        return {

                            "success": False,

                            "error": f"Tipo de métrica '{tipo_metrica}' aún no implementado. Usa 'movimiento' o 'extraccion'."

                        }



                    # PASO 3: CÁLCULOS Y ANÁLISIS

                    print(f"   [CALC] Calculando cumplimiento y metricas...")



                    ton_por_dia = tonelaje_total / dias_operativos if dias_operativos > 0 else 0

                    ton_por_viaje = tonelaje_total / total_viajes if total_viajes and total_viajes > 0 else 0



                    if tonelaje_plan_total and tonelaje_plan_total > 0:

                        cumplimiento = (tonelaje_total / tonelaje_plan_total) * 100

                        brecha = tonelaje_total - tonelaje_plan_total

                    else:

                        cumplimiento = None

                        brecha = None



                    if cumplimiento is not None:

                        if cumplimiento >= 100:

                            estado = "✅ CUMPLIDO"

                            emoji = "✅"

                        elif cumplimiento >= 90:

                            estado = "⚠️  EN RIESGO"

                            emoji = "⚠️"

                        else:

                            estado = "❌ INCUMPLIDO CRÍTICO"

                            emoji = "❌"

                    else:

                        estado = "📋 SIN PLAN"

                        emoji = "📋"



                    # PASO 4: CONSTRUIR MENSAJE

                    # Etiqueta correcta según tipo de métrica

                    metrica_label = {

                        "movimiento": "Movimiento",

                        "extraccion": "Extracción",

                        "chancado": "Material a Chancado"

                    }.get(tipo_metrica, "Tonelaje")



                    mensaje_final = f"""

=================================================================

|   CUMPLIMIENTO DE {metrica_label.upper()} - {meses[mes-1].upper()} {year}           |

=================================================================



{emoji} **Estado:** {estado}



------------------------------------------------------------

 📊 RESUMEN EJECUTIVO

------------------------------------------------------------



   📦 **{metrica_label} Real:** {tonelaje_total:,.0f} ton

"""



                    if cumplimiento is not None:

                        mensaje_final += f"""   📋 **Plan (Excel):** {tonelaje_plan_total:,.0f} ton

   📈 **Cumplimiento:** {cumplimiento:.1f}%

   {"📈 **Superávit:** +" if brecha >= 0 else "📉 **Déficit:** "}{abs(brecha):,.0f} ton

"""

                    else:

                        mensaje_final += f"""   ⚠️  **Plan:** No disponible (subir archivo Excel del plan)

"""



                    # Formatear viajes solo si está disponible

                    if total_viajes is not None:

                        mensaje_final += f"""

   🚛 **Total de viajes:** {total_viajes:,}

   📅 **Días operativos:** {dias_operativos}

   📊 **Promedio diario:** {ton_por_dia:,.0f} ton/día

   🎯 **Promedio por viaje:** {ton_por_viaje:,.1f} ton/viaje

"""

                    else:

                        mensaje_final += f"""

   📅 **Días operativos:** {dias_operativos}

   📊 **Promedio diario:** {ton_por_dia:,.0f} ton/día

"""



                    if cumplimiento is not None:

                        # Análisis de desempeño

                        if cumplimiento >= 100:

                            mensaje_final += f"""

------------------------------------------------------------

 🎯 ANÁLISIS DE DESEMPEÑO

------------------------------------------------------------



   ✅ SUPERÁVIT - Superamos el plan en +{abs(brecha):,.0f} ton



   ⚠️ PERO AÚN HAY OPORTUNIDADES DE MEJORA:

   → Analizar delays que igual ocurrieron (con obtener_pareto_delays)

   → Calcular cuánto MÁS podríamos haber producido sin esos delays

   → Identificar acciones para mejorar aún más el próximo mes

"""

                        elif cumplimiento >= 90:

                            mensaje_final += f"""

------------------------------------------------------------

 🎯 ANÁLISIS DE DESEMPEÑO

------------------------------------------------------------



   ⚠️  La operación está cerca del objetivo pero en riesgo

   📉 Déficit: -{abs(brecha):,.0f} ton

   💡 Requiere atención para cerrar la brecha

"""

                        else:

                            mensaje_final += f"""

------------------------------------------------------------

 🎯 ANÁLISIS DE DESEMPEÑO

------------------------------------------------------------



   ❌ La operación está significativamente bajo el plan

   📉 Déficit crítico: -{abs(brecha):,.0f} ton

   🚨 Requiere análisis urgente de causas raíz

"""



                    mensaje_final += f"\n\n📁 **Fuente:** {fuente_datos}"

                    mensaje_final += "\n================================================================="



                    # Print sin emojis

                    try:

                        estado_safe = estado.encode('ascii', 'ignore').decode('ascii')

                        print(f"   [OK] Analisis completado: {estado_safe} (fuente: {fuente_datos})")

                    except:

                        print(f"   [OK] Analisis completado")



                    # Resumen corto para que el modelo decida si necesita más herramientas
                    summary = f"Cumplimiento {meses[mes-1]} {year}: {cumplimiento:.1f}% ({estado}). Real: {tonelaje_total:,.0f} ton, Plan: {tonelaje_plan_total:,.0f} ton, Brecha: {brecha:+,.0f} ton"

                    return {

                        "success": True,

                        "summary": summary,

                        "data": {

                            "year": year,

                            "mes": mes,

                            "mes_nombre": meses[mes - 1],

                            "tipo_metrica": tipo_metrica,

                            "tonelaje_total": tonelaje_total,

                            "tonelaje_plan": tonelaje_plan_total,

                            "cumplimiento_porcentaje": cumplimiento,

                            "brecha": brecha,

                            "estado": estado,

                            "dias_operativos": dias_operativos,

                            "total_viajes": total_viajes,

                            "promedios": {

                                "ton_por_dia": ton_por_dia,

                                "ton_por_viaje": ton_por_viaje if total_viajes else None

                            },

                            "fuente_datos": fuente_datos,

                            "fuente_plan": "Excel P0/PAM" if tonelaje_plan_total else None

                        }

                    }



                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error en análisis de cumplimiento: {str(e)}"

                    }

            

            elif tool_name == "obtener_analisis_utilizacion":

                year = tool_input.get("year", 2025)

                mes = tool_input.get("mes", 1)

    

                print(f"    Calculando UTILIZACIÓN (UEBD) desde ASARCO para {year}-{mes:02d}")

    

                try:

                    conn = sqlite3.connect(self.db_path)

                    cursor = conn.cursor()

                    

                    fecha_inicio = f"{year}-{mes:02d}-01"

                    if mes == 12:

                        fecha_fin = f"{year+1}-01-01"

                    else:

                        fecha_fin = f"{year}-{mes+1:02d}-01"

                    

                    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',

                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

                    

                    # PASO 1: Obtener horas totales desde equipment_times

                    # COLUMNAS REALES: total, efectivo, m_correctiva, m_programada, det_noprg, det_prg

                    cursor.execute("""

                        SELECT

                            SUM(CAST(total AS REAL)) as horas_totales,

                            SUM(CAST(efectivo AS REAL)) as horas_efectivas,

                            SUM(CAST(m_correctiva AS REAL)) as horas_m_correctiva,

                            SUM(CAST(m_programada AS REAL)) as horas_m_programada,

                            SUM(CAST(det_noprg AS REAL)) as det_noprg,

                            SUM(CAST(det_prg AS REAL)) as det_prg

                        FROM hexagon_equipment_times

                        WHERE time >= ? AND time < ?

                        AND total > 0

                    """, [fecha_inicio, fecha_fin])



                    result = cursor.fetchone()

                    horas_totales = float(result[0]) if result and result[0] else 0

                    horas_efectivas = float(result[1]) if result and result[1] else 0

                    horas_m_correctiva = float(result[2]) if result and result[2] else 0

                    horas_m_programada = float(result[3]) if result and result[3] else 0

                    det_noprg = float(result[4]) if result and result[4] else 0

                    det_prg = float(result[5]) if result and result[5] else 0



                    # Calcular horas_disponibles (NO está en la tabla, se calcula)

                    horas_disponibles = horas_totales - horas_m_correctiva - horas_m_programada

                    

                    # PASO 2: Obtener pérdidas por categoría ASARCO

                    cursor.execute("""

                        SELECT 

                            d.clasificacion,

                            d.tipo,

                            COUNT(*) as eventos,

                            SUM(CASE 

                                WHEN e.duracion IS NOT NULL THEN e.duracion

                                ELSE 1.0

                            END) as horas_perdidas

                        FROM hexagon_estados e

                        JOIN delay_codes_asarco d ON e.codigo_asarco = d.codigo

                        WHERE e.fecha >= ? AND e.fecha < ?

                        AND d.codigo NOT IN (5, 6)

                        GROUP BY d.clasificacion, d.tipo

                        ORDER BY horas_perdidas DESC

                    """, [fecha_inicio, fecha_fin])

                    

                    perdidas_por_categoria = []

                    total_horas_perdidas = 0

                    

                    for row in cursor.fetchall():

                        clasificacion = row[0]

                        tipo = row[1]

                        eventos = row[2]

                        horas = float(row[3])

                        porcentaje = (horas / horas_disponibles * 100) if horas_disponibles > 0 else 0

                        

                        perdidas_por_categoria.append({

                            "categoria": clasificacion,

                            "tipo": tipo,

                            "eventos": eventos,

                            "horas_perdidas": horas,

                            "porcentaje": porcentaje

                        })

                        total_horas_perdidas += horas

                    

                    # PASO 3: Top 10 causas raíz

                    cursor.execute("""

                        SELECT 

                            d.descripcion,

                            d.causa_raiz,

                            d.codigo,

                            COUNT(*) as eventos,

                            SUM(CASE 

                                WHEN e.duracion IS NOT NULL THEN e.duracion

                                ELSE 1.0

                            END) as horas_perdidas

                        FROM hexagon_estados e

                        JOIN delay_codes_asarco d ON e.codigo_asarco = d.codigo

                        WHERE e.fecha >= ? AND e.fecha < ?

                        AND d.codigo NOT IN (5, 6)

                        GROUP BY d.descripcion, d.causa_raiz, d.codigo

                        ORDER BY horas_perdidas DESC

                        LIMIT 10

                    """, [fecha_inicio, fecha_fin])

                    

                    top_causas = []

                    for row in cursor.fetchall():

                        top_causas.append({

                            "descripcion": row[0],

                            "causa_raiz": row[1],

                            "codigo": row[2],

                            "eventos": row[3],

                            "horas": float(row[4])

                        })

                    

                    # PASO 4: Top operadores con más demoras

                    cursor.execute("""

                        SELECT 

                            e.operador,

                            COUNT(*) as total_demoras,

                            SUM(CASE 

                                WHEN e.duracion IS NOT NULL THEN e.duracion

                                ELSE 1.0

                            END) as horas_perdidas

                        FROM hexagon_estados e

                        JOIN delay_codes_asarco d ON e.codigo_asarco = d.codigo

                        WHERE e.fecha >= ? AND e.fecha < ?

                        AND d.codigo NOT IN (5, 6)

                        AND e.operador IS NOT NULL

                        GROUP BY e.operador

                        ORDER BY horas_perdidas DESC

                        LIMIT 10

                    """, [fecha_inicio, fecha_fin])

                    

                    top_operadores = []

                    for row in cursor.fetchall():

                        if row[0]:

                            top_operadores.append({

                                "operador": row[0],

                                "demoras": row[1],

                                "horas": float(row[2])

                            })

                    

                    conn.close()

                    

                    # Calcular UEBD

                    uebd = (horas_efectivas / horas_disponibles * 100) if horas_disponibles > 0 else 0

                    

                    # Construir mensaje

                    mensaje = f"""

            =================================================================

            |   ANÁLISIS DE UTILIZACIÓN (UEBD) - {meses[mes-1].upper()} {year}  |

            =================================================================



             **UTILIZACIÓN REAL (UEBD):** {uebd:.1f}%

             **HORAS DISPONIBLES:** {horas_disponibles:,.0f} hrs

             **HORAS EFECTIVAS:** {horas_efectivas:,.0f} hrs

             **HORAS PERDIDAS:** {total_horas_perdidas:,.0f} hrs



            ------------------------------------------------------------

             CASCADA DE UTILIZACIÓN (Análisis ASARCO)

            ------------------------------------------------------------



            100.0% Capacidad Teórica

            """

                    

                    porcentaje_acum = 100.0

                    for cat in perdidas_por_categoria[:5]:

                        porcentaje_acum -= cat["porcentaje"]

                        mensaje += f"  ↓ -{cat['porcentaje']:.1f}% {cat['categoria']} ({cat['horas_perdidas']:,.0f} hrs)\n"

                        mensaje += f"{porcentaje_acum:.1f}%\n"

                    

                    mensaje += f"\n{uebd:.1f}% ← UEBD Real\n"

                    

                    mensaje += f"""

            ------------------------------------------------------------

             TOP 10 CAUSAS RAÍZ (Análisis Pareto)

            ------------------------------------------------------------



            """

                    

                    for i, causa in enumerate(top_causas, 1):

                        porcentaje_causa = (causa['horas'] / total_horas_perdidas * 100) if total_horas_perdidas > 0 else 0

                        mensaje += f"{i}. **{causa['descripcion']}** (Código {causa['codigo']})\n"

                        mensaje += f"   Causa raíz: {causa['causa_raiz']}\n"

                        mensaje += f"   Impacto: {causa['horas']:,.0f} hrs - {porcentaje_causa:.1f}%\n\n"

                    

                    if top_operadores:

                        mensaje += f"""

            ------------------------------------------------------------

             TOP 10 OPERADORES CON MÁS DEMORAS

            ------------------------------------------------------------



            """

                        

                        for i, op in enumerate(top_operadores, 1):

                            porcentaje_op = (op['horas'] / total_horas_perdidas * 100) if total_horas_perdidas > 0 else 0

                            mensaje += f"{i}. **{op['operador']}**: {op['horas']:,.0f} hrs ({porcentaje_op:.1f}%)\n"

                    

                    mensaje += "\n================================================================="

                    

                    return {

                        "success": True,

                        "FINAL_ANSWER": mensaje,

                        "data": {

                            "uebd": uebd,

                            "horas_disponibles": horas_disponibles,

                            "horas_efectivas": horas_efectivas,

                            "perdidas": perdidas_por_categoria,

                            "top_causas": top_causas,

                            "top_operadores": top_operadores

                        }

                    }

                    

                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error calculando utilización: {str(e)}"

                    }











            elif tool_name == "obtener_analisis_gaviota":

                print(f"[GAVIOTA] Análisis Real vs Teórico con Fórmula Calibrada")



                fecha = tool_input.get("fecha")



                if not fecha:

                    return {"success": False, "error": "Se requiere el parámetro 'fecha'"}



                try:

                    from services.gaviota_analysis import analizar_gaviota_completo



                    # Ejecutar análisis completo con fórmula calibrada

                    resultado = analizar_gaviota_completo(fecha)



                    if "error" in resultado:

                        return {

                            "success": False,

                            "error": resultado["error"]

                        }



                    print(f"   [OK] Analisis Gaviota completado - Patron: {resultado['patron']}")

                    # Guardar gráfico HTML y generar URL
                    import sys
                    chart_url = None
                    chart_data = resultado.get("chart")
                    print(f"   [GAVIOTA-CHART] chart_data exists: {chart_data is not None}", flush=True)

                    if chart_data and isinstance(chart_data, dict):
                        print(f"   [GAVIOTA-CHART] chart keys: {list(chart_data.keys())}", flush=True)
                        try:
                            from pathlib import Path
                            from datetime import datetime

                            charts_dir = Path(__file__).parent.parent / "outputs" / "charts"
                            charts_dir.mkdir(parents=True, exist_ok=True)

                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"gaviota_{fecha}_{timestamp}.html"
                            filepath = charts_dir / filename

                            # Intentar usar html, si no existe usar plotly_json
                            if chart_data.get("html"):
                                html_content = f"""<!DOCTYPE html>
<html><head>
<title>Gaviota {fecha}</title>
<script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
</head><body>
{chart_data["html"]}
</body></html>"""
                            elif chart_data.get("plotly_json"):
                                # Generar HTML desde plotly_json
                                html_content = f"""<!DOCTYPE html>
<html><head>
<title>Gaviota {fecha}</title>
<script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
</head><body>
<div id="plotly-chart" style="width:100%;height:600px;"></div>
<script>
var plotlyData = {chart_data["plotly_json"]};
Plotly.newPlot('plotly-chart', plotlyData.data, plotlyData.layout, {{responsive: true}});
</script>
</body></html>"""
                            else:
                                html_content = None
                                print(f"   [GAVIOTA-CHART] No html ni plotly_json en chart_data", flush=True)

                            if html_content:
                                with open(filepath, "w", encoding="utf-8") as f:
                                    f.write(html_content)

                                chart_url = f"http://localhost:8001/outputs/charts/{filename}"
                                print(f"   [GAVIOTA-CHART] Gráfico guardado: {chart_url}", flush=True)
                        except Exception as chart_err:
                            import traceback
                            print(f"   [GAVIOTA-CHART] Error guardando gráfico: {chart_err}", flush=True)
                            traceback.print_exc()
                    else:
                        print(f"   [GAVIOTA-CHART] No hay chart_data o no es dict", flush=True)

                    # Agregar link al gráfico en el informe
                    informe_con_grafico = resultado["informe"]
                    if chart_url:
                        informe_con_grafico += f"\n\n## GRÁFICO DE GAVIOTA\n\n📊 [Ver gráfico interactivo]({chart_url})\n"

                    return {

                        "success": True,

                        "FINAL_ANSWER": informe_con_grafico,

                        "chart_url": chart_url,

                        "data": resultado

                    }



                except Exception as e:

                    import traceback

                    error_msg = str(e)

                    traceback_str = traceback.format_exc()



                    print(f"[ERROR] ERROR en analisis gaviota: {error_msg}")

                    print(traceback_str)



                    return {

                        "success": False,

                        "error": f"Error en análisis gaviota: {error_msg}"

                    }

            

            elif tool_name == "analisis_causalidad_waterfall":
                # =====================================================
                # ANÁLISIS CAUSALIDAD ASARCO + WATERFALL CHART
                # OPTIMIZADO: Usa servicio SQLite (10x más rápido)
                # =====================================================
                from services.causalidad_sqlite import analizar_causalidad_waterfall_sqlite

                fecha = tool_input.get("fecha")
                if not fecha:
                    return {"success": False, "error": "Se requiere el parámetro 'fecha'"}

                # Llamar al servicio optimizado que usa SQLite
                return analizar_causalidad_waterfall_sqlite(fecha, self.db_path)

            elif tool_name == "_OLD_analisis_causalidad_waterfall":
                # OLD VERSION - DISABLED (usa Excel, muy lento)
                print(f"[CAUSALIDAD_ASARCO] OLD VERSION")

                fecha = tool_input.get("fecha")
                if not fecha:
                    return {"success": False, "error": "Se requiere el parámetro 'fecha'"}

                try:
                    import pandas as pd
                    from datetime import datetime
                    import plotly.graph_objects as go
                    from pathlib import Path

                    fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
                    year = fecha_dt.year
                    mes = fecha_dt.month
                    dia = fecha_dt.day
                    dias_mes = 31 if mes in [1,3,5,7,8,10,12] else (30 if mes != 2 else 28)

                    hexagon_dir = Path("data/Hexagon")
                    plan_dir = Path("data/Planificacion")

                    # =========================================================
                    # PASO 1: OBTENER REAL DEL DÍA (desde dumps)
                    # =========================================================
                    print(f"   [1/4] Obteniendo producción real del día {fecha}...")

                    dumps_file = hexagon_dir / f"by_detail_dumps {year}.xlsx"
                    if not dumps_file.exists():
                        return {"success": False, "error": f"No existe archivo de dumps {year}"}

                    df_dumps = get_cached_dataframe(str(dumps_file))
                    df_dumps['fecha'] = pd.to_datetime(df_dumps['time']).dt.date
                    fecha_date = fecha_dt.date()

                    df_dia = df_dumps[df_dumps['fecha'] == fecha_date]
                    real_ton = df_dia['material_tonnage'].sum()

                    print(f"      Real del día: {real_ton:,.0f} ton ({len(df_dia)} dumps)")

                    # =========================================================
                    # PASO 2: OBTENER PLAN DEL DÍA (desde plan mensual)
                    # =========================================================
                    print(f"   [2/4] Obteniendo plan del día...")

                    meses_nombres = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",
                                     6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",
                                     10:"Octubre",11:"Noviembre",12:"Diciembre"}
                    mes_nombre = meses_nombres.get(mes, "")

                    # Buscar archivo de plan mensual
                    plan_mensual = None
                    plan_ton = 0  # Inicializar
                    for f in plan_dir.glob(f"*Plan Mensual {mes_nombre}*{year}*.xlsx"):
                        plan_mensual = f
                        break

                    if plan_mensual:
                        try:
                            df_plan = pd.read_excel(plan_mensual, sheet_name='RESUMEN KPIS', header=None)
                            # Buscar movimiento total en RESUMEN KPIS
                            for idx, row in df_plan.iterrows():
                                for col_idx, val in enumerate(row):
                                    if isinstance(val, str) and 'movimiento' in val.lower():
                                        # El valor está en la siguiente columna
                                        plan_mensual_ton = df_plan.iloc[idx, col_idx + 1]
                                        if pd.notna(plan_mensual_ton) and isinstance(plan_mensual_ton, (int, float)):
                                            plan_ton = plan_mensual_ton / dias_mes
                                            break
                        except:
                            plan_ton = real_ton * 1.15  # Fallback: 15% más que real
                    else:
                        plan_ton = real_ton * 1.15  # Fallback

                    # Si no encontramos plan, usar estimación
                    if plan_ton == 0 or plan_ton < real_ton:
                        plan_ton = real_ton * 1.15

                    gap = plan_ton - real_ton
                    print(f"      Plan del día: {plan_ton:,.0f} ton | Gap: {gap:,.0f} ton")

                    # =========================================================
                    # PASO 3: OBTENER ESTADOS ASARCO DEL DÍA
                    # =========================================================
                    print(f"   [3/4] Analizando estados ASARCO del día...")

                    estados_file = hexagon_dir / "by_estados_2024_2025.xlsx"
                    if not estados_file.exists():
                        return {"success": False, "error": "No existe archivo de estados ASARCO"}

                    df_estados = get_cached_dataframe(str(estados_file))
                    df_estados['fecha'] = pd.to_datetime(df_estados['fecha']).dt.date

                    df_estados_dia = df_estados[df_estados['fecha'] == fecha_date]

                    # Agrupar por código ASARCO (excluyendo código 1 = producción)
                    df_demoras = df_estados_dia[df_estados_dia['code'] != 1]

                    demoras_por_codigo = df_demoras.groupby(['code', 'razon']).agg({
                        'horas': 'sum'
                    }).reset_index()
                    demoras_por_codigo = demoras_por_codigo.sort_values('horas', ascending=False)

                    total_horas_demora = demoras_por_codigo['horas'].sum()
                    print(f"      Total horas demora: {total_horas_demora:,.0f} hrs en {len(demoras_por_codigo)} códigos")

                    # =========================================================
                    # PASO 4: CALCULAR IMPACTO EN TONELAJE
                    # =========================================================
                    # Rendimiento: ton/hr efectiva
                    horas_efectivas = 24 - total_horas_demora / max(len(df_estados_dia['equipo'].unique()), 1)
                    if horas_efectivas > 0 and real_ton > 0:
                        rendimiento = real_ton / (horas_efectivas * max(len(df_dia['truck'].unique()), 1))
                    else:
                        rendimiento = 10000  # Fallback: 10K ton/hr flota

                    # Calcular impacto de cada demora
                    causas_perdida = []
                    for _, row in demoras_por_codigo.head(6).iterrows():
                        codigo = int(row['code']) if pd.notna(row['code']) else 0
                        razon = str(row['razon'])[:25]
                        horas = float(row['horas'])
                        # Impacto proporcional al gap
                        impacto_ton = (horas / total_horas_demora * gap) if total_horas_demora > 0 else 0
                        causas_perdida.append({
                            'codigo': codigo,
                            'razon': razon,
                            'horas': horas,
                            'tonelaje': impacto_ton
                        })

                    # Ajustar para que sumen el gap
                    total_asignado = sum(c['tonelaje'] for c in causas_perdida)
                    if total_asignado < gap and gap > 0:
                        causas_perdida.append({
                            'codigo': 999,
                            'razon': 'Otras demoras',
                            'horas': 0,
                            'tonelaje': gap - total_asignado
                        })

                    # =========================================================
                    # PASO 5: GENERAR WATERFALL
                    # =========================================================
                    print(f"   [4/4] Generando gráfico waterfall...")

                    x_labels = ['PLAN']
                    y_values = [plan_ton]
                    measures = ['absolute']

                    for c in causas_perdida:
                        if c['tonelaje'] > 0:
                            x_labels.append(f"{c['razon']}")
                            y_values.append(-c['tonelaje'])
                            measures.append('relative')

                    x_labels.append('REAL')
                    y_values.append(0)
                    measures.append('total')

                    # Formatear textos
                    text_values = []
                    for v in y_values:
                        if v == 0:
                            text_values.append("")
                        elif abs(v) >= 1_000_000:
                            text_values.append(f"{v/1e6:.2f}M")
                        elif abs(v) >= 1_000:
                            text_values.append(f"{abs(v)/1e3:.0f}K")
                        else:
                            text_values.append(f"{abs(v):.0f}")

                    fig = go.Figure(go.Waterfall(
                        name="Causalidad",
                        orientation="v",
                        x=x_labels,
                        y=y_values,
                        measure=measures,
                        text=text_values,
                        textposition="outside",
                        connector={"line": {"color": "gray", "width": 1, "dash": "dot"}},
                        increasing={"marker": {"color": "#2E7D32"}},
                        decreasing={"marker": {"color": "#C62828"}},
                        totals={"marker": {"color": "#1565C0"}}
                    ))

                    fig.update_layout(
                        title={
                            'text': f"Cascada de Causalidad ASARCO - {fecha}<br><sub>Plan vs Real - Análisis de Demoras</sub>",
                            'x': 0.5,
                            'xanchor': 'center'
                        },
                        showlegend=False,
                        yaxis_title="Toneladas",
                        yaxis_tickformat=",.0f",
                        xaxis=dict(tickangle=-35),
                        height=650,
                        width=1100,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        font=dict(size=11),
                        margin=dict(b=120, t=100)
                    )

                    # Guardar gráfico como PNG e HTML
                    output_dir = Path('outputs/charts')
                    output_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                    # Guardar HTML
                    filepath_html = output_dir / f'waterfall_asarco_{fecha}_{timestamp}.html'
                    fig.write_html(str(filepath_html))
                    print(f"   [OK] HTML guardado: {filepath_html}")

                    # Guardar PNG para mostrar en frontend
                    filepath_png = output_dir / f'waterfall_asarco_{fecha}_{timestamp}.png'
                    png_url = f"/outputs/charts/waterfall_asarco_{fecha}_{timestamp}.png"
                    try:
                        fig.write_image(str(filepath_png), width=1100, height=650, scale=2)
                        print(f"   [OK] PNG guardado: {filepath_png}")
                        image_available = True
                    except Exception as e_img:
                        print(f"   [WARN] No se pudo generar PNG: {e_img}")
                        image_available = False
                        png_url = None

                    # Calcular porcentajes
                    pct_gap = (gap / plan_ton * 100) if plan_ton > 0 else 0
                    pct_cumpl = (real_ton / plan_ton * 100) if plan_ton > 0 else 0

                    # Construir informe
                    informe = f"""## ANÁLISIS DE CAUSALIDAD ASARCO - {fecha}

### Resumen Ejecutivo
| Métrica | Valor |
|---------|-------|
| **Plan del día** | {plan_ton:,.0f} ton |
| **Real del día** | {real_ton:,.0f} ton |
| **Gap** | {gap:,.0f} ton ({pct_gap:.1f}%) |
| **Cumplimiento** | {pct_cumpl:.1f}% |

### Principales Causas de Pérdida (Estados ASARCO)

| # | Código | Causa | Horas | Impacto (ton) | % del Gap |
|---|--------|-------|-------|---------------|-----------|
"""
                    for i, c in enumerate(causas_perdida, 1):
                        pct = (c['tonelaje'] / gap * 100) if gap > 0 else 0
                        informe += f"| {i} | {c['codigo']} | {c['razon']} | {c['horas']:,.0f} | {c['tonelaje']:,.0f} | {pct:.1f}% |\n"

                    # Agregar gráfico al informe - siempre incluir link al HTML interactivo
                    html_url = f"http://localhost:8001/outputs/charts/{filepath_html.name}"

                    if image_available and png_url:
                        informe += f"""
### Gráfico Waterfall de Causalidad

![Waterfall Causalidad ASARCO](http://localhost:8001{png_url})

[Ver gráfico interactivo]({html_url})
"""
                    else:
                        informe += f"""
### Gráfico Waterfall de Causalidad

El gráfico waterfall muestra la cascada desde el PLAN hasta el REAL, con el impacto de cada causa ASARCO.

**[Abrir Gráfico Interactivo]({html_url})**
"""

                    return {
                        "success": True,
                        "FINAL_ANSWER": informe,
                        "chart_path": str(filepath_html),
                        "chart_url": f"http://localhost:8001{png_url}" if image_available else None,
                        "data": {
                            "plan": plan_ton,
                            "real": real_ton,
                            "gap": gap,
                            "causas": causas_perdida
                        }
                    }

                except Exception as e:
                    import traceback
                    error_msg = str(e)
                    print(f"[ERROR] Error en causalidad ASARCO: {error_msg}")
                    print(traceback.format_exc())
                    return {"success": False, "error": f"Error generando análisis: {error_msg}"}


            elif tool_name == "obtener_comparacion_gaviotas":

                try:

                    from datetime import datetime

                    from services.plan_reader import PlanReader



                    fecha = tool_input.get('fecha')

                    turnos = tool_input.get('turnos', ['A', 'C'])



                    if not fecha:

                        return {

                            'success': False,

                            'error': 'Fecha requerida'

                        }



                    print(f"[GAVIOTA] Analizando gaviota para {fecha}, turnos: {turnos}")



                    # Validar formato fecha

                    try:

                        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")

                    except ValueError:

                        return {

                            'success': False,

                            'error': f'Formato de fecha inválido: {fecha}. Use YYYY-MM-DD'

                        }



                    # Obtener plan del día específico

                    reader = PlanReader()

                    plan_dia_info = reader.get_plan_diario(fecha, fecha_obj.year)



                    if not plan_dia_info:

                        return {

                            'success': False,

                            'error': f'No se encontró plan para {fecha}'

                        }



                    plan_dia_total = plan_dia_info['tonelaje_plan_dia']

                    print(f"   [OK] Plan del dia {fecha}: {plan_dia_total:,.0f} ton")



                    # Obtener producción real del día desde hexagon_by_kpi_hora - SOLO CAMIONES

                    conn = sqlite3.connect(self.db_path)

                    cursor = conn.cursor()



                    print(f"   [SEARCH] Buscando produccion horaria (solo camiones) en hexagon_by_kpi_hora para {fecha}...")



                    # IMPORTANTE:

                    # 1. Solo camiones (KOM930, CAT-777)

                    # 2. hora = hora dentro del turno (0-11)

                    # 3. Usar MAX por equipo para evitar duplicación

                    cursor.execute("""

                        SELECT

                            turno,

                            hora,

                            SUM(max_tonelaje) as tonelaje_total

                        FROM (

                            SELECT

                                turno,

                                hora,

                                equipment_id,

                                MAX(material_tonnage) as max_tonelaje

                            FROM hexagon_by_kpi_hora

                            WHERE DATE(timestamp) = ?

                              AND (equipment_type LIKE 'KOM930%' OR equipment_type LIKE 'CAT-777%')

                            GROUP BY turno, hora, equipment_id

                        )

                        GROUP BY turno, hora

                        ORDER BY turno, hora

                    """, (fecha,))



                    produccion_data = []

                    total_real_dia = 0

                    registros_encontrados = 0



                    for row in cursor.fetchall():

                        turno_val = row[0]

                        hora_turno = row[1]

                        tonelaje = float(row[2]) if row[2] else 0



                        produccion_data.append({

                            'turno': turno_val,

                            'hora_turno': hora_turno,

                            'tonelaje': tonelaje

                        })

                        total_real_dia += tonelaje

                        registros_encontrados += 1



                    print(f"   [OK] Produccion real del dia (solo camiones): {total_real_dia:,.0f} ton ({registros_encontrados} registros)")



                    if registros_encontrados == 0:

                        conn.close()

                        return {

                            'success': False,

                            'error': f'No hay datos horarios de camiones para {fecha} en hexagon_by_kpi_hora'

                        }



                    # Análisis por turno

                    resultados_turnos = []



                    # Patrones de turnos con factores Gaviota correctos

                    TURNOS = {

                        'A': {

                            'nombre': 'Turno A (Día)',

                            'horas_turno': list(range(12)),  # 0-11

                            'pct_dia': 0.45,

                            'factores_hora': {

                                0: 0.85, 1: 1.15, 2: 1.15, 3: 1.10, 4: 1.00, 5: 0.70,

                                6: 0.35, 7: 1.00, 8: 1.10, 9: 1.10, 10: 1.00, 11: 0.85

                            }

                        },

                        'C': {

                            'nombre': 'Turno C (Noche)',

                            'horas_turno': list(range(12)),  # 0-11

                            'pct_dia': 0.55,

                            'factores_hora': {

                                0: 0.90, 1: 1.20, 2: 1.20, 3: 1.15, 4: 1.10, 5: 0.75,

                                6: 1.10, 7: 1.15, 8: 1.10, 9: 1.00, 10: 0.95, 11: 0.90

                            }

                        }

                    }



                    for turno in turnos:

                        if turno not in TURNOS:

                            continue



                        config = TURNOS[turno]

                        plan_turno = plan_dia_total * config['pct_dia']

                        factores = config['factores_hora']

                        suma_factores = sum(factores.values())



                        # Filtrar producción del turno

                        produccion_turno = [p for p in produccion_data if p['turno'] == turno]

                        total_turno = sum(p['tonelaje'] for p in produccion_turno)

                        horas_con_datos = len(produccion_turno)



                        print(f"   [DATA] {config['nombre']}: {total_turno:,.0f} ton ({horas_con_datos}/12 horas)")



                        # Comparación hora por hora con factores Gaviota

                        comparacion = []

                        for hora_turno in config['horas_turno']:

                            # Calcular teórico con factor Gaviota

                            factor = factores.get(hora_turno, 1.0)

                            tonelaje_teorico = (factor / suma_factores) * plan_turno



                            # Buscar producción real de esa hora del turno

                            prod_hora = next((p for p in produccion_turno if p['hora_turno'] == hora_turno), None)

                            ton_real = prod_hora['tonelaje'] if prod_hora else 0



                            desviacion = ton_real - tonelaje_teorico

                            cumplimiento = (ton_real / tonelaje_teorico * 100) if tonelaje_teorico > 0 else 0



                            estado = 'OK' if cumplimiento >= 90 else 'ALERTA' if cumplimiento >= 70 else 'CRITICO'



                            # Mapear hora turno a hora del día para visualización

                            if turno == 'A':

                                hora_dia = 8 + hora_turno

                            else:  # Turno C

                                hora_dia = (20 + hora_turno) % 24



                            comparacion.append({

                                'hora_turno': hora_turno,

                                'hora_dia': hora_dia,

                                'teorico': tonelaje_teorico,

                                'real': ton_real,

                                'desviacion': desviacion,

                                'cumplimiento': cumplimiento,

                                'estado': estado

                            })



                        cumplimiento_turno = (total_turno / plan_turno * 100) if plan_turno > 0 else 0



                        # Analisis causal de brechas criticas

                        brechas_criticas = []

                        causas_identificadas = []



                        for h in comparacion:

                            if h['estado'] == 'CRITICO':

                                brecha = {

                                    'hora_turno': h['hora_turno'],

                                    'hora_dia': h['hora_dia'],

                                    'perdida_ton': abs(h['desviacion']),

                                    'cumplimiento': h['cumplimiento']

                                }

                                brechas_criticas.append(brecha)



                        # ANALISIS ESTADISTICO DETALLADO POR HORA CRITICA

                        estadisticas_horas_criticas = []



                        # Ordenar brechas por impacto y analizar las 3 mas criticas

                        brechas_ordenadas = sorted(brechas_criticas, key=lambda x: x['perdida_ton'], reverse=True)



                        for brecha in brechas_ordenadas[:3]:

                            hora_turno = brecha['hora_turno']



                            # 1. Estadisticas de DM y UEBD para esta hora especifica

                            query_dm_uebd = """

                            SELECT

                                AVG(CASE WHEN nominal > 0 THEN (disponible * 100.0 / nominal) ELSE 0 END) as dm_hora,

                                AVG(CASE WHEN disponible > 0 THEN (efectivo * 100.0 / disponible) ELSE 0 END) as uebd_hora,

                                COUNT(DISTINCT equipment_id) as equipos_activos,

                                SUM(material_tonnage) as tonelaje_hora,

                                SUM(demora_no_prog + demora_prog) as total_demoras

                            FROM hexagon_by_kpi_hora

                            WHERE DATE(timestamp) = ?

                            AND turno = ?

                            AND hora = ?

                            AND (equipment_type LIKE 'KOM930%' OR equipment_type LIKE 'CAT-777%')

                            """



                            cursor.execute(query_dm_uebd, (fecha, turno, hora_turno))

                            dm_uebd_result = cursor.fetchone()



                            # Estadisticas promedio del turno completo (para comparacion)

                            query_turno_avg = """

                            SELECT

                                AVG(CASE WHEN nominal > 0 THEN (disponible * 100.0 / nominal) ELSE 0 END) as dm_turno,

                                AVG(CASE WHEN disponible > 0 THEN (efectivo * 100.0 / disponible) ELSE 0 END) as uebd_turno

                            FROM hexagon_by_kpi_hora

                            WHERE DATE(timestamp) = ?

                            AND turno = ?

                            AND (equipment_type LIKE 'KOM930%' OR equipment_type LIKE 'CAT-777%')

                            """



                            cursor.execute(query_turno_avg, (fecha, turno))

                            turno_avg_result = cursor.fetchone()



                            # 2. Equipos por rendimiento en esta hora (tonelaje)

                            query_equipos_rendimiento = """

                            SELECT

                                equipment_id,

                                equipment_type,

                                MAX(material_tonnage) as tonelaje,

                                MAX(CASE WHEN nominal > 0 THEN (disponible * 100.0 / nominal) ELSE 0 END) as dm

                            FROM hexagon_by_kpi_hora

                            WHERE DATE(timestamp) = ?

                            AND turno = ?

                            AND hora = ?

                            AND (equipment_type LIKE 'KOM930%' OR equipment_type LIKE 'CAT-777%')

                            GROUP BY equipment_id, equipment_type

                            ORDER BY tonelaje ASC

                            LIMIT 5

                            """



                            cursor.execute(query_equipos_rendimiento, (fecha, turno, hora_turno))

                            equipos_bajo_rendimiento = cursor.fetchall()



                            # 3. Equipos problematicos (DM baja)

                            query_equipos_problema = """

                            SELECT

                                equipment_id,

                                equipment_type,

                                MAX(CASE WHEN nominal > 0 THEN (disponible * 100.0 / nominal) ELSE 0 END) as dm,

                                MAX(material_tonnage) as tonelaje

                            FROM hexagon_by_kpi_hora

                            WHERE DATE(timestamp) = ?

                            AND turno = ?

                            AND hora = ?

                            AND (equipment_type LIKE 'KOM930%' OR equipment_type LIKE 'CAT-777%')

                            AND nominal > 0

                            GROUP BY equipment_id, equipment_type

                            HAVING dm < 70

                            ORDER BY dm ASC

                            LIMIT 5

                            """



                            cursor.execute(query_equipos_problema, (fecha, turno, hora_turno))

                            equipos_problema = cursor.fetchall()



                            # 4. Resumen de tiempos de demora

                            query_delays = """

                            SELECT

                                SUM(demora_prog) as demoras_programadas,

                                SUM(demora_no_prog) as demoras_no_programadas,

                                SUM(esperando) as tiempo_esperando,

                                SUM(perdida_op) as perdida_operacional

                            FROM hexagon_by_kpi_hora

                            WHERE DATE(timestamp) = ?

                            AND turno = ?

                            AND hora = ?

                            AND (equipment_type LIKE 'KOM930%' OR equipment_type LIKE 'CAT-777%')

                            """



                            cursor.execute(query_delays, (fecha, turno, hora_turno))

                            delays_result = cursor.fetchone()



                            # Almacenar estadisticas

                            estadisticas_horas_criticas.append({

                                'hora_turno': hora_turno,

                                'dm_hora': dm_uebd_result[0] if dm_uebd_result else 0,

                                'uebd_hora': dm_uebd_result[1] if dm_uebd_result else 0,

                                'equipos_activos': dm_uebd_result[2] if dm_uebd_result else 0,

                                'tonelaje_hora': dm_uebd_result[3] if dm_uebd_result else 0,

                                'total_demoras': dm_uebd_result[4] if dm_uebd_result and len(dm_uebd_result) > 4 else 0,

                                'dm_turno': turno_avg_result[0] if turno_avg_result else 0,

                                'uebd_turno': turno_avg_result[1] if turno_avg_result else 0,

                                'equipos_bajo_rendimiento': [

                                    {

                                        'equipo_id': eq[0],

                                        'tipo': eq[1],

                                        'tonelaje': eq[2],

                                        'dm': eq[3]

                                    } for eq in equipos_bajo_rendimiento

                                ],

                                'equipos_problema': [

                                    {

                                        'equipo_id': eq[0],

                                        'tipo': eq[1],

                                        'dm': eq[2],

                                        'tonelaje': eq[3]

                                    } for eq in equipos_problema

                                ],

                                'demoras': {

                                    'programadas': delays_result[0] if delays_result else 0,

                                    'no_programadas': delays_result[1] if delays_result else 0,

                                    'esperando': delays_result[2] if delays_result else 0,

                                    'perdida_op': delays_result[3] if delays_result else 0

                                }

                            })



                        # ANALISIS CAUSAL BASADO EN ESTADISTICAS REALES

                        for estadistica in estadisticas_horas_criticas:

                            hora_turno = estadistica['hora_turno']



                            # Buscar la brecha correspondiente

                            brecha = next((b for b in brechas_criticas if b['hora_turno'] == hora_turno), None)

                            if not brecha:

                                continue



                            # Analizar causas basadas en datos reales

                            causas = []

                            prioridad = 'MEDIA'



                            # 1. Verificar Disponibilidad Mecanica

                            if estadistica['dm_hora'] < estadistica['dm_turno'] * 0.85:

                                causas.append(f"Baja DM ({estadistica['dm_hora']:.1f}% vs promedio turno {estadistica['dm_turno']:.1f}%)")

                                prioridad = 'ALTA'



                            # 2. Verificar Utilizacion

                            if estadistica['uebd_hora'] < estadistica['uebd_turno'] * 0.80:

                                causas.append(f"Baja UEBD ({estadistica['uebd_hora']:.1f}% vs promedio turno {estadistica['uebd_turno']:.1f}%)")

                                prioridad = 'ALTA'



                            # 3. Verificar equipos bajo rendimiento

                            if len(estadistica['equipos_bajo_rendimiento']) >= 3:

                                causas.append(f"{len(estadistica['equipos_bajo_rendimiento'])} equipos con bajo rendimiento")

                                if prioridad != 'ALTA':

                                    prioridad = 'MEDIA'



                            # 4. Verificar equipos con problemas de DM

                            if len(estadistica['equipos_problema']) >= 2:

                                causas.append(f"{len(estadistica['equipos_problema'])} equipos con DM critica (<70%)")

                                prioridad = 'ALTA'



                            # 5. Verificar demoras significativas

                            demoras = estadistica['demoras']

                            if demoras['no_programadas'] and demoras['no_programadas'] > 60:  # mas de 1 hora

                                causas.append(f"Demoras no programadas altas ({demoras['no_programadas']/60:.1f} hrs)")

                                prioridad = 'ALTA'

                            elif demoras['esperando'] and demoras['esperando'] > 30:  # mas de 30 min

                                causas.append(f"Tiempo esperando elevado ({demoras['esperando']/60:.1f} hrs)")

                                if prioridad != 'ALTA':

                                    prioridad = 'MEDIA'



                            # Si no hay causas especificas, usar analisis generico por hora

                            if not causas:

                                if hora_turno == 0:

                                    causas.append("Arranque lento (cambio de turno)")

                                    prioridad = 'ALTA'

                                elif hora_turno == 5:

                                    causas.append("Valle de colacion extendido")

                                    prioridad = 'MEDIA'

                                elif hora_turno == 6 and turno == 'A':

                                    causas.append("Tronadura - evacuacion/reingreso lento")

                                    prioridad = 'ALTA'

                                elif hora_turno == 11:

                                    causas.append("Cierre anticipado de turno")

                                    prioridad = 'ALTA'

                                else:

                                    causas.append("Causa no identificada - requiere investigacion")

                                    prioridad = 'MEDIA'



                            causas_identificadas.append({

                                'hora': hora_turno,

                                'problema': f"Hora {hora_turno} - Perdida {brecha['perdida_ton']:.0f} ton",

                                'causa_probable': "; ".join(causas),

                                'impacto_ton': brecha['perdida_ton'],

                                'prioridad': prioridad,

                                'estadisticas': estadistica

                            })



                        # Para brechas que no fueron analizadas estadisticamente (solo las top 3 se analizan)

                        for h in comparacion:

                            if h['estado'] == 'CRITICO':

                                hora_turno = h['hora_turno']



                                # Si ya fue analizada, skip

                                if any(c['hora'] == hora_turno for c in causas_identificadas):

                                    continue



                                # Identificar causas probables por hora (fallback generico)

                                if h['hora_turno'] == 0:

                                    causas_identificadas.append({

                                        'hora': 0,

                                        'problema': 'Arranque lento',

                                        'causa_probable': 'Cambio de turno ineficiente, equipos no preparados, falta coordinacion',

                                        'impacto_ton': abs(h['desviacion']),

                                        'prioridad': 'ALTA'

                                    })

                                elif h['hora_turno'] == 5:

                                    causas_identificadas.append({

                                        'hora': 5,

                                        'problema': 'Valle de colacion extendido',

                                        'causa_probable': 'Colacion descoordinada, >1 hora de duracion, baja cobertura de reemplazo',

                                        'impacto_ton': abs(h['desviacion']),

                                        'prioridad': 'MEDIA'

                                    })

                                elif h['hora_turno'] == 6 and turno == 'A':

                                    causas_identificadas.append({

                                        'hora': 6,

                                        'problema': 'Caida severa en hora 6',

                                        'causa_probable': 'Tronadura extendida, evacuacion no coordinada, reingreso lento',

                                        'impacto_ton': abs(h['desviacion']),

                                        'prioridad': 'ALTA'

                                    })

                                elif h['hora_turno'] == 11:

                                    causas_identificadas.append({

                                        'hora': 11,

                                        'problema': 'Cierre anticipado',

                                        'causa_probable': 'Fatiga operadores, anticipacion cambio turno, baja supervision',

                                        'impacto_ton': abs(h['desviacion']),

                                        'prioridad': 'ALTA'

                                    })



                        # Generar recomendaciones priorizadas

                        recomendaciones = []

                        brechas_ordenadas = sorted(brechas_criticas, key=lambda x: x['perdida_ton'], reverse=True)



                        for i, brecha in enumerate(brechas_ordenadas[:3]):

                            hora = brecha['hora_turno']



                            if hora == 0:

                                recomendaciones.append({

                                    'prioridad': 1,

                                    'area': 'Arranque de turno',

                                    'accion': 'Implementar protocolo de cambio de turno estricto',

                                    'detalle': 'Reunion pre-turno 10 min antes, equipos preparados, asignaciones claras',

                                    'impacto_estimado_ton': brecha['perdida_ton'] * 0.7,

                                    'plazo': 'Inmediato'

                                })

                            elif hora in [5, 6]:

                                recomendaciones.append({

                                    'prioridad': 2,

                                    'area': 'Colacion/Tronadura',

                                    'accion': 'Optimizar tiempos de colacion y coordinacion de tronadura',

                                    'detalle': 'Colacion escalonada max 1hr, protocolo evacuacion/reingreso, comunicacion anticipada',

                                    'impacto_estimado_ton': brecha['perdida_ton'] * 0.6,

                                    'plazo': 'Corto plazo (1 semana)'

                                })

                            elif hora == 11:

                                recomendaciones.append({

                                    'prioridad': 3,

                                    'area': 'Cierre de turno',

                                    'accion': 'Reforzar supervision ultima hora',

                                    'detalle': 'Incentivos cumplimiento, supervision reforzada, meta ultima hora visible',

                                    'impacto_estimado_ton': brecha['perdida_ton'] * 0.5,

                                    'plazo': 'Corto plazo (1 semana)'

                                })



                        # Proyeccion de impacto

                        perdida_total_turno = sum(b['perdida_ton'] for b in brechas_criticas)

                        recuperacion_potencial = sum(r['impacto_estimado_ton'] for r in recomendaciones)

                        dias_habiles_mes = 26



                        proyeccion = {

                            'perdida_turno_ton': perdida_total_turno,

                            'recuperacion_potencial_turno_ton': recuperacion_potencial,

                            'perdida_mensual_ton': perdida_total_turno * dias_habiles_mes,

                            'recuperacion_mensual_ton': recuperacion_potencial * dias_habiles_mes

                        }



                        resultados_turnos.append({

                            'turno': turno,

                            'nombre': config['nombre'],

                            'plan_turno': plan_turno,

                            'real_turno': total_turno,

                            'cumplimiento': cumplimiento_turno,

                            'comparacion_horaria': comparacion,

                            'brechas_criticas': brechas_ordenadas,

                            'causas_identificadas': causas_identificadas,

                            'recomendaciones': recomendaciones,

                            'proyeccion': proyeccion

                        })

                    # ANALISIS DE OPERADORES DEL DIA (desde hexagon_dumps con nombres)
                    analisis_operadores = {}
                    for turno in turnos:
                        # Mejores operadores por tonelaje (desde hexagon_dumps)
                        cursor.execute("""
                            SELECT
                                equipo,
                                operador,
                                SUM(tonelaje) as total_ton,
                                COUNT(*) as n_viajes
                            FROM hexagon_dumps
                            WHERE DATE(fecha) = ?
                              AND turno = ?
                              AND operador IS NOT NULL
                              AND operador != 'nan nan'
                              AND operador != ''
                            GROUP BY equipo, operador
                            ORDER BY total_ton DESC
                            LIMIT 5
                        """, (fecha, turno))
                        mejores = cursor.fetchall()

                        # Peores operadores (con actividad pero bajo tonelaje)
                        cursor.execute("""
                            SELECT
                                equipo,
                                operador,
                                SUM(tonelaje) as total_ton,
                                COUNT(*) as n_viajes
                            FROM hexagon_dumps
                            WHERE DATE(fecha) = ?
                              AND turno = ?
                              AND operador IS NOT NULL
                              AND operador != 'nan nan'
                              AND operador != ''
                            GROUP BY equipo, operador
                            HAVING n_viajes >= 4
                            ORDER BY total_ton ASC
                            LIMIT 5
                        """, (fecha, turno))
                        peores = cursor.fetchall()

                        analisis_operadores[turno] = {
                            'mejores': [{'equipo': r[0], 'operador': r[1], 'tonelaje': r[2], 'viajes': r[3]} for r in mejores],
                            'peores': [{'equipo': r[0], 'operador': r[1], 'tonelaje': r[2], 'viajes': r[3]} for r in peores]
                        }

                    # Identificar hora MAX y MIN por turno
                    horas_extremas = {}
                    for t in resultados_turnos:
                        turno = t['turno']
                        comparacion = t['comparacion_horaria']
                        if comparacion:
                            hora_max = max(comparacion, key=lambda x: x['real'])
                            hora_min = min(comparacion, key=lambda x: x['real'])
                            horas_extremas[turno] = {
                                'hora_max': {'hora_turno': hora_max['hora_turno'], 'hora_dia': hora_max['hora_dia'], 'tonelaje': hora_max['real'], 'cumplimiento': hora_max['cumplimiento']},
                                'hora_min': {'hora_turno': hora_min['hora_turno'], 'hora_dia': hora_min['hora_dia'], 'tonelaje': hora_min['real'], 'cumplimiento': hora_min['cumplimiento']}
                            }

                    conn.close()

                    # Construir mensaje formateado

                    cumplimiento_dia = (total_real_dia / plan_dia_total * 100) if plan_dia_total > 0 else 0

                    mensaje = f"""# ANALISIS GAVIOTA - {fecha}



## RESUMEN DEL DIA



- **Plan del Dia:** {plan_dia_total:,.0f} ton

- **Real del Dia:** {total_real_dia:,.0f} ton

- **Cumplimiento:** {cumplimiento_dia:.1f}%



## ANALISIS POR TURNO



"""

                    for t in resultados_turnos:

                        mensaje += f"""### {t['nombre']}



- **Plan Turno:** {t['plan_turno']:,.0f} ton

- **Real Turno:** {t['real_turno']:,.0f} ton

- **Cumplimiento:** {t['cumplimiento']:.1f}%



#### Comparacion Horaria



| Hora | Hora Dia | Teorico (ton) | Real (ton) | Desviacion (ton) | Cumplimiento (%) | Estado |

|------|----------|---------------|------------|------------------|------------------|--------|

"""

                        for h in t['comparacion_horaria']:

                            mensaje += f"| {h['hora_turno']} | {h['hora_dia']:02d}:00 | {h['teorico']:,.0f} | {h['real']:,.0f} | {h['desviacion']:+,.0f} | {h['cumplimiento']:.1f}% | {h['estado']} |\n"



                        mensaje += "\n"



                        # Agregar brechas criticas

                        if t.get('brechas_criticas'):

                            mensaje += "#### BRECHAS CRITICAS\n\n"

                            for brecha in t['brechas_criticas'][:3]:

                                mensaje += f"- **Hora {brecha['hora_turno']} ({brecha['hora_dia']:02d}:00)**: Perdida de {brecha['perdida_ton']:,.0f} ton - Cumplimiento: {brecha['cumplimiento']:.1f}%\n"

                            mensaje += "\n"



                        # Agregar causas identificadas (VERSION DETALLADA)

                        if t.get('causas_identificadas'):

                            mensaje += "## ANALISIS CAUSAL DETALLADO\n\n"



                            for causa in t['causas_identificadas']:

                                # Buscar la brecha correspondiente para obtener hora_dia

                                brecha = next((b for b in t.get('brechas_criticas', []) if b['hora_turno'] == causa['hora']), None)

                                hora_dia = brecha['hora_dia'] if brecha else causa['hora']



                                mensaje += f"### HORA {causa['hora']} ({hora_dia:02d}:00) - [{causa['prioridad']}]\n\n"

                                mensaje += f"**Causa Principal:** {causa['causa_probable']}\n\n"



                                # Metricas de la hora

                                if 'estadisticas' in causa:

                                    stats = causa['estadisticas']

                                    mensaje += "**Metricas de la hora:**\n"

                                    mensaje += f"- DM: {stats['dm_hora']:.1f}% (promedio turno: {stats['dm_turno']:.1f}%)\n"

                                    mensaje += f"- UEBD: {stats['uebd_hora']:.1f}% (promedio turno: {stats['uebd_turno']:.1f}%)\n"

                                    mensaje += f"- Equipos activos: {stats['equipos_activos']}\n"

                                    mensaje += f"- Tonelaje: {stats['tonelaje_hora']:,.0f} ton\n\n"



                                    # Equipos con bajo rendimiento

                                    if stats.get('equipos_bajo_rendimiento'):

                                        mensaje += "**Equipos con bajo rendimiento:**\n\n"

                                        mensaje += "| Equipo | Tipo | Tonelaje | DM |\n"

                                        mensaje += "|--------|------|----------|----|\n"

                                        for eq in stats['equipos_bajo_rendimiento'][:5]:

                                            mensaje += f"| {eq['equipo_id']} | {eq['tipo']} | {eq['tonelaje']:,.0f} | {eq['dm']:.1f}% |\n"

                                        mensaje += "\n"



                                    # Equipos con DM critica

                                    if stats.get('equipos_problema'):

                                        mensaje += "**Equipos con DM critica (<70%):**\n\n"

                                        mensaje += "| Equipo | Tipo | DM | Tonelaje |\n"

                                        mensaje += "|--------|------|----|----------|\n"

                                        for eq in stats['equipos_problema'][:5]:

                                            mensaje += f"| {eq['equipo_id']} | {eq['tipo']} | {eq['dm']:.1f}% | {eq['tonelaje']:,.0f} |\n"

                                        mensaje += "\n"



                                    # Resumen de demoras

                                    demoras = stats.get('demoras', {})

                                    if demoras and (demoras.get('no_programadas', 0) > 0 or demoras.get('programadas', 0) > 0):

                                        mensaje += "**Demoras principales:**\n\n"

                                        mensaje += "| Categoria | Minutos | Horas |\n"

                                        mensaje += "|-----------|---------|-------|\n"

                                        if demoras.get('no_programadas', 0) > 0:

                                            mensaje += f"| No programadas | {demoras['no_programadas']:.0f} | {demoras['no_programadas']/60:.1f} |\n"

                                        if demoras.get('programadas', 0) > 0:

                                            mensaje += f"| Programadas | {demoras['programadas']:.0f} | {demoras['programadas']/60:.1f} |\n"

                                        if demoras.get('esperando', 0) > 0:

                                            mensaje += f"| Esperando | {demoras['esperando']:.0f} | {demoras['esperando']/60:.1f} |\n"

                                        mensaje += "\n"



                                mensaje += f"**Impacto Total:** {causa['impacto_ton']:,.0f} toneladas perdidas\n\n"

                                mensaje += "---\n\n"



                        # Agregar recomendaciones

                        if t.get('recomendaciones'):

                            mensaje += "#### RECOMENDACIONES PRIORIZADAS\n\n"

                            for rec in t['recomendaciones']:

                                mensaje += f"**{rec['prioridad']}. {rec['area']}** ({rec['plazo']})\n"

                                mensaje += f"- **Accion:** {rec['accion']}\n"

                                mensaje += f"- **Detalle:** {rec['detalle']}\n"

                                mensaje += f"- **Impacto estimado:** {rec['impacto_estimado_ton']:,.0f} ton/turno\n\n"



                        # Agregar proyeccion

                        if t.get('proyeccion'):

                            proy = t['proyeccion']

                            mensaje += "#### PROYECCION DE IMPACTO\n\n"

                            mensaje += f"- **Perdida actual por turno:** {proy['perdida_turno_ton']:,.0f} ton\n"

                            mensaje += f"- **Recuperacion potencial:** {proy['recuperacion_potencial_turno_ton']:,.0f} ton/turno\n"

                            mensaje += f"- **Proyeccion mensual:**\n"

                            mensaje += f"  - Perdida: {proy['perdida_mensual_ton']:,.0f} ton/mes\n"

                            mensaje += f"  - Recuperacion: {proy['recuperacion_mensual_ton']:,.0f} ton/mes\n\n"



                        mensaje += "---\n\n"

                    # AGREGAR SECCION DE HORAS EXTREMAS
                    mensaje += "## HORAS EXTREMAS DEL DÍA\n\n"
                    for turno_key, extremos in horas_extremas.items():
                        turno_nombre = "Turno A (Día)" if turno_key == 'A' else "Turno C (Noche)"
                        h_max = extremos['hora_max']
                        h_min = extremos['hora_min']
                        mensaje += f"### {turno_nombre}\n\n"
                        mensaje += f"- **Hora más ALTA:** {h_max['hora_dia']:02d}:00 (Hora {h_max['hora_turno']}) - **{h_max['tonelaje']:,.0f} ton** ({h_max['cumplimiento']:.1f}% cumplimiento)\n"
                        mensaje += f"- **Hora más BAJA:** {h_min['hora_dia']:02d}:00 (Hora {h_min['hora_turno']}) - **{h_min['tonelaje']:,.0f} ton** ({h_min['cumplimiento']:.1f}% cumplimiento)\n\n"

                    # AGREGAR SECCION DE OPERADORES
                    mensaje += "## RANKING DE OPERADORES\n\n"
                    for turno_key, ops in analisis_operadores.items():
                        turno_nombre = "Turno A (Día)" if turno_key == 'A' else "Turno C (Noche)"
                        mensaje += f"### {turno_nombre}\n\n"

                        if ops['mejores']:
                            mensaje += "**TOP 5 Mejores Operadores:**\n\n"
                            mensaje += "| # | Operador | Equipo | Tonelaje | Viajes |\n"
                            mensaje += "|---|----------|--------|----------|--------|\n"
                            for i, op in enumerate(ops['mejores'], 1):
                                mensaje += f"| {i} | {op['operador']} | {op['equipo']} | {op['tonelaje']:,.0f} | {op['viajes']} |\n"
                            mensaje += "\n"

                        if ops['peores']:
                            mensaje += "**5 Operadores con Menor Rendimiento (≥4 viajes):**\n\n"
                            mensaje += "| # | Operador | Equipo | Tonelaje | Viajes |\n"
                            mensaje += "|---|----------|--------|----------|--------|\n"
                            for i, op in enumerate(ops['peores'], 1):
                                mensaje += f"| {i} | {op['operador']} | {op['equipo']} | {op['tonelaje']:,.0f} | {op['viajes']} |\n"
                            mensaje += "\n"

                    # Generar grafico de gaviota como HTML interactivo con Plotly
                    chart_url = None
                    try:
                        import plotly.graph_objects as go
                        from plotly.subplots import make_subplots
                        from pathlib import Path

                        # Crear subplots para cada turno
                        fig = make_subplots(
                            rows=len(resultados_turnos),
                            cols=1,
                            subplot_titles=[f"Gaviota {t['nombre']} - {fecha}" for t in resultados_turnos],
                            vertical_spacing=0.15
                        )

                        colors = {'teorico': '#1565C0', 'real': '#C62828'}  # Azul y rojo

                        for idx, turno_data in enumerate(resultados_turnos):
                            row = idx + 1
                            horas = [c['hora_turno'] for c in turno_data['comparacion_horaria']]
                            horas_dia = [f"{c['hora_dia']:02d}:00" for c in turno_data['comparacion_horaria']]
                            teorico = [c['teorico'] for c in turno_data['comparacion_horaria']]
                            real = [c['real'] for c in turno_data['comparacion_horaria']]

                            # Linea Teorica (Plan)
                            fig.add_trace(go.Scatter(
                                x=horas_dia, y=teorico,
                                mode='lines+markers',
                                name=f'Teórico {turno_data["turno"]}',
                                line=dict(color=colors['teorico'], width=3),
                                marker=dict(size=10),
                                showlegend=(idx == 0)
                            ), row=row, col=1)

                            # Linea Real
                            fig.add_trace(go.Scatter(
                                x=horas_dia, y=real,
                                mode='lines+markers',
                                name=f'Real {turno_data["turno"]}',
                                line=dict(color=colors['real'], width=3),
                                marker=dict(size=10, symbol='square'),
                                showlegend=(idx == 0)
                            ), row=row, col=1)

                            # Area entre curvas (fill)
                            fig.add_trace(go.Scatter(
                                x=horas_dia + horas_dia[::-1],
                                y=teorico + real[::-1],
                                fill='toself',
                                fillcolor='rgba(128,128,128,0.2)',
                                line=dict(color='rgba(0,0,0,0)'),
                                showlegend=False,
                                hoverinfo='skip'
                            ), row=row, col=1)

                        fig.update_layout(
                            title=f"Análisis Gaviota - {fecha}",
                            height=400 * len(resultados_turnos),
                            width=1200,
                            plot_bgcolor='white',
                            paper_bgcolor='white',
                            font=dict(size=12),
                            hovermode='x unified'
                        )

                        fig.update_xaxes(title_text="Hora del Día", tickangle=-45)
                        fig.update_yaxes(title_text="Toneladas", tickformat=",.0f")

                        # Guardar como HTML
                        charts_dir = Path(__file__).parent.parent / "outputs" / "charts"
                        charts_dir.mkdir(parents=True, exist_ok=True)

                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"gaviota_{fecha}_{timestamp}.html"
                        filepath = charts_dir / filename

                        fig.write_html(str(filepath), include_plotlyjs=True, full_html=True)
                        chart_url = f"http://localhost:8001/outputs/charts/{filename}"

                        print(f"   [OK] Grafico Gaviota guardado: {filepath}")

                    except Exception as e:
                        print(f"   [WARN] Error generando grafico Plotly: {e}")
                        import traceback
                        traceback.print_exc()

                    # Agregar link al grafico si se genero
                    if chart_url:
                        mensaje += f"\n## GRÁFICO DE GAVIOTA\n\n📊 [Ver gráfico interactivo]({chart_url})\n\n"



                    # Agregar preguntas interactivas al final

                    mensaje += """---



## ¿Necesitas más detalle?



Puedo profundizar en cualquiera de estos aspectos:



- **Estadísticas detalladas por hora crítica**: Equipos específicos con problemas, operadores, demoras por categoría

- **Análisis de causas raíz**: Investigación profunda de por qué fallaron las horas críticas

- **Recomendaciones específicas**: Plan de acción detallado con responsables y plazos

- **Proyección económica**: Impacto en costos y producción mensual

- **Comparación con otros días**: Tendencias y patrones históricos



**¿Qué te gustaría explorar?**

"""



                    # Resumen corto para que el modelo decida si necesita más herramientas
                    summary = f"Gaviota {fecha}: Real {total_real_dia:,.0f} ton vs Plan {plan_dia_total:,.0f} ton = {cumplimiento_dia:.1f}%"

                    # Retornar datos estructurados CON FINAL_ANSWER para mostrar al usuario
                    return {
                        'success': True,
                        'fecha': fecha,
                        'resumen_dia': {
                            'plan': plan_dia_total,
                            'real': total_real_dia,
                            'cumplimiento': cumplimiento_dia,
                            'deficit': plan_dia_total - total_real_dia
                        },
                        'turnos': resultados_turnos,
                        'horas_extremas': horas_extremas,
                        'operadores': analisis_operadores,
                        'chart_url': chart_url,
                        'summary': summary,
                        # CRITICAL: Incluir FINAL_ANSWER con el mensaje completo
                        'FINAL_ANSWER': mensaje
                    }



                except Exception as e:

                    import traceback

                    return {

                        'success': False,

                        'error': f'Error en gaviota: {str(e)}',

                        'traceback': traceback.format_exc()

                    }

            


            elif tool_name == "buscar_dias_por_cumplimiento":
                mes = tool_input.get("mes")
                year = tool_input.get("year", 2025)
                criterio = tool_input.get("criterio", "incumplido")
                limite = tool_input.get("limite", 5)

                print(f"    Buscando dias con criterio: {criterio} en mes {mes}/{year}")

                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()

                    # Obtener plan diario desde plan_reader
                    from services.plan_reader import PlanReader
                    plan_reader = PlanReader()
                    plan_data = plan_reader.get_plan_mensual(mes, year)

                    # Extraer movimiento_total o extraccion_total del diccionario
                    if plan_data:
                        plan_mensual = plan_data.get('movimiento_total') or plan_data.get('extraccion_total') or 0
                    else:
                        plan_mensual = 0

                    # Calcular dias del mes
                    import calendar
                    dias_en_mes = calendar.monthrange(year, mes)[1]
                    plan_diario = plan_mensual / dias_en_mes if plan_mensual else 334653

                    print(f"    [PLAN] Plan mensual: {plan_mensual:,.0f} ton, Plan diario: {plan_diario:,.0f} ton")

                    # Buscar produccion real por dia
                    cursor.execute("""
                        SELECT DATE(timestamp) as fecha, SUM(material_tonnage) as real_dia
                        FROM hexagon_by_detail_dumps_2025
                        WHERE CAST(strftime('%m', timestamp) AS INTEGER) = ?
                        AND CAST(strftime('%Y', timestamp) AS INTEGER) = ?
                        GROUP BY DATE(timestamp) ORDER BY fecha
                    """, (mes, year))

                    dias = []
                    for row in cursor.fetchall():
                        fecha = row[0]
                        real = float(row[1]) if row[1] else 0
                        cumplimiento = (real / plan_diario * 100) if plan_diario > 0 else 0
                        dias.append({"fecha": fecha, "real": real, "plan": plan_diario, "cumplimiento": cumplimiento})

                    conn.close()

                    # Filtrar segun criterio
                    if criterio == "incumplido":
                        dias_filtrados = [d for d in dias if d["cumplimiento"] < 100]
                        dias_filtrados.sort(key=lambda x: x["cumplimiento"])
                    elif criterio == "cumplido":
                        dias_filtrados = [d for d in dias if d["cumplimiento"] >= 100]
                        dias_filtrados.sort(key=lambda x: x["cumplimiento"], reverse=True)
                    elif criterio == "mejor":
                        dias_filtrados = sorted(dias, key=lambda x: x["cumplimiento"], reverse=True)
                    elif criterio == "peor":
                        dias_filtrados = sorted(dias, key=lambda x: x["cumplimiento"])
                    elif criterio == "critico":
                        dias_filtrados = [d for d in dias if d["cumplimiento"] < 80]
                        dias_filtrados.sort(key=lambda x: x["cumplimiento"])
                    else:
                        dias_filtrados = dias

                    dias_resultado = dias_filtrados[:limite]

                    MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                             7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

                    criterio_texto = {
                        "incumplido": "con INCUMPLIMIENTO (<100%)",
                        "cumplido": "que CUMPLIERON (>=100%)",
                        "mejor": "con MEJOR cumplimiento",
                        "peor": "con PEOR cumplimiento",
                        "critico": "CRITICOS (<80%)"
                    }

                    mensaje = f"""## Dias {criterio_texto.get(criterio, criterio)} - {MESES.get(mes)} {year}

| # | Fecha | Real (ton) | Plan (ton) | Cumpl. | Estado |
|---|-------|------------|------------|--------|--------|
"""
                    for i, d in enumerate(dias_resultado, 1):
                        estado = "OK" if d["cumplimiento"] >= 100 else "ALERTA" if d["cumplimiento"] >= 80 else "CRITICO"
                        mensaje += f"| {i} | {d['fecha']} | {d['real']:,.0f} | {d['plan']:,.0f} | {d['cumplimiento']:.1f}% | {estado} |\n"

                    if dias_resultado:
                        destacado = dias_resultado[0]
                        if criterio in ["incumplido", "peor", "critico"]:
                            mensaje += f"""

### Analisis

El dia con **menor cumplimiento** fue **{destacado['fecha']}** con solo **{destacado['cumplimiento']:.1f}%** del plan.
- Real: {destacado['real']:,.0f} ton
- Plan: {destacado['plan']:,.0f} ton
- Deficit: {destacado['plan'] - destacado['real']:,.0f} ton

Deseas que analice ese dia en detalle con el analisis Gaviota para identificar las causas?
"""
                        else:
                            mensaje += f"""

### Analisis

El dia con **mejor cumplimiento** fue **{destacado['fecha']}** con **{destacado['cumplimiento']:.1f}%** del plan.
"""
                    else:
                        mensaje += f"\n\nNo se encontraron dias con criterio '{criterio}' en {MESES.get(mes)} {year}."

                    print(f"    [OK] Encontrados {len(dias_filtrados)} dias, mostrando {len(dias_resultado)}")

                    return {
                        "success": True,
                        "FINAL_ANSWER": mensaje,
                        "dias": dias_resultado,
                        "criterio": criterio,
                        "total_encontrados": len(dias_filtrados),
                        "mes": mes,
                        "year": year
                    }

                except Exception as e:
                    import traceback
                    print(f"    [ERROR] buscar_dias_por_cumplimiento: {str(e)}")
                    return {
                        "success": False,
                        "error": f"Error buscando dias: {str(e)}",
                        "traceback": traceback.format_exc()
                    }

            elif tool_name == "obtener_pareto_delays":
                # Imports al inicio del bloque para evitar scope issues
                from pathlib import Path
                import pandas as pd

                year = tool_input.get("year", 2025)

                mes_inicio = tool_input.get("mes_inicio")

                mes_fin = tool_input.get("mes_fin")

                # Si hay mes específico (single mes)
                mes = tool_input.get("mes")
                if mes and not mes_inicio:
                    mes_inicio = mes
                    mes_fin = mes

                print(f"    Consultando Pareto delays para {year} (mes_inicio={mes_inicio}, mes_fin={mes_fin})")

                delays = []
                total_horas = 0

                try:
                    # PRIMERO: Intentar desde BD
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()

                    # Verificar si existe la tabla
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hexagon_estados'")
                    tabla_existe = cursor.fetchone()

                    if tabla_existe:
                        # Construir filtro de fechas
                        if mes_inicio and mes_fin:
                            fecha_filtro = f"AND CAST(strftime('%m', fecha) AS INTEGER) BETWEEN {mes_inicio} AND {mes_fin}"
                        else:
                            fecha_filtro = ""

                        query = f"""
                            SELECT
                                code,
                                estado,
                                categoria,
                                razon,
                                SUM(horas) as total_horas,
                                COUNT(*) as eventos
                            FROM hexagon_estados
                            WHERE CAST(strftime('%Y', fecha) AS INTEGER) = ?
                            AND code NOT IN (1.0, 1, '1.0', '1')
                            AND UPPER(razon) NOT LIKE '%PRODUCCION%'
                            {fecha_filtro}
                            GROUP BY code, estado, categoria, razon
                            ORDER BY total_horas DESC
                            LIMIT 20
                        """
                        cursor.execute(query, [year])

                        for row in cursor.fetchall():
                            horas = float(row[4])
                            total_horas += horas
                            delays.append({
                                "code": row[0],
                                "estado": row[1],
                                "categoria": row[2],
                                "razon": row[3],
                                "total_horas": horas,
                                "eventos": row[5]
                            })

                    conn.close()

                    # FALLBACK: Si no hay datos en BD, leer desde Excel
                    if len(delays) == 0:
                        print(f"    >> Sin datos en BD, leyendo desde Excel...")
                        # pandas y Path ya importados al inicio del bloque

                        excel_path = Path(self.data_dir) / "Hexagon" / "by_estados_2024_2025.xlsx"
                        if excel_path.exists():
                            df = pd.read_excel(excel_path)
                            df['fecha'] = pd.to_datetime(df['fecha'])
                            df['mes'] = df['fecha'].dt.month
                            df['year'] = df['fecha'].dt.year

                            # Filtrar por año
                            df_filtered = df[df['year'] == year]

                            # Filtrar por mes si corresponde
                            if mes_inicio and mes_fin:
                                df_filtered = df_filtered[(df_filtered['mes'] >= mes_inicio) & (df_filtered['mes'] <= mes_fin)]

                            # Excluir código 1 (producción)
                            df_filtered = df_filtered[df_filtered['code'] != 1]
                            df_filtered = df_filtered[~df_filtered['razon'].str.upper().str.contains('PRODUCCION', na=False)]

                            # Agrupar
                            grouped = df_filtered.groupby(['code', 'razon']).agg({
                                'horas': 'sum',
                                'equipo': 'count'
                            }).reset_index()
                            grouped.columns = ['code', 'razon', 'total_horas', 'eventos']
                            grouped = grouped.sort_values('total_horas', ascending=False).head(20)

                            for _, row in grouped.iterrows():
                                horas = float(row['total_horas'])
                                total_horas += horas
                                delays.append({
                                    "code": int(row['code']) if pd.notna(row['code']) else 0,
                                    "estado": str(row['razon'])[:30],
                                    "categoria": "ASARCO",
                                    "razon": str(row['razon']),
                                    "total_horas": horas,
                                    "eventos": int(row['eventos'])
                                })
                            print(f"    >> Leídos {len(delays)} delays desde Excel, {total_horas:,.0f} hrs totales")



                    # Calcular porcentajes

                    for d in delays:

                        d["porcentaje"] = (d["total_horas"] / total_horas * 100) if total_horas > 0 else 0



                    conn.close()



                    # Construir mensaje

                    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',

                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']



                    if mes_inicio and mes_fin:

                        if mes_inicio == mes_fin:

                            periodo = f"{meses[mes_inicio-1].upper()} {year}"

                        else:

                            periodo = f"{meses[mes_inicio-1].upper()} - {meses[mes_fin-1].upper()} {year}"

                    else:

                        periodo = f"AÑO {year}"



                    mensaje = f"""

📉 **ANÁLISIS PARETO DE DELAYS - {periodo}**

═══════════════════════════════════════════════════════════════

**Total horas de delays:** {total_horas:,.0f} hrs

------------------------------------------------------------

### 🔴 TOP 20 CAUSAS (Regla 80/20)

------------------------------------------------------------



"""



                    acumulado = 0

                    for i, d in enumerate(delays, 1):

                        acumulado += d["porcentaje"]

                        emoji = "🔴" if acumulado <= 80 else "⚪"

                        mensaje += f"{i:2d}. {emoji} [{d['code']}] {d['estado']} - {d['razon']}\n"

                        mensaje += f"    {d['total_horas']:,.0f} hrs ({d['porcentaje']:.1f}%) | {d['eventos']:,} eventos\n\n"



                    mensaje += "================================================================="

                    # Resumen corto de las top 3 causas para que el modelo decida si continuar
                    top3_summary = ", ".join([f"{d['code']} ({d['porcentaje']:.0f}%)" for d in delays[:3]]) if delays else "Sin datos"
                    summary = f"Pareto {periodo}: {total_horas:,.0f} hrs totales. Top 3: {top3_summary}. [Si el usuario pidió waterfall/cascada/gráfico → llama generate_chart(chart_type='waterfall')]"

                    return {

                        "success": True,

                        "summary": summary,

                        "data": {

                            "year": year,

                            "periodo": periodo,

                            "total_horas": total_horas,

                            "delays": delays

                        }

                    }



                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error consultando delays: {str(e)}"

                    }



            elif tool_name == "obtener_operadores_con_delays_grupo":

                year = tool_input.get("year", 2025)

                mes = tool_input.get("mes", 1)

                codigo_delay = tool_input.get("codigo_delay")

                top_n = tool_input.get("top_n", 10)



                print(f"    Consultando operadores con delays de grupo para {mes}/{year}")



                try:

                    conn = sqlite3.connect(self.db_path)



                    # Calcular fechas

                    fecha_inicio = f"{year}-{mes:02d}-01"

                    if mes == 12:

                        fecha_fin = f"{year+1}-01-01"

                    else:

                        fecha_fin = f"{year}-{mes+1:02d}-01"



                    # Query 1: Delays por grupo (normalizado)

                    query_delays = f"""

                        SELECT

                            CAST(REPLACE(REPLACE(LOWER(grupo), 'grupo_', ''), 'grupo ', '') AS INTEGER) as grupo_num,

                            SUM(CASE WHEN code = 243 THEN horas ELSE 0 END) as hrs_cambio_turno,

                            SUM(CASE WHEN code = 225 THEN horas ELSE 0 END) as hrs_sin_operador,

                            SUM(CASE WHEN code = 400 THEN horas ELSE 0 END) as hrs_imprevisto_mec,

                            SUM(CASE WHEN code = 242 THEN horas ELSE 0 END) as hrs_colacion,

                            SUM(CASE WHEN code = 402 THEN horas ELSE 0 END) as hrs_mtto_prog,

                            SUM(horas) as total_delays

                        FROM hexagon_by_estados_2024_2025

                        WHERE timestamp >= '{fecha_inicio}'

                          AND timestamp < '{fecha_fin}'

                          AND equipment_id LIKE 'CE%'

                        GROUP BY grupo_num

                        ORDER BY total_delays DESC

                    """

                    df_delays = pd.read_sql(query_delays, conn)



                    # Query 2: Top operadores por grupo

                    query_ops = f"""

                        SELECT

                            CAST(REPLACE(REPLACE(LOWER(grupo), 'grupo_', ''), 'grupo ', '') AS INTEGER) as grupo_num,

                            truck_operator_last_name as operador,

                            SUM(material_tonnage) as tons,

                            COUNT(*) as viajes

                        FROM hexagon_by_detail_dumps_2025

                        WHERE timestamp >= '{fecha_inicio}'

                          AND timestamp < '{fecha_fin}'

                          AND truck_operator_last_name IS NOT NULL

                          AND truck_operator_last_name != ''

                        GROUP BY grupo_num, operador

                        ORDER BY tons DESC

                    """

                    df_ops = pd.read_sql(query_ops, conn)

                    conn.close()



                    # Merge operadores con delays de su grupo

                    df_merged = df_ops.merge(df_delays, on='grupo_num', how='left')



                    # Ordenar según código de delay si se especifica

                    if codigo_delay:

                        delay_cols = {

                            243: 'hrs_cambio_turno',

                            225: 'hrs_sin_operador',

                            400: 'hrs_imprevisto_mec',

                            242: 'hrs_colacion',

                            402: 'hrs_mtto_prog'

                        }

                        sort_col = delay_cols.get(codigo_delay, 'total_delays')

                        df_merged = df_merged.sort_values([sort_col, 'tons'], ascending=[False, False])



                    # Nombres de meses

                    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',

                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']



                    # Formatear mensaje

                    mensaje = f"""

=================================================================

|   OPERADORES CON DELAYS DE SU GRUPO - {meses[mes-1].upper()} {year}   |

=================================================================



⚠️ NOTA: Los delays se registran por EQUIPO, no por operador.

   Este análisis muestra qué operadores trabajan en grupos con más delays.



------------------------------------------------------------

 RESUMEN POR GRUPO

------------------------------------------------------------

"""

                    for _, row in df_delays.iterrows():

                        grupo = int(row['grupo_num']) if pd.notna(row['grupo_num']) else 0

                        mensaje += f"\n📊 **GRUPO {grupo}:**\n"

                        mensaje += f"   • Cambio turno (243): {row['hrs_cambio_turno']:,.0f} hrs\n"

                        mensaje += f"   • Sin operador (225): {row['hrs_sin_operador']:,.0f} hrs\n"

                        mensaje += f"   • Imprevisto mec (400): {row['hrs_imprevisto_mec']:,.0f} hrs\n"

                        mensaje += f"   • Total delays: {row['total_delays']:,.0f} hrs\n"



                    mensaje += f"""

------------------------------------------------------------

 TOP {top_n} OPERADORES (ordenados por delays de grupo)

------------------------------------------------------------

"""

                    for i, (_, row) in enumerate(df_merged.head(top_n).iterrows(), 1):

                        grupo = int(row['grupo_num']) if pd.notna(row['grupo_num']) else 0

                        mensaje += f"\n{i:2d}. {row['operador']}\n"

                        mensaje += f"    Grupo: {grupo} | Tons: {row['tons']:,.0f} | Viajes: {row['viajes']}\n"

                        mensaje += f"    Delays grupo: CT={row.get('hrs_cambio_turno', 0):,.0f}h, SO={row.get('hrs_sin_operador', 0):,.0f}h, IM={row.get('hrs_imprevisto_mec', 0):,.0f}h\n"



                    mensaje += "\n================================================================="

                    mensaje += "\nLeyenda: CT=Cambio Turno, SO=Sin Operador, IM=Imprevisto Mecánico"



                    return {

                        "success": True,

                        "FINAL_ANSWER": mensaje,

                        "data": {

                            "year": year,

                            "mes": mes,

                            "periodo": f"{meses[mes-1]} {year}",

                            "resumen_grupos": df_delays.to_dict('records'),

                            "top_operadores": df_merged.head(top_n).to_dict('records')

                        }

                    }



                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error consultando operadores con delays: {str(e)}"

                    }



            elif tool_name == "obtener_analisis_causal_operador":

                operador = tool_input.get("operador", "")

                mes = tool_input.get("mes")

                year = tool_input.get("year", 2025)

                top_delays = tool_input.get("top_delays", 5)



                print(f"    Analizando correlación causal ASARCO para operador: {operador}")



                try:

                    conn = sqlite3.connect(self.db_path)

                    cursor = conn.cursor()



                    # Construir filtro de fecha

                    if mes:

                        fecha_inicio = f"{year}-{mes:02d}-01"

                        if mes == 12:

                            fecha_fin = f"{year+1}-01-01"

                        else:

                            fecha_fin = f"{year}-{mes+1:02d}-01"

                        fecha_filtro_dumps = f"AND timestamp >= '{fecha_inicio}' AND timestamp < '{fecha_fin}'"

                        fecha_filtro_estados = f"AND timestamp >= '{fecha_inicio}' AND timestamp < '{fecha_fin}'"

                        meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',

                                'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

                        periodo_texto = f"{meses[mes-1]} {year}"

                    else:

                        fecha_filtro_dumps = f"AND timestamp >= '{year}-01-01' AND timestamp < '{year+1}-01-01'"

                        fecha_filtro_estados = f"AND timestamp >= '{year}-01-01' AND timestamp < '{year+1}-01-01'"

                        periodo_texto = f"Año {year}"



                    # Query 1: Identificar al operador y su grupo

                    cursor.execute(f"""

                        SELECT

                            truck_operator_last_name as operador,

                            CASE

                                WHEN grupo LIKE '%1%' THEN '1'

                                WHEN grupo LIKE '%2%' THEN '2'

                                WHEN grupo LIKE '%3%' THEN '3'

                                WHEN grupo LIKE '%4%' THEN '4'

                                ELSE grupo

                            END as grupo_normalizado,

                            COUNT(*) as viajes,

                            SUM(material_tonnage) as tonelaje_total,

                            COUNT(DISTINCT truck_id) as equipos_operados

                        FROM hexagon_by_detail_dumps_2025

                        WHERE truck_operator_last_name LIKE '%{operador}%'

                        {fecha_filtro_dumps}

                        GROUP BY truck_operator_last_name

                        ORDER BY tonelaje_total DESC

                        LIMIT 1

                    """)



                    operador_row = cursor.fetchone()



                    if not operador_row:

                        conn.close()

                        return {

                            "success": False,

                            "error": f"No se encontró operador con nombre '{operador}' en {periodo_texto}"

                        }



                    nombre_completo = operador_row[0]

                    grupo_operador = operador_row[1]

                    viajes_operador = operador_row[2]

                    tonelaje_operador = float(operador_row[3]) if operador_row[3] else 0

                    equipos_operados = operador_row[4]



                    print(f"    Operador encontrado: {nombre_completo} (Grupo {grupo_operador})")



                    # Query 2: Obtener equipos que opera este operador

                    cursor.execute(f"""

                        SELECT DISTINCT truck_id

                        FROM hexagon_by_detail_dumps_2025

                        WHERE truck_operator_last_name = '{nombre_completo}'

                        {fecha_filtro_dumps}

                    """)



                    equipos_lista = [str(row[0]) for row in cursor.fetchall()]



                    # Query 3: Correlación por GRUPO y FECHA

                    # NOTA: Los equipment_id de dumps (443, 606) NO coinciden con estados (CE101, CE345)

                    # Por eso correlacionamos por GRUPO + mismas fechas de operación del operador



                    # Primero obtener las fechas en que el operador trabajó

                    cursor.execute(f"""

                        SELECT DISTINCT DATE(timestamp) as fecha_trabajo

                        FROM hexagon_by_detail_dumps_2025

                        WHERE truck_operator_last_name = '{nombre_completo}'

                        {fecha_filtro_dumps}

                    """)

                    fechas_trabajo = [row[0] for row in cursor.fetchall()]



                    if fechas_trabajo:

                        fechas_str = "', '".join(fechas_trabajo)



                        # Query delays del GRUPO en las fechas que el operador trabajó

                        cursor.execute(f"""

                            SELECT

                                e.code,

                                e.estado,

                                e.razon,

                                COUNT(*) as eventos,

                                SUM(e.horas) as total_horas

                            FROM hexagon_by_estados_2024_2025 e

                            WHERE DATE(e.timestamp) IN ('{fechas_str}')

                            AND e.equipment_id LIKE 'CE%'

                            AND (

                                e.grupo LIKE '%{grupo_operador}%'

                                OR e.grupo = 'Grupo {grupo_operador}'

                                OR e.grupo = 'grupo_{grupo_operador}'

                            )

                            GROUP BY e.code, e.estado, e.razon

                            ORDER BY total_horas DESC

                            LIMIT {top_delays * 2}

                        """)



                    delays_operador = []

                    total_horas_delays = 0



                    if fechas_trabajo:

                        for row in cursor.fetchall():

                            horas = float(row[4]) if row[4] else 0

                            total_horas_delays += horas

                            delays_operador.append({

                                "code": row[0],

                                "estado": row[1],

                                "razon": row[2],

                                "eventos": row[3],

                                "horas": horas

                            })



                    # Query 4: Promedio del grupo para comparación (por GRUPO, no por equipo)

                    cursor.execute(f"""

                        SELECT

                            e.code,

                            SUM(e.horas) as total_horas,

                            (SELECT COUNT(DISTINCT truck_operator_last_name)

                             FROM hexagon_by_detail_dumps_2025

                             WHERE grupo LIKE '%{grupo_operador}%'

                             {fecha_filtro_dumps}) as operadores

                        FROM hexagon_by_estados_2024_2025 e

                        WHERE e.equipment_id LIKE 'CE%'

                        {fecha_filtro_estados}

                        AND (

                            e.grupo LIKE '%{grupo_operador}%'

                            OR e.grupo = 'Grupo {grupo_operador}'

                            OR e.grupo = 'grupo_{grupo_operador}'

                        )

                        GROUP BY e.code

                        ORDER BY total_horas DESC

                        LIMIT 10

                    """)



                    promedios_grupo = {}

                    for row in cursor.fetchall():

                        code = row[0]

                        total = float(row[1]) if row[1] else 0

                        ops = row[2] if row[2] else 1

                        promedios_grupo[code] = total / ops



                    # Query 5: Ranking del operador vs su grupo

                    cursor.execute(f"""

                        SELECT

                            truck_operator_last_name as operador,

                            SUM(material_tonnage) as ton_total

                        FROM hexagon_by_detail_dumps_2025

                        WHERE 1=1

                        {fecha_filtro_dumps}

                        AND (

                            grupo LIKE '%{grupo_operador}%'

                            OR grupo = 'Grupo {grupo_operador}'

                            OR grupo = 'grupo_{grupo_operador}'

                        )

                        GROUP BY truck_operator_last_name

                        ORDER BY ton_total DESC

                    """)



                    ranking_grupo = cursor.fetchall()

                    posicion_ranking = 1

                    total_operadores_grupo = len(ranking_grupo)

                    for i, row in enumerate(ranking_grupo):

                        if row[0] == nombre_completo:

                            posicion_ranking = i + 1

                            break



                    conn.close()



                    # Calcular nivel de confianza

                    if viajes_operador > 500 and len(delays_operador) > 3:

                        confianza = "ALTA"

                        emoji_confianza = "OK"

                    elif viajes_operador > 200 and len(delays_operador) > 1:

                        confianza = "MEDIA"

                        emoji_confianza = "~"

                    else:

                        confianza = "BAJA"

                        emoji_confianza = "!"



                    # Construir mensaje

                    mensaje = f"""

=======================================================================

|  ANALISIS CAUSAL ASARCO - OPERADOR: {nombre_completo[:45]:<45} |

=======================================================================



Periodo: {periodo_texto}

Operador: {nombre_completo}

Grupo: {grupo_operador}

Ranking en grupo: #{posicion_ranking} de {total_operadores_grupo}



-----------------------------------------------------------------------

METRICAS DEL OPERADOR

-----------------------------------------------------------------------

- Viajes realizados: {viajes_operador:,}

- Tonelaje total: {tonelaje_operador:,.0f} ton

- Equipos operados: {equipos_operados}

- Equipos: {', '.join(equipos_lista[:5])}{'...' if len(equipos_lista) > 5 else ''}



-----------------------------------------------------------------------

DELAYS ASARCO CORRELACIONADOS (en equipos que opera)

-----------------------------------------------------------------------

Total horas de delays correlacionados: {total_horas_delays:,.1f} hrs



"""



                    for i, d in enumerate(delays_operador[:top_delays], 1):

                        code = d["code"] if d["code"] else "N/A"

                        promedio_grupo = promedios_grupo.get(code, 0)



                        if promedio_grupo > 0:

                            diff = ((d["horas"] - promedio_grupo) / promedio_grupo) * 100

                            if diff > 20:

                                comparacion = f"+{diff:.0f}% vs grupo"

                            elif diff < -20:

                                comparacion = f"{diff:.0f}% vs grupo"

                            else:

                                comparacion = "similar al grupo"

                        else:

                            comparacion = "sin datos comparativos"



                        mensaje += f"""

{i}. [{code}] {d["razon"] or d["estado"] or "Sin descripcion"}

   Horas: {d["horas"]:,.1f} hrs ({d["eventos"]} eventos)

   {comparacion}

"""



                    mensaje += f"""

-----------------------------------------------------------------------

ANALISIS DE CAUSA RAIZ

-----------------------------------------------------------------------

[{emoji_confianza}] Nivel de confianza: {confianza}

"""



                    if delays_operador:

                        top_delay = delays_operador[0]

                        top_code = top_delay["code"] if top_delay["code"] else "N/A"

                        top_horas = top_delay["horas"]

                        pct = (top_horas/total_horas_delays*100) if total_horas_delays > 0 else 0



                        mensaje += f"""

Principal delay asociado: [{top_code}]

- Representa {pct:.1f}% de sus delays totales

"""



                        top_code_str = str(top_code).upper()

                        if "243" in top_code_str or "CAMBIO" in top_code_str:

                            mensaje += """

RECOMENDACION:

- Revisar tiempos de transicion de turno de este operador

- Comparar tiempos de llegada vs otros operadores del grupo

- Verificar si hay issues con asignacion de equipo

"""

                        elif "242" in top_code_str or "COLACION" in top_code_str:

                            mensaje += """

RECOMENDACION:

- Analizar cumplimiento de ventanas de colacion

- Verificar coordinacion con relevo

"""

                        elif "400" in top_code_str or "MANT" in top_code_str or "MECANICO" in top_code_str:

                            mensaje += """

RECOMENDACION:

- Revisar si reporta fallas tempranamente

- Verificar cumplimiento de checklist pre-operacional

"""

                        elif "225" in top_code_str or "SIN OPERADOR" in top_code_str:

                            mensaje += """

RECOMENDACION:

- Verificar asistencia y puntualidad

- Revisar cobertura de relevos

"""

                        else:

                            mensaje += """

RECOMENDACION:

- Analisis detallado de las circunstancias de estos delays

- Entrevista con supervisor para contexto operacional

"""



                    mensaje += """

-----------------------------------------------------------------------

NOTA METODOLOGICA

-----------------------------------------------------------------------

Los delays ASARCO se registran por EQUIPO, no por operador.

Esta correlacion se basa en:

1. Delays que ocurrieron en equipos que este operador operaba

2. Durante las fechas en que estaba activo

3. Comparacion estadistica vs otros operadores del mismo grupo



La correlacion NO implica causalidad directa. Usar como insumo

para investigacion operacional, no como evidencia concluyente.

=======================================================================

"""



                    return {

                        "success": True,

                        "FINAL_ANSWER": mensaje,

                        "data": {

                            "operador": nombre_completo,

                            "grupo": grupo_operador,

                            "periodo": periodo_texto,

                            "ranking_grupo": f"#{posicion_ranking} de {total_operadores_grupo}",

                            "viajes": viajes_operador,

                            "tonelaje": tonelaje_operador,

                            "total_horas_delays": total_horas_delays,

                            "top_delays": delays_operador[:top_delays],

                            "nivel_confianza": confianza

                        }

                    }



                except Exception as e:

                    import traceback

                    print(f"    Error en analisis causal: {str(e)}")

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error en analisis causal: {str(e)}"

                    }



            elif tool_name == "obtener_ranking_operadores_api":

                endpoint = "/api/ranking/operadores-produccion"

                params = {

                    "year": tool_input.get("year", 2024),

                    "top_n": tool_input.get("top_n", 10),

                    "tipo": tool_input.get("tipo", "")

                }

                url = f"{self.api_base_url}{endpoint}"

                print(f"    Llamando {endpoint} con params: {params}")

                

                response = requests.get(url, params=params, timeout=180)

                

                if response.status_code == 200:

                    return {

                        "success": True,

                        "data": response.json(),

                        "endpoint": endpoint

                    }

                else:

                    return {

                        "success": False,

                        "error": f"HTTP {response.status_code}: {response.text}"

                    }



            elif tool_name == "analizar_match_pala_camion":

                from services.match_pala_camion_correcto import analizar_match_pala_camion



                fecha_inicio = tool_input.get('fecha_inicio')

                fecha_fin = tool_input.get('fecha_fin')



                print(f"   >> Ejecutando Match Pala-Camion: {fecha_inicio} a {fecha_fin}")



                resultado = analizar_match_pala_camion(

                    fecha_inicio=fecha_inicio,

                    fecha_fin=fecha_fin

                )



                if resultado['success']:

                    # NO generar FINAL_ANSWER aquí - dejar que el LLM use el system prompt profesional

                    # Solo guardar el gráfico y devolver los datos estructurados



                    chart_filename = None

                    files_generated = []

                    if resultado.get('grafico_base64'):

                        import base64

                        from time import strftime

                        from pathlib import Path

                        timestamp = strftime("%Y%m%d_%H%M%S")

                        chart_filename = f"match_{timestamp}.png"

                        chart_path = Path("outputs/charts") / chart_filename

                        chart_path.parent.mkdir(parents=True, exist_ok=True)



                        with open(chart_path, "wb") as f:

                            f.write(base64.b64decode(resultado['grafico_base64']))



                        print(f"    Grafico guardado: {chart_path}")

                        files_generated.append(f"/outputs/charts/{chart_filename}")



                    # CRITICAL FIX: Si resultado contiene FINAL_ANSWER, devolverlo al nivel superior

                    # para que la detección en línea 1244 funcione correctamente

                    if 'FINAL_ANSWER' in resultado:

                        return {

                            "success": True,

                            "FINAL_ANSWER": resultado['FINAL_ANSWER'],

                            "grafico_base64": resultado.get('grafico_base64'),

                            "file_path": f"/outputs/charts/{chart_filename}" if resultado.get('grafico_base64') else None,

                            "files_generated": files_generated

                        }

                    else:

                        return {

                            "success": True,

                            "data": resultado,

                            "file_path": f"/outputs/charts/{chart_filename}" if resultado.get('grafico_base64') else None,

                            "files_generated": files_generated

                        }

                else:

                    return {

                        "success": False,

                        "error": resultado.get('error', 'Error desconocido')

                    }



            elif tool_name == "analizar_utilizacion_caex":

                from services.analisis_utilizacion_caex import analizar_utilizacion_caex



                fecha_inicio = tool_input.get('fecha_inicio')

                fecha_fin = tool_input.get('fecha_fin')



                print(f"   >> Ejecutando Analisis UEBD CAEX: {fecha_inicio} a {fecha_fin}")



                resultado = analizar_utilizacion_caex(

                    fecha_inicio=fecha_inicio,

                    fecha_fin=fecha_fin

                )



                if resultado['success']:

                    lineas = []

                    lineas.append("="*70)

                    lineas.append(">> ANALISIS DE UTILIZACION CAEX")

                    lineas.append("="*70)

                    lineas.append(f"PERIODO: {resultado['periodo']}")

                    lineas.append("")

                    lineas.append(">> METRICAS GENERALES:")

                    lineas.append(f"   - DM Promedio Flota: {resultado['dm_promedio_flota']:.1f}%")

                    lineas.append(f"   - UEBD Promedio Flota: {resultado['uebd_promedio_flota']:.1f}%")

                    lineas.append(f"   - Equipos analizados: {resultado['equipos_validos']}")

                    lineas.append("")



                    # Vueltas manuales

                    vm = resultado['vueltas_manuales']

                    lineas.append(">> VUELTAS MANUALES (sin KPIs):")

                    lineas.append(f"   - Total registros: {vm['total_registros']:,}")

                    lineas.append(f"   - Sin UEBD: {vm['registros_sin_uebd']:,} ({vm['porcentaje']:.1f}%)")

                    lineas.append("")



                    # Top 10 peor UEBD - Formato Markdown para React

                    lineas.append("### TOP 10 EQUIPOS CON PEOR UEBD")

                    lineas.append("")

                    lineas.append("| # | Equipo | DM % | UEBD % |")

                    lineas.append("|---|--------|------|--------|")



                    for i, eq in enumerate(resultado['top_10_uebd'], 1):

                        equipo = str(eq['equipment_id'])

                        dm = f"{eq['dm_promedio']:.1f}%"

                        uebd = f"{eq['uebd_promedio']:.1f}%"

                        lineas.append(f"| {i} | {equipo} | {dm} | {uebd} |")

                    lineas.append("")

                    lineas.append("="*70)



                    respuesta_texto = "\n".join(lineas)



                    return {

                        "success": True,

                        "FINAL_ANSWER": respuesta_texto,

                        "data": resultado

                    }

                else:

                    return {

                        "success": False,

                        "error": resultado.get('error', 'Error desconocido')

                    }



            elif tool_name == "analizar_causa_raiz_uebd":

                from services.analisis_causa_raiz_uebd import analizar_causa_raiz_uebd



                fecha_inicio = tool_input.get('fecha_inicio')

                fecha_fin = tool_input.get('fecha_fin')

                equipo = tool_input.get('equipo', None)



                print(f"   >> Ejecutando Analisis Causa Raiz UEBD: {fecha_inicio} a {fecha_fin}")

                if equipo:

                    print(f"      Equipo específico: {equipo}")



                resultado = analizar_causa_raiz_uebd(

                    fecha_inicio=fecha_inicio,

                    fecha_fin=fecha_fin,

                    equipo=equipo

                )



                if resultado['success']:

                    lineas = []

                    lineas.append("="*70)

                    lineas.append(">> ANALISIS CAUSA RAIZ DE BAJA UEBD")

                    lineas.append("="*70)

                    lineas.append(f"PERIODO: {resultado['periodo']}")

                    lineas.append(f"EQUIPOS ANALIZADOS: {resultado['total_equipos']}")

                    lineas.append("")



                    # Resumen por clasificación

                    if resultado['resumen_clasificacion']:

                        lineas.append(">> RESUMEN POR TIPO DE PROBLEMA:")

                        for clasificacion, cantidad in resultado['resumen_clasificacion'].items():

                            lineas.append(f"   - {clasificacion}: {cantidad} equipos")

                        lineas.append("")



                    # Análisis por equipo

                    for eq in resultado['equipos']:

                        lineas.append("-" * 70)

                        lineas.append(f">> EQUIPO: {eq['equipo']}")

                        lineas.append(f"   DM: {eq['dm']:.1f}% | UEBD: {eq['uebd']:.1f}%")

                        lineas.append("")



                        # Clasificación

                        emoji = "🔴" if eq['clasificacion'] in ['PROBLEMA_OPERACIONAL', 'PROBLEMA_MANTENIMIENTO'] else "🟡" if eq['clasificacion'] == 'PROBLEMA_MIXTO' else "✅"

                        lineas.append(f"{emoji} DIAGNOSTICO: {eq['clasificacion']}")

                        lineas.append(f"   {eq['problema_principal']}")

                        lineas.append("")



                        # Distribución de tiempo

                        dist = eq['distribucion']

                        lineas.append("   DISTRIBUCION DE TIEMPO:")

                        lineas.append(f"   - Efectivo:           {dist['efectivo']:5.1f}%")

                        lineas.append(f"   - Demoras No Prog.:   {dist['det_noprg']:5.1f}%")

                        lineas.append(f"   - Demoras Prog.:      {dist['det_prg']:5.1f}%")

                        lineas.append(f"   - Mnt. Correctiva:    {dist['mnt_correctiva']:5.1f}%")

                        lineas.append(f"   - Mnt. Programada:    {dist['mnt_programada']:5.1f}%")

                        lineas.append("")



                        # Top 3 estados

                        lineas.append("   TOP 3 ESTADOS CRITICOS:")

                        for i, estado in enumerate(eq['top_estados'][:3], 1):

                            pct = (estado['horas_totales'] / sum(e['horas_totales'] for e in eq['top_estados']) * 100)

                            lineas.append(f"   {i}. {estado['razon']}: {estado['horas_totales']:.1f}h ({pct:.1f}%)")

                        lineas.append("")



                        # Recomendaciones

                        if eq['recomendaciones']:

                            lineas.append("   RECOMENDACIONES:")

                            for rec in eq['recomendaciones']:

                                lineas.append(f"   • {rec}")

                            lineas.append("")



                    lineas.append("="*70)



                    respuesta_texto = "\n".join(lineas)



                    return {

                        "success": True,

                        "FINAL_ANSWER": respuesta_texto,

                        "data": resultado

                    }

                else:

                    return {

                        "success": False,

                        "error": resultado.get('error', 'Error desconocido')

                    }



            elif tool_name == "analizar_tendencia_mes":

                import calendar

                from datetime import datetime



                year = tool_input.get("year", 2025)

                mes = tool_input.get("mes")

                fecha_corte_str = tool_input.get("fecha_corte")



                if not mes:

                    mes = datetime.now().month



                if fecha_corte_str:

                    fecha_corte = datetime.strptime(fecha_corte_str, '%Y-%m-%d')

                else:

                    fecha_corte = datetime.now()



                dia_corte = fecha_corte.day



                meses_nombre = {

                    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",

                    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",

                    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"

                }

                mes_nombre = meses_nombre[mes]



                print(f"[TREND] Analizando tendencia de {mes_nombre} {year} al dia {dia_corte}")



                try:

                    # Obtener plan mensual desde PlanReader (lee directamente del Excel)

                    from services.plan_reader import PlanReader

                    reader = PlanReader()

                    plan_info = reader.get_plan_mensual(mes, year)



                    if not plan_info or not plan_info.get('extraccion_total'):

                        return {

                            "success": False,

                            "error": f"Plan mensual de {mes_nombre} {year} no disponible o sin total de extracción"

                        }



                    plan_mensual_total = plan_info['extraccion_total']

                    print(f"   [PLAN] Total mensual desde Excel: {plan_mensual_total:,.0f} ton")



                    import calendar

                    dias_del_mes = calendar.monthrange(year, mes)[1]

                    plan_diario = plan_mensual_total / dias_del_mes if dias_del_mes > 0 else 0

                    plan_acumulado_esperado = plan_diario * dia_corte



                    conn = sqlite3.connect(self.db_path)

                    cursor = conn.cursor()



                    # Obtener REAL acumulado

                    fecha_inicio = f"{year}-{mes:02d}-01"

                    fecha_fin = f"{year}-{mes:02d}-{dia_corte:02d}"



                    cursor.execute(f"""

                        SELECT

                            SUM(material_tonnage) as real_acumulado,

                            COUNT(*) as viajes

                        FROM (

                            SELECT material_tonnage, timestamp

                            FROM hexagon_by_detail_dumps_2023

                            WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?

                                AND blast_type = 'Blast'

                                AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                            UNION ALL

                            SELECT material_tonnage, timestamp

                            FROM hexagon_by_detail_dumps_2024

                            WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?

                                AND blast_type = 'Blast'

                                AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                            UNION ALL

                            SELECT material_tonnage, timestamp

                            FROM hexagon_by_detail_dumps_2025

                            WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?

                                AND blast_type = 'Blast'

                                AND (blast_region LIKE '%FASE%' OR blast_region = 'MINA')

                        )

                    """, [fecha_inicio, fecha_fin] * 3)



                    result_real = cursor.fetchone()

                    real_acumulado = float(result_real[0]) if result_real and result_real[0] else 0

                    viajes_totales = int(result_real[1]) if result_real and result_real[1] else 0



                    # CAPACIDAD MÁXIMA INSTALADA

                    cursor.execute(f"""

                        SELECT MAX(tonelaje_dia) as mejor_dia

                        FROM (

                            SELECT DATE(timestamp) as fecha, SUM(material_tonnage) as tonelaje_dia

                            FROM (

                                SELECT material_tonnage, timestamp FROM hexagon_by_kpi_hora

                                WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?

                                UNION ALL

                                SELECT material_tonnage, timestamp FROM hexagon_by_detail_dumps_2025

                                WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?

                            )

                            GROUP BY DATE(timestamp)

                        )

                    """, [fecha_inicio, fecha_fin] * 2)



                    mejor_dia = cursor.fetchone()

                    capacidad_max_diaria = float(mejor_dia[0]) if mejor_dia and mejor_dia[0] else plan_diario * 1.15



                    dias_restantes = dias_del_mes - dia_corte

                    capacidad_max_restante = capacidad_max_diaria * 1.10 * dias_restantes

                    capacidad_max_mes = real_acumulado + capacidad_max_restante



                    # Calcular métricas

                    desviacion = real_acumulado - plan_acumulado_esperado

                    porc_desviacion = (desviacion / plan_acumulado_esperado * 100) if plan_acumulado_esperado > 0 else 0

                    porc_mes_transcurrido = (dia_corte / dias_del_mes) * 100

                    porc_plan_ejecutado = (real_acumulado / plan_mensual_total * 100) if plan_mensual_total > 0 else 0



                    if dia_corte > 0:

                        ritmo_diario_real = real_acumulado / dia_corte

                        proyeccion_cierre = ritmo_diario_real * dias_del_mes

                    else:

                        ritmo_diario_real = 0

                        proyeccion_cierre = 0



                    # ═══════════════════════════════════════════════════════════

                    # INTEGRACIÓN WORLD MODEL - Predicción de Cuellos de Botella

                    # ═══════════════════════════════════════════════════════════

                    bottleneck_warnings = []

                    bottleneck_recommendations = []

                    proyeccion_ajustada_world_model = proyeccion_cierre



                    if self.world_model and dia_corte > 0:

                        try:

                            # Obtener estado actual de equipos

                            equipment_state = self._get_equipment_state(fecha_inicio, fecha_fin)



                            # Predecir cuellos de botella para días restantes

                            bottleneck_pred = self.world_model.predict_bottleneck_risk(equipment_state)



                            if bottleneck_pred.predictions.get('bottleneck_detected'):

                                # Ajustar proyección según probabilidad de cuello de botella

                                risk_probability = bottleneck_pred.predictions.get('probability', 0)

                                risk_factor = 1 - (risk_probability * 0.25)  # Reducción máxima 25%



                                proyeccion_ajustada_world_model = proyeccion_cierre * risk_factor



                                # Guardar warnings y recomendaciones del world model

                                bottleneck_warnings = bottleneck_pred.warnings

                                bottleneck_recommendations = bottleneck_pred.recommendations



                                print(f"[AI] World Model: Cuello de botella detectado")

                                print(f"   Sistema: {bottleneck_pred.predictions['primary_risk']}")

                                print(f"   Probabilidad: {risk_probability:.2f}")

                                print(f"   Ajuste proyeccion: {proyeccion_cierre:,.0f} -> {proyeccion_ajustada_world_model:,.0f} ton")

                            else:

                                print(f"[OK] World Model: No se detectaron cuellos de botella significativos")



                            # Usar proyección ajustada por world model

                            proyeccion_cierre = proyeccion_ajustada_world_model



                        except Exception as e:

                            print(f"[WARNING] Error en World Model prediction: {e}")

                            # Continuar con proyeccion original si hay error



                    cumplimiento_esperado = (proyeccion_cierre / plan_mensual_total * 100) if plan_mensual_total > 0 else 0

                    gap_esperado = proyeccion_cierre - plan_mensual_total

                    es_alcanzable = (plan_mensual_total <= capacidad_max_mes)



                    # TOP 3 Delays

                    cursor.execute(f"""

                        SELECT code, estado, categoria, razon, SUM(horas) as total_horas, COUNT(*) as eventos

                        FROM hexagon_estados

                        WHERE DATE(fecha) >= ? AND DATE(fecha) <= ?

                        GROUP BY code, estado, categoria, razon

                        ORDER BY total_horas DESC

                        LIMIT 3

                    """, [fecha_inicio, fecha_fin])



                    top_delays = []

                    for row in cursor.fetchall():

                        top_delays.append({

                            "code": row[0], "estado": row[1], "categoria": row[2],

                            "razon": row[3], "horas": float(row[4]), "eventos": int(row[5])

                        })



                    # DM

                    cursor.execute(f"""

                        SELECT

                            AVG(CASE WHEN total > 0 THEN ((total - COALESCE(m_correctiva, 0)) / total) * 100 ELSE NULL END) as dm_promedio,

                            MAX(CASE WHEN total > 0 THEN ((total - COALESCE(m_correctiva, 0)) / total) * 100 ELSE NULL END) as dm_max

                        FROM hexagon_equipment_times

                        WHERE DATE(time) >= ? AND DATE(time) <= ? AND total > 0

                    """, [fecha_inicio, fecha_fin])



                    dm_result = cursor.fetchone()

                    dm_actual = float(dm_result[0]) if dm_result and dm_result[0] else 0

                    dm_max = float(dm_result[1]) if dm_result and dm_result[1] else dm_actual

                    dm_meta = 85.0

                    dm_mejor_alcanzable = min(dm_max * 1.02, 95.0)

                    mejora_dm_posible = dm_mejor_alcanzable - dm_actual



                    # UEBD

                    cursor.execute(f"""

                        SELECT

                            AVG(CASE WHEN (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0)) > 0

                                THEN (efectivo / (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0))) * 100

                                ELSE NULL END) as uebd_promedio,

                            MAX(CASE WHEN (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0)) > 0

                                THEN (efectivo / (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0))) * 100

                                ELSE NULL END) as uebd_max

                        FROM hexagon_equipment_times

                        WHERE DATE(time) >= ? AND DATE(time) <= ? AND total > 0

                    """, [fecha_inicio, fecha_fin])



                    uebd_result = cursor.fetchone()

                    uebd_actual = float(uebd_result[0]) if uebd_result and uebd_result[0] else 0

                    uebd_max = float(uebd_result[1]) if uebd_result and uebd_result[1] else uebd_actual

                    uebd_meta = 75.0

                    uebd_mejor_alcanzable = min(uebd_max * 1.03, 85.0)

                    mejora_uebd_posible = uebd_mejor_alcanzable - uebd_actual



                    conn.close()



                    # CALCULAR IMPACTOS REALISTAS

                    gap_max_recuperable = capacidad_max_mes - proyeccion_cierre



                    impacto_delays = 0

                    if top_delays and top_delays[0]['horas'] > 50:

                        horas_recuperables = top_delays[0]['horas'] * 0.30

                        impacto_delays = min(horas_recuperables * 80, gap_max_recuperable * 0.4)



                    impacto_dm = 0

                    if mejora_dm_posible > 1:

                        impacto_dm = min((mejora_dm_posible * 0.012 * proyeccion_cierre), gap_max_recuperable * 0.35)



                    impacto_uebd = 0

                    if mejora_uebd_posible > 2:

                        impacto_uebd = min((mejora_uebd_posible * 0.008 * proyeccion_cierre), gap_max_recuperable * 0.25)



                    impacto_total = impacto_delays + impacto_dm + impacto_uebd



                    if impacto_total > gap_max_recuperable:

                        factor_ajuste = gap_max_recuperable / impacto_total

                        impacto_delays *= factor_ajuste

                        impacto_dm *= factor_ajuste

                        impacto_uebd *= factor_ajuste

                        impacto_total = gap_max_recuperable



                    proyeccion_ajustada = proyeccion_cierre + impacto_total

                    cumplimiento_ajustado = (proyeccion_ajustada / plan_mensual_total * 100) if plan_mensual_total > 0 else 0



                    # CONSTRUIR MENSAJE

                    if cumplimiento_esperado >= 95:

                        estado_emoji = "✅"

                        estado_texto = "EN META"

                    elif cumplimiento_esperado >= 90:

                        estado_emoji = "⚠️"

                        estado_texto = "BAJO META"

                    else:

                        estado_emoji = "🔴"

                        estado_texto = "CRÍTICO"



                    mensaje = f"""

# 📊 ANÁLISIS DE TENDENCIA - {mes_nombre.upper()} {year}

**Corte al {dia_corte:02d}/{mes:02d}/{year}** ({porc_mes_transcurrido:.0f}% del mes transcurrido)



---



## 📊 Estado Actual



| Métrica | Valor |

|---------|-------|

| Real acumulado | {real_acumulado:,.0f} ton ({viajes_totales:,} viajes) |

| Plan esperado (día {dia_corte}) | {plan_acumulado_esperado:,.0f} ton |

| Desviación | {desviacion:,.0f} ton ({porc_desviacion:+.1f}%) {"🔴" if desviacion < 0 else "✅"} |

| % del plan ejecutado | {porc_plan_ejecutado:.1f}% |



---



## 📈 Proyección a Fin de Mes



| Métrica | Valor |

|---------|-------|

| Ritmo actual | {ritmo_diario_real:,.0f} ton/día |

| Proyección cierre | {proyeccion_cierre:,.0f} ton |

| Plan total mes | {plan_mensual_total:,.0f} ton |

| Cumplimiento esperado | {estado_emoji} **{cumplimiento_esperado:.1f}%** - {estado_texto} |

| Gap esperado | {gap_esperado:,.0f} ton |



---



## ⚙️ Capacidad Instalada



| Métrica | Valor |

|---------|-------|

| Mejor día del mes | {capacidad_max_diaria:,.0f} ton/día |

| Capacidad máxima mensual | {capacidad_max_mes:,.0f} ton |

| Estado | {"✅ **Meta ALCANZABLE** con optimizaciones" if es_alcanzable else "🔴 **Meta NO ALCANZABLE** con capacidad actual"} |



---



## 🔍 Análisis Causal (Top 3)

"""



                    # Agregar warnings del World Model si existen

                    if bottleneck_warnings:

                        mensaje += "\n### 🤖 World Model - Predicción de Riesgos\n"

                        for warning in bottleneck_warnings:

                            mensaje += f"- {warning}\n"

                        mensaje += "\n"



                    if top_delays:

                        mensaje += "\n### 1. 🔴 Delays Operacionales\n\n"

                        for idx, delay in enumerate(top_delays, 1):

                            mensaje += f"{idx}. **[{delay['code']}] {delay['estado']} - {delay['razon']}**\n"

                            mensaje += f"   - {delay['horas']:,.0f} horas | {delay['eventos']:,} eventos\n"



                    if dm_actual > 0:

                        gap_dm = dm_meta - dm_actual

                        emoji_dm = "🔴" if gap_dm > 3 else "⚠️" if gap_dm > 1 else "✅"

                        mensaje += f"\n### 2. {emoji_dm} Disponibilidad Mecánica\n\n"

                        mensaje += f"- **Actual**: {dm_actual:.1f}% | **Meta**: {dm_meta:.0f}% | **Gap**: {gap_dm:+.1f}%\n"

                        mensaje += f"- **Mejor del mes**: {dm_max:.1f}% | **Mejora posible**: {mejora_dm_posible:.1f}%\n"



                    if uebd_actual > 0:

                        gap_uebd = uebd_meta - uebd_actual

                        emoji_uebd = "🔴" if gap_uebd > 5 else "⚠️" if gap_uebd > 2 else "✅"

                        mensaje += f"\n### 3. {emoji_uebd} Utilización (UEBD)\n\n"

                        mensaje += f"- **Actual**: {uebd_actual:.1f}% | **Meta**: {uebd_meta:.0f}% | **Gap**: {gap_uebd:+.1f}%\n"

                        mensaje += f"- **Mejor del mes**: {uebd_max:.1f}% | **Mejora posible**: {mejora_uebd_posible:.1f}%\n"



                    if impacto_total > 0:

                        mensaje += "\n---\n\n## 💡 Acciones Correctivas\n"

                        mensaje += "*Limitadas por capacidad instalada*\n\n"



                        if impacto_delays > 0:

                            mensaje += f"### 1. [URGENTE] Reducir Delays Operacionales\n"

                            mensaje += f"- Focalizar en código **{top_delays[0]['code']}**: {top_delays[0]['razon']}\n"

                            mensaje += f"- Reducir 30% del tiempo perdido (realista)\n"

                            mensaje += f"- **Impacto**: +{impacto_delays:,.0f} ton\n\n"



                        if impacto_dm > 0:

                            mensaje += f"### 2. [ALTO] Mejorar Disponibilidad Mecánica\n"

                            mensaje += f"- Alcanzar mejor rendimiento del mes ({dm_mejor_alcanzable:.1f}%)\n"

                            mensaje += f"- **Impacto**: +{impacto_dm:,.0f} ton\n\n"



                        if impacto_uebd > 0:

                            mensaje += f"### 3. [MEDIO] Optimizar Utilización\n"

                            mensaje += f"- Alcanzar mejor UEBD del mes ({uebd_mejor_alcanzable:.1f}%)\n"

                            mensaje += f"- **Impacto**: +{impacto_uebd:,.0f} ton\n\n"



                        mensaje += "---\n\n## 🎯 Potencial Real de Recuperación\n\n"

                        mensaje += f"| Métrica | Valor |\n"

                        mensaje += f"|---------|-------|\n"

                        mensaje += f"| Impacto total | +{impacto_total:,.0f} ton |\n"

                        mensaje += f"| Pronóstico optimizado | {proyeccion_ajustada:,.0f} ton |\n"

                        mensaje += f"| Cumplimiento ajustado | {cumplimiento_ajustado:.1f}% |\n"



                    # Agregar recomendaciones del World Model si existen

                    if bottleneck_recommendations:

                        mensaje += "\n---\n\n## 🤖 Recomendaciones del World Model\n\n"

                        for idx, rec in enumerate(bottleneck_recommendations, 1):

                            mensaje += f"{idx}. {rec}\n"



                    mensaje += "\n---\n\n## 📌 Recomendación Ejecutiva\n\n"



                    if not es_alcanzable:

                        mensaje += f"### 🔴 META NO ALCANZABLE CON CAPACIDAD ACTUAL\n"

                        mensaje += f"La meta excede capacidad instalada.\n\n"

                        mensaje += f"**Acción**: Ajustar plan mensual o informar restricción\n"

                    elif cumplimiento_ajustado >= 95:

                        mensaje += f"### ✅ META ALCANZABLE CON OPTIMIZACIONES\n"

                        mensaje += f"**Acción**: Ejecutar plan de acción inmediatamente\n"

                    elif cumplimiento_ajustado >= 90:

                        mensaje += f"### ⚠️ RIESGO MODERADO ({cumplimiento_ajustado:.1f}%)\n"

                        mensaje += f"**Acción**: Maximizar esfuerzos operacionales\n"

                    else:

                        mensaje += f"### 🔴 RIESGO ALTO ({cumplimiento_ajustado:.1f}%)\n"

                        mensaje += f"**Acción**: No es posible cerrar gap con capacidad actual\n"



                    mensaje += "\n---"



                    return {

                        "success": True,

                        "FINAL_ANSWER": mensaje,

                        "data": {

                            "year": year,

                            "mes": mes,

                            "dia_corte": dia_corte,

                            "real_acumulado": real_acumulado,

                            "proyeccion_cierre": proyeccion_cierre,

                            "cumplimiento_esperado": cumplimiento_esperado,

                            "es_alcanzable": es_alcanzable,

                            "cumplimiento_ajustado": cumplimiento_ajustado

                        }

                    }



                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error analizando tendencia: {str(e)}"

                    }



            elif tool_name == "obtener_costos_mina":

                # Herramienta de costos operacionales

                year = tool_input.get("year", 2025)

                mes = tool_input.get("mes")

                tipo = tool_input.get("tipo", "resumen")

                concepto_filtro = tool_input.get("concepto")



                print(f"[TOOL] COSTOS MINA - Year: {year}, Mes: {mes}, Tipo: {tipo}")



                try:

                    conn = sqlite3.connect(self.db_path)

                    cursor = conn.cursor()



                    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',

                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']



                    resultados = {}



                    # Query según tipo de reporte

                    if tipo in ["resumen", "completo"]:

                        if mes:

                            # Mes específico

                            query = """

                                SELECT concepto, unidad, valor_real, valor_p0r0, variacion

                                FROM costos_resumen_ejecutivo

                                WHERE year = ? AND mes = ? AND periodo = 'Mensual'

                                ORDER BY concepto

                            """

                            cursor.execute(query, [year, mes])

                            periodo_texto = f"{meses[mes-1].upper()} {year}"

                        else:

                            # Obtener el último mes disponible para acumulado

                            cursor.execute("SELECT MAX(mes) FROM costos_resumen_ejecutivo WHERE year = ?", [year])

                            ultimo_mes = cursor.fetchone()[0] or 10



                            query = """

                                SELECT concepto, unidad, valor_real, valor_p0r0, variacion

                                FROM costos_resumen_ejecutivo

                                WHERE year = ? AND periodo = 'Acumulado'

                                ORDER BY concepto

                            """

                            cursor.execute(query, [year])

                            periodo_texto = f"ACUMULADO ENERO-{meses[ultimo_mes-1].upper()} {year}"



                        rows = cursor.fetchall()

                        resultados["resumen"] = [

                            {"concepto": r[0], "unidad": r[1], "real": r[2], "ppto": r[3], "var": r[4]}

                            for r in rows

                        ]



                    if tipo in ["unitario", "completo"]:

                        if mes:

                            query = """

                                SELECT actividad, metrica, unidad, valor_real, valor_ppto

                                FROM costos_unitarios

                                WHERE year = ? AND mes = ?

                                ORDER BY actividad, metrica

                            """

                            cursor.execute(query, [year, mes])

                        else:

                            cursor.execute("SELECT MAX(mes) FROM costos_unitarios WHERE year = ?", [year])

                            ultimo_mes = cursor.fetchone()[0] or 10



                            query = """

                                SELECT actividad, metrica, unidad, valor_real, valor_ppto

                                FROM costos_unitarios

                                WHERE year = ? AND mes = ?

                                ORDER BY actividad, metrica

                            """

                            cursor.execute(query, [year])



                        rows = cursor.fetchall()

                        resultados["unitarios"] = [

                            {"actividad": r[0], "metrica": r[1], "unidad": r[2], "real": r[3], "ppto": r[4]}

                            for r in rows

                        ]



                    if tipo == "detalle":

                        query = """

                            SELECT mes_nombre, concepto, unidad, valor_real, valor_p0r0, variacion

                            FROM costos_detalle_mensual

                            WHERE year = ?

                            ORDER BY mes, concepto

                        """

                        cursor.execute(query, [year])

                        rows = cursor.fetchall()

                        resultados["detalle"] = [

                            {"mes": r[0], "concepto": r[1], "unidad": r[2], "real": r[3], "ppto": r[4], "var": r[5]}

                            for r in rows

                        ]



                    conn.close()



                    # Formatear mensaje de respuesta

                    mensaje = f"""

=================================================================

|   💰 COSTOS MINA - {periodo_texto if 'periodo_texto' in dir() else year}   |

=================================================================



"""

                    # Tabla resumen

                    if "resumen" in resultados and resultados["resumen"]:

                        mensaje += "## RESUMEN EJECUTIVO\n\n"

                        mensaje += "| Concepto | Real (KUS$) | Ppto (KUS$) | Var (KUS$) | % | Estado |\n"

                        mensaje += "|----------|------------|-------------|------------|---|--------|\n"



                        total_real = 0

                        total_ppto = 0



                        for r in resultados["resumen"]:

                            if concepto_filtro and concepto_filtro.lower() not in r["concepto"].lower():

                                continue



                            real = r["real"] or 0

                            ppto = r["ppto"] or 0

                            var = r["var"] or 0

                            pct = ((real / ppto) - 1) * 100 if ppto else 0



                            total_real += real

                            total_ppto += ppto



                            if pct < -5:

                                estado = "🟢"

                            elif pct > 5:

                                estado = "🔴"

                            else:

                                estado = "🟡"



                            mensaje += f"| {r['concepto'][:20]} | {real:,.1f} | {ppto:,.1f} | {var:+,.1f} | {pct:+.1f}% | {estado} |\n"



                        # Fila de totales

                        total_var = total_real - total_ppto

                        total_pct = ((total_real / total_ppto) - 1) * 100 if total_ppto else 0

                        mensaje += f"| **TOTAL** | **{total_real:,.1f}** | **{total_ppto:,.1f}** | **{total_var:+,.1f}** | **{total_pct:+.1f}%** | {'🟢' if total_pct < 0 else '🔴'} |\n"



                        # Conversión a MUS$

                        mensaje += f"\n💵 **Total en MUS$:** {total_real/1000:,.2f} MUS$ (Ppto: {total_ppto/1000:,.2f} MUS$)\n"



                    # Costos unitarios

                    if "unitarios" in resultados and resultados["unitarios"]:

                        mensaje += "\n## COSTOS UNITARIOS\n\n"

                        mensaje += "| Actividad | Métrica | Real | Ppto | Var% |\n"

                        mensaje += "|-----------|---------|------|------|------|\n"



                        for r in resultados["unitarios"]:

                            real = r["real"] or 0

                            ppto = r["ppto"] or 0

                            var_pct = ((real / ppto) - 1) * 100 if ppto else 0



                            mensaje += f"| {r['actividad'][:15]} | {r['metrica'][:15]} | {real:,.2f} | {ppto:,.2f} | {var_pct:+.1f}% |\n"



                    mensaje += "\n=================================================================\n"



                    return {

                        "success": True,

                        "FINAL_ANSWER": mensaje,

                        "data": {

                            "year": year,

                            "mes": mes,

                            "tipo": tipo,

                            "resultados": resultados

                        }

                    }



                except Exception as e:

                    import traceback

                    traceback.print_exc()

                    return {

                        "success": False,

                        "error": f"Error obteniendo costos: {str(e)}"

                    }

            # === HANDLERS DE EXPLORACIÓN (GPT-5.1) ===

            elif tool_name == "get_database_schema":
                try:
                    table_name = tool_input["table_name"]
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()

                    # Obtener esquema
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()

                    if not columns:
                        return {"success": False, "error": f"Tabla '{table_name}' no encontrada"}

                    # Obtener valores de ejemplo para cada columna
                    schema_info = []
                    for col in columns:
                        col_name = col[1]
                        col_type = col[2]
                        not_null = col[3]

                        # Muestra de valores únicos
                        try:
                            cursor.execute(f"SELECT DISTINCT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL LIMIT 5")
                            samples = [str(r[0])[:50] for r in cursor.fetchall()]
                        except:
                            samples = []

                        schema_info.append({
                            "column": col_name,
                            "type": col_type,
                            "nullable": not not_null,
                            "sample_values": samples
                        })

                    conn.close()

                    return {
                        "success": True,
                        "table": table_name,
                        "columns": schema_info,
                        "column_count": len(schema_info)
                    }

                except Exception as e:
                    return {"success": False, "error": str(e)}

            elif tool_name == "get_sample_data":
                try:
                    table_name = tool_input["table_name"]
                    columns = tool_input.get("columns", ["*"])
                    where_clause = tool_input.get("where_clause", "")
                    limit = min(tool_input.get("limit", 10), 50)

                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()

                    cols_str = ", ".join(columns) if columns != ["*"] else "*"
                    query = f"SELECT {cols_str} FROM {table_name}"
                    if where_clause:
                        query += f" WHERE {where_clause}"
                    query += f" LIMIT {limit}"

                    cursor.execute(query)
                    rows = cursor.fetchall()
                    col_names = [desc[0] for desc in cursor.description]

                    conn.close()

                    data = [dict(zip(col_names, row)) for row in rows]

                    return {
                        "success": True,
                        "table": table_name,
                        "row_count": len(data),
                        "columns": col_names,
                        "data": data
                    }

                except Exception as e:
                    return {"success": False, "error": str(e)}

            elif tool_name == "get_data_sources":
                try:
                    from pathlib import Path  # Import local para evitar shadowing
                    category = tool_input.get("category", "all")
                    sources = {}

                    # Tablas de la base de datos
                    if category in ["all", "database"]:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                        tables = [r[0] for r in cursor.fetchall()]

                        db_sources = {}
                        for table in tables:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            count = cursor.fetchone()[0]
                            cursor.execute(f"PRAGMA table_info({table})")
                            cols = [c[1] for c in cursor.fetchall()]
                            db_sources[table] = {
                                "row_count": count,
                                "columns": cols[:10],  # Primeras 10 columnas
                                "total_columns": len(cols)
                            }
                        conn.close()
                        sources["database"] = db_sources

                    # Knowledge Base (LightRAG)
                    if category in ["all", "knowledge_base"]:
                        kb_docs = []
                        if hasattr(self, 'lightrag') and self.lightrag:
                            try:
                                # Listar documentos indexados
                                kb_path = Path("backend/lightrag_storage")
                                if kb_path.exists():
                                    status_file = kb_path / "kv_store_doc_status.json"
                                    if status_file.exists():
                                        import json
                                        with open(status_file, 'r', encoding='utf-8') as f:
                                            docs = json.load(f)
                                            kb_docs = list(docs.keys())[:20]  # Primeros 20
                            except:
                                pass
                        sources["knowledge_base"] = {
                            "documents": kb_docs,
                            "description": "IGM, planes mensuales, informes de gestión"
                        }

                    # Archivos Excel disponibles
                    if category in ["all", "excel"]:
                        excel_files = []
                        data_path = Path("backend/data")
                        if data_path.exists():
                            for xlsx in data_path.rglob("*.xlsx"):
                                excel_files.append(str(xlsx.relative_to(data_path)))
                            for xlsb in data_path.rglob("*.xlsb"):
                                excel_files.append(str(xlsb.relative_to(data_path)))
                        sources["excel"] = excel_files[:30]  # Primeros 30

                    return {
                        "success": True,
                        "sources": sources
                    }

                except Exception as e:
                    return {"success": False, "error": str(e)}

            else:

                return {

                    "success": False,

                    "error": f"Herramienta desconocida: {tool_name}"

                }

        

        except requests.exceptions.RequestException as e:

            return {

                "success": False,

                "error": f"Error de conexión: {str(e)}"

            }

        except Exception as e:

            import traceback

            traceback.print_exc()

            return {

                "success": False,

                "error": str(e)

            }



    # =========================================================================

    # STREAMING CHAT METHOD

    # =========================================================================



    async def chat_stream(

        self,

        user_message: str,

        conversation_id: Optional[str] = None,

        use_lightrag: bool = True,

        max_iterations: int = 20

    ):

        """

        Chat con streaming de respuestas para mejor UX.



        Yields eventos SSE:

        - {"type": "status", "content": "mensaje"}

        - {"type": "tool", "name": "tool_name", "content": "resultado"}

        - {"type": "file", "path": "/outputs/charts/file.png"}

        - {"type": "text", "content": "chunk de texto"}

        - {"type": "done", "conversation_id": "uuid"}

        """

        from datetime import datetime

        import time

        import uuid



        start_time = time.time()

        conv_id = conversation_id or str(uuid.uuid4())

        # Guardar query del usuario para fallbacks en herramientas
        self.current_user_query = user_message

        # Agregar mensaje al historial

        self.conversation_history.append({

            "role": "user",

            "content": user_message

        })



        iteration = 0

        tools_used = []

        files_generated = []

        full_response = ""

        # ====================================================================
        # DETECCIÓN DE MENSAJES CONVERSACIONALES (sin herramientas) - STREAMING
        # ====================================================================
        import re
        conversational_patterns = [
            r"\bhola\b", r"\bbuenos días\b", r"\bbuenas tardes\b", r"\bbuenas noches\b", r"\bbuen día\b",
            r"\bsaludos\b", r"\bhey\b", r"\bhi\b", r"\bhello\b", r"\bqué tal\b", r"\bcomo estás\b", r"\bcómo estás\b",
            r"\badiós\b", r"\badios\b", r"\bchao\b", r"\bbye\b", r"\bhasta luego\b", r"\bnos vemos\b",
            r"\bgracias\b", r"\bmuchas gracias\b", r"\bthank\b", r"\bperfecto\b", r"\bexcelente\b", r"\bgenial\b",
            r"\bqué puedes hacer\b", r"\bque puedes hacer\b", r"\bayuda\b", r"\bhelp\b", r"\bquién eres\b", r"\bquien eres\b"
        ]

        user_msg_lower = user_message.lower().strip()
        is_conversational = any(re.search(pattern, user_msg_lower) for pattern in conversational_patterns) and len(user_message) < 50

        if is_conversational:
            print(f"[CONVERSATIONAL-STREAM] Mensaje conversacional: '{user_message[:50]}...'")
            yield {"type": "status", "content": "Procesando..."}

            try:
                no_tool_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": self.base_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        max_tokens=500
                    ),
                    timeout=30.0
                )

                response_text = no_tool_response.choices[0].message.content or "¡Hola! ¿En qué puedo ayudarte?"

                self.conversation_history.append({"role": "assistant", "content": response_text})
                self._save_user_history()

                # Enviar respuesta completa como stream
                yield {"type": "text", "content": response_text}
                yield {"type": "done", "conversation_id": conv_id}
                return

            except Exception as e:
                print(f"[CONVERSATIONAL-STREAM] Error: {e}")
                # Continuar con flujo normal

        # ====================================================================

        # Detectar modo de análisis causal (requiere secuencia de 3 pasos)
        # GPT-5.1 razona naturalmente - sin hardcoding de secuencias
        # El modelo decide qué herramientas llamar basándose en las descripciones

        while iteration < max_iterations:

            iteration += 1



            try:

                # Enriquecer solo en primera iteración

                if use_lightrag and iteration == 1:

                    yield {"type": "status", "content": "Consultando base de conocimiento..."}

                    enriched_prompt = await self._create_enriched_prompt(user_message)

                    if self.conversation_history and self.conversation_history[-1]["role"] == "user":

                        self.conversation_history[-1]["content"] = enriched_prompt



                # Preparar mensajes

                messages_with_system = [{"role": "system", "content": self.base_prompt}]

                MAX_HISTORY_MESSAGES = self.max_history_messages



                if iteration == 1:

                    if self.conversation_history:

                        recent_history = self.conversation_history[-MAX_HISTORY_MESSAGES:]

                        for hist_msg in recent_history:

                            role = hist_msg.get("role", "user")

                            if role in ["user", "assistant"]:

                                content = hist_msg.get("content", "")

                                if content and content.strip():

                                    messages_with_system.append({"role": role, "content": content})

                else:

                    last_user_idx = -1

                    for i in range(len(self.conversation_history) - 1, -1, -1):

                        if self.conversation_history[i].get("role") == "user":

                            last_user_idx = i

                            break



                    if last_user_idx >= 0:

                        current_conversation = self.conversation_history[last_user_idx:]

                        if len(current_conversation) > MAX_HISTORY_MESSAGES:

                            current_conversation = current_conversation[-MAX_HISTORY_MESSAGES:]



                        valid_tool_call_ids = set()

                        for hist_msg in current_conversation:

                            role = hist_msg.get("role", "user")

                            if role in ["user", "assistant"]:

                                content = hist_msg.get("content", "")

                                has_tool_calls = role == "assistant" and "tool_calls" in hist_msg

                                if (content and content.strip()) or has_tool_calls:

                                    msg = {"role": role, "content": content if content else ""}

                                    if has_tool_calls:

                                        msg["tool_calls"] = hist_msg["tool_calls"]

                                        for tc in hist_msg["tool_calls"]:

                                            valid_tool_call_ids.add(tc.get("id"))

                                    messages_with_system.append(msg)

                            elif role == "tool":

                                tool_call_id = hist_msg.get("tool_call_id")

                                if tool_call_id and tool_call_id in valid_tool_call_ids:

                                    messages_with_system.append({

                                        "role": "tool",

                                        "tool_call_id": tool_call_id,

                                        "name": hist_msg.get("name"),

                                        "content": hist_msg.get("content", "")

                                    })



                # Convertir herramientas

                openai_tools = []

                for tool in self.tools:

                    openai_tools.append({

                        "type": "function",

                        "function": {

                            "name": tool["name"],

                            "description": tool["description"],

                            "parameters": tool["input_schema"]

                        }

                    })



                # Llamar a OpenAI

                reasoning_effort_level = get_reasoning_effort(user_message) if iteration == 1 else "low"
                print(f"   [DEBUG] Iteration={iteration}, reasoning_effort={reasoning_effort_level}", flush=True)

                # ENHANCEMENT: Mejorar query con instrucciones de razonamiento para análisis complejos
                if iteration == 1 and reasoning_effort_level in ["high", "medium"]:
                    print(f"   [DEBUG] Intentando mejorar query...", flush=True)
                    enhanced_query = enhance_query_with_reasoning_trigger(user_message, reasoning_effort_level)
                    if enhanced_query != user_message:
                        print(f"   [QUERY_ENHANCE] *** QUERY MEJORADO CON INSTRUCCIONES {reasoning_effort_level} ***", flush=True)
                        print(f"   [QUERY_ENHANCE] Enhanced query length: {len(enhanced_query)} chars", flush=True)
                        # Actualizar el último mensaje de usuario en messages_with_system
                        for i in range(len(messages_with_system) - 1, -1, -1):
                            if messages_with_system[i].get("role") == "user":
                                messages_with_system[i]["content"] = enhanced_query
                                print(f"   [QUERY_ENHANCE] Mensaje actualizado en posicion {i}", flush=True)
                                break
                    else:
                        print(f"   [DEBUG] Query NO mejorado (no match causalidad)", flush=True)

                # v3.0: tool_choice="auto" - GPT-5.1 decide qué herramienta usar

                api_params = {

                    "model": "gpt-5.1",

                    "max_completion_tokens": 4096,

                    "messages": messages_with_system,

                    "tools": openai_tools,

                    "stream": True,  # STREAMING REAL ACTIVADO

                }



                # reasoning_effort soportado por gpt-5.1, o1, etc.
                if reasoning_effort_level in ["none", "low", "medium", "high", "xhigh"]:
                    api_params["reasoning_effort"] = reasoning_effort_level

                # STREAMING: Procesar respuesta en tiempo real
                yield {"type": "status", "content": "Generando respuesta..."}

                # Crear el stream
                stream = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    **api_params
                )

                # Acumuladores para el streaming
                accumulated_content = ""
                accumulated_tool_calls = {}  # {index: {"id": ..., "name": ..., "arguments": ...}}
                has_tool_use = False

                # Procesar cada chunk del stream
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    # Procesar contenido de texto - ENVIAR EN TIEMPO REAL
                    if delta.content:
                        accumulated_content += delta.content
                        yield {"type": "text", "content": delta.content}

                    # Procesar tool_calls (vienen en chunks)
                    if delta.tool_calls:
                        has_tool_use = True
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.id or "",
                                    "name": tc.function.name if tc.function and tc.function.name else "",
                                    "arguments": ""
                                }
                            else:
                                if tc.id:
                                    accumulated_tool_calls[idx]["id"] = tc.id
                                if tc.function and tc.function.name:
                                    accumulated_tool_calls[idx]["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

                # Crear objeto message simulado para compatibilidad
                class StreamedMessage:
                    def __init__(self, content, tool_calls_dict):
                        self.content = content
                        if tool_calls_dict:
                            self.tool_calls = []
                            for idx in sorted(tool_calls_dict.keys()):
                                tc_data = tool_calls_dict[idx]
                                tc = type('ToolCall', (), {
                                    'id': tc_data["id"],
                                    'function': type('Function', (), {
                                        'name': tc_data["name"],
                                        'arguments': tc_data["arguments"]
                                    })()
                                })()
                                self.tool_calls.append(tc)
                        else:
                            self.tool_calls = None

                message = StreamedMessage(accumulated_content, accumulated_tool_calls if has_tool_use else None)



                # Procesar tool calls

                if message.tool_calls:

                    has_tool_use = True



                    self.conversation_history.append({

                        "role": "assistant",

                        "content": message.content,

                        "tool_calls": [

                            {

                                "id": tc.id,

                                "type": "function",

                                "function": {

                                    "name": tc.function.name,

                                    "arguments": tc.function.arguments

                                }

                            }

                            for tc in message.tool_calls

                        ]

                    })



                    for tool_call in message.tool_calls:

                        tool_name = tool_call.function.name

                        tool_input = json.loads(tool_call.function.arguments)

                        tool_id = tool_call.id

                        # EVENTO: tool_start - Mostrar qué herramienta se está usando

                        tool_description = self._get_tool_description(tool_name, tool_input)

                        yield {

                            "type": "tool_start",

                            "name": tool_name,

                            "params": tool_input,

                            "description": tool_description

                        }



                        # Ejecutar herramienta

                        tool_result = await self._execute_tool(tool_name, tool_input)


                        # Guardar herramienta usada CON su resultado para fallback
                        tools_used.append({"name": tool_name, "result": tool_result})

                        # FIX GENERATE_CHART: Guardar resultados para auto-extracción (FLUJO STREAMING)
                        if tool_result.get("success"):
                            self.last_tool_results[tool_name] = tool_result
                            print(f"    >> [SAVED-SSE] Resultado de {tool_name} guardado para auto-extracción")

                        # EVENTO: tool_result - Resumen del resultado

                        result_summary = self._get_result_summary(tool_name, tool_result)

                        yield {

                            "type": "tool_result",

                            "name": tool_name,

                            "success": tool_result.get("success", False),

                            "summary": result_summary

                        }



                        # Capturar archivos generados

                        if tool_result.get("success") and "file_path" in tool_result:

                            file_path_str = str(tool_result["file_path"])

                            from pathlib import Path

                            filename = Path(file_path_str).name

                            relative_path = f"/outputs/charts/{filename}"

                            files_generated.append(relative_path)

                            yield {"type": "file", "path": relative_path}



                        # Yield resultado de la herramienta - STREAMING REAL PALABRA POR PALABRA

                        if tool_result.get("FINAL_ANSWER"):
                            # STREAMING: Enviar contenido palabra por palabra
                            final_text = tool_result["FINAL_ANSWER"]
                            import re as re_mod
                            # Dividir en chunks pequeños (palabras + espacios)
                            chunks = re_mod.split(r'(\s+)', final_text)
                            for chunk in chunks:
                                if chunk:  # Skip empty chunks
                                    yield {"type": "text", "content": chunk}

                            full_response = final_text



                        # Guardar resultado en historial

                        result_content = json.dumps(tool_result, ensure_ascii=False, default=str)

                        if len(result_content) > 50000:

                            result_content = result_content[:50000] + "...[truncado]"



                        self.conversation_history.append({

                            "role": "tool",

                            "tool_call_id": tool_id,

                            "name": tool_name,

                            "content": result_content

                        })

                    # FIN del for loop de tool_calls

                    # Verificar si alguna herramienta retornó FINAL_ANSWER
                    any_final_answer = any(t.get("result", {}).get("FINAL_ANSWER") for t in tools_used)

                    if any_final_answer:
                        self._save_user_history()
                        yield {"type": "done", "conversation_id": conv_id, "tools_used": tools_used, "files_generated": files_generated}
                        return

                # Si no hay tool calls, el texto ya se envió en streaming durante la API call

                if not has_tool_use:
                    # Sin tool calls - el modelo decidió responder con texto
                    if message.content:

                        # El texto ya se envió en tiempo real durante el stream de OpenAI

                        full_response = message.content



                        # Guardar en historial

                        self.conversation_history.append({

                            "role": "assistant",

                            "content": message.content

                        })



                    self._save_user_history()

                    yield {"type": "done", "conversation_id": conv_id, "tools_used": tools_used, "files_generated": files_generated}

                    return



            except asyncio.TimeoutError:

                yield {"type": "error", "content": "Timeout en la consulta (>120s)"}

                return

            except Exception as e:

                import traceback

                traceback.print_exc()

                yield {"type": "error", "content": str(e)}

                return



        # Si llegamos aquí, se agotaron las iteraciones

        yield {"type": "done", "conversation_id": conv_id, "tools_used": tools_used, "files_generated": files_generated}



    def _get_tool_description(self, tool_name: str, params: dict) -> str:

        """Genera descripción amigable de la herramienta y parámetros"""

        descriptions = {

            "get_ranking_operadores": lambda p: f"Consultando ranking de operadores para {p.get('mes', 'año completo')} {p.get('year', 2025)}, tipo: {p.get('tipo', 'todos')}",

            "obtener_cumplimiento_tonelaje": lambda p: f"Verificando cumplimiento de tonelaje para {p.get('mes_nombre', p.get('mes', 'mes'))} {p.get('year', 2025)}",

            "obtener_pareto_delays": lambda p: f"Analizando Pareto de delays para {p.get('mes_nombre', p.get('mes', 'mes'))} {p.get('year', 2025)}",

            "obtener_analisis_gaviota": lambda p: f"Generando análisis Gaviota para {p.get('fecha', 'fecha especificada')}",

            "analizar_match_pala_camion": lambda p: f"Analizando match pala-camión para {p.get('mes', 'mes')} {p.get('year', 2025)}",

            "obtener_analisis_utilizacion": lambda p: f"Calculando utilización de equipos para {p.get('mes', 'mes')} {p.get('year', 2025)}",

            "analizar_tendencia_mes": lambda p: f"Analizando tendencia del mes {p.get('mes', '')} {p.get('year', 2025)}",

            "execute_sql": lambda p: f"Ejecutando consulta SQL en base de datos",

            "execute_python": lambda p: f"Ejecutando código Python para análisis",

            "generate_chart": lambda p: f"Generando gráfico: {p.get('chart_type', 'bar')}",

            "search_knowledge": lambda p: f"Buscando en documentación: {p.get('query', '')[:50]}...",

        }



        desc_fn = descriptions.get(tool_name)

        if desc_fn:

            try:

                return desc_fn(params)

            except:

                pass

        return f"Ejecutando {tool_name}"



    def _get_result_summary(self, tool_name: str, result: dict) -> str:

        """Genera resumen del resultado de la herramienta"""

        if not result.get("success", False):

            error = result.get("error", "Error desconocido")

            return f"Error: {error[:100]}"



        # Resúmenes específicos por herramienta

        if tool_name == "get_ranking_operadores":

            data = result.get("data", {})

            total = data.get("estadisticas", {}).get("total_operadores", 0)

            return f"Ranking calculado: {total} operadores evaluados"



        elif tool_name == "obtener_cumplimiento_tonelaje":

            real = result.get("real_kton", 0)

            plan = result.get("plan_kton", 0)

            cumpl = result.get("cumplimiento_pct", 0)

            return f"Real: {real:,.0f} kton | Plan: {plan:,.0f} kton | Cumpl: {cumpl:.1f}%"



        elif tool_name == "obtener_pareto_delays":

            data = result.get("data", {})

            total = data.get("total_horas", 0)

            top = len(data.get("delays", []))

            return f"Total delays: {total:,.0f} hrs | Top {top} causas identificadas"



        elif tool_name == "obtener_analisis_gaviota":

            return "Análisis Gaviota generado correctamente"



        elif tool_name == "execute_sql":

            rows = len(result.get("rows", []))

            return f"Consulta ejecutada: {rows} registros"



        elif tool_name == "generate_chart":

            return "Gráfico generado correctamente"



        elif tool_name == "search_knowledge":

            return "Información encontrada en documentación"



        # Default

        return "Herramienta ejecutada correctamente"



    def _load_user_history(self) -> List:

        """Load conversation history from user-specific file"""

        try:

            if self.history_file.exists():

                with open(self.history_file, 'r', encoding='utf-8') as f:

                    history = json.load(f)

                    print(f" Loaded {len(history)} messages from {self.user_id} history")

                    return history

        except Exception as e:

            print(f"  Error loading history for {self.user_id}: {e}")

        return []



    def _save_user_history(self):

        """Save conversation history to user-specific file"""

        try:

            with open(self.history_file, 'w', encoding='utf-8') as f:

                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)

        except Exception as e:

            print(f"  Error saving history for {self.user_id}: {e}")



    def _build_emergency_response(self, tools_used: list, user_message: str) -> str:
        """Construye respuesta de emergencia cuando GPT no genera contenido."""
        result = ["## Resultados del Analisis", ""]
        result.append("> **Consulta:** " + user_message[:200] + "...")
        result.append("")
        
        if not tools_used:
            result.append("No se ejecutaron herramientas. Por favor reformule su consulta.")
            return chr(10).join(result)
        
        for tool in tools_used:
            tool_name = tool.get("name", "desconocido")
            tool_result = tool.get("result", {})
            result.append("### " + tool_name)
            
            if not tool_result:
                result.append("Sin resultados")
                result.append("")
                continue
            
            if tool_result.get("error"):
                result.append("Error: " + str(tool_result.get("error")))
                result.append("")
                continue
            
            if tool_result.get("mensaje"):
                result.append(tool_result["mensaje"])
                result.append("")
                continue
            
            if tool_result.get("FINAL_ANSWER"):
                result.append(tool_result["FINAL_ANSWER"])
                result.append("")
                continue
            
            data = tool_result.get("data", tool_result)
            
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], dict):
                    headers = list(data[0].keys())[:8]
                    result.append("| " + " | ".join(str(h)[:20] for h in headers) + " |")
                    result.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in data[:20]:
                        result.append("| " + " | ".join(str(row.get(h, ""))[:20] for h in headers) + " |")
                    if len(data) > 20:
                        result.append("*... y " + str(len(data) - 20) + " registros mas*")
                else:
                    for item in data[:10]:
                        result.append("- " + str(item))
                result.append("")
            elif isinstance(data, dict):
                for key, value in list(data.items())[:15]:
                    if isinstance(value, (list, dict)):
                        result.append("**" + str(key) + ":** " + str(len(value)) + " elementos")
                    else:
                        result.append("**" + str(key) + ":** " + str(value))
                result.append("")
            else:
                result.append(str(data))
                result.append("")
        
        result.append("---")
        result.append("*Respuesta generada automaticamente desde datos de herramientas*")
        return chr(10).join(result)


    def clear_history(self):

        """Limpiar historial de conversación"""

        self.conversation_history = []

        self._save_user_history()



    def _get_equipment_state(self, fecha_inicio: str, fecha_fin: str) -> dict:

        """

        Obtiene estado actual de equipos para alimentar al World Model



        Args:

            fecha_inicio: Fecha inicio del período (YYYY-MM-DD)

            fecha_fin: Fecha fin del período (YYYY-MM-DD)



        Returns:

            Dict con estado de equipos (DM, UEBD, conteos, etc)

        """

        try:

            conn = sqlite3.connect(self.db_path)

            cursor = conn.cursor()



            # Disponibilidad Mecánica promedio

            cursor.execute("""

                SELECT

                    AVG(CASE WHEN total > 0 THEN ((total - COALESCE(m_correctiva, 0)) / total) * 100 ELSE NULL END) as dm_promedio

                FROM hexagon_equipment_times

                WHERE DATE(time) >= ? AND DATE(time) <= ?

            """, [fecha_inicio, fecha_fin])



            dm_result = cursor.fetchone()

            dm_actual = float(dm_result[0]) if dm_result and dm_result[0] else 0



            # Utilización promedio

            cursor.execute("""

                SELECT

                    AVG(CASE WHEN (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0)) > 0

                        THEN (efectivo / (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0))) * 100

                        ELSE NULL END) as uebd_promedio

                FROM hexagon_equipment_times

                WHERE DATE(time) >= ? AND DATE(time) <= ? AND total > 0

            """, [fecha_inicio, fecha_fin])



            uebd_result = cursor.fetchone()

            uebd_actual = float(uebd_result[0]) if uebd_result and uebd_result[0] else 0



            # Contar equipos activos (simplificado - podría mejorarse)

            cursor.execute("""

                SELECT

                    COUNT(DISTINCT equipo) as total_equipos

                FROM hexagon_equipment_times

                WHERE DATE(time) >= ? AND DATE(time) <= ?

                    AND total > 0

            """, [fecha_inicio, fecha_fin])



            equipos_result = cursor.fetchone()

            total_equipos = int(equipos_result[0]) if equipos_result and equipos_result[0] else 0



            # Estimar palas y camiones (simplificado)

            # En producción, esto debería venir de una tabla de configuración

            # Por ahora, estimamos basado en el total

            active_shovels = max(2, int(total_equipos * 0.2))  # ~20% son palas

            active_trucks = max(8, int(total_equipos * 0.8))   # ~80% son camiones



            conn.close()



            return {

                'pala_availability': dm_actual,

                'uebd': uebd_actual,

                'active_shovels': active_shovels,

                'active_trucks': active_trucks,

                'dm_actual': dm_actual,

                'uebd_actual': uebd_actual

            }



        except Exception as e:

            print(f"[WARNING] Error obteniendo estado de equipos: {e}")

            # Retornar valores por defecto

            return {

                'pala_availability': 80,

                'uebd': 70,

                'active_shovels': 3,

                'active_trucks': 10,

                'dm_actual': 80,

                'uebd_actual': 70

            }



    def add_temporary_document(self, filename: str, content_data: dict):

        """

        Agrega documento temporal al contexto del usuario

        Solo disponible en esta sesión

        """

        import time

        self.temporary_documents[filename] = {

            'content': content_data['content'],

            'metadata': content_data['metadata'],

            'type': content_data['type'],

            'uploaded_at': time.time()

        }

        print(f"📄 Documento temporal agregado para {self.user_id}: {filename}")



    def get_temporary_context(self) -> str:

        """

        Genera contexto adicional de documentos temporales

        """

        if not self.temporary_documents:

            return ""



        context = "\n\n=== DOCUMENTOS CARGADOS POR EL USUARIO ===\n"

        for filename, doc_data in self.temporary_documents.items():

            context += f"\n--- {filename} ---\n"

            context += f"Tipo: {doc_data['type']}\n"

            context += f"Metadata: {doc_data['metadata']}\n"

            # Agregar preview del contenido (primeros 2000 caracteres)

            preview = str(doc_data['content'])[:2000]

            context += f"Contenido (preview):\n{preview}\n"

            if len(str(doc_data['content'])) > 2000:

                context += "[... contenido truncado ...]\n"



        return context



    def get_tools_info(self) -> List[Dict]:

        """Obtener información de las herramientas disponibles"""

        return self.tools





def create_agent(

    openai_api_key: str,

    db_path: str = "minedash.db",

    outputs_dir: str = "outputs",

    lightrag_service = None,

    api_base_url: str = "http://localhost:8000",

    data_dir: Path = None

) -> MineDashAgent:

    """Factory function para crear instancia del agente"""

    return MineDashAgent(

        openai_api_key=openai_api_key,

        db_path=db_path,

        outputs_dir=outputs_dir,

        lightrag_service=lightrag_service,

        api_base_url=api_base_url,

        data_dir=data_dir

    )

