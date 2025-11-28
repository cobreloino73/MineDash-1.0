# services/causal_analytics.py
"""
Análisis Causal - Correlación Operador + Equipo + Estados
División Salvador - Codelco Chile
NOTA: Las columnas de Hexagon están invertidas:
  - truck_operator_last_name = NOMBRE
  - truck_operator_first_name = APELLIDO
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

class CausalAnalytics:
    """Análisis causal correlacionando dumps, estados y tiempos"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.hexagon_dir = data_dir / "Hexagon"
    
    def analisis_operador_utilizacion(
        self,
        operador_apellido: str,
        year: int = 2024,
        mes_inicio: int = 1,
        mes_fin: int = 12
    ) -> Dict[str, Any]:
        """
        Análisis causal de utilización de un operador
        
        Correlaciona:
        1. Dumps del operador (qué equipos usó)
        2. Estados de esos equipos (códigos ASARCO)
        3. Horas de esos equipos (utilización)
        
        Returns:
        - Equipos usados por el operador
        - Códigos ASARCO más frecuentes en esos equipos
        - Análisis de utilización
        - Patrones identificados
        """
        try:
            print(f"\n🔍 Analizando operador: {operador_apellido} ({year})")
            
            # ===================================================================
            # 1. CARGAR DUMPS - Identificar equipos usados por operador
            # ===================================================================
            dumps_file = self.hexagon_dir / f"by_detail_dumps {year}.xlsx"
            print(f"   📥 Cargando dumps...")
            df_dumps = pd.read_excel(dumps_file)
            
            # ✅ CORRECCIÓN: Las columnas están invertidas en Hexagon
            # truck_operator_first_name = APELLIDO
            # truck_operator_last_name = NOMBRE
            
            # Filtrar por operador (buscar en first_name que tiene el apellido)
            df_op = df_dumps[
                df_dumps['truck_operator_first_name'].astype(str).str.upper().str.contains(
                    operador_apellido.upper(), na=False
                )
            ].copy()
            
            if len(df_op) == 0:
                return {
                    "error": f"No se encontró operador con apellido: {operador_apellido}",
                    "sugerencia": "Verifica el apellido"
                }
            
            # ✅ CORRECCIÓN: Invertir el orden (apellido + nombre)
            operador_nombre_completo = (
                df_op['truck_operator_first_name'].mode()[0] + ' ' +
                df_op['truck_operator_last_name'].mode()[0]
            ).upper()
            
            print(f"   ✅ Operador: {operador_nombre_completo}")
            
            # Convertir fecha
            df_op['fecha'] = pd.to_datetime(df_op['time']).dt.date
            df_op['mes'] = pd.to_datetime(df_op['time']).dt.month
            
            # Filtrar por rango de meses
            df_op = df_op[(df_op['mes'] >= mes_inicio) & (df_op['mes'] <= mes_fin)]
            
            print(f"   📊 {len(df_op):,} dumps encontrados")
            
            # Resumen por equipo
            equipos_usados = df_op.groupby('truck').agg({
                'material_tonnage': ['sum', 'count'],
                'fecha': 'nunique',
                'shift': lambda x: list(x.unique())
            }).reset_index()
            
            equipos_usados.columns = ['equipo', 'toneladas', 'dumps', 'dias', 'turnos']
            equipos_usados = equipos_usados.sort_values('toneladas', ascending=False)
            
            print(f"   🚜 {len(equipos_usados)} equipos diferentes usados")
            
            # ===================================================================
            # 2. CARGAR ESTADOS - Códigos ASARCO de los equipos usados
            # ===================================================================
            estados_file = self.hexagon_dir / "by_estados_2024_2025.xlsx"
            
            if not estados_file.exists():
                estados_analisis = {"info": "Archivo de estados no disponible"}
            else:
                print(f"   📥 Cargando estados ASARCO...")
                df_estados = pd.read_excel(estados_file)
                
                # Filtrar por equipos y período
                df_estados['fecha'] = pd.to_datetime(df_estados['fecha']).dt.date
                df_estados['mes'] = pd.to_datetime(df_estados['fecha']).dt.month
                
                # Filtrar por año
                df_estados_year = df_estados[pd.to_datetime(df_estados['fecha']).dt.year == year]
                df_estados_filtered = df_estados_year[
                    (df_estados_year['mes'] >= mes_inicio) & 
                    (df_estados_year['mes'] <= mes_fin)
                ]
                
                # Solo equipos que usó el operador
                equipos_list = equipos_usados['equipo'].tolist()
                df_estados_op = df_estados_filtered[df_estados_filtered['equipo'].isin(equipos_list)]
                
                print(f"   📋 {len(df_estados_op):,} registros de estados")
                
                # Resumen por código ASARCO
                if len(df_estados_op) > 0:
                    codigos_resumen = df_estados_op.groupby(['code', 'razon']).agg({
                        'horas': 'sum',
                        'equipo': 'count'
                    }).reset_index()
                    codigos_resumen.columns = ['codigo', 'razon', 'horas_total', 'ocurrencias']
                    codigos_resumen = codigos_resumen.sort_values('horas_total', ascending=False)
                    
                    # Top 10 códigos
                    top_codigos = []
                    for _, row in codigos_resumen.head(10).iterrows():
                        top_codigos.append({
                            'codigo': int(row['codigo']) if not pd.isna(row['codigo']) else 0,
                            'razon': str(row['razon']),
                            'horas': round(float(row['horas_total']), 1),
                            'ocurrencias': int(row['ocurrencias']),
                            'porcentaje': round(row['horas_total'] / codigos_resumen['horas_total'].sum() * 100, 1)
                        })
                    
                    estados_analisis = {
                        "total_horas_detencion": round(float(df_estados_op['horas'].sum()), 1),
                        "total_eventos": len(df_estados_op),
                        "top_10_codigos": top_codigos
                    }
                else:
                    estados_analisis = {"info": "No hay estados para los equipos en el período"}
            
            # ===================================================================
            # 3. CARGAR EQUIPMENT_TIMES - Utilización de equipos
            # ===================================================================
            times_files = [
                self.hexagon_dir / f"by_equipment_times {year} p1.xlsx",
                self.hexagon_dir / f"by_equipment_times {year} p2.xlsx"
            ]
            
            df_times_list = []
            for f in times_files:
                if f.exists():
                    print(f"   📥 Cargando {f.name}...")
                    df_times_list.append(pd.read_excel(f))
            
            if df_times_list:
                df_times = pd.concat(df_times_list, ignore_index=True)
                
                # Filtrar por equipos y período
                df_times['fecha'] = pd.to_datetime(df_times['time']).dt.date
                df_times['mes'] = pd.to_datetime(df_times['time']).dt.month
                
                # Filtrar por año
                df_times_year = df_times[pd.to_datetime(df_times['time']).dt.year == year]
                df_times_filtered = df_times_year[
                    (df_times_year['mes'] >= mes_inicio) & 
                    (df_times_year['mes'] <= mes_fin)
                ]
                
                # Solo equipos que usó el operador
                df_times_op = df_times_filtered[df_times_filtered['equipment'].isin(equipos_list)]
                
                print(f"   ⏱️  {len(df_times_op):,} registros de tiempos")
                
                if len(df_times_op) > 0:
                    # Convertir de segundos a horas
                    time_cols = ['total', 'efectivo', 'det_noprg', 'det_prg', 'm_programada', 'm_correctiva']
                    for col in time_cols:
                        df_times_op[f'{col}_hrs'] = df_times_op[col] / 3600
                    
                    # Resumen
                    total_hrs = df_times_op['total_hrs'].sum()
                    utilizacion = {
                        'horas_totales': round(total_hrs, 1),
                        'horas_efectivas': round(df_times_op['efectivo_hrs'].sum(), 1),
                        'horas_det_noprg': round(df_times_op['det_noprg_hrs'].sum(), 1),
                        'horas_det_prg': round(df_times_op['det_prg_hrs'].sum(), 1),
                        'horas_m_programada': round(df_times_op['m_programada_hrs'].sum(), 1),
                        'horas_m_correctiva': round(df_times_op['m_correctiva_hrs'].sum(), 1),
                        'utilizacion_pct': round(df_times_op['efectivo_hrs'].sum() / total_hrs * 100, 1) if total_hrs > 0 else 0
                    }
                else:
                    utilizacion = {"info": "No hay datos de tiempos para el período"}
            else:
                utilizacion = {"info": "Archivos de tiempos no disponibles"}
            
            # ===================================================================
            # 4. ANÁLISIS Y PATRONES
            # ===================================================================
            
            # Resumen de producción
            produccion = {
                'total_dumps': len(df_op),
                'total_toneladas': int(df_op['material_tonnage'].sum()),
                'total_toneladas_formatted': f"{df_op['material_tonnage'].sum():,.0f}",
                'promedio_ton_dump': round(df_op['material_tonnage'].mean(), 1),
                'equipos_diferentes': len(equipos_usados),
                'dias_trabajados': df_op['fecha'].nunique(),
                'turnos': list(df_op['shift'].unique())
            }
            
            # Top equipos usados
            top_equipos = []
            for _, row in equipos_usados.head(5).iterrows():
                top_equipos.append({
                    'equipo': row['equipo'],
                    'toneladas': int(row['toneladas']),
                    'toneladas_formatted': f"{row['toneladas']:,.0f}",
                    'dumps': int(row['dumps']),
                    'dias': int(row['dias'])
                })
            
            # ===================================================================
            # 5. RESULTADO FINAL
            # ===================================================================
            
            return {
                "success": True,
                "operador": operador_nombre_completo,
                "periodo": {
                    "year": year,
                    "mes_inicio": mes_inicio,
                    "mes_fin": mes_fin
                },
                "produccion": produccion,
                "top_5_equipos": top_equipos,
                "utilizacion": utilizacion,
                "estados_asarco": estados_analisis,
                "interpretacion": self._generar_interpretacion(produccion, utilizacion, estados_analisis)
            }
            
        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _generar_interpretacion(self, produccion, utilizacion, estados):
        """Genera interpretación de los datos"""
        interpretacion = []
        
        # Utilización
        if isinstance(utilizacion, dict) and 'utilizacion_pct' in utilizacion:
            util_pct = utilizacion['utilizacion_pct']
            if util_pct < 50:
                interpretacion.append(f"⚠️ Utilización BAJA ({util_pct}%) - Revisar causas")
            elif util_pct < 70:
                interpretacion.append(f"⚡ Utilización MEDIA ({util_pct}%) - Margen de mejora")
            else:
                interpretacion.append(f"✅ Utilización BUENA ({util_pct}%)")
        
        # Códigos ASARCO
        if isinstance(estados, dict) and 'top_10_codigos' in estados:
            if estados['top_10_codigos']:
                top_codigo = estados['top_10_codigos'][0]
                interpretacion.append(
                    f"🔴 Código {top_codigo['codigo']} ({top_codigo['razon']}) representa "
                    f"{top_codigo['porcentaje']}% del tiempo de detención"
                )
        
        return interpretacion

def get_causal_analytics(data_dir: Path = None):
    """Obtiene instancia"""
    if data_dir is None:
        from config import Config
        data_dir = Config.DATA_DIR
    return CausalAnalytics(data_dir)