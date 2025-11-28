# services/ranking_analytics.py
"""
Analytics directo sobre archivos de datos - VERSION ROBUSTA
División Salvador - Codelco Chile
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

class RankingAnalytics:
    """Análisis de rankings desde archivos raw"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.hexagon_dir = data_dir / "Hexagon"
    
    def _find_column(self, df: pd.DataFrame, posibles_nombres: List[str]) -> str:
        """Encuentra una columna por diferentes nombres posibles"""
        for nombre in posibles_nombres:
            if nombre in df.columns:
                return nombre
        return None
    
    def ranking_operadores_produccion(
        self, 
        year: int = 2024, 
        top_n: int = 5,
        tipo: str = ""  # CAEX, EMT, CF, o vacío para todos
    ) -> Dict[str, Any]:
        """
        Ranking de operadores por producción (toneladas)
        """
        try:
            # 1. BUSCAR ARCHIVO
            posibles_archivos = [
                self.hexagon_dir / f"by_detail_dumps {year}.xlsx",
                self.hexagon_dir / f"by_detail_dumps{year}.xlsx",
                self.hexagon_dir / "by_detail_dumps.xlsx"
            ]
            
            archivo_dumps = None
            for archivo in posibles_archivos:
                if archivo.exists():
                    archivo_dumps = archivo
                    break
            
            if not archivo_dumps:
                return {
                    "error": f"No se encontró archivo de dumps para {year}",
                    "sugerencia": "Verifica que exista: by_detail_dumps 2024.xlsx en la carpeta Hexagon"
                }
            
            print(f"\n📊 Leyendo: {archivo_dumps.name}")
            df = pd.read_excel(archivo_dumps)
            print(f"   Total registros: {len(df):,}")
            
            # 2. IDENTIFICAR COLUMNAS
            col_nombre = self._find_column(df, ['truck_operator_first_name', 'Nombres'])
            col_apellido = self._find_column(df, ['truck_operator_last_name', 'Apellidos'])
            col_toneladas = self._find_column(df, ['material_tonnage', 'payload', 'Tonnage'])
            col_equipo = self._find_column(df, ['truck', 'Equipment'])
            col_fecha = self._find_column(df, ['time', 'Date', 'timestamp'])
            col_turno = self._find_column(df, ['shift', 'Crew', 'Turno'])
            
            if not all([col_nombre, col_apellido, col_toneladas]):
                return {
                    "error": "Faltan columnas críticas",
                    "necesarias": ["operador_nombre", "operador_apellido", "toneladas"],
                    "encontradas": {
                        "nombre": col_nombre,
                        "apellido": col_apellido,
                        "toneladas": col_toneladas
                    }
                }
            
            print(f"   ✅ Columnas: {col_nombre}, {col_apellido}, {col_toneladas}")
            
            # 3. CREAR NOMBRE OPERADOR
            df['Operador'] = (
                df[col_apellido].astype(str).str.strip().str.upper() + ' ' +
                df[col_nombre].astype(str).str.strip().str.upper()
            )
            df['Operador'] = df['Operador'].str.replace(r'\s+', ' ', regex=True)
            
            # 4. LIMPIAR DATOS
            df = df[df['Operador'].notna()]
            df = df[~df['Operador'].isin(['NAN NAN', 'NONE NONE', ' ', ''])]
            df = df[df['Operador'].str.len() > 5]
            
            print(f"   Operadores válidos: {len(df):,}")
            
            if len(df) == 0:
                return {"error": "No hay operadores válidos en el archivo"}
            
            # 5. FILTRAR POR AÑO
            if col_fecha:
                df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
                df = df[df[col_fecha].notna()]
                df = df[df[col_fecha].dt.year == year]
                print(f"   Año {year}: {len(df):,}")
            
            if len(df) == 0:
                return {
                    "error": f"No hay datos para el año {year}",
                    "sugerencia": "Prueba con year=2023 o year=2025"
                }
            
            # 6. FILTRAR POR TIPO DE EQUIPO
            if tipo and col_equipo:
                antes = len(df)
                if tipo.upper() == "CAEX":
                    df = df[df[col_equipo].astype(str).str.contains('CA-', case=False, na=False)]
                elif tipo.upper() == "EMT":
                    df = df[df[col_equipo].astype(str).str.contains('EMT', case=False, na=False)]
                elif tipo.upper() == "CF":
                    df = df[df[col_equipo].astype(str).str.contains('CF', case=False, na=False)]
                print(f"   Tipo {tipo}: {len(df):,} (de {antes:,})")
            
            if len(df) == 0:
                return {
                    "error": f"No hay datos tipo {tipo}",
                    "sugerencia": "Elimina el filtro de tipo o usa tipo diferente"
                }
            
            # 7. CONVERTIR TONELADAS
            df[col_toneladas] = pd.to_numeric(df[col_toneladas], errors='coerce')
            df = df[df[col_toneladas] > 0]
            
            print(f"   Con toneladas válidas: {len(df):,}")
            
            if len(df) == 0:
                return {"error": "No hay toneladas válidas"}
            
            # 8. AGRUPAR POR OPERADOR
            if col_turno:
                agrupado = df.groupby(['Operador', col_turno])
            else:
                agrupado = df.groupby('Operador')
            
            metricas = agrupado.agg({
                col_toneladas: ['sum', 'count', 'mean']
            }).reset_index()
            
            # Renombrar columnas
            if col_turno:
                metricas.columns = ['Operador', 'Grupo', 'Toneladas', 'Dumps', 'TonPorDump']
            else:
                metricas.columns = ['Operador', 'Toneladas', 'Dumps', 'TonPorDump']
                metricas['Grupo'] = 'N/A'
            
            # Equipos usados
            if col_equipo:
                equipos_count = df.groupby('Operador')[col_equipo].nunique()
                metricas = metricas.merge(
                    equipos_count.rename('Equipos'),
                    left_on='Operador',
                    right_index=True,
                    how='left'
                )
                metricas['Equipos'] = metricas['Equipos'].fillna(0).astype(int)
            else:
                metricas['Equipos'] = 0
            
            # 9. ORDENAR Y TOP N
            metricas = metricas.sort_values('Toneladas', ascending=False)
            top = metricas.head(top_n)
            
            print(f"   Total operadores: {len(metricas)}")
            print(f"   Top {top_n} seleccionados")
            
            # 10. FORMATEAR RANKING
            ranking = []
            for i, (_, row) in enumerate(top.iterrows(), 1):
                ranking.append({
                    'posicion': i,
                    'operador': row['Operador'],
                    'grupo': str(row['Grupo']),
                    'toneladas_total': int(row['Toneladas']),
                    'toneladas_total_formatted': f"{row['Toneladas']:,.0f}",
                    'dumps': int(row['Dumps']),
                    'ton_por_dump': round(float(row['TonPorDump']), 1),
                    'equipos_usados': int(row['Equipos'])
                })
            
            # 11. ESTADÍSTICAS
            stats = {
                'total_operadores': len(metricas),
                'total_toneladas': int(metricas['Toneladas'].sum()),
                'total_toneladas_formatted': f"{metricas['Toneladas'].sum():,.0f}",
                'promedio_por_operador': int(metricas['Toneladas'].mean()),
                'promedio_por_operador_formatted': f"{metricas['Toneladas'].mean():,.0f}",
                'total_dumps': int(metricas['Dumps'].sum()),
                'promedio_dumps_por_operador': int(metricas['Dumps'].mean())
            }
            
            return {
                "success": True,
                "year": year,
                "tipo": tipo if tipo else "TODOS",
                "top_n": top_n,
                "ranking": ranking,
                "estadisticas": stats,
                "archivo_fuente": archivo_dumps.name,
                "registros_procesados": len(df)
            }
            
        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "tipo_error": type(e).__name__,
                "traceback": traceback.format_exc()
            }
    
    def ranking_operadores_dumps(self, year: int = 2024, top_n: int = 5) -> Dict[str, Any]:
        """Ranking por cantidad de dumps"""
        resultado = self.ranking_operadores_produccion(year, top_n * 2, tipo="")
        
        if "error" in resultado:
            return resultado
        
        ranking = resultado["ranking"]
        ranking.sort(key=lambda x: x['dumps'], reverse=True)
        
        return {
            "success": True,
            "year": year,
            "top_n": top_n,
            "ranking": ranking[:top_n],
            "criterio": "Número de dumps (viajes)",
            "estadisticas": resultado["estadisticas"]
        }

def get_ranking_analytics(data_dir: Path = None):
    """Obtiene instancia"""
    if data_dir is None:
        from config import Config
        data_dir = Config.DATA_DIR
    return RankingAnalytics(data_dir)