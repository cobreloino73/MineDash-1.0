"""
Sistema de Insights Inteligentes - MineDash AI
Genera alertas, recomendaciones y predicciones basadas en análisis de datos
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class Plan:
    """Definición de planes de producción"""
    nombre: str
    tonelaje_mensual: float
    disponibilidad_meta: float
    utilizacion_meta: float
    
PLANES = {
    'P0': Plan(
        nombre='Plan Base P0',
        tonelaje_mensual=350000,
        disponibilidad_meta=85.0,
        utilizacion_meta=65.0
    ),
    'PND': Plan(
        nombre='Plan No Desviado',
        tonelaje_mensual=380000,
        disponibilidad_meta=87.0,
        utilizacion_meta=70.0
    ),
    'MENSUAL': Plan(
        nombre='Plan Mensual',
        tonelaje_mensual=365000,
        disponibilidad_meta=86.0,
        utilizacion_meta=67.0
    )
}

class InsightsSystem:
    """Sistema de generación de insights inteligentes"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.hexagon_dir = data_dir / "Hexagon"
    
    def generar_insights(
        self, 
        year: int = 2024,
        plan_tipo: Literal['P0', 'PND', 'MENSUAL'] = 'P0'
    ) -> Dict[str, Any]:
        """
        Genera insights completos del sistema
        
        Args:
            year: Año de análisis
            plan_tipo: Tipo de plan a comparar
            
        Returns:
            Dict con alertas, recomendaciones y predicciones
        """
        plan = PLANES[plan_tipo]
        
        # Cargar datos
        kpis = self._calcular_kpis_actuales(year)
        cumplimiento = self._calcular_cumplimiento_plan(year, plan)
        codigos_asarco = self._analizar_codigos_asarco(year)
        
        # Generar cada tipo de insight
        alertas = self._generar_alertas(kpis, cumplimiento, codigos_asarco, plan)
        recomendaciones = self._generar_recomendaciones(kpis, cumplimiento, codigos_asarco, plan)
        predicciones = self._generar_predicciones(kpis, cumplimiento, plan, year)
        
        # Construir resultado
        result = {
            "success": True,
            "plan_referencia": {
                "tipo": plan_tipo,
                "nombre": plan.nombre,
                "tonelaje_meta": float(plan.tonelaje_mensual),
                "disponibilidad_meta": float(plan.disponibilidad_meta),
                "utilizacion_meta": float(plan.utilizacion_meta)
            },
            "kpis_actuales": kpis,
            "cumplimiento": cumplimiento,
            "total_alertas": len(alertas),
            "total_recomendaciones": len(recomendaciones),
            "total_predicciones": len(predicciones),
            "alertas": alertas,
            "recomendaciones": recomendaciones,
            "predicciones": predicciones
        }
        
        # Convertir todos los numpy a tipos nativos
        return self._convert_numpy(result)
    
    def _calcular_kpis_actuales(self, year: int) -> Dict[str, Any]:
        """Calcula KPIs actuales del sistema"""
        kpis = {}
        
        try:
            # Cargar datos de tiempos
            times_files = [
                self.hexagon_dir / f"by_equipment_times {year} p1.xlsx",
                self.hexagon_dir / f"by_equipment_times {year} p2.xlsx"
            ]
            
            df_times_list = []
            for f in times_files:
                if f.exists():
                    df_times_list.append(pd.read_excel(f))
            
            if df_times_list:
                df_times = pd.concat(df_times_list, ignore_index=True)
                df_times['fecha'] = pd.to_datetime(df_times['time']).dt.date
                
                # Últimos 7 días
                fecha_limite = df_times['fecha'].max() - timedelta(days=7)
                df_recent = df_times[df_times['fecha'] >= fecha_limite]
                
                # Disponibilidad
                total_hrs = df_recent['total'].sum() / 3600
                mant_correctiva = df_recent['m_correctiva'].sum() / 3600
                disponibilidad = ((total_hrs - mant_correctiva) / total_hrs * 100) if total_hrs > 0 else 0
                
                # Utilización
                efectivo = df_recent['efectivo'].sum() / 3600
                utilizacion = (efectivo / total_hrs * 100) if total_hrs > 0 else 0
                
                kpis['disponibilidad'] = round(disponibilidad, 1)
                kpis['utilizacion'] = round(utilizacion, 1)
                kpis['periodo'] = 'Últimos 7 días'
                kpis['horas_totales'] = round(total_hrs, 0)
                kpis['horas_efectivas'] = round(efectivo, 0)
                kpis['horas_mant_correctiva'] = round(mant_correctiva, 0)
            
            # Cargar dumps para producción
            dumps_file = self.hexagon_dir / f"by_detail_dumps {year}.xlsx"
            if dumps_file.exists():
                df_dumps = pd.read_excel(dumps_file)
                df_dumps['fecha'] = pd.to_datetime(df_dumps['time']).dt.date
                df_dumps['mes'] = pd.to_datetime(df_dumps['time']).dt.month
                
                # Mes actual
                mes_actual = df_dumps['mes'].max()
                df_mes = df_dumps[df_dumps['mes'] == mes_actual]
                
                tonelaje_mes = df_mes['material_tonnage'].sum()
                dumps_mes = len(df_mes)
                
                kpis['tonelaje_mes_actual'] = int(tonelaje_mes)
                kpis['dumps_mes_actual'] = dumps_mes
                kpis['mes'] = mes_actual
                
        except Exception as e:
            print(f"Error calculando KPIs: {e}")
        
        return kpis
    
    def _calcular_cumplimiento_plan(self, year: int, plan: Plan) -> Dict[str, Any]:
        """Calcula cumplimiento contra el plan"""
        cumplimiento = {}
        
        try:
            dumps_file = self.hexagon_dir / f"by_detail_dumps {year}.xlsx"
            if dumps_file.exists():
                df_dumps = pd.read_excel(dumps_file)
                df_dumps['mes'] = pd.to_datetime(df_dumps['time']).dt.month
                
                # Último mes completo
                mes_maximo = df_dumps['mes'].max()
                ultimo_mes = mes_maximo - 1 if mes_maximo > 1 else mes_maximo
                
                df_mes = df_dumps[df_dumps['mes'] == ultimo_mes]
                tonelaje_real = df_mes['material_tonnage'].sum()
                
                cumplimiento_pct = (tonelaje_real / plan.tonelaje_mensual) * 100
                deficit = plan.tonelaje_mensual - tonelaje_real
                
                cumplimiento['ultimo_mes'] = ultimo_mes
                cumplimiento['tonelaje_real'] = int(tonelaje_real)
                cumplimiento['tonelaje_plan'] = int(plan.tonelaje_mensual)
                cumplimiento['cumplimiento_pct'] = round(cumplimiento_pct, 1)
                cumplimiento['deficit'] = int(deficit)
                cumplimiento['estado'] = 'cumplido' if cumplimiento_pct >= 100 else 'deficit'
                    
        except Exception as e:
            print(f"Error calculando cumplimiento: {e}")
        
        return cumplimiento
    
    def _analizar_codigos_asarco(self, year: int) -> Dict[str, Any]:
        """Analiza códigos ASARCO críticos"""
        codigos_info = {}
        
        try:
            estados_file = self.hexagon_dir / "by_estados_2024_2025.xlsx"
            
            if estados_file.exists():
                df_estados = pd.read_excel(estados_file)
                df_estados['fecha'] = pd.to_datetime(df_estados['fecha']).dt.date
                
                # Últimos 30 días
                fecha_limite = df_estados['fecha'].max() - timedelta(days=30)
                df_recent = df_estados[df_estados['fecha'] >= fecha_limite]
                
                # Top códigos
                codigos_top = df_recent.groupby(['code', 'razon']).agg({
                    'horas': 'sum'
                }).reset_index()
                codigos_top = codigos_top.sort_values('horas', ascending=False).head(5)
                
                codigos_info['top_5'] = []
                for _, row in codigos_top.iterrows():
                    codigos_info['top_5'].append({
                        'codigo': int(row['code']),
                        'razon': row['razon'],
                        'horas': round(row['horas'], 1)
                    })
                
        except Exception as e:
            print(f"Error analizando códigos ASARCO: {e}")
        
        return codigos_info
    
    def _generar_alertas(
        self, 
        kpis: Dict, 
        cumplimiento: Dict, 
        codigos_asarco: Dict,
        plan: Plan
    ) -> List[Dict[str, Any]]:
        """Genera alertas del sistema"""
        alertas = []
        
        # Alerta de disponibilidad
        if 'disponibilidad' in kpis:
            if kpis['disponibilidad'] < plan.disponibilidad_meta:
                brecha = plan.disponibilidad_meta - kpis['disponibilidad']
                alertas.append({
                    'tipo': 'critical' if brecha > 5 else 'warning',
                    'categoria': 'disponibilidad',
                    'titulo': f"Disponibilidad bajo meta ({kpis['disponibilidad']}%)",
                    'descripcion': f"Disponibilidad actual {kpis['disponibilidad']}% vs meta {plan.disponibilidad_meta}%. Brecha: {brecha:.1f} puntos porcentuales.",
                    'kpi': 'Disponibilidad Mecánica',
                    'valor_actual': f"{kpis['disponibilidad']}%",
                    'valor_meta': f"{plan.disponibilidad_meta}%",
                    'impacto': 'Alto - Afecta directamente capacidad productiva',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Alerta de utilización
        if 'utilizacion' in kpis:
            if kpis['utilizacion'] < plan.utilizacion_meta:
                brecha = plan.utilizacion_meta - kpis['utilizacion']
                alertas.append({
                    'tipo': 'critical' if brecha > 10 else 'warning',
                    'categoria': 'utilizacion',
                    'titulo': f"Utilización bajo meta ({kpis['utilizacion']}%)",
                    'descripcion': f"Utilización actual {kpis['utilizacion']}% vs meta {plan.utilizacion_meta}%. Brecha: {brecha:.1f} puntos porcentuales.",
                    'kpi': 'Utilización Efectiva',
                    'valor_actual': f"{kpis['utilizacion']}%",
                    'valor_meta': f"{plan.utilizacion_meta}%",
                    'impacto': 'Alto - Horas productivas perdidas',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Alerta de cumplimiento de plan
        if cumplimiento and cumplimiento.get('estado') == 'deficit':
            alertas.append({
                'tipo': 'critical',
                'categoria': 'produccion',
                'titulo': f"Déficit de plan mes {cumplimiento['ultimo_mes']}",
                'descripcion': f"Cumplimiento: {cumplimiento['cumplimiento_pct']}% ({cumplimiento['tonelaje_real']:,} de {cumplimiento['tonelaje_plan']:,} ton). Déficit: {abs(cumplimiento['deficit']):,} toneladas.",
                'kpi': 'Cumplimiento Plan',
                'valor_actual': f"{cumplimiento['cumplimiento_pct']}%",
                'valor_meta': '100%',
                'impacto': 'Crítico - No cumplimiento de compromisos',
                'timestamp': datetime.now().isoformat()
            })
        
        # Alerta de códigos ASARCO
        if codigos_asarco and 'top_5' in codigos_asarco and len(codigos_asarco['top_5']) > 0:
            top_codigo = codigos_asarco['top_5'][0]
            if top_codigo['horas'] > 1000:  # Más de 1000 horas en 30 días
                alertas.append({
                    'tipo': 'warning',
                    'categoria': 'asarco',
                    'titulo': f"Código ASARCO {top_codigo['codigo']} con alto impacto",
                    'descripcion': f"Código {top_codigo['codigo']} ({top_codigo['razon']}) acumula {top_codigo['horas']:.0f} horas en últimos 30 días.",
                    'kpi': 'Códigos ASARCO',
                    'valor_actual': f"{top_codigo['horas']:.0f} hrs",
                    'codigo_asarco': top_codigo['codigo'],
                    'impacto': 'Medio - Requiere análisis de causa raíz',
                    'timestamp': datetime.now().isoformat()
                })
        
        return alertas
    
    def _generar_recomendaciones(
        self,
        kpis: Dict,
        cumplimiento: Dict,
        codigos_asarco: Dict,
        plan: Plan
    ) -> List[Dict[str, Any]]:
        """Genera recomendaciones accionables"""
        recomendaciones = []
        
        # Recomendación para disponibilidad
        if 'disponibilidad' in kpis and kpis['disponibilidad'] < plan.disponibilidad_meta:
            recomendaciones.append({
                'prioridad': 'alta',
                'categoria': 'mantenimiento',
                'titulo': 'Incrementar mantención preventiva',
                'descripcion': f"Con {kpis.get('horas_mant_correctiva', 0):.0f} horas de mantención correctiva, hay oportunidad de reducir fallas imprevistas.",
                'acciones': [
                    'Revisar plan de mantención preventiva',
                    'Identificar equipos con mayor tasa de fallas',
                    'Implementar mantención predictiva con sensores',
                    'Aumentar stock de repuestos críticos'
                ],
                'impacto_estimado': f"+{(plan.disponibilidad_meta - kpis['disponibilidad']) * 0.6:.1f} puntos porcentuales en disponibilidad",
                'plazo': 'Mediano plazo (2-4 semanas)',
                'kpi_objetivo': 'Disponibilidad Mecánica'
            })
        
        # Recomendación para utilización
        if 'utilizacion' in kpis and kpis['utilizacion'] < plan.utilizacion_meta:
            recomendaciones.append({
                'prioridad': 'alta',
                'categoria': 'operaciones',
                'titulo': 'Optimizar asignación de operadores y coordinación',
                'descripcion': 'Análisis indica oportunidades en coordinación entre áreas y asignación de recursos.',
                'acciones': [
                    'Analizar códigos 219 (Falta Equipo Carguío) y 225 (Sin Operador)',
                    'Evaluar redistribución de dotación por turno',
                    'Mejorar coordinación despacho-carguío',
                    'Implementar sistema de alertas tempranas de demoras'
                ],
                'impacto_estimado': f"+{(plan.utilizacion_meta - kpis['utilizacion']) * 0.7:.1f} puntos porcentuales en utilización",
                'plazo': 'Corto plazo (1-2 semanas)',
                'kpi_objetivo': 'Utilización Efectiva'
            })
        
        # Recomendación para cumplimiento de plan
        if cumplimiento and cumplimiento.get('estado') == 'deficit':
            recomendaciones.append({
                'prioridad': 'crítica',
                'categoria': 'estrategia',
                'titulo': 'Plan de recuperación de producción',
                'descripcion': f"Déficit acumulado de {abs(cumplimiento['deficit']):,} toneladas requiere acciones inmediatas.",
                'acciones': [
                    'Extender horarios de operación en turnos de mayor rendimiento',
                    'Priorizar equipos de mayor capacidad',
                    'Revisar rutas de acarreo para optimizar ciclos',
                    'Coordinar con planificación para ajuste de frentes de carga'
                ],
                'impacto_estimado': f"Recuperar ~{abs(cumplimiento['deficit']) * 0.5:,.0f} toneladas",
                'plazo': 'Inmediato (esta semana)',
                'kpi_objetivo': 'Cumplimiento Plan'
            })
        
        # Recomendación basada en códigos ASARCO
        if codigos_asarco and 'top_5' in codigos_asarco and len(codigos_asarco['top_5']) > 0:
            top_codigo = codigos_asarco['top_5'][0]
            if top_codigo['codigo'] == 400:  # Imprevisto Mecánico
                recomendaciones.append({
                    'prioridad': 'alta',
                    'categoria': 'mantenimiento',
                    'titulo': 'Reducir imprevistos mecánicos (Código 400)',
                    'descripcion': f"Código 400 acumula {top_codigo['horas']:.0f} horas, indicando oportunidades de mejora en confiabilidad.",
                    'acciones': [
                        'Análisis de causa raíz de fallas recurrentes',
                        'Identificar componentes con mayor tasa de falla',
                        'Revisar procedimientos de mantención',
                        'Capacitar a personal de mantención en diagnóstico'
                    ],
                    'impacto_estimado': f"-{top_codigo['horas'] * 0.3:.0f} horas de detención mensual",
                    'plazo': 'Mediano plazo (3-6 semanas)',
                    'kpi_objetivo': 'Disponibilidad Mecánica'
                })
        
        return recomendaciones
    
    def _generar_predicciones(
        self,
        kpis: Dict,
        cumplimiento: Dict,
        plan: Plan,
        year: int
    ) -> List[Dict[str, Any]]:
        """Genera predicciones basadas en tendencias"""
        predicciones = []
        
        try:
            # Predicción de cumplimiento mes actual
            if 'tonelaje_mes_actual' in kpis and 'mes' in kpis:
                # Calcular días transcurridos del mes
                hoy = datetime.now()
                dias_mes = 30  # Simplificado
                dia_actual = hoy.day
                
                if dia_actual > 0:
                    # Proyección lineal
                    ritmo_diario = kpis['tonelaje_mes_actual'] / dia_actual
                    proyeccion_mes = ritmo_diario * dias_mes
                    cumplimiento_proyectado = (proyeccion_mes / plan.tonelaje_mensual) * 100
                    
                    probabilidad = 'Alta' if cumplimiento_proyectado >= 95 else 'Media' if cumplimiento_proyectado >= 85 else 'Baja'
                    
                    predicciones.append({
                        'tipo': 'proyeccion',
                        'titulo': 'Proyección cumplimiento fin de mes',
                        'descripcion': f"Basado en ritmo actual de {ritmo_diario:,.0f} ton/día, se proyecta terminar el mes con {proyeccion_mes:,.0f} toneladas.",
                        'metrica': 'Cumplimiento de plan',
                        'valor_proyectado': f"{cumplimiento_proyectado:.1f}%",
                        'valor_objetivo': '100%',
                        'probabilidad': probabilidad,
                        'confianza': '75%',
                        'supuestos': [
                            'Mantención de ritmo productivo actual',
                            'Sin eventos climáticos adversos',
                            'Disponibilidad mecánica estable'
                        ]
                    })
            
            # Predicción de disponibilidad
            if 'disponibilidad' in kpis:
                # Tendencia simple basada en distancia a meta
                brecha = plan.disponibilidad_meta - kpis['disponibilidad']
                tendencia = 'estable'
                if brecha > 3:
                    tendencia = 'a la baja'
                elif brecha < -2:
                    tendencia = 'al alza'
                
                riesgo_nivel = 'Alto' if tendencia == 'a la baja' else 'Medio' if tendencia == 'estable' else 'Bajo'
                
                predicciones.append({
                    'tipo': 'tendencia',
                    'titulo': 'Tendencia de disponibilidad mecánica',
                    'descripcion': f"Disponibilidad actual de {kpis['disponibilidad']}% muestra tendencia {tendencia} respecto a meta de {plan.disponibilidad_meta}%.",
                    'metrica': 'Disponibilidad Mecánica',
                    'tendencia': tendencia,
                    'riesgo': riesgo_nivel,
                    'recomendacion': 'Implementar plan de contingencia' if tendencia == 'a la baja' else 'Mantener monitoreo' if tendencia == 'estable' else 'Continuar con plan actual'
                })
            
            # Predicción de utilización
            if 'utilizacion' in kpis:
                brecha = plan.utilizacion_meta - kpis['utilizacion']
                
                if brecha > 5:
                    predicciones.append({
                        'tipo': 'riesgo',
                        'titulo': 'Riesgo de no cumplir meta de utilización',
                        'descripcion': f"Con utilización actual de {kpis['utilizacion']}%, existe riesgo de no alcanzar meta mensual de {plan.utilizacion_meta}%.",
                        'metrica': 'Utilización Efectiva',
                        'nivel_riesgo': 'Alto' if brecha > 10 else 'Medio',
                        'brecha_actual': f"{brecha:.1f} puntos porcentuales",
                        'accion_sugerida': 'Implementar acciones correctivas inmediatas para mejorar coordinación operacional'
                    })
                
        except Exception as e:
            print(f"Error generando predicciones: {e}")
        
        return predicciones
    
    def _convert_numpy(self, obj):
        """Convierte tipos numpy a tipos nativos de Python para serialización JSON"""
        if isinstance(obj, dict):
            return {key: self._convert_numpy(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        else:
            return obj

def get_insights_system(data_dir: Path = None):
    """Obtiene instancia del sistema de insights"""
    if data_dir is None:
        from config import Config
        data_dir = Config.DATA_DIR
    return InsightsSystem(data_dir)