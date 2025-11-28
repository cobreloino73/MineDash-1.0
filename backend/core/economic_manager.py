"""
 ECONOMIC PARAMETERS MANAGER
Sistema para actualizar parámetros económicos de forma dinámica
Permite 3 métodos: Chat Natural, Excel Upload, API Direct
"""

import pandas as pd
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Union
import json
import re


class EconomicParametersManager:
    """Gestor de parámetros económicos con múltiples métodos de actualización"""
    
    def __init__(self, db_path: str = "minedash.db"):
        self.db_path = db_path
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Crear tabla si no existe"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS economic_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter_name TEXT NOT NULL UNIQUE,
                parameter_value REAL NOT NULL,
                unit TEXT,
                description TEXT,
                source TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ==========================================================================
    # MÉTODO 1: ACTUALIZACIÓN VIA CHAT NATURAL
    # ==========================================================================
    
    def update_from_natural_language(self, text: str, source: str = "Usuario") -> Dict:
        """
        Actualiza parámetros desde lenguaje natural.
        
        Ejemplos válidos:
        - "El precio del mineral es 52.50 USD por tonelada"
        - "Costo operacional CAEX: 450 dólares/hora"
        - "Actualiza precio_venta_mineral_oxido a 48.75 USD/ton"
        
        Args:
            text: Texto en lenguaje natural
            source: Fuente del dato (ej: "Usuario", "Finanzas Salvador")
        
        Returns:
            Dict con resultado de la operación
        """
        updates = []
        
        # Patrones de extracción
        patterns = [
            # "precio del mineral es 52.50 USD/ton"
            (r"precio\s+(?:del\s+)?mineral\s+(?:es|:)?\s*(\d+\.?\d*)\s*(?:USD|US\$|\$)?(?:/|\s+por\s+)?(?:ton|tonelada)?",
             "precio_venta_mineral_oxido", "USD/ton", "Precio de venta mineral óxido"),
            
            # "costo operacional CAEX: 450 USD/hora"
            (r"costo\s+(?:operacional\s+)?caex\s*:?\s*(\d+\.?\d*)\s*(?:USD|US\$|\$)?(?:/|\s+por\s+)?hora",
             "costo_op_caex_hora", "USD/hora", "Costo operacional CAEX"),
            
            # "costo downtime CAEX es 800 USD/hora"
            (r"costo\s+downtime\s+caex\s+(?:es|:)?\s*(\d+\.?\d*)\s*(?:USD|US\$|\$)?(?:/|\s+por\s+)?hora",
             "costo_downtime_caex", "USD/hora", "Costo downtime CAEX"),
            
            # "costo pala: 350 USD/hora"
            (r"costo\s+(?:operacional\s+)?pala\s*:?\s*(\d+\.?\d*)\s*(?:USD|US\$|\$)?(?:/|\s+por\s+)?hora",
             "costo_op_pala_hora", "USD/hora", "Costo operacional pala"),
            
            # "target producción: 25000 toneladas/día"
            (r"target\s+(?:de\s+)?producci[oó]n\s*:?\s*(\d+\.?\d*)\s*(?:ton|toneladas)?(?:/|\s+por\s+)?d[ií]a",
             "target_toneladas_dia", "ton/dia", "Target diario de producción"),
            
            # Formato directo: "actualiza precio_venta_mineral a 52.50"
            (r"(?:actualiza|update|set)\s+(\w+)\s+(?:a|to|=)\s*(\d+\.?\d*)",
             None, None, None)  # Caso especial, se maneja después
        ]
        
        text_lower = text.lower()
        
        for pattern_info in patterns:
            if len(pattern_info) == 4:
                pattern, param_name, unit, description = pattern_info
            else:
                pattern = pattern_info[0]
                param_name = None
            
            match = re.search(pattern, text_lower)
            if match:
                if param_name is None:
                    # Formato directo con nombre de parámetro
                    param_name = match.group(1)
                    value = float(match.group(2))
                    # Buscar info existente del parámetro
                    existing = self.get_parameter(param_name)
                    if existing:
                        unit = existing.get('unit', '')
                        description = existing.get('description', '')
                    else:
                        unit = ""
                        description = f"Parámetro {param_name}"
                else:
                    value = float(match.group(1))
                
                updates.append({
                    "parameter_name": param_name,
                    "value": value,
                    "unit": unit,
                    "description": description
                })
        
        if not updates:
            return {
                "success": False,
                "message": "No se detectaron parámetros económicos en el texto",
                "hint": "Ejemplos: 'precio del mineral es 52.50 USD/ton' o 'costo CAEX: 450 USD/hora'"
            }
        
        # Aplicar actualizaciones
        results = []
        for update in updates:
            result = self.update_parameter(
                parameter_name=update['parameter_name'],
                value=update['value'],
                unit=update['unit'],
                description=update['description'],
                source=source
            )
            results.append(result)
        
        return {
            "success": True,
            "updates_count": len(results),
            "updates": results,
            "message": f" {len(results)} parámetro(s) actualizado(s) correctamente"
        }
    
    # ==========================================================================
    # MÉTODO 2: ACTUALIZACIÓN VIA EXCEL
    # ==========================================================================
    
    def update_from_excel(self, file_path: str, source: str = "Excel Upload") -> Dict:
        """
        Actualiza parámetros desde archivo Excel.
        
        El Excel debe tener columnas:
        - parameter_name: Nombre del parámetro (ej: precio_venta_mineral_oxido)
        - value: Valor numérico
        - unit: Unidad (ej: USD/ton) [opcional]
        - description: Descripción [opcional]
        
        Args:
            file_path: Ruta al archivo Excel
            source: Fuente de los datos
        
        Returns:
            Dict con resultado de la operación
        """
        try:
            # Leer Excel
            df = pd.read_excel(file_path)
            
            # Validar columnas requeridas
            required_cols = ['parameter_name', 'value']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                return {
                    "success": False,
                    "message": f"Columnas faltantes en Excel: {', '.join(missing_cols)}",
                    "required_columns": required_cols
                }
            
            # Procesar cada fila
            results = []
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    param_name = str(row['parameter_name']).strip()
                    value = float(row['value'])
                    unit = str(row.get('unit', '')) if 'unit' in row else ''
                    description = str(row.get('description', '')) if 'description' in row else ''
                    
                    result = self.update_parameter(
                        parameter_name=param_name,
                        value=value,
                        unit=unit,
                        description=description,
                        source=source
                    )
                    results.append(result)
                
                except Exception as e:
                    errors.append(f"Fila {idx + 2}: {str(e)}")
            
            return {
                "success": len(errors) == 0,
                "updates_count": len(results),
                "errors_count": len(errors),
                "updates": results,
                "errors": errors,
                "message": f" {len(results)} parámetros actualizados, {len(errors)} errores"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error leyendo Excel: {str(e)}"
            }
    
    def generate_excel_template(self, output_path: str = "economic_params_template.xlsx"):
        """
        Genera un Excel template con los parámetros actuales para editar.
        
        Args:
            output_path: Ruta donde guardar el template
        """
        params = self.get_all_parameters()
        
        df = pd.DataFrame(params)
        
        # Reordenar columnas
        cols_order = ['parameter_name', 'parameter_value', 'unit', 'description', 'source', 'updated_at']
        df = df[[col for col in cols_order if col in df.columns]]
        
        # Renombrar para que sea más claro
        df.rename(columns={
            'parameter_value': 'value',
            'updated_at': 'last_updated'
        }, inplace=True)
        
        # Guardar
        df.to_excel(output_path, index=False, sheet_name='Parametros Economicos')
        
        print(f" Template generado: {output_path}")
        print(f"   - Edita los valores en la columna 'value'")
        print(f"   - Guarda el archivo")
        print(f"   - Usa update_from_excel('{output_path}') para cargar")
        
        return output_path
    
    # ==========================================================================
    # MÉTODO 3: ACTUALIZACIÓN VIA API/DICCIONARIO
    # ==========================================================================
    
    def update_parameter(
        self,
        parameter_name: str,
        value: float,
        unit: str = "",
        description: str = "",
        source: str = "API"
    ) -> Dict:
        """
        Actualiza un parámetro individual.
        
        Args:
            parameter_name: Nombre del parámetro
            value: Valor numérico
            unit: Unidad (ej: USD/ton)
            description: Descripción
            source: Fuente del dato
        
        Returns:
            Dict con resultado
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Verificar si existe
            cursor.execute(
                "SELECT id FROM economic_parameters WHERE parameter_name = ?",
                (parameter_name,)
            )
            exists = cursor.fetchone() is not None
            
            if exists:
                # UPDATE
                cursor.execute("""
                    UPDATE economic_parameters
                    SET parameter_value = ?,
                        unit = ?,
                        description = ?,
                        source = ?,
                        updated_at = ?
                    WHERE parameter_name = ?
                """, (value, unit, description, source, datetime.now(), parameter_name))
                
                action = "actualizado"
            else:
                # INSERT
                cursor.execute("""
                    INSERT INTO economic_parameters 
                    (parameter_name, parameter_value, unit, description, source, updated_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (parameter_name, value, unit, description, source, datetime.now(), datetime.now()))
                
                action = "creado"
            
            conn.commit()
            
            return {
                "success": True,
                "action": action,
                "parameter": {
                    "name": parameter_name,
                    "value": value,
                    "unit": unit,
                    "description": description,
                    "source": source
                },
                "message": f" Parámetro '{parameter_name}' {action}: {value} {unit}"
            }
        
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
        
        finally:
            conn.close()
    
    def update_batch(self, parameters: List[Dict]) -> Dict:
        """
        Actualiza múltiples parámetros de una vez.
        
        Args:
            parameters: Lista de dicts con keys: parameter_name, value, unit, description, source
        
        Returns:
            Dict con resultados
        """
        results = []
        
        for param in parameters:
            result = self.update_parameter(
                parameter_name=param.get('parameter_name'),
                value=param.get('value'),
                unit=param.get('unit', ''),
                description=param.get('description', ''),
                source=param.get('source', 'Batch Update')
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            "success": success_count == len(results),
            "total": len(results),
            "success_count": success_count,
            "failed_count": len(results) - success_count,
            "results": results
        }
    
    # ==========================================================================
    # CONSULTAS
    # ==========================================================================
    
    def get_parameter(self, parameter_name: str) -> Optional[Dict]:
        """Obtiene un parámetro específico"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT parameter_name, parameter_value, unit, description, source, updated_at
            FROM economic_parameters
            WHERE parameter_name = ?
        """, (parameter_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "parameter_name": row[0],
                "value": row[1],
                "unit": row[2],
                "description": row[3],
                "source": row[4],
                "updated_at": row[5]
            }
        return None
    
    def get_all_parameters(self) -> List[Dict]:
        """Obtiene todos los parámetros"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT parameter_name, parameter_value, unit, description, source, updated_at
            FROM economic_parameters
            ORDER BY parameter_name
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "parameter_name": row[0],
                "parameter_value": row[1],
                "unit": row[2],
                "description": row[3],
                "source": row[4],
                "updated_at": row[5]
            }
            for row in rows
        ]
    
    def delete_parameter(self, parameter_name: str) -> Dict:
        """Elimina un parámetro"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "DELETE FROM economic_parameters WHERE parameter_name = ?",
                (parameter_name,)
            )
            conn.commit()
            
            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f" Parámetro '{parameter_name}' eliminado"
                }
            else:
                return {
                    "success": False,
                    "message": f"️  Parámetro '{parameter_name}' no existe"
                }
        
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
        
        finally:
            conn.close()


