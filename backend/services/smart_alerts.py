"""
Sistema de Smart Alerts - Detección Automática de Problemas Críticos
División Salvador - Codelco Chile
"""

import sqlite3
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path


class SmartAlertsEngine:
    """Motor de alertas inteligentes para detección automática de problemas"""

    def __init__(self, db_path: str = "minedash.db"):
        self.db_path = db_path

        # Umbrales críticos
        self.UMBRAL_DM_CRITICO = 70.0  # DM < 70% es crítico
        self.UMBRAL_UEBD_CRITICO = 75.0  # UEBD < 75% es crítico
        self.UMBRAL_CUMPLIMIENTO_CRITICO = 80.0  # Cumplimiento < 80% es crítico
        self.DIAS_ANALISIS = 7  # Analizar últimos 7 días

    def analizar_alertas(self) -> Dict[str, Any]:
        """
        Ejecuta análisis completo y retorna alertas críticas

        Returns:
            Dict con alertas por categoría
        """
        alertas = {
            "criticas": [],
            "advertencias": [],
            "informativas": [],
            "resumen": {}
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # ALERTA 1: DM Crítica de Equipos
            fecha_limite = (datetime.now() - timedelta(days=self.DIAS_ANALISIS)).strftime('%Y-%m-%d')

            cursor.execute("""
                SELECT
                    equipment_id,
                    equipment_type,
                    AVG(disponible * 100.0 / NULLIF(nominal, 0)) as dm_promedio,
                    COUNT(*) as horas_analizadas
                FROM hexagon_by_kpi_hora
                WHERE timestamp >= ?
                  AND nominal > 0
                  AND equipment_id NOT LIKE 'TE%'
                GROUP BY equipment_id, equipment_type
                HAVING dm_promedio < ?
                ORDER BY dm_promedio ASC
                LIMIT 10
            """, (fecha_limite, self.UMBRAL_DM_CRITICO))

            equipos_criticos = cursor.fetchall()
            if equipos_criticos:
                for equipo, tipo, dm, horas in equipos_criticos:
                    alertas["criticas"].append({
                        "tipo": "DM_CRITICA",
                        "equipo": equipo,
                        "equipment_type": tipo,
                        "valor": round(dm, 1),
                        "umbral": self.UMBRAL_DM_CRITICO,
                        "mensaje": f"🔴 {equipo} ({tipo}) con DM crítica: {dm:.1f}% (últimos {self.DIAS_ANALISIS} días)",
                        "prioridad": "CRITICA",
                        "accion_recomendada": "Revisión urgente de mantenimiento"
                    })

            # ALERTA 2: UEBD Bajo en Producción
            cursor.execute("""
                SELECT
                    equipment_id,
                    AVG((efectivo * 100.0) / NULLIF(disponible, 0)) as uebd_promedio,
                    AVG(disponible * 100.0 / NULLIF(nominal, 0)) as dm_promedio
                FROM hexagon_by_kpi_hora
                WHERE timestamp >= ?
                  AND disponible > 0
                  AND equipment_id NOT LIKE 'TE%'
                  AND tipo = 'Truck'
                GROUP BY equipment_id
                HAVING uebd_promedio < ? AND dm_promedio > 70
                ORDER BY uebd_promedio ASC
                LIMIT 5
            """, (fecha_limite, self.UMBRAL_UEBD_CRITICO))

            uebd_bajo = cursor.fetchall()
            if uebd_bajo:
                for equipo, uebd, dm in uebd_bajo:
                    alertas["advertencias"].append({
                        "tipo": "UEBD_BAJO",
                        "equipo": equipo,
                        "valor_uebd": round(uebd, 1),
                        "valor_dm": round(dm, 1),
                        "mensaje": f"⚠️ {equipo} disponible (DM {dm:.1f}%) pero con UEBD bajo: {uebd:.1f}%",
                        "prioridad": "ALTA",
                        "accion_recomendada": "Revisar asignación y utilización operacional"
                    })

            # ALERTA 3: Cumplimiento Mensual Bajo
            mes_actual = datetime.now().month
            year_actual = datetime.now().year

            # Obtener plan mensual
            from services.plan_reader import get_plan_tonelaje
            plan_mensual = get_plan_tonelaje(mes_actual, year_actual)

            if plan_mensual:
                # Obtener real acumulado del mes
                fecha_inicio_mes = f"{year_actual}-{mes_actual:02d}-01"

                cursor.execute("""
                    SELECT SUM(material_tonnage)
                    FROM hexagon_by_kpi_hora
                    WHERE timestamp >= ?
                """, (fecha_inicio_mes,))

                real_mes = cursor.fetchone()[0] or 0

                if real_mes > 0:
                    cumplimiento_pct = (real_mes / plan_mensual) * 100

                    if cumplimiento_pct < self.UMBRAL_CUMPLIMIENTO_CRITICO:
                        alertas["criticas"].append({
                            "tipo": "CUMPLIMIENTO_BAJO",
                            "valor": round(cumplimiento_pct, 1),
                            "plan": plan_mensual,
                            "real": real_mes,
                            "brecha": plan_mensual - real_mes,
                            "mensaje": f"🔴 Cumplimiento mensual en {cumplimiento_pct:.1f}% (objetivo ≥80%)",
                            "prioridad": "CRITICA",
                            "accion_recomendada": "Intensificar operaciones y revisar factores limitantes"
                        })

            # ALERTA 4: Equipos Sin Producción
            cursor.execute("""
                SELECT DISTINCT equipment_id, equipment_type
                FROM hexagon_by_kpi_hora
                WHERE timestamp >= ?
                  AND equipment_id NOT LIKE 'TE%'
                  AND tipo = 'Truck'
                  AND disponible > 0
                  AND material_tonnage = 0
                GROUP BY equipment_id, equipment_type
                HAVING COUNT(*) > 10
            """, (fecha_limite,))

            sin_produccion = cursor.fetchall()
            if sin_produccion:
                for equipo, tipo in sin_produccion[:5]:  # Top 5
                    alertas["advertencias"].append({
                        "tipo": "SIN_PRODUCCION",
                        "equipo": equipo,
                        "equipment_type": tipo,
                        "mensaje": f"⚠️ {equipo} disponible pero sin producción (>10 horas)",
                        "prioridad": "MEDIA",
                        "accion_recomendada": "Verificar asignación operacional"
                    })

            # Generar resumen
            alertas["resumen"] = {
                "total_criticas": len(alertas["criticas"]),
                "total_advertencias": len(alertas["advertencias"]),
                "total_informativas": len(alertas["informativas"]),
                "fecha_analisis": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "periodo_analizado": f"Últimos {self.DIAS_ANALISIS} días"
            }

            return alertas

        finally:
            conn.close()

    def generar_reporte_alertas(self) -> str:
        """
        Genera reporte profesional de alertas en formato markdown

        Returns:
            String con reporte markdown
        """
        alertas = self.analizar_alertas()

        lineas = []
        lineas.append("🚨 **SMART ALERTS - REPORTE DE ALERTAS AUTOMÁTICAS**")
        lineas.append("")
        lineas.append("═══════════════════════════════════════════════════════════════")
        lineas.append("")

        # Resumen ejecutivo
        resumen = alertas["resumen"]
        lineas.append("## 📊 Resumen Ejecutivo")
        lineas.append("")
        lineas.append(f"**Fecha Análisis:** {resumen['fecha_analisis']}")
        lineas.append(f"**Período:** {resumen['periodo_analizado']}")
        lineas.append("")
        lineas.append(f"- 🔴 **Alertas Críticas:** {resumen['total_criticas']}")
        lineas.append(f"- ⚠️ **Advertencias:** {resumen['total_advertencias']}")
        lineas.append(f"- ℹ️ **Informativas:** {resumen['total_informativas']}")
        lineas.append("")
        lineas.append("---")
        lineas.append("")

        # Alertas Críticas
        if alertas["criticas"]:
            lineas.append("## 🔴 ALERTAS CRÍTICAS (Acción Inmediata Requerida)")
            lineas.append("")

            for i, alerta in enumerate(alertas["criticas"], 1):
                lineas.append(f"### {i}. {alerta['tipo']}")
                lineas.append("")
                lineas.append(f"**Mensaje:** {alerta['mensaje']}")
                lineas.append(f"**Acción Recomendada:** {alerta['accion_recomendada']}")

                if alerta['tipo'] == 'DM_CRITICA':
                    lineas.append(f"**Equipo:** {alerta['equipo']}")
                    lineas.append(f"**DM Actual:** {alerta['valor']}% (umbral: {alerta['umbral']}%)")
                elif alerta['tipo'] == 'CUMPLIMIENTO_BAJO':
                    lineas.append(f"**Cumplimiento:** {alerta['valor']}%")
                    lineas.append(f"**Plan:** {alerta['plan']:,.0f} ton")
                    lineas.append(f"**Real:** {alerta['real']:,.0f} ton")
                    lineas.append(f"**Brecha:** -{alerta['brecha']:,.0f} ton")

                lineas.append("")

            lineas.append("---")
            lineas.append("")

        # Advertencias
        if alertas["advertencias"]:
            lineas.append("## ⚠️ ADVERTENCIAS (Revisar en 24-48 hrs)")
            lineas.append("")

            for i, alerta in enumerate(alertas["advertencias"], 1):
                lineas.append(f"{i}. {alerta['mensaje']}")
                lineas.append(f"   - **Acción:** {alerta['accion_recomendada']}")
                lineas.append("")

            lineas.append("---")
            lineas.append("")

        # Sin alertas
        if not alertas["criticas"] and not alertas["advertencias"]:
            lineas.append("## ✅ SISTEMA OPERANDO NORMALMENTE")
            lineas.append("")
            lineas.append("No se detectaron problemas críticos ni advertencias.")
            lineas.append("")

        lineas.append("═══════════════════════════════════════════════════════════════")
        lineas.append("")
        lineas.append("**Sistema de Monitoreo Continuo Activo** ✓")

        return "\n".join(lineas)


def get_smart_alerts() -> str:
    """
    Función principal para obtener reporte de alertas

    Returns:
        Reporte de alertas en formato markdown
    """
    engine = SmartAlertsEngine()
    return engine.generar_reporte_alertas()


if __name__ == "__main__":
    # Test
    print(get_smart_alerts())
