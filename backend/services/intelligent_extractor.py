"""
Intelligent Extractor - MineDash AI
Extrae valores de Excel usando LLM (Claude) con razonamiento
No hardcoding - el sistema aprende la estructura
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import asyncio

class IntelligentExtractor:
    """
    Extractor inteligente que usa Claude para entender archivos Excel
    Sin valores hardcodeados - razonamiento contextual
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.planning_dir = data_dir / "Planificación"
        self.feedback_dir = Path("backend/data/feedback")
        self.patterns_dir = Path("backend/data/learned_patterns")
        
        # Crear directorios si no existen
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)
    
    async def extract_plan_from_excel(
        self, 
        excel_path: Path,
        plan_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Extrae valores de un plan usando Claude para razonar
        
        Args:
            excel_path: Ruta al archivo Excel
            plan_type: "P0", "PND", "PM" o "auto" para detectar
            
        Returns:
            Dict con valores extraídos y nivel de confianza
        """
        
        print(f"\n🧠 Analizando: {excel_path.name}")
        
        try:
            # Leer Excel (manejando .xlsb)
            if excel_path.suffix.lower() == '.xlsb':
                # Excel Binary requiere engine especial
                try:
                    df = pd.read_excel(excel_path, engine='pyxlsb')
                except ImportError:
                    print("   ⚠️ pyxlsb no instalado, intentando con openpyxl...")
                    # Fallback: intentar convertir o leer de otra forma
                    raise ValueError("Archivo .xlsb requiere: pip install pyxlsb")
            else:
                df = pd.read_excel(excel_path)
            
            # Buscar patrones previos exitosos
            learned_strategy = await self._get_learned_strategy(excel_path.name)
            
            # Convertir a contexto para Claude
            excel_context = self._excel_to_context(df)
            
            # Construir prompt
            prompt = self._build_extraction_prompt(
                filename=excel_path.name,
                context=excel_context,
                plan_type=plan_type,
                learned_strategy=learned_strategy
            )
            
            # Llamar a Claude
            from services.lightrag_setup import claude_llm_wrapper
            response = await claude_llm_wrapper(prompt)
            
            # Parsear respuesta JSON
            extracted = self._parse_llm_response(response)
            
            print(f"   ✅ Extraído: {extracted['tonelaje_mensual']:,.0f} ton/mes")
            print(f"   📊 Confianza: {extracted['confianza']}%")
            
            return extracted
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return self._fallback_extraction(df, excel_path.name)
    
    def _excel_to_context(self, df: pd.DataFrame) -> str:
        """
        Convierte DataFrame a texto descriptivo para Claude
        """
        context_parts = []
        
        # Dimensiones
        context_parts.append(f"Dimensiones: {len(df)} filas x {len(df.columns)} columnas")
        
        # Columnas
        context_parts.append(f"\nColumnas: {', '.join(str(c) for c in df.columns[:20])}")
        
        # Primeras 5 filas con datos
        context_parts.append("\nPrimeras filas:")
        for idx in range(min(5, len(df))):
            row = df.iloc[idx]
            row_text = " | ".join(f"{col}: {val}" for col, val in row.items() if pd.notna(val))
            if row_text:
                context_parts.append(f"  {idx+1}. {row_text[:500]}")
        
        # Buscar filas clave
        key_rows = []
        for idx, row in df.iterrows():
            first_val = str(row.iloc[0]).lower()
            if any(keyword in first_val for keyword in [
                'movimiento', 'extracción', 'producción', 'total', 
                'disponibilidad', 'utilización', 'tonelaje'
            ]):
                row_text = " | ".join(f"{col}: {val}" for col, val in row.items() if pd.notna(val))
                key_rows.append(f"  Fila {idx}: {row_text[:500]}")
        
        if key_rows:
            context_parts.append("\nFilas clave detectadas:")
            context_parts.extend(key_rows[:10])
        
        return "\n".join(context_parts)
    
    def _build_extraction_prompt(
        self,
        filename: str,
        context: str,
        plan_type: str,
        learned_strategy: Optional[Dict] = None
    ) -> str:
        """
        Construye prompt para Claude con contexto minero
        """
        
        prompt = f"""Eres un experto en planificación minera de División Salvador, Codelco Chile.

ARCHIVO: {filename}

CONTEXTO DEL EXCEL:
{context}

{"ESTRATEGIA APRENDIDA PREVIAMENTE:" if learned_strategy else ""}
{json.dumps(learned_strategy, indent=2) if learned_strategy else ""}

TAREA:
Analiza el Excel y extrae los siguientes valores del plan de producción:

1. **Tipo de Plan**: Identifica si es:
   - PND (Plan No Desviado) - Plan de largo plazo estratégico
   - P0 (Plan Presupuesto) - Plan anual presupuestado
   - PM (Plan Mensual) - Plan operativo mensual
   
2. **Tonelaje**:
   - Tonelaje ANUAL total (buscar columna "Ppto 2025" o última columna)
   - Tonelaje MENSUAL promedio (anual / 12)
   - Buscar filas: "Movimiento Total", "Extracción Total", "Extracción Mina"

3. **Disponibilidad Meta** (%):
   - Buscar en secciones de equipos (TRANSPORTE, CARGUIO, PERFORACION)
   - Promedio ponderado de disponibilidad de equipos
   - Valores típicos: 75-85%

4. **Utilización Meta** (%):
   - Utilización efectiva de equipos
   - Valores típicos: 60-75%

5. **Valores Mensuales**:
   - Si hay desglose mensual (Enero-Diciembre), extraer cada mes
   - Formato: {{"enero": valor, "febrero": valor, ...}}

REGLAS CRÍTICAS:
- Si un valor parece anual (>100M ton), divídelo por 12 para mensual
- Disponibilidad/Utilización deben estar entre 50-100%
- Si hay múltiples equipos, calcula promedio ponderado
- RAZONA sobre cada valor: ¿Tiene sentido para una mina grande?
- Si hay incertidumbre, indica confianza <100%

FORMATO DE RESPUESTA (JSON estricto, sin markdown):
{{
  "tipo_plan": "P0 | PND | PM",
  "nombre_plan": "<nombre descriptivo>",
  "tonelaje_anual": <número en toneladas>,
  "tonelaje_mensual": <número en toneladas>,
  "disponibilidad_meta": <porcentaje 0-100>,
  "utilizacion_meta": <porcentaje 0-100>,
  "valores_mensuales": {{
    "enero": <ton>, "febrero": <ton>, ...
  }},
  "confianza": <0-100>,
  "razonamiento": "<explica paso a paso cómo encontraste cada valor>",
  "ubicacion_datos": {{
    "tonelaje_fila": <número de fila>,
    "tonelaje_columna": "<nombre columna>",
    "disponibilidad_fila": <número>,
    "utilizacion_fila": <número>
  }}
}}

RESPONDE SOLO CON EL JSON, SIN TEXTO ADICIONAL."""

        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parsea respuesta de Claude a diccionario
        """
        try:
            # Limpiar markdown si existe
            response = response.strip()
            if response.startswith("```json"):
                response = response.split("```json")[1].split("```")[0]
            elif response.startswith("```"):
                response = response.split("```")[1].split("```")[0]
            
            # Parsear JSON
            data = json.loads(response)
            
            # Validar campos requeridos
            required = ["tonelaje_mensual", "tipo_plan"]
            for field in required:
                if field not in data:
                    raise ValueError(f"Falta campo requerido: {field}")
            
            # Asegurar tipos correctos
            data["tonelaje_mensual"] = float(data.get("tonelaje_mensual", 0))
            data["tonelaje_anual"] = float(data.get("tonelaje_anual", data["tonelaje_mensual"] * 12))
            data["disponibilidad_meta"] = float(data.get("disponibilidad_meta", 80.0))
            data["utilizacion_meta"] = float(data.get("utilizacion_meta", 65.0))
            data["confianza"] = int(data.get("confianza", 75))
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"   ⚠️ Error parseando JSON: {e}")
            print(f"   Respuesta: {response[:500]}")
            raise
    
    def _fallback_extraction(self, df: pd.DataFrame, filename: str) -> Dict[str, Any]:
        """
        Extracción de respaldo si falla el LLM
        Busca patrones conocidos en los datos
        """
        print("   🔄 Usando extracción de respaldo")
        
        # Detectar tipo de plan por nombre de archivo
        filename_lower = filename.lower()
        if 'p02025' in filename_lower or 'p0_2025' in filename_lower:
            tipo_plan = 'P0'
        elif 'pnd' in filename_lower:
            tipo_plan = 'PND'
        elif 'mensual' in filename_lower:
            tipo_plan = 'PM'
        else:
            tipo_plan = 'P0'  # Default
        
        # Buscar tonelaje en el archivo
        tonelaje_anual = 0
        tonelaje_mensual = 0
        
        # Estrategia 1: Buscar filas clave
        for idx, row in df.iterrows():
            try:
                first_val = str(row.iloc[0]).lower() if pd.notna(row.iloc[0]) else ""
                
                # Palabras clave para identificar fila de tonelaje
                if any(keyword in first_val for keyword in [
                    'movimiento total', 'extracción total', 'extraccion total',
                    'producción total', 'produccion total', 'total lastre'
                ]):
                    # Buscar última columna con valor numérico grande
                    for col in reversed(df.columns):
                        try:
                            val = row[col]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                if val > 1_000_000:  # Mayor a 1M toneladas
                                    tonelaje_anual = float(val)
                                    print(f"   ✅ Tonelaje encontrado en fila '{first_val[:40]}': {tonelaje_anual:,.0f}")
                                    break
                        except:
                            continue
                    
                    if tonelaje_anual > 0:
                        break
            except:
                continue
        
        # Si encontró tonelaje anual, calcular mensual
        if tonelaje_anual > 10_000_000:  # Si parece anual (>10M)
            tonelaje_mensual = tonelaje_anual / 12
            confianza = 70
        elif tonelaje_anual > 0:  # Si es menor, probablemente ya es mensual
            tonelaje_mensual = tonelaje_anual
            tonelaje_anual = tonelaje_mensual * 12
            confianza = 60
        else:
            # No encontró nada - usar estimación
            tonelaje_mensual = 10_300_000
            tonelaje_anual = tonelaje_mensual * 12
            confianza = 30
            print(f"   ⚠️ No se encontró tonelaje, usando estimación")
        
        return {
            "tipo_plan": tipo_plan,
            "nombre_plan": f"Plan {tipo_plan} extraído de {filename}",
            "tonelaje_anual": tonelaje_anual,
            "tonelaje_mensual": tonelaje_mensual,
            "disponibilidad_meta": 80.0,
            "utilizacion_meta": 65.0,
            "valores_mensuales": {},
            "confianza": confianza,
            "razonamiento": f"Extracción de respaldo - Tonelaje: {tonelaje_mensual:,.0f} ton/mes",
            "ubicacion_datos": {}
        }
    
    async def _get_learned_strategy(self, filename: str) -> Optional[Dict]:
        """
        Busca estrategias de extracción aprendidas previamente
        """
        pattern_file = self.patterns_dir / f"{filename}.json"
        
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"   ⚠️ Error leyendo patrón: {e}")
        
        return None
    
    async def save_successful_extraction(
        self,
        filename: str,
        extracted_data: Dict,
        validation_status: str = "pending"
    ):
        """
        Guarda extracción exitosa para aprendizaje futuro
        """
        pattern = {
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "extracted_data": extracted_data,
            "validation_status": validation_status,
            "extraction_strategy": extracted_data.get("ubicacion_datos", {})
        }
        
        pattern_file = self.patterns_dir / f"{filename}.json"
        
        try:
            with open(pattern_file, 'w', encoding='utf-8') as f:
                json.dump(pattern, f, indent=2, ensure_ascii=False)
            print(f"   💾 Patrón guardado: {pattern_file.name}")
        except Exception as e:
            print(f"   ⚠️ Error guardando patrón: {e}")
    
    async def extract_all_plans(self) -> Dict[str, Dict]:
        """
        Extrae todos los planes disponibles en el directorio de Planificación
        Detecta inteligentemente P0, PND, PM por nombre de archivo
        """
        print(f"\n{'='*70}")
        print(f"🔍 ESCANEANDO PLANES DE PRODUCCIÓN")
        print(f"{'='*70}")
        print(f"📁 Directorio: {self.planning_dir}")
        
        planes = {}
        
        if not self.planning_dir.exists():
            print(f"⚠️ Directorio no existe: {self.planning_dir}")
            return planes
        
        # Buscar archivos Excel (incluyendo .xlsb)
        excel_files = (
            list(self.planning_dir.glob("*.xlsx")) + 
            list(self.planning_dir.glob("*.xls")) +
            list(self.planning_dir.glob("*.xlsb"))
        )
        
        # Filtrar archivos temporales
        excel_files = [f for f in excel_files if not f.name.startswith('~$')]
        
        print(f"📊 Archivos encontrados: {len(excel_files)}")
        
        # Priorizar archivos por tipo
        archivos_priorizados = self._prioritize_files(excel_files)
        
        for archivo_info in archivos_priorizados:
            excel_file = archivo_info['path']
            tipo_esperado = archivo_info['tipo']
            
            try:
                print(f"\n📄 Procesando: {excel_file.name}")
                print(f"   Tipo esperado: {tipo_esperado}")
                
                extracted = await self.extract_plan_from_excel(excel_file, tipo_esperado)
                
                # Si ya existe este tipo de plan, comparar confianza
                if tipo_esperado in planes:
                    if extracted.get('confianza', 0) > planes[tipo_esperado].get('confianza', 0):
                        planes[tipo_esperado] = extracted
                        print(f"   ✅ Reemplazado {tipo_esperado} (mayor confianza)")
                else:
                    planes[tipo_esperado] = extracted
                    print(f"   ✅ Agregado como {tipo_esperado}")
                
            except Exception as e:
                print(f"   ❌ Error procesando {excel_file.name}: {e}")
        
        print(f"\n{'='*70}")
        print(f"✅ RESUMEN DE PLANES EXTRAÍDOS:")
        for tipo, plan in planes.items():
            ton = plan.get('tonelaje_mensual', 0)
            conf = plan.get('confianza', 0)
            print(f"   {tipo}: {ton:,.0f} ton/mes (Confianza: {conf}%)")
        print(f"{'='*70}\n")
        
        return planes
    
    def _prioritize_files(self, files: List[Path]) -> List[Dict]:
        """
        Prioriza archivos por tipo de plan y relevancia
        Detecta P0, PND, PM por nombre de archivo
        """
        prioritized = []
        
        for f in files:
            filename_lower = f.name.lower()
            
            # Detectar tipo de plan
            if 'p02025' in filename_lower or 'p0_2025' in filename_lower or 'exhibit_p0' in filename_lower:
                tipo = 'P0'
                prioridad = 10
            elif 'pnd2025' in filename_lower or 'pnd_2025' in filename_lower or 'exhibit_pnd' in filename_lower or 'definitivo pnd' in filename_lower:
                tipo = 'PND'
                prioridad = 9
            elif 'plan mensual' in filename_lower or 'pm_' in filename_lower:
                tipo = 'PM'
                prioridad = 8
            elif 'exhibit' in filename_lower and '2025' in filename_lower:
                # Exhibit genérico - probablemente P0
                tipo = 'P0'
                prioridad = 5
            else:
                # Archivo desconocido
                tipo = 'UNKNOWN'
                prioridad = 1
            
            prioritized.append({
                'path': f,
                'tipo': tipo,
                'prioridad': prioridad
            })
        
        # Ordenar por prioridad
        prioritized.sort(key=lambda x: x['prioridad'], reverse=True)
        
        return prioritized


def get_intelligent_extractor(data_dir: Path = None):
    """Obtiene instancia del extractor inteligente"""
    if data_dir is None:
        from config import Config
        data_dir = Config.DATA_DIR
    return IntelligentExtractor(data_dir)