# =============================================================================
# HERRAMIENTA PARA EL AGENTE
# =============================================================================

def get_economic_tool_definition() -> Dict:
    """
    Definición de herramienta para que Claude pueda actualizar parámetros económicos.
    Esta función se agrega al array de tools del MineDashAgent.
    """
    return {
        "name": "update_economic_parameters",
        "description": """Actualiza parámetros económicos en la base de datos.

USO EXCLUSIVO: Solo el administrador puede usar esta herramienta.

Permite al usuario actualizar:
- Precios de venta de mineral (USD/ton)
- Costos operacionales por tipo de equipo (USD/hora)
- Costos de downtime (USD/hora)
- Targets operacionales

El usuario puede escribir en lenguaje natural:
- "El precio del mineral es 52.50 USD/ton"
- "Costo operacional CAEX: 450 dólares/hora"
- "Target de producción: 25000 toneladas/día"

O proporcionar datos estructurados.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["natural_language", "structured"],
                    "description": "Método de actualización"
                },
                "text": {
                    "type": "string",
                    "description": "Texto en lenguaje natural (para method='natural_language')"
                },
                "parameters": {
                    "type": "array",
                    "description": "Lista de parámetros a actualizar (para method='structured')",
                    "items": {
                        "type": "object",
                        "properties": {
                            "parameter_name": {"type": "string"},
                            "value": {"type": "number"},
                            "unit": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["parameter_name", "value"]
                    }
                },
                "source": {
                    "type": "string",
                    "description": "Fuente de los datos (ej: 'Finanzas Salvador', 'Usuario David')"
                }
            },
            "required": ["method"]
        }
    }


# =============================================================================
# EJEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    manager = EconomicParametersManager()
    
    print("="*70)
    print(" ECONOMIC PARAMETERS MANAGER - EJEMPLOS")
    print("="*70)
    
    # EJEMPLO 1: Actualización vía lenguaje natural
    print("\n EJEMPLO 1: Lenguaje Natural")
    print("-" * 70)
    
    result = manager.update_from_natural_language(
        text="""
        El precio del mineral óxido es 52.50 USD por tonelada.
        El costo operacional de los CAEX es 450 dólares por hora.
        El costo de downtime CAEX es 800 USD/hora.
        El target de producción es 25000 toneladas por día.
        """,
        source="Finanzas Salvador - Memo 2024-11-08"
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # EJEMPLO 2: Actualización estructurada
    print("\n EJEMPLO 2: Actualización Estructurada")
    print("-" * 70)
    
    result = manager.update_batch([
        {
            "parameter_name": "precio_venta_mineral_sulfuro",
            "value": 55.75,
            "unit": "USD/ton",
            "description": "Precio venta mineral sulfuro",
            "source": "Finanzas Salvador"
        },
        {
            "parameter_name": "costo_op_pala_hora",
            "value": 350.00,
            "unit": "USD/hora",
            "description": "Costo operacional pala",
            "source": "Finanzas Salvador"
        }
    ])
    
    print(f" {result['success_count']}/{result['total']} parámetros actualizados")
    
    # EJEMPLO 3: Consultar parámetros
    print("\n EJEMPLO 3: Consultar Todos los Parámetros")
    print("-" * 70)
    
    all_params = manager.get_all_parameters()
    
    for param in all_params:
        status = "" if param['parameter_value'] != 0.0 else "️ "
        print(f"{status} {param['parameter_name']}: {param['parameter_value']} {param['unit']}")
        print(f"   Fuente: {param['source']}")
        print()
    
    # EJEMPLO 4: Generar template Excel
    print("\n EJEMPLO 4: Generar Template Excel")
    print("-" * 70)
    
    template_path = manager.generate_excel_template()
    
    print(f"\n{'='*70}")
    print(" Economic Parameters Manager listo para usar")
    print("="*70)
