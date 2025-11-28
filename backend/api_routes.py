"""
API Routes para Dashboard e Insights - MineDash AI v2
VERSIÓN OPTIMIZADA con query de gaviota corregida

OPTIMIZACIÓN APLICADA:
- Gaviota usa rangos de timestamp (3-5s) en vez de DATE() (90s+)
- Aprovecha índice idx_by_timestamp existente

TABLAS DISPONIBLES:
- hexagon_by_equipment_times_2023
- hexagon_by_equipment_times_2024_p1
- hexagon_by_equipment_times_2024_p2
- hexagon_by_equipment_times_2025

COLUMNAS DE HORAS:
- total (nominales)
- efectivo (productivas)
- m_correctiva, m_programada
- det_noprg, det_prg
- waiting, queued, reserva

CÁLCULOS ASARCO:
DM = ((total - m_correctiva) / total) × 100
UEBD = (efectivo / (total - m_correctiva - m_programada)) × 100
UEBA = (efectivo / total) × 100
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta  # ✅ AGREGADO PARA OPTIMIZACIÓN
import sqlite3
from pathlib import Path

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS DE DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/api/dashboard")
async def get_dashboard(
    area: str = Query("todas", description="Área operacional"),
    year: int = Query(2024, description="Año de datos")
):
    """
    Endpoint principal del dashboard
    Retorna KPIs, equipos y métricas operacionales CON DATOS REALES
    """
    try:
        conn = sqlite3.connect("minedash.db")
        cursor = conn.cursor()
        
        # ======== KPIs PRINCIPALES ========
        
        # Producción total desde hexagon_by_detail_dumps_*
        cursor.execute("""
            SELECT 
                SUM(material_tonnage) as total_toneladas,
                COUNT(DISTINCT truck_equipment_type) as tipos_equipos,
                COUNT(*) as total_dumps
            FROM (
                SELECT material_tonnage, truck_equipment_type, timestamp
                FROM hexagon_by_detail_dumps_2023
                WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT material_tonnage, truck_equipment_type, timestamp
                FROM hexagon_by_detail_dumps_2024
                WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT material_tonnage, truck_equipment_type, timestamp
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%Y', timestamp) = ?
            )
        """, (str(year), str(year), str(year)))
        
        prod_data = cursor.fetchone()
        total_toneladas = prod_data[0] or 0
        tipos_equipos = prod_data[1] or 0
        total_dumps = prod_data[2] or 0
        
        # Días operativos
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT DATE(timestamp)) as dias_operativos
            FROM (
                SELECT timestamp FROM hexagon_by_detail_dumps_2023 WHERE strftime('%Y', timestamp) = ?
                UNION
                SELECT timestamp FROM hexagon_by_detail_dumps_2024 WHERE strftime('%Y', timestamp) = ?
                UNION
                SELECT timestamp FROM hexagon_by_detail_dumps_2025 WHERE strftime('%Y', timestamp) = ?
            )
        """, (str(year), str(year), str(year)))
        
        dias_operativos = cursor.fetchone()[0] or 1
        
        # ✅ DM y UEBD CALCULADOS desde horas reales
        cursor.execute("""
            WITH equipment_times_all AS (
                SELECT timestamp, equipment_type, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2023
                WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT timestamp, equipment_type, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2024_p1
                WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT timestamp, equipment_type, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2024_p2
                WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT timestamp, equipment_type, total, efectivo, m_correctiva, m_programada
                FROM hexagon_by_equipment_times_2025
                WHERE strftime('%Y', timestamp) = ?
            )
            SELECT 
                -- DM: (Total - M.Correctiva) / Total × 100
                ROUND(AVG(
                    CASE WHEN total > 0 
                    THEN ((total - COALESCE(m_correctiva, 0)) / total) * 100 
                    ELSE NULL END
                ), 1) as dm_promedio,
                
                -- UEBD: Efectivo / (Total - M.Correctiva - M.Programada) × 100
                ROUND(AVG(
                    CASE WHEN (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0)) > 0
                    THEN (efectivo / (total - COALESCE(m_correctiva, 0) - COALESCE(m_programada, 0))) * 100
                    ELSE NULL END
                ), 1) as uebd_promedio,
                
                -- UEBA: Efectivo / Total × 100
                ROUND(AVG(
                    CASE WHEN total > 0
                    THEN (efectivo / total) * 100
                    ELSE NULL END
                ), 1) as ueba_promedio,
                
                COUNT(DISTINCT equipment_type) as equipos_evaluados
            FROM equipment_times_all
            WHERE total > 0
        """, (str(year), str(year), str(year), str(year)))
        
        dm_data = cursor.fetchone()
        
        # Si hay datos reales, usarlos
        if dm_data and dm_data[0]:
            disponibilidad_actual = dm_data[0]
            utilizacion_actual = dm_data[1] or 0
            ueba_actual = dm_data[2] or 0
            equipos_evaluados = dm_data[3] or 0
            dm_fuente = "Calculado desde horas reales (ASARCO)"
            dm_contexto = f"Promedio de {equipos_evaluados} tipos de equipos en {year}"
        else:
            disponibilidad_actual = None
            utilizacion_actual = None
            ueba_actual = None
            equipos_evaluados = 0
            dm_fuente = "No disponible"
            dm_contexto = "⚠️ Sin datos de horas para este período"
        
        # Operadores activos
        cursor.execute("""
            SELECT COUNT(DISTINCT truck_operator_first_name || ' ' || truck_operator_last_name)
            FROM (
                SELECT truck_operator_first_name, truck_operator_last_name, timestamp
                FROM hexagon_by_detail_dumps_2023
                WHERE strftime('%Y', timestamp) = ?
                UNION
                SELECT truck_operator_first_name, truck_operator_last_name, timestamp
                FROM hexagon_by_detail_dumps_2024
                WHERE strftime('%Y', timestamp) = ?
                UNION
                SELECT truck_operator_first_name, truck_operator_last_name, timestamp
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%Y', timestamp) = ?
            )
            WHERE truck_operator_first_name IS NOT NULL
            AND truck_operator_last_name IS NOT NULL
        """, (str(year), str(year), str(year)))
        
        operadores_activos = cursor.fetchone()[0] or 0
        
        # ======== TENDENCIAS (comparar con mes anterior) ========
        
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', timestamp) as mes,
                SUM(material_tonnage) as toneladas
            FROM (
                SELECT material_tonnage, timestamp FROM hexagon_by_detail_dumps_2023
                UNION ALL
                SELECT material_tonnage, timestamp FROM hexagon_by_detail_dumps_2024
                UNION ALL
                SELECT material_tonnage, timestamp FROM hexagon_by_detail_dumps_2025
            )
            GROUP BY mes
            ORDER BY mes DESC
            LIMIT 2
        """)
        
        meses_data = cursor.fetchall()
        cambio_produccion = 0
        if len(meses_data) >= 2:
            mes_actual = meses_data[0][1] or 0
            mes_anterior = meses_data[1][1] or 1
            cambio_produccion = ((mes_actual - mes_anterior) / mes_anterior * 100) if mes_anterior > 0 else 0
        
        # ======== TOP EQUIPOS POR TIPO ========
        
        cursor.execute("""
            SELECT
                truck_equipment_type,
                SUM(material_tonnage) as toneladas,
                COUNT(*) as dumps,
                ROUND(AVG(material_tonnage), 2) as ton_por_dump,
                COUNT(DISTINCT truck_operator_first_name || ' ' || truck_operator_last_name) as operadores
            FROM (
                SELECT truck_equipment_type, material_tonnage, truck_operator_first_name, truck_operator_last_name
                FROM hexagon_by_detail_dumps_2023 WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT truck_equipment_type, material_tonnage, truck_operator_first_name, truck_operator_last_name
                FROM hexagon_by_detail_dumps_2024 WHERE strftime('%Y', timestamp) = ?
                UNION ALL
                SELECT truck_equipment_type, material_tonnage, truck_operator_first_name, truck_operator_last_name
                FROM hexagon_by_detail_dumps_2025 WHERE strftime('%Y', timestamp) = ?
            )
            WHERE truck_equipment_type IS NOT NULL
            GROUP BY truck_equipment_type
            ORDER BY toneladas DESC
            LIMIT 10
        """, (str(year), str(year), str(year)))
        
        equipos = []
        for row in cursor.fetchall():
            equipos.append({
                "tipo": row[0],
                "toneladas": float(row[1]) if row[1] else 0,
                "dumps": row[2],
                "ton_por_dump": float(row[3]) if row[3] else 0,
                "operadores": row[4]
            })
        
        # ✅ ALERTAS BASADAS EN DATOS REALES
        alertas = []
        
        # Alerta si DM < 85%
        if disponibilidad_actual is not None and disponibilidad_actual < 85:
            perdida_por_dm = (85 - disponibilidad_actual) * 200
            alertas.append({
                "tipo": "critical",
                "titulo": "Disponibilidad Mecánica bajo target",
                "mensaje": f"DM actual: {disponibilidad_actual}% vs target 85%. Pérdida estimada: {perdida_por_dm:.0f} ton/día",
                "area": "Todas",
                "fuente": "Calculado desde horas ASARCO",
                "fecha": datetime.now().isoformat()
            })
        
        # Alerta si UEBD < 75%
        if utilizacion_actual is not None and utilizacion_actual < 75:
            alertas.append({
                "tipo": "warning",
                "titulo": "Utilización Efectiva bajo target",
                "mensaje": f"UEBD actual: {utilizacion_actual}% (Target: 75%)",
                "area": "Todas",
                "fuente": "Calculado desde horas ASARCO",
                "fecha": datetime.now().isoformat()
            })
        
        # Si NO hay datos de DM/UEBD
        if disponibilidad_actual is None:
            alertas.append({
                "tipo": "info",
                "titulo": "Métricas de disponibilidad no disponibles",
                "mensaje": "No se encontraron datos de horas para calcular DM/UEBD en este período.",
                "area": "Todas",
                "fuente": "Sistema",
                "fecha": datetime.now().isoformat()
            })
        
        conn.close()
        
        # ======== CONSTRUIR RESPUESTA ========
        
        response = {
            "kpis": {
                "produccion": {
                    "value": round(total_toneladas, 0),
                    "unit": "ton",
                    "change": round(cambio_produccion, 1),
                    "trend": "up" if cambio_produccion > 0 else "down" if cambio_produccion < 0 else "neutral",
                    "target": 0,
                    "status": "ok" if cambio_produccion >= 0 else "warning",
                    "contexto": f"Total {year} - {dias_operativos} días operativos - {total_dumps:,} viajes",
                    "fuente": "hexagon_by_detail_dumps"
                },
                "disponibilidad": {
                    "value": disponibilidad_actual,
                    "unit": "%",
                    "change": round(disponibilidad_actual - 85, 1) if disponibilidad_actual else None,
                    "trend": "up" if disponibilidad_actual and disponibilidad_actual >= 85 else "down" if disponibilidad_actual else "neutral",
                    "target": 85.0,
                    "status": "ok" if disponibilidad_actual and disponibilidad_actual >= 85 else "warning" if disponibilidad_actual else "unknown",
                    "contexto": dm_contexto,
                    "fuente": dm_fuente
                },
                "utilizacion": {
                    "value": utilizacion_actual,
                    "unit": "%",
                    "change": round(utilizacion_actual - 75, 1) if utilizacion_actual else None,
                    "trend": "up" if utilizacion_actual and utilizacion_actual >= 75 else "down" if utilizacion_actual else "neutral",
                    "target": 75.0,
                    "status": "ok" if utilizacion_actual and utilizacion_actual >= 75 else "warning" if utilizacion_actual else "unknown",
                    "contexto": f"UEBD promedio {year}" if utilizacion_actual else "⚠️ No disponible",
                    "fuente": dm_fuente
                },
                "operadores": {
                    "value": operadores_activos,
                    "unit": "personas",
                    "change": 0,
                    "trend": "neutral",
                    "target": 0,
                    "status": "ok",
                    "contexto": f"Operadores que realizaron viajes en {year}",
                    "fuente": "hexagon_by_detail_dumps"
                },
                "equipos_activos": {
                    "value": tipos_equipos,
                    "unit": "tipos",
                    "change": 0,
                    "trend": "neutral",
                    "target": 0,
                    "status": "ok",
                    "contexto": f"Tipos de equipos operados en {year}",
                    "fuente": "hexagon_by_detail_dumps"
                }
            },
            "equipment": equipos,
            "alertas": alertas,
            "timestamp": datetime.now().isoformat(),
            "area": area,
            "year": year,
            "periodo": f"{year}"
        }
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos de dashboard: {str(e)}")


@router.get("/api/dashboard/kpis")
async def get_dashboard_kpis(year: int = 2024):
    """Solo KPIs sin equipos (más rápido)"""
    full_data = await get_dashboard(area="todas", year=year)
    return {
        "kpis": full_data["kpis"],
        "timestamp": full_data["timestamp"],
        "alertas": full_data.get("alertas", [])
    }


# ═══════════════════════════════════════════════════════════════
# ✅ ENDPOINT METADATA - ÚLTIMO MES/AÑO CON DATOS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/data/metadata")
async def get_data_metadata():
    """
    Retorna información sobre los datos cargados:
    - Último mes/año con datos de producción
    - Lista de meses disponibles por año
    - Timestamp de última actualización

    Usado por Dashboard e Insights para auto-detectar el período actual.
    """
    conn = None
    try:
        conn = sqlite3.connect("minedash.db")
        cursor = conn.cursor()

        # Buscar último mes/año con datos en production
        cursor.execute("""
            SELECT
                strftime('%Y', timestamp) as year,
                strftime('%m', timestamp) as month,
                MAX(timestamp) as last_timestamp
            FROM (
                SELECT timestamp FROM hexagon_by_detail_dumps_2023 WHERE timestamp IS NOT NULL
                UNION ALL
                SELECT timestamp FROM hexagon_by_detail_dumps_2024 WHERE timestamp IS NOT NULL
                UNION ALL
                SELECT timestamp FROM hexagon_by_detail_dumps_2025 WHERE timestamp IS NOT NULL
            )
            GROUP BY year, month
            ORDER BY year DESC, month DESC
            LIMIT 1
        """)

        row = cursor.fetchone()

        if row:
            last_year = int(row[0])
            last_month = int(row[1])
            last_timestamp = row[2]
        else:
            # Fallback a fecha actual
            last_year = datetime.now().year
            last_month = datetime.now().month
            last_timestamp = datetime.now().isoformat()

        # Obtener lista de meses disponibles por año
        cursor.execute("""
            SELECT DISTINCT
                strftime('%Y', timestamp) as year,
                strftime('%m', timestamp) as month
            FROM (
                SELECT timestamp FROM hexagon_by_detail_dumps_2023 WHERE timestamp IS NOT NULL
                UNION ALL
                SELECT timestamp FROM hexagon_by_detail_dumps_2024 WHERE timestamp IS NOT NULL
                UNION ALL
                SELECT timestamp FROM hexagon_by_detail_dumps_2025 WHERE timestamp IS NOT NULL
            )
            ORDER BY year DESC, month DESC
        """)

        available_periods = {}
        for yr, mo in cursor.fetchall():
            year_int = int(yr)
            month_int = int(mo)
            if year_int not in available_periods:
                available_periods[year_int] = []
            available_periods[year_int].append(month_int)

        # Ordenar meses dentro de cada año
        for yr in available_periods:
            available_periods[yr] = sorted(available_periods[yr])

        conn.close()

        return {
            "success": True,
            "last_loaded": {
                "year": last_year,
                "month": last_month,
                "timestamp": last_timestamp
            },
            "available_periods": available_periods,
            "available_years": sorted(available_periods.keys(), reverse=True)
        }

    except Exception as e:
        if conn:
            conn.close()
        import traceback
        traceback.print_exc()
        # Fallback en caso de error
        return {
            "success": False,
            "error": str(e),
            "last_loaded": {
                "year": 2025,
                "month": 1,
                "timestamp": None
            },
            "available_periods": {2025: [1]},
            "available_years": [2025]
        }


# ═══════════════════════════════════════════════════════════════
# ✅ ENDPOINT GAVIOTA - VERSIÓN OPTIMIZADA
# ═══════════════════════════════════════════════════════════════

@router.get("/api/dashboard/gaviota")
async def get_gaviota(
    fecha: Optional[str] = Query(None, description="Fecha específica YYYY-MM-DD"),
    turno: Optional[str] = Query(None, description="Turno A, B o C")
):
    """
    Análisis de Gaviota: Producción hora por hora
    ✅ Optimizado para usar índice en timestamp
    ✅ Rellena horas faltantes (0-11)
    ✅ Detecta y corrige outliers usando IQR
    """
    conn = None
    try:
        conn = sqlite3.connect("minedash.db")
        cursor = conn.cursor()

        # 1) fecha por defecto = última con datos
        if not fecha:
            cursor.execute("""
                SELECT DATE(timestamp) AS fecha
                FROM hexagon_by_kpi_hora
                WHERE timestamp IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            fecha = row[0] if row else "2024-07-15"

        # 2) rangos de timestamp
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
        fecha_inicio = fecha_obj.strftime("%Y-%m-%d 00:00:00")
        fecha_fin = (fecha_obj + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

        # normalizar y validar turno
        if turno:
            turno_norm = turno.upper()
            if turno_norm not in ["A", "B", "C"]:
                raise HTTPException(status_code=400, detail=f"Turno inválido: {turno}. Use A, B o C")
        else:
            turno_norm = None

        # 3) query optimizada
        # NOTA: hora en DB es relativa al turno (0-11)
        #   - Turno A: hora 0 = 08:00, hora 11 = 19:00
        #   - Turno C: hora 0 = 20:00, hora 11 = 07:00
        query = """
            SELECT 
                hora,
                SUM(material_tonnage) AS tonelaje,
                COUNT(*) AS registros
            FROM hexagon_by_kpi_hora
            WHERE timestamp >= ?
              AND timestamp < ?
        """
        params = [fecha_inicio, fecha_fin]

        if turno_norm:
            query += " AND turno = ?"
            params.append(turno_norm)

        query += " GROUP BY hora ORDER BY hora"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # 4) pasar a lista base
        data_raw = [
            {
                "hora": int(r[0]) if r[0] is not None else 0,
                "tonelaje": float(r[1]) if r[1] else 0.0,
                "registros": r[2]
            }
            for r in rows
        ]

        # 5) rellenar horas 0..11 (turno de 12 pasos)
        horas_dict = {d["hora"]: d for d in data_raw}
        gaviota_data = []
        for h in range(12):
            if h in horas_dict:
                gaviota_data.append(horas_dict[h])
            else:
                gaviota_data.append({
                    "hora": h,
                    "tonelaje": 0.0,
                    "registros": 0,
                    "corregido": True
                })

        # 5a) Detección de outliers usando IQR
        outliers = []
        tonelajes = [d["tonelaje"] for d in gaviota_data if d["tonelaje"] > 0]
        if len(tonelajes) > 4:
            import numpy as np
            q1 = np.percentile(tonelajes, 25)
            q3 = np.percentile(tonelajes, 75)
            iqr = q3 - q1
            limite_superior = q3 + 1.5 * iqr
            limite_inferior = q1 - 1.5 * iqr
            
            for i, d in enumerate(gaviota_data):
                tonelaje_original = d["tonelaje"]
                if tonelaje_original > 0 and (tonelaje_original > limite_superior or tonelaje_original < limite_inferior):
                    mediana = np.median(tonelajes)
                    outliers.append({
                        "hora": d["hora"],
                        "valor_original": tonelaje_original,
                        "motivo": "fuera de rango IQR"
                    })
                    gaviota_data[i]["tonelaje"] = mediana
                    gaviota_data[i]["corregido"] = True

        # 6) análisis de patrón
        analisis = None
        if len(gaviota_data) >= 8:
            datos_hora = {d["hora"]: d["tonelaje"] for d in gaviota_data}

            primera_hora = datos_hora.get(0, 0)
            segunda_hora = datos_hora.get(1, 0)
            valle_colacion = (
                datos_hora.get(4, 0) +
                datos_hora.get(5, 0) +
                datos_hora.get(6, 0) +
                datos_hora.get(7, 0)
            ) / 4
            penultima_hora = datos_hora.get(10, 0)
            ultima_hora = datos_hora.get(11, 0)

            horas_turno = [datos_hora.get(h, 0) for h in range(12)]
            promedio = sum(horas_turno) / 12 if horas_turno else 0

            arranque_fuerte = (primera_hora + segunda_hora) / 2 > promedio * 0.8 if promedio else False
            termino_fuerte = (penultima_hora + ultima_hora) / 2 > promedio * 0.8 if promedio else False
            valle_controlado = valle_colacion < promedio * 0.8 if promedio else False

            if arranque_fuerte and termino_fuerte and valle_controlado:
                tipo = "Perfecta (M invertida)"
                perdida_dia = 0
                estado = "excelente"
                descripcion = "Arranque y término fuertes, valle de colación controlado. Patrón ideal."
            elif not arranque_fuerte and not termino_fuerte:
                tipo = "U extendida (problemas en puntas)"
                perdida_dia = int(promedio * 0.3 * 12) if promedio else 0
                estado = "critico"
                descripcion = "Arranque tardío y término anticipado. Se pierde producción al inicio y fin del turno."
            elif not arranque_fuerte:
                tipo = "Arranque lento"
                perdida_dia = int(promedio * 0.2 * 12) if promedio else 0
                estado = "regular"
                descripcion = "Demora en alcanzar ritmo productivo. Revisar cambio de turno y disponibilidad de equipos."
            elif not termino_fuerte:
                tipo = "Término anticipado"
                perdida_dia = int(promedio * 0.2 * 12) if promedio else 0
                estado = "regular"
                descripcion = "Caída de producción hacia el final. Revisar fatiga operacional y coordinación de cierre."
            elif not valle_controlado:
                tipo = "Sin valle de colación"
                perdida_dia = 0
                estado = "bueno"
                descripcion = "Producción constante sin optimizar colación."
            else:
                tipo = "Normal con variaciones"
                perdida_dia = int(promedio * 0.1 * 12) if promedio else 0
                estado = "regular"
                descripcion = "Patrón aceptable con oportunidades de mejora."

            analisis = {
                "tipo_patron": tipo,
                "estado": estado,
                "descripcion": descripcion,
                "metricas": {
                    "hora_0_arranque": round(primera_hora, 1),
                    "hora_1": round(segunda_hora, 1),
                    "horas_4_7_colacion": round(valle_colacion, 1),
                    "hora_10": round(penultima_hora, 1),
                    "hora_11_termino": round(ultima_hora, 1),
                    "promedio_turno": round(promedio, 1),
                    "total_turno": round(sum(horas_turno), 1),
                },
                "perdida_estimada_ton": perdida_dia,
                "horas_analizadas": len(horas_turno),
                "outliers_corregidos": len(outliers),
                "outliers": outliers
            }

        return {
            "success": True,
            "fecha": fecha,
            "turno": turno_norm if turno_norm else "Todos",
            "datos_horarios": gaviota_data,
            "analisis": analisis,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando gaviota: {str(e)}")
    finally:
        if conn:
            conn.close()


