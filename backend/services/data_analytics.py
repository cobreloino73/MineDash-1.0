# services/data_analytics.py
"""
Análisis de datos tabulares y rankings
Para queries que requieren agregación/filtrado específico
"""

import pandas as pd
from pathlib import Path
from config import Config
from typing import List, Dict, Any
import json

class DataAnalytics:
    """Análisis directo sobre archivos de datos"""
    
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self._cache = {}
    
    def _load_file(self, filename: str) -> pd.DataFrame:
        """Carga archivo Excel o CSV"""
        if filename in self._cache:
            return self._cache[filename]
        
        filepath = Path(self.data_dir) / filename
        
        if not filepath.exists():
            # Buscar en subdirectorios
            for f in self.data_dir.rglob(filename):
                filepath = f
                break
        
        if filepath.suffix == '.csv':
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        self._cache[filename] = df
        return df
    
    def ranking_operadores_utilizacion(self, year: int = 2024, top_n: int = 5) -> Dict[str, Any]:
        """
        Genera ranking de operadores por utilización
        
        Busca en archivos que contengan:
        - Columna de operador
        - Columna de utilización o horas productivas
        - Columna de fecha/año
        """
        try:
            # Buscar archivos relevantes
            archivos_operadores = []
            
            for archivo in self.data_dir.rglob("*.xlsx"):
                if any(keyword in archivo.name.lower() for keyword in ['operador', 'operator', 'equipment', 'equipo']):
                    archivos_operadores.append(archivo)
            
            if not archivos_operadores:
                return {
                    "error": "No se encontraron archivos de operadores",
                    "archivos_buscados": str(self.data_dir)
                }
            
            # Procesar cada archivo
            resultados = []
            
            for archivo in archivos_operadores:
                try:
                    df = pd.read_excel(archivo)
                    
                    # Buscar columnas relevantes
                    col_operador = self._find_column(df, ['operador', 'operator', 'nombre'])
                    col_utilizacion = self._find_column(df, ['utilizacion', 'utilization', 'uebd', 'productivo'])
                    col_fecha = self._find_column(df, ['fecha', 'date', 'timestamp', 'año', 'year'])
                    col_grupo = self._find_column(df, ['grupo', 'group', 'turno', 'shift', 'equipo'])
                    
                    if not all([col_operador, col_utilizacion]):
                        continue
                    
                    # Filtrar por año si hay columna de fecha
                    df_filtered = df.copy()
                    if col_fecha:
                        df_filtered[col_fecha] = pd.to_datetime(df_filtered[col_fecha], errors='coerce')
                        df_filtered = df_filtered[df_filtered[col_fecha].dt.year == year]
                    
                    # Agregar por operador
                    if col_grupo:
                        agrupacion = df_filtered.groupby([col_operador, col_grupo])[col_utilizacion].mean().reset_index()
                    else:
                        agrupacion = df_filtered.groupby(col_operador)[col_utilizacion].mean().reset_index()
                    
                    agrupacion.columns = ['operador', 'grupo', 'utilizacion'] if col_grupo else ['operador', 'utilizacion']
                    
                    resultados.append({
                        'archivo': archivo.name,
                        'data': agrupacion
                    })
                    
                except Exception as e:
                    continue
            
            if not resultados:
                return {
                    "error": "No se pudieron procesar los archivos",
                    "archivos_encontrados": [str(a) for a in archivos_operadores]
                }
            
            # Consolidar resultados
            df_final = pd.concat([r['data'] for r in resultados], ignore_index=True)
            
            # Agregar por operador (promedio si hay múltiples fuentes)
            if 'grupo' in df_final.columns:
                df_ranking = df_final.groupby(['operador', 'grupo'])['utilizacion'].mean().reset_index()
            else:
                df_ranking = df_final.groupby('operador')['utilizacion'].mean().reset_index()
                df_ranking['grupo'] = 'N/A'
            
            # Ordenar y tomar top N
            df_ranking = df_ranking.sort_values('utilizacion', ascending=False).head(top_n)
            
            # Formatear resultado
            ranking = []
            for i, row in df_ranking.iterrows():
                ranking.append({
                    'posicion': len(ranking) + 1,
                    'operador': row['operador'],
                    'grupo': row['grupo'],
                    'utilizacion': f"{row['utilizacion']:.1f}%"
                })
            
            return {
                "success": True,
                "year": year,
                "top_n": top_n,
                "ranking": ranking,
                "total_operadores": len(df_final['operador'].unique()),
                "archivos_procesados": [r['archivo'] for r in resultados]
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "tipo": type(e).__name__
            }
    
    def _find_column(self, df: pd.DataFrame, keywords: List[str]) -> str:
        """Encuentra columna por keywords"""
        cols_lower = {col.lower(): col for col in df.columns}
        
        for keyword in keywords:
            for col_lower, col_original in cols_lower.items():
                if keyword in col_lower:
                    return col_original
        
        return None

# Instancia global
analytics = DataAnalytics()