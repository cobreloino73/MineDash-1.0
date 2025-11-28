"""
Endpoint de Análisis Pareto de Delays - MineDash AI v2.0
Analiza hexagon_estados para identificar 20% de causas que generan 80% del impacto
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime
import sqlite3

router = APIRouter()


@router.get("/api/analytics/pareto-delays")
async def get_pareto_delays(
    year: int = Query(2024, description="Año de análisis"),
    mes_inicio: int = Query(1, description="Mes inicio (1-12)"),
    mes_fin: int = Query(12, description="Mes fin (1-12)"),
    top_n: int = Query(20, description="Top N causas a mostrar")
):
    """
    Análisis Pareto de Delays según metodología ASARCO
    
    Identifica las principales causas de pérdida de tiempo productivo:
    - M. CORRECTIVA: Mantenimiento correctivo no planificado
    - DET.NOPRG.: Detenciones no programadas (operacionales)
    - DET.PROG.: Detenciones programadas (no operacionales)
    
    Relaciona con UEBD bajo (47.5% actual vs 75% target)
    """
    try:
        conn = sqlite3.connect("minedash.db")
        cursor = conn.cursor()
        
        # ======== ANÁLISIS PARETO POR CATEGORIA + RAZON ========
        
        cursor.execute("""
            SELECT 
                categoria,
                COALESCE(razon, 'Sin razón especificada') as razon,
                estado,
                COUNT(*) as cantidad_eventos,
                SUM(horas) as horas_perdidas,
                ROUND(AVG(horas), 2) as horas_promedio_evento
            FROM hexagon_estados
            WHERE strftime('%Y', fecha) = ?
              AND CAST(strftime('%m', fecha) AS INTEGER) BETWEEN ? AND ?
              AND categoria IN ('M. CORRECTIVA', 'DET.NOPRG.', 'DET.PROG.', 'M. PROGRAMADA')
              AND horas > 0
            GROUP BY categoria, razon, estado
            ORDER BY horas_perdidas DESC
            LIMIT ?
        """, (str(year), mes_inicio, mes_fin, top_n))
        
        delays_data = []
        total_horas_perdidas = 0
        
        for row in cursor.fetchall():
            horas = float(row[4]) if row[4] else 0
            total_horas_perdidas += horas
            
            delays_data.append({
                "categoria": row[0],
                "razon": row[1],
                "estado": row[2],
                "cantidad_eventos": row[3],
                "horas_perdidas": horas,
                "horas_promedio_evento": float(row[5]) if row[5] else 0
            })
        
        # Calcular porcentajes acumulados (Pareto)
        acumulado = 0
        for item in delays_data:
            item["porcentaje"] = round((item["horas_perdidas"] / total_horas_perdidas * 100), 1) if total_horas_perdidas > 0 else 0
            acumulado += item["porcentaje"]
            item["porcentaje_acumulado"] = round(acumulado, 1)
            item["en_pareto_80"] = acumulado <= 80
        
        # Identificar causas críticas (80% del impacto)
        causas_criticas = [d for d in delays_data if d["en_pareto_80"]]
        
        # ======== RESUMEN POR CATEGORIA ========
        
        cursor.execute("""
            SELECT 
                categoria,
                COUNT(*) as eventos,
                SUM(horas) as horas,
                COUNT(DISTINCT equipo) as equipos_afectados
            FROM hexagon_estados
            WHERE strftime('%Y', fecha) = ?
              AND CAST(strftime('%m', fecha) AS INTEGER) BETWEEN ? AND ?
              AND categoria IN ('M. CORRECTIVA', 'DET.NOPRG.', 'DET.PROG.', 'M. PROGRAMADA')
            GROUP BY categoria
            ORDER BY horas DESC
        """, (str(year), mes_inicio, mes_fin))
        
        resumen_categorias = []
        for row in cursor.fetchall():
            horas = float(row[2]) if row[2] else 0
            resumen_categorias.append({
                "categoria": row[0],
                "eventos": row[1],
                "horas_perdidas": horas,
                "porcentaje": round((horas / total_horas_perdidas * 100), 1) if total_horas_perdidas > 0 else 0,
                "equipos_afectados": row[3]
            })
        
               
        # ======== RELACIÓN CON UEBD BAJO ========
        
        # Obtener UEBD actual
        cursor.execute("""
            WITH equipment_times_all AS (
                SELECT timestamp, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2023
                WHERE strftime('%Y', timestamp) = ?
                  AND CAST(strftime('%m', timestamp) AS INTEGER) BETWEEN ? AND ?
                UNION ALL
                SELECT timestamp, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2024_p1
                WHERE strftime('%Y', timestamp) = ?
                  AND CAST(strftime('%m', timestamp) AS INTEGER) BETWEEN ? AND ?
                UNION ALL
                SELECT timestamp, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2024_p2
                WHERE strftime('%Y', timestamp) = ?
                  AND CAST(strftime('%m', timestamp) AS INTEGER) BETWEEN ? AND ?
                UNION ALL
                SELECT timestamp, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2025
                WHERE strftime('%Y', timestamp) = ?
                  AND CAST(strftime('%m', timestamp) AS INTEGER) BETWEEN ? AND ?
            )
            SELECT 
                ROUND(AVG(
                    CASE WHEN (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0)) > 0
                    THEN (efectivo / (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0))) * 100
                    ELSE NULL END
                ), 1) as uebd_actual,
                SUM(total) as horas_nominales_totales,
                SUM(efectivo) as horas_efectivas_totales
            FROM equipment_times_all
            WHERE total > 0
        """, (str(year), mes_inicio, mes_fin,
              str(year), mes_inicio, mes_fin,
              str(year), mes_inicio, mes_fin,
              str(year), mes_inicio, mes_fin))
        
        uebd_data = cursor.fetchone()
        uebd_actual = uebd_data[0] if uebd_data and uebd_data[0] else 0
        horas_nominales = uebd_data[1] if uebd_data else 0
        horas_efectivas = uebd_data[2] if uebd_data else 0
        
        # Target UEBD
        uebd_target = 75.0
        brecha_uebd = uebd_target - uebd_actual
        
        # Horas que deberíamos tener efectivas para llegar al target
        horas_disponibles = horas_nominales - total_horas_perdidas
        horas_efectivas_target = (horas_disponibles * uebd_target / 100) if horas_disponibles > 0 else 0
        horas_faltantes = horas_efectivas_target - horas_efectivas
        
        conn.close()
        
        # ======== CONSTRUIR RESPUESTA ========
        
        return {
            "success": True,
            "periodo": {
                "year": year,
                "mes_inicio": mes_inicio,
                "mes_fin": mes_fin,
                "descripcion": f"{year}-{mes_inicio:02d} a {year}-{mes_fin:02d}"
            },
            "uebd": {
                "actual": uebd_actual,
                "target": uebd_target,
                "brecha": round(brecha_uebd, 1),
                "status": "ok" if uebd_actual >= uebd_target else "critical",
                "horas_nominales": round(horas_nominales, 1),
                "horas_efectivas": round(horas_efectivas, 1),
                "horas_efectivas_target": round(horas_efectivas_target, 1),
                "horas_faltantes_para_target": round(horas_faltantes, 1)
            },
                "pareto": {
                "total_horas_perdidas": round(total_horas_perdidas, 1),
                "top_delays": delays_data,
                "causas_criticas_80": causas_criticas,
                "cantidad_causas_criticas": len(causas_criticas),
                "porcentaje_impacto_causas_criticas": round(sum(c["porcentaje"] for c in causas_criticas), 1)
           },
            "resumen_por_categoria": resumen_categorias,
            "recomendaciones": _generar_recomendaciones(causas_criticas, uebd_actual, brecha_uebd),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en análisis Pareto: {str(e)}")


def _generar_recomendaciones(causas_criticas: List[Dict], uebd_actual: float, brecha_uebd: float) -> List[Dict]:
    """Genera recomendaciones basadas en análisis Pareto"""
    recomendaciones = []
    
    if not causas_criticas:
        return recomendaciones
    
    # Top 1 causa
    top_causa = causas_criticas[0]
    
    if top_causa["categoria"] == "M. CORRECTIVA":
        recomendaciones.append({
            "prioridad": "CRÍTICA",
            "titulo": f"Reducir Mantenimiento Correctivo: {top_causa['razon']}",
            "descripcion": f"{top_causa['horas_perdidas']:.0f} horas perdidas en {top_causa['cantidad_eventos']} eventos",
            "acciones": [
                "Implementar mantenimiento predictivo en equipos con mayor tasa de fallas",
                "Analizar causa raíz de fallas recurrentes",
                "Aumentar frecuencia de inspecciones preventivas",
                "Mejorar stock de repuestos críticos"
            ],
            "impacto_estimado": f"Reducción de {top_causa['porcentaje']}% en horas perdidas",
            "objetivo": "Convertir correctivo en preventivo para aumentar DM"
        })
    
    elif top_causa["categoria"] == "DET.NOPRG.":
        recomendaciones.append({
            "prioridad": "CRÍTICA",
            "titulo": f"Optimizar Operaciones: {top_causa['razon']}",
            "descripcion": f"{top_causa['horas_perdidas']:.0f} horas perdidas en {top_causa['cantidad_eventos']} eventos",
            "acciones": [
                "Revisar coordinación despacho-carguío",
                "Analizar causas de esperas operacionales",
                "Mejorar comunicación entre turnos",
                "Implementar sistema de alertas tempranas"
            ],
            "impacto_estimado": f"Recuperar {top_causa['porcentaje']}% de horas perdidas",
            "objetivo": "Reducir detenciones operacionales para aumentar UEBD"
        })
    
    # Si UEBD < 60%, es crítico
    if uebd_actual < 60:
        recomendaciones.append({
            "prioridad": "CRÍTICA",
            "titulo": "UEBD Críticamente Bajo",
            "descripcion": f"UEBD actual {uebd_actual}% vs target 75% (brecha: {brecha_uebd:.1f}%)",
            "acciones": [
                f"Enfocar en las {len(causas_criticas)} causas críticas identificadas (80% del impacto)",
                "Establecer task force para reducción de delays",
                "Implementar tablero de control en tiempo real",
                "Revisión diaria de causas de pérdidas"
            ],
            "impacto_estimado": f"Cerrar brecha de {brecha_uebd:.1f}% en UEBD",
            "objetivo": "Alcanzar target de 75% UEBD en 3 meses"
        })
    
    return recomendaciones


# ======== ENDPOINT ADICIONAL: TOP EQUIPOS CON MÁS DELAYS ========

@router.get("/api/analytics/equipos-criticos")
async def get_equipos_criticos(
    year: int = Query(2024),
    top_n: int = Query(10)
):
    """
    Identifica equipos con mayor cantidad de delays
    Para priorizar intervenciones de mantenimiento
    """
    try:
        conn = sqlite3.connect("minedash.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                equipo,
                flota,
                COUNT(*) as total_eventos,
                SUM(CASE WHEN categoria = 'M. CORRECTIVA' THEN 1 ELSE 0 END) as eventos_correctivo,
                SUM(CASE WHEN categoria = 'DET.NOPRG.' THEN 1 ELSE 0 END) as eventos_det_noprg,
                SUM(horas) as horas_perdidas_totales,
                ROUND(AVG(horas), 2) as horas_promedio_evento
            FROM hexagon_estados
            WHERE strftime('%Y', fecha) = ?
              AND categoria IN ('M. CORRECTIVA', 'DET.NOPRG.', 'DET.PROG.')
            GROUP BY equipo, flota
            ORDER BY horas_perdidas_totales DESC
            LIMIT ?
        """, (str(year), top_n))
        
        equipos_criticos = []
        for row in cursor.fetchall():
            equipos_criticos.append({
                "equipo": row[0],
                "flota": row[1],
                "total_eventos": row[2],
                "eventos_correctivo": row[3],
                "eventos_det_noprg": row[4],
                "horas_perdidas": float(row[5]) if row[5] else 0,
                "horas_promedio_evento": float(row[6]) if row[6] else 0,
                "criticidad": "Alta" if row[3] > 50 else "Media" if row[3] > 20 else "Baja"
            })
        
        conn.close()
        
        return {
            "success": True,
            "year": year,
            "equipos_criticos": equipos_criticos,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error identificando equipos críticos: {str(e)}")