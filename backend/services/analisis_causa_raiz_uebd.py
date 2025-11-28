# -*- coding: utf-8 -*-
"""
Análisis de Causa Raíz de Baja Utilización (UEBD)
Identifica si el problema es operacional o de mantenimiento
"""

import pandas as pd
import sqlite3
from datetime import datetime

def analizar_causa_raiz_uebd(fecha_inicio, fecha_fin, equipo=None, db_path='minedash.db'):
    """
    Analiza causa raíz de baja UEBD por equipo

    Args:
        fecha_inicio: str formato 'YYYY-MM-DD'
        fecha_fin: str formato 'YYYY-MM-DD'
        equipo: str opcional, código del equipo (ej: 'CE112')
        db_path: str path a la base de datos

    Returns:
        dict con análisis de causa raíz
    """
    conn = sqlite3.connect(db_path)

    # PASO 1: Obtener DM y UEBD de equipos
    query_metricas = """
    SELECT
        equipment_id as equipo,
        AVG(CASE WHEN tponominal > 0 THEN tpodisponible * 100.0 / tponominal ELSE NULL END) as dm_promedio,
        AVG(CASE WHEN tpodisponible > 0 THEN tpoefectivoreal * 100.0 / tpodisponible ELSE NULL END) as uebd_promedio
    FROM hexagon_by_kpi_hora2
    WHERE empresa = 'CODELCO'
      AND timestamp >= ?
      AND timestamp < ?
      AND tipo = 'Truck'
      AND tponominal > 0
    """

    if equipo:
        query_metricas += f" AND equipment_id = '{equipo}'"

    query_metricas += """
    GROUP BY equipment_id
    HAVING COUNT(*) >= 100
      AND AVG(CASE WHEN tpodisponible > 0 THEN tpoefectivoreal * 100.0 / tpodisponible ELSE NULL END) IS NOT NULL
    ORDER BY uebd_promedio ASC
    """

    df_metricas = pd.read_sql_query(query_metricas, conn, params=[fecha_inicio, fecha_fin])

    resultados = []

    for _, row in df_metricas.iterrows():
        equipo_id = row['equipo']
        dm = row['dm_promedio']
        uebd = row['uebd_promedio']

        # PASO 2: Obtener estados del equipo
        query_estados = """
        SELECT
            categoria,
            estado,
            razon,
            SUM(horas) as horas_totales,
            COUNT(*) as frecuencia
        FROM hexagon_estados
        WHERE equipo = ?
          AND fecha >= ?
          AND fecha < ?
        GROUP BY categoria, estado, razon
        ORDER BY horas_totales DESC
        """

        df_estados = pd.read_sql_query(query_estados, conn, params=[equipo_id, fecha_inicio, fecha_fin])

        if df_estados.empty:
            continue

        # Calcular totales por categoría
        total_horas = df_estados['horas_totales'].sum()

        cat_efectivo = df_estados[df_estados['categoria'] == 'EFECTIVO']['horas_totales'].sum()
        cat_det_noprg = df_estados[df_estados['categoria'] == 'DET.NOPRG.']['horas_totales'].sum()
        cat_det_prg = df_estados[df_estados['categoria'] == 'DET.PROG.']['horas_totales'].sum()
        cat_mnt_correctiva = df_estados[df_estados['categoria'] == 'M. CORRECTIVA']['horas_totales'].sum()
        cat_mnt_programada = df_estados[df_estados['categoria'] == 'M. PROGRAMADA']['horas_totales'].sum()

        # Porcentajes
        pct_efectivo = (cat_efectivo / total_horas * 100) if total_horas > 0 else 0
        pct_det_noprg = (cat_det_noprg / total_horas * 100) if total_horas > 0 else 0
        pct_det_prg = (cat_det_prg / total_horas * 100) if total_horas > 0 else 0
        pct_mnt_correctiva = (cat_mnt_correctiva / total_horas * 100) if total_horas > 0 else 0
        pct_mnt_programada = (cat_mnt_programada / total_horas * 100) if total_horas > 0 else 0

        # CLASIFICACIÓN
        if dm >= 70 and uebd < 55:
            clasificacion = "PROBLEMA_OPERACIONAL"
            problema_principal = "Alta DM pero baja UEBD - Equipo disponible pero no utilizado"
        elif dm < 60 and uebd < 55:
            clasificacion = "PROBLEMA_MANTENIMIENTO"
            problema_principal = "Baja DM y baja UEBD - Fallas mecánicas recurrentes"
        elif dm >= 60 and uebd >= 55:
            clasificacion = "ACEPTABLE"
            problema_principal = "Rendimiento dentro de rangos aceptables"
        else:
            clasificacion = "PROBLEMA_MIXTO"
            problema_principal = "Problemas combinados de mantenimiento y operación"

        # Top 5 estados críticos
        top_estados = df_estados.head(5).to_dict('records')

        # Razones específicas más frecuentes
        sin_operador = df_estados[df_estados['razon'] == 'SIN OPERADOR']['horas_totales'].sum()
        falta_carguio = df_estados[df_estados['razon'] == 'FALTA EQUIPO CARGUIO']['horas_totales'].sum()
        imprevisto_mecanico = df_estados[df_estados['razon'] == 'IMPREVISTO MECANICO']['horas_totales'].sum()

        # RECOMENDACIONES
        recomendaciones = []

        if clasificacion == "PROBLEMA_OPERACIONAL":
            if pct_det_noprg > 20:
                recomendaciones.append(f"URGENTE: {pct_det_noprg:.1f}% en demoras no programadas")
            if sin_operador > 50:
                recomendaciones.append(f"Asignar operador permanente ({sin_operador:.1f} horas sin operador)")
            if falta_carguio > 20:
                recomendaciones.append("Mejorar coordinación con equipos de carguío")
            recomendaciones.append("Revisar asignación de frentes y planificación")

        elif clasificacion == "PROBLEMA_MANTENIMIENTO":
            if pct_mnt_correctiva > 40:
                recomendaciones.append(f"CRÍTICO: {pct_mnt_correctiva:.1f}% en mantenimiento correctivo")
            if imprevisto_mecanico > 200:
                recomendaciones.append(f"Análisis RCA de fallas ({imprevisto_mecanico:.1f} horas fuera de servicio)")
            recomendaciones.append("Aumentar mantenimiento preventivo")
            recomendaciones.append("Revisar plan de repuestos críticos")

        elif clasificacion == "PROBLEMA_MIXTO":
            recomendaciones.append("Atacar problemas de mantenimiento primero")
            recomendaciones.append("Luego optimizar asignación operacional")

        resultados.append({
            'equipo': equipo_id,
            'dm': dm,
            'uebd': uebd,
            'clasificacion': clasificacion,
            'problema_principal': problema_principal,
            'distribucion': {
                'efectivo': pct_efectivo,
                'det_noprg': pct_det_noprg,
                'det_prg': pct_det_prg,
                'mnt_correctiva': pct_mnt_correctiva,
                'mnt_programada': pct_mnt_programada
            },
            'top_estados': top_estados,
            'recomendaciones': recomendaciones
        })

    conn.close()

    # Resumen por clasificación
    df_result = pd.DataFrame(resultados)
    resumen_clasificacion = df_result['clasificacion'].value_counts().to_dict() if not df_result.empty else {}

    return {
        'success': True,
        'periodo': f"{fecha_inicio} a {fecha_fin}",
        'total_equipos': len(resultados),
        'resumen_clasificacion': resumen_clasificacion,
        'equipos': resultados
    }
