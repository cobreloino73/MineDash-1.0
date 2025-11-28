# -*- coding: utf-8 -*-
"""
Análisis de Utilización (UEBD) de equipos CAEX
Filtra vueltas manuales y calcula métricas clave
"""

import pandas as pd
import sqlite3
from datetime import datetime

def analizar_utilizacion_caex(fecha_inicio, fecha_fin, db_path='minedash.db'):
    """
    Analiza utilización (UEBD) de camiones CAEX en un periodo

    Args:
        fecha_inicio: str formato 'YYYY-MM-DD'
        fecha_fin: str formato 'YYYY-MM-DD'
        db_path: str path a la base de datos

    Returns:
        dict con resultados del análisis
    """
    conn = sqlite3.connect(db_path)

    # Query para obtener DM y UEBD por equipo
    query = """
    SELECT
        equipment_id,
        tipo,
        COUNT(*) as horas_totales,
        SUM(CASE WHEN tpodisponible > 0 THEN 1 ELSE 0 END) as horas_con_dm,
        SUM(CASE WHEN tpoefectivoreal > 0 THEN 1 ELSE 0 END) as horas_con_uebd,
        AVG(CASE WHEN tponominal > 0 THEN tpodisponible * 100.0 / tponominal ELSE NULL END) as dm_promedio,
        AVG(CASE WHEN tpodisponible > 0 THEN tpoefectivoreal * 100.0 / tpodisponible ELSE NULL END) as uebd_promedio,
        AVG(tponominal) as horas_nominales_promedio,
        AVG(tpodisponible) as horas_disponibles_promedio,
        AVG(tpoefectivoreal) as horas_efectivas_promedio
    FROM hexagon_by_kpi_hora2
    WHERE empresa = 'CODELCO'
      AND timestamp >= ?
      AND timestamp < ?
      AND tipo = 'Truck'
      AND tponominal > 0
    GROUP BY equipment_id, tipo
    HAVING COUNT(*) >= 100
    ORDER BY dm_promedio ASC
    """

    df = pd.read_sql_query(query, conn, params=[fecha_inicio, fecha_fin])

    # Filtrar NaN en UEBD
    df_valido = df[df['uebd_promedio'].notna()].copy()

    # Calcular estadísticas
    total_equipos = len(df)
    equipos_validos = len(df_valido)
    vueltas_manuales_pct = (total_equipos - equipos_validos) / total_equipos * 100 if total_equipos > 0 else 0

    # Top 10 con peor DM
    top_10_dm = df_valido.nsmallest(10, 'dm_promedio').to_dict('records')

    # Top 10 con peor UEBD
    top_10_uebd = df_valido.nsmallest(10, 'uebd_promedio').to_dict('records')

    # Promedios generales
    dm_promedio_flota = df_valido['dm_promedio'].mean()
    uebd_promedio_flota = df_valido['uebd_promedio'].mean()

    # Contar registros sin UEBD (vueltas manuales estimadas)
    query_manuales = """
    SELECT COUNT(*) as total_registros,
           SUM(CASE WHEN tpoefectivoreal = 0 OR tpoefectivoreal IS NULL THEN 1 ELSE 0 END) as registros_sin_uebd
    FROM hexagon_by_kpi_hora2
    WHERE empresa = 'CODELCO'
      AND timestamp >= ?
      AND timestamp < ?
      AND tipo = 'Truck'
      AND tponominal > 0
    """
    df_manuales = pd.read_sql_query(query_manuales, conn, params=[fecha_inicio, fecha_fin])

    total_reg = int(df_manuales['total_registros'].iloc[0])
    reg_sin_uebd = int(df_manuales['registros_sin_uebd'].iloc[0])
    pct_sin_uebd = (reg_sin_uebd / total_reg * 100) if total_reg > 0 else 0

    conn.close()

    resultado = {
        'success': True,
        'periodo': f"{fecha_inicio} a {fecha_fin}",
        'total_equipos': total_equipos,
        'equipos_validos': equipos_validos,
        'dm_promedio_flota': dm_promedio_flota,
        'uebd_promedio_flota': uebd_promedio_flota,
        'top_10_dm': top_10_dm,
        'top_10_uebd': top_10_uebd,
        'vueltas_manuales': {
            'total_registros': total_reg,
            'registros_sin_uebd': reg_sin_uebd,
            'porcentaje': pct_sin_uebd
        }
    }

    return resultado
