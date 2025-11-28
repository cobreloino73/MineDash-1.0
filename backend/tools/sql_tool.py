# Formato OpenAI function calling
"""
MineDash AI - SQL Tool
Herramienta para ejecutar consultas SQL de forma segura
"""

import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path


class SQLTool:
    """
    Herramienta para ejecutar consultas SQL
    
    Características:
    - Ejecución segura (solo SELECT)
    - Conversión automática a formato legible
    - Manejo de errores robusto
    - Límite de resultados
    """
    
    def __init__(self, db_path: str, max_results: int = 1000):
        """
        Inicializar SQL Tool
        
        Args:
            db_path: Ruta a la base de datos SQLite
            max_results: Número máximo de filas a retornar
        """
        self.db_path = db_path
        self.max_results = max_results
        
        # Verificar que DB existe
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Base de datos no encontrada: {db_path}")
    
    def execute(self, query: str) -> List[Dict[str, Any]]:
        """
        Ejecutar consulta SQL
        
        Args:
            query: Consulta SQL (solo SELECT permitido)
            
        Returns:
            Lista de diccionarios con resultados
        """
        try:
            # Validar que sea solo SELECT
            query_upper = query.strip().upper()
            if not query_upper.startswith('SELECT'):
                return [{
                    'error': 'Solo se permiten consultas SELECT',
                    'query': query
                }]
            
            # Palabras prohibidas (para seguridad)
            prohibited_words = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE']
            for word in prohibited_words:
                if word in query_upper:
                    return [{
                        'error': f'Palabra prohibida detectada: {word}',
                        'query': query
                    }]
            
            # Ejecutar consulta
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Para tener nombres de columnas
            cursor = conn.cursor()
            
            # Agregar LIMIT si no existe
            if 'LIMIT' not in query_upper:
                query += f' LIMIT {self.max_results}'
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            results = []
            for row in rows:
                results.append(dict(row))
            
            conn.close()
            
            if not results:
                return [{'message': 'Consulta ejecutada correctamente pero sin resultados'}]
            
            return results
            
        except sqlite3.Error as e:
            return [{
                'error': f'Error SQL: {str(e)}',
                'query': query
            }]
        except Exception as e:
            return [{
                'error': f'Error inesperado: {str(e)}',
                'query': query
            }]
    
    def execute_to_dataframe(self, query: str) -> Optional[pd.DataFrame]:
        """
        Ejecutar consulta y retornar como DataFrame de pandas
        
        Args:
            query: Consulta SQL
            
        Returns:
            DataFrame con resultados o None si hay error
        """
        results = self.execute(query)
        
        if not results:
            return None
        
        if 'error' in results[0]:
            return None
        
        return pd.DataFrame(results)
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Obtener información sobre una tabla
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            Dict con información de la tabla
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener esquema
            cursor.execute(f"PRAGMA table_info({table_name})")
            schema = cursor.fetchall()
            
            # Obtener conteo de filas
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'table_name': table_name,
                'columns': [
                    {
                        'name': col[1],
                        'type': col[2],
                        'not_null': bool(col[3]),
                        'primary_key': bool(col[5])
                    }
                    for col in schema
                ],
                'row_count': row_count
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'table_name': table_name
            }
    
    def list_tables(self) -> List[str]:
        """
        Listar todas las tablas en la base de datos
        
        Returns:
            Lista de nombres de tablas
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return tables
            
        except Exception as e:
            return []
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Obtener datos de muestra de una tabla
        
        Args:
            table_name: Nombre de la tabla
            limit: Número de filas a retornar
            
        Returns:
            Lista de diccionarios con datos de muestra
        """
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute(query)


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    # Crear tool
    sql_tool = SQLTool("minedash.db")
    
    # Listar tablas
    print("\n=== TABLAS DISPONIBLES ===")
    tables = sql_tool.list_tables()
    for table in tables:
        print(f"  - {table}")
    
    # Ejemplo de consulta
    if tables:
        print(f"\n=== DATOS DE MUESTRA: {tables[0]} ===")
        sample = sql_tool.get_sample_data(tables[0], limit=3)
        for row in sample:
            print(row)
        
        # Info de tabla
        print(f"\n=== INFO DE TABLA: {tables[0]} ===")
        info = sql_tool.get_table_info(tables[0])
        print(f"Columnas: {len(info.get('columns', []))}")
        print(f"Filas: {info.get('row_count', 0)}")