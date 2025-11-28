"""
Plan Comparison Service - MineDash AI
Compara resultados reales vs planes (P0, PND, PM)
Responde consultas en lenguaje natural con tablas
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import calendar

class PlanComparisonService:
    """
    Servicio que compara producción real vs planes
    Responde consultas como: "dame julio 2025 real vs planes"
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.hexagon_dir = data_dir / "Hexagon"
        self.planning_dir = data_dir / "Planificación"
        
        # Cache de planes
        self._planes_cache = None
    
    async def compare_real_vs_plans(
        self,
        mes: int,
        year: int = 2024,
        incluir_acumulado: bool = True
    ) -> Dict[str, Any]:
        """
        Compara resultado real vs todos los planes
        
        Args:
            mes: Mes a comparar (1-12)
            year: Año
            incluir_acumulado: Si incluir acumulado del año
            
        Returns:
            Dict con tabla comparativa
        """
        
        # Cargar planes si no están en cache
        if self._planes_cache is None:
            await self._load_plans()
        
        # Obtener real del mes
        real_mes = await self._get_real_month(mes, year)
        
        # Obtener real acumulado
        real_acum = await self._get_real_accumulated(mes, year) if incluir_acumulado else None
        
        # Construir tabla comparativa
        tabla = self._build_comparison_table(
            mes=mes,
            year=year,
            real_mes=real_mes,
            real_acum=real_acum,
            planes=self._planes_cache
        )
        
        return {
            "success": True,
            "mes": mes,
            "mes_nombre": calendar.month_name[mes],
            "year": year,
            "tabla": tabla,
            "resumen": self._generate_summary(tabla),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _load_plans(self):
        """Carga todos los planes disponibles"""
        print("🔄 Cargando planes...")
        
        from services.intelligent_extractor import get_intelligent_extractor
        extractor = get_intelligent_extractor(self.data_dir)
        
        self._planes_cache = await extractor.extract_all_plans()
        
        print(f"✅ Planes cargados: {list(self._planes_cache.keys())}")
    
    async def _get_real_month(self, mes: int, year: int) -> Dict[str, Any]:
        """Obtiene producción real de un mes específico"""
        try:
            dumps_file = self.hexagon_dir / f"by_detail_dumps {year}.xlsx"
            
            if not dumps_file.exists():
                return {
                    "tonelaje": 0,
                    "dumps": 0,
                    "error": f"Archivo no encontrado: {dumps_file.name}"
                }
            
            df = pd.read_excel(dumps_file)
            df['fecha'] = pd.to_datetime(df['time'])
            df['mes'] = df['fecha'].dt.month
            
            # Filtrar por mes
            df_mes = df[df['mes'] == mes]
            
            tonelaje = df_mes['material_tonnage'].sum()
            dumps = len(df_mes)
            
            return {
                "tonelaje": float(tonelaje),
                "dumps": int(dumps),
                "ton_por_dump": float(tonelaje / dumps) if dumps > 0 else 0,
                "source": dumps_file.name
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo real mes {mes}: {e}")
            return {
                "tonelaje": 0,
                "dumps": 0,
                "error": str(e)
            }
    
    async def _get_real_accumulated(self, hasta_mes: int, year: int) -> Dict[str, Any]:
        """Obtiene producción real acumulada hasta un mes"""
        try:
            dumps_file = self.hexagon_dir / f"by_detail_dumps {year}.xlsx"
            
            if not dumps_file.exists():
                return {
                    "tonelaje": 0,
                    "dumps": 0,
                    "error": f"Archivo no encontrado"
                }
            
            df = pd.read_excel(dumps_file)
            df['fecha'] = pd.to_datetime(df['time'])
            df['mes'] = df['fecha'].dt.month
            
            # Filtrar hasta el mes
            df_acum = df[df['mes'] <= hasta_mes]
            
            tonelaje = df_acum['material_tonnage'].sum()
            dumps = len(df_acum)
            
            return {
                "tonelaje": float(tonelaje),
                "dumps": int(dumps),
                "meses": hasta_mes,
                "promedio_mensual": float(tonelaje / hasta_mes) if hasta_mes > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo acumulado: {e}")
            return {
                "tonelaje": 0,
                "dumps": 0,
                "error": str(e)
            }
    
    def _build_comparison_table(
        self,
        mes: int,
        year: int,
        real_mes: Dict,
        real_acum: Optional[Dict],
        planes: Dict[str, Dict]
    ) -> List[Dict[str, Any]]:
        """
        Construye tabla comparativa Real vs Planes
        """
        
        tabla = []
        
        # Fila 1: Real del mes
        if real_mes:
            tabla.append({
                "concepto": f"Real {calendar.month_name[mes]} {year}",
                "tipo": "Real",
                "tonelaje": real_mes.get("tonelaje", 0),
                "tonelaje_formatted": f"{real_mes.get('tonelaje', 0):,.0f}",
                "dumps": real_mes.get("dumps", 0),
                "ton_por_dump": real_mes.get("ton_por_dump", 0)
            })
        
        # Fila 2: Plan Mensual (PM)
        if "PM" in planes:
            pm = planes["PM"]
            ton_mes_pm = pm.get("tonelaje_mensual", 0)
            ton_real = real_mes.get("tonelaje", 0)
            
            cumplimiento_pm = (ton_real / ton_mes_pm * 100) if ton_mes_pm > 0 else 0
            brecha_pm = ton_real - ton_mes_pm
            
            tabla.append({
                "concepto": f"Plan Mensual (PM) {calendar.month_name[mes]}",
                "tipo": "PM",
                "tonelaje": ton_mes_pm,
                "tonelaje_formatted": f"{ton_mes_pm:,.0f}",
                "cumplimiento_pct": round(cumplimiento_pm, 1),
                "brecha": brecha_pm,
                "brecha_formatted": f"{brecha_pm:+,.0f}",
                "estado": "✅ Cumplido" if cumplimiento_pm >= 100 else "⚠️ Déficit"
            })
        
        # Fila 3: Plan Anual (P0) - Mensual
        if "P0" in planes:
            p0 = planes["P0"]
            ton_mes_p0 = p0.get("tonelaje_mensual", 0)
            ton_real = real_mes.get("tonelaje", 0)
            
            cumplimiento_p0 = (ton_real / ton_mes_p0 * 100) if ton_mes_p0 > 0 else 0
            brecha_p0 = ton_real - ton_mes_p0
            
            tabla.append({
                "concepto": f"Plan Anual (P0) - Promedio Mensual",
                "tipo": "P0",
                "tonelaje": ton_mes_p0,
                "tonelaje_formatted": f"{ton_mes_p0:,.0f}",
                "cumplimiento_pct": round(cumplimiento_p0, 1),
                "brecha": brecha_p0,
                "brecha_formatted": f"{brecha_p0:+,.0f}",
                "estado": "✅ Cumplido" if cumplimiento_p0 >= 100 else "⚠️ Déficit"
            })
        
        # Fila 4: Plan Largo Plazo (PND) - Mensual
        if "PND" in planes:
            pnd = planes["PND"]
            ton_mes_pnd = pnd.get("tonelaje_mensual", 0)
            ton_real = real_mes.get("tonelaje", 0)
            
            cumplimiento_pnd = (ton_real / ton_mes_pnd * 100) if ton_mes_pnd > 0 else 0
            brecha_pnd = ton_real - ton_mes_pnd
            
            tabla.append({
                "concepto": f"Plan No Desviado (PND) - Promedio Mensual",
                "tipo": "PND",
                "tonelaje": ton_mes_pnd,
                "tonelaje_formatted": f"{ton_mes_pnd:,.0f}",
                "cumplimiento_pct": round(cumplimiento_pnd, 1),
                "brecha": brecha_pnd,
                "brecha_formatted": f"{brecha_pnd:+,.0f}",
                "estado": "✅ Cumplido" if cumplimiento_pnd >= 100 else "⚠️ Déficit"
            })
        
        # SECCIÓN ACUMULADA
        if real_acum:
            # Separador
            tabla.append({
                "concepto": "═══════════════════════════════",
                "tipo": "SEPARADOR",
                "tonelaje": None
            })
            
            # Fila 5: Real Acumulado
            tabla.append({
                "concepto": f"Real Acumulado Ene-{calendar.month_name[mes][:3]} {year}",
                "tipo": "Real Acumulado",
                "tonelaje": real_acum.get("tonelaje", 0),
                "tonelaje_formatted": f"{real_acum.get('tonelaje', 0):,.0f}",
                "dumps": real_acum.get("dumps", 0),
                "meses": real_acum.get("meses", 0),
                "promedio_mensual": real_acum.get("promedio_mensual", 0),
                "promedio_mensual_formatted": f"{real_acum.get('promedio_mensual', 0):,.0f}"
            })
            
            # Fila 6: P0 Acumulado
            if "P0" in planes:
                p0 = planes["P0"]
                ton_acum_p0 = p0.get("tonelaje_mensual", 0) * mes
                ton_real_acum = real_acum.get("tonelaje", 0)
                
                cumpl_acum_p0 = (ton_real_acum / ton_acum_p0 * 100) if ton_acum_p0 > 0 else 0
                brecha_acum_p0 = ton_real_acum - ton_acum_p0
                
                tabla.append({
                    "concepto": f"Plan Anual (P0) - Acumulado {mes} meses",
                    "tipo": "P0 Acumulado",
                    "tonelaje": ton_acum_p0,
                    "tonelaje_formatted": f"{ton_acum_p0:,.0f}",
                    "cumplimiento_pct": round(cumpl_acum_p0, 1),
                    "brecha": brecha_acum_p0,
                    "brecha_formatted": f"{brecha_acum_p0:+,.0f}",
                    "estado": "✅ Cumplido" if cumpl_acum_p0 >= 100 else "⚠️ Déficit"
                })
            
            # Fila 7: PND Acumulado
            if "PND" in planes:
                pnd = planes["PND"]
                ton_acum_pnd = pnd.get("tonelaje_mensual", 0) * mes
                ton_real_acum = real_acum.get("tonelaje", 0)
                
                cumpl_acum_pnd = (ton_real_acum / ton_acum_pnd * 100) if ton_acum_pnd > 0 else 0
                brecha_acum_pnd = ton_real_acum - ton_acum_pnd
                
                tabla.append({
                    "concepto": f"Plan No Desviado (PND) - Acumulado {mes} meses",
                    "tipo": "PND Acumulado",
                    "tonelaje": ton_acum_pnd,
                    "tonelaje_formatted": f"{ton_acum_pnd:,.0f}",
                    "cumplimiento_pct": round(cumpl_acum_pnd, 1),
                    "brecha": brecha_acum_pnd,
                    "brecha_formatted": f"{brecha_acum_pnd:+,.0f}",
                    "estado": "✅ Cumplido" if cumpl_acum_pnd >= 100 else "⚠️ Déficit"
                })
        
        return tabla
    
    def _generate_summary(self, tabla: List[Dict]) -> Dict[str, Any]:
        """Genera resumen ejecutivo de la comparación"""
        
        # Encontrar mejor y peor cumplimiento
        cumplimientos = [
            row for row in tabla 
            if row.get("cumplimiento_pct") is not None and row["tipo"] != "SEPARADOR"
        ]
        
        if not cumplimientos:
            return {}
        
        mejor = max(cumplimientos, key=lambda x: x.get("cumplimiento_pct", 0))
        peor = min(cumplimientos, key=lambda x: x.get("cumplimiento_pct", 0))
        
        return {
            "mejor_cumplimiento": {
                "plan": mejor.get("tipo"),
                "porcentaje": mejor.get("cumplimiento_pct"),
                "estado": mejor.get("estado")
            },
            "peor_cumplimiento": {
                "plan": peor.get("tipo"),
                "porcentaje": peor.get("cumplimiento_pct"),
                "estado": peor.get("estado")
            },
            "total_planes_comparados": len(cumplimientos)
        }


def get_plan_comparison_service(data_dir: Path = None):
    """Obtiene instancia del servicio de comparación"""
    if data_dir is None:
        from config import Config
        data_dir = Config.DATA_DIR
    return PlanComparisonService(data_dir)