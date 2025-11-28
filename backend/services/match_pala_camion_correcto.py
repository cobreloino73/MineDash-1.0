# -*- coding: utf-8 -*-
"""
MineDash AI v2.0 - Análisis Match Pala-Camión CORRECTO
Genera scatter plot con 744 puntos (31 días × 24 horas)
Autor: AIMINE
Fecha: 2025-01-16
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from pathlib import Path
import io
import base64

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

DB_PATH = "minedash.db"  # Ajustar según ubicación

# DM Plan comprometida (promedio mensual del plan)
# Valores solo para equipos Codelco (Fase 1, sin tercerizados TE)
DM_PLAN_PALAS = 80.0      # % - Solo equipos Codelco
DM_PLAN_CAMIONES = 73.7   # % - Solo equipos Codelco

# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def analizar_match_pala_camion(
    fecha_inicio: str,
    fecha_fin: str,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Analiza el match pala-camión para un período específico.
    
    Args:
        fecha_inicio: Fecha inicio en formato 'YYYY-MM-DD'
        fecha_fin: Fecha fin en formato 'YYYY-MM-DD' 
        db_path: Ruta a la base de datos SQLite
        
    Returns:
        Dict con resultados del análisis incluyendo:
        - datos_puntos: Lista de puntos [dm_palas, dm_camiones] por hora
        - cuadrantes: % de tiempo en cada cuadrante
        - grafico_base64: Imagen del scatter plot en base64
        - estadisticas: Métricas agregadas
        - responsable_principal: Cuello de botella identificado
    """
    
    conn = sqlite3.connect(db_path)

    try:
        # =================================================================
        # FIX: Si fecha_inicio == fecha_fin, agregar 1 día al fin
        # Esto permite análisis de un solo día
        # =================================================================
        if fecha_inicio == fecha_fin:
            from datetime import datetime, timedelta
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d') + timedelta(days=1)
            fecha_fin = fecha_fin_dt.strftime('%Y-%m-%d')
            print(f"[MATCH] Ajustando fecha_fin a {fecha_fin} para incluir día completo")

        # =================================================================
        # PASO 1: Extraer datos hora por hora
        # =================================================================

        # QUERY ACTUALIZADO: Usa hexagon_by_kpi_hora (tiene datos hasta agosto 2025)
        # Filtra equipos Codelco por prefijo (ya que no tiene columna empresa)
        query = """
        SELECT
            DATE(timestamp) as fecha,
            hora,
            turno,
            tipo,
            AVG(disponible * 100.0 / NULLIF(nominal, 0)) as dm_pct
        FROM hexagon_by_kpi_hora
        WHERE timestamp >= ?
          AND timestamp < ?
          AND tipo IN ('Shovel', 'Truck')
          AND nominal > 0
          AND (
              -- Filtrar solo equipos Codelco (excluir tercerizados TE)
              equipment_id NOT LIKE 'TE%'
          )
        GROUP BY DATE(timestamp), hora, turno, tipo
        ORDER BY fecha, turno, hora, tipo
        """
        
        df = pd.read_sql_query(query, conn, params=[fecha_inicio, fecha_fin])
        
        if df.empty:
            return {
                "success": False,
                "error": f"No hay datos disponibles para el período {fecha_inicio} a {fecha_fin}",
                "total_horas": 0
            }
        
        # =================================================================
        # PASO 2: Pivotar para tener DM de palas y camiones por hora
        # =================================================================
        
        df_pivot = df.pivot_table(
            index=['fecha', 'hora', 'turno'],
            columns='tipo',
            values='dm_pct',
            aggfunc='mean'
        ).reset_index()

        print(f">> Filas después del pivot: {len(df_pivot)}")
        print(f">> Columnas: {df_pivot.columns.tolist()}")
        if len(df_pivot) > 0:
            print(f">> Primera fila: {df_pivot.iloc[0].to_dict()}")

        # Renombrar columnas
        df_pivot.columns.name = None
        df_pivot.rename(columns={'Shovel': 'dm_palas', 'Truck': 'dm_camiones'}, inplace=True)

        # Rellenar NaN con 0 en lugar de eliminar filas
        df_pivot = df_pivot.fillna(0)
        
        total_horas = len(df_pivot)
        
        if total_horas == 0:
            return {
                "success": False,
                "error": "No hay horas con datos simultáneos de palas y camiones",
                "total_horas": 0
            }
        
        # =================================================================
        # PASO 3: Clasificar cada hora en cuadrantes
        # =================================================================
        
        def clasificar_cuadrante(row):
            """Clasifica una hora en uno de los 4 cuadrantes"""
            palas_ok = row['dm_palas'] >= DM_PLAN_PALAS
            camiones_ok = row['dm_camiones'] >= DM_PLAN_CAMIONES
            
            if palas_ok and camiones_ok:
                return 'OPTIMO'
            elif palas_ok and not camiones_ok:
                return 'DM_CAMIONES'
            elif not palas_ok and camiones_ok:
                return 'DM_PALAS'
            else:
                return 'DM_AMBOS'
        
        df_pivot['cuadrante'] = df_pivot.apply(clasificar_cuadrante, axis=1)
        
        # =================================================================
        # PASO 4: Calcular estadísticas por cuadrante
        # =================================================================
        
        cuadrantes = df_pivot['cuadrante'].value_counts()
        cuadrantes_pct = (cuadrantes / total_horas * 100).round(2)
        
        cuadrantes_dict = {
            'OPTIMO': {
                'horas': int(cuadrantes.get('OPTIMO', 0)),
                'porcentaje': float(cuadrantes_pct.get('OPTIMO', 0)),
                'descripcion': 'Ambos tipos disponibles según plan'
            },
            'DM_CAMIONES': {
                'horas': int(cuadrantes.get('DM_CAMIONES', 0)),
                'porcentaje': float(cuadrantes_pct.get('DM_CAMIONES', 0)),
                'descripcion': 'Problema de disponibilidad de camiones'
            },
            'DM_PALAS': {
                'horas': int(cuadrantes.get('DM_PALAS', 0)),
                'porcentaje': float(cuadrantes_pct.get('DM_PALAS', 0)),
                'descripcion': 'Problema de disponibilidad de palas'
            },
            'DM_AMBOS': {
                'horas': int(cuadrantes.get('DM_AMBOS', 0)),
                'porcentaje': float(cuadrantes_pct.get('DM_AMBOS', 0)),
                'descripcion': 'Ambos tipos por debajo del plan'
            }
        }
        
        # =================================================================
        # PASO 5: Identificar responsable principal
        # =================================================================
        
        responsable = identificar_responsable(cuadrantes_dict)
        
        # =================================================================
        # PASO 6: Generar gráfico scatter plot
        # =================================================================
        
        grafico_base64 = generar_scatter_plot(
            df_pivot,
            DM_PLAN_PALAS,
            DM_PLAN_CAMIONES,
            fecha_inicio,
            fecha_fin
        )
        
        # =================================================================
        # PASO 7: Estadísticas generales
        # =================================================================
        
        estadisticas = {
            'dm_palas_promedio': round(df_pivot['dm_palas'].mean(), 2),
            'dm_camiones_promedio': round(df_pivot['dm_camiones'].mean(), 2),
            'dm_palas_min': round(df_pivot['dm_palas'].min(), 2),
            'dm_palas_max': round(df_pivot['dm_palas'].max(), 2),
            'dm_camiones_min': round(df_pivot['dm_camiones'].min(), 2),
            'dm_camiones_max': round(df_pivot['dm_camiones'].max(), 2),
            'match_score': round(cuadrantes_pct.get('OPTIMO', 0), 2)
        }
        
        # ===================================================================
        # ANALISIS ADICIONAL 1: COMPARACION CON PLAN MENSUAL
        # ===================================================================
        try:
            from datetime import datetime as dt_import
            from services.plan_reader import get_plan_tonelaje, get_plan_disponibilidades

            fecha_obj = dt_import.strptime(fecha_inicio, '%Y-%m-%d')
            year = fecha_obj.year
            mes = fecha_obj.month

            meses_nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
            mes_nombre = meses_nombres[mes - 1]

            # PASO 1: Obtener PLAN MENSUAL usando PlanReader (SOLO EQUIPOS CODELCO)
            print(f"   📖 Obteniendo plan mensual desde Excel usando PlanReader...")
            plan_info = get_plan_tonelaje(mes, year)

            plan_mensual = None
            requiere_confirmacion_fases = False
            fases_info = ""

            if plan_info:
                plan_mensual = plan_info.get('tonelaje')
                requiere_confirmacion_fases = plan_info.get('requiere_confirmacion', False)
                fases_codelco = plan_info.get('fases_codelco', [])
                fases_contratista = plan_info.get('fases_contratista', [])

                if fases_codelco:
                    fases_info = f" ({', '.join(fases_codelco)} - Codelco)"
                    if fases_contratista:
                        fases_info += f" [Excluye: {', '.join(fases_contratista)} - Contratista]"

                print(f"   ✅ Plan Mensual obtenido: {plan_mensual:,.0f} ton{fases_info}")
            else:
                print(f"   ⚠️  No se encontró plan mensual para {mes_nombre} {year}")

            # PASO 1.2: Obtener DISPONIBILIDADES PLANIFICADAS
            disponibilidades_plan = get_plan_disponibilidades(mes, year)
            dm_plan_palas_excel = disponibilidades_plan.get('palas')
            dm_plan_camiones_excel = disponibilidades_plan.get('camiones')

            if dm_plan_palas_excel:
                print(f"   📊 DM Plan Palas (Excel): {dm_plan_palas_excel:.1f}%")
            if dm_plan_camiones_excel:
                print(f"   📊 DM Plan Camiones (Excel): {dm_plan_camiones_excel:.1f}%")

            # PASO 2: Obtener TONELAJE REAL del mes (solo equipos Codelco)
            query_real = """
            SELECT SUM(material_tonnage) as tonelaje_real
            FROM hexagon_by_detail_dumps_2025
            WHERE DATE(timestamp) >= ?
              AND DATE(timestamp) < ?
              AND empresa = 'CODELCO'
            """
            df_real = pd.read_sql_query(query_real, conn, params=[fecha_inicio, fecha_fin])
            tonelaje_real = float(df_real['tonelaje_real'].iloc[0]) if not df_real.empty and df_real['tonelaje_real'].iloc[0] else 0

            # PASO 3: Calcular brecha y cumplimiento
            if plan_mensual and plan_mensual > 0:
                brecha = tonelaje_real - plan_mensual
                cumplimiento_pct = (tonelaje_real / plan_mensual * 100)
            else:
                brecha = None
                cumplimiento_pct = None

            analisis_tonelaje = {
                'tonelaje_real': tonelaje_real,
                'plan_mensual': plan_mensual,
                'brecha': brecha,
                'cumplimiento_pct': cumplimiento_pct,
                'mes_nombre': mes_nombre.capitalize(),
                'dm_plan_palas': dm_plan_palas_excel,
                'dm_plan_camiones': dm_plan_camiones_excel,
                'fuente': 'Excel (PlanReader)',
                'requiere_confirmacion_fases': requiere_confirmacion_fases,
                'fases_info': fases_info
            }

            print(f"   📦 Tonelaje Real: {tonelaje_real:,.0f} ton")
            if cumplimiento_pct:
                print(f"   📈 Cumplimiento: {cumplimiento_pct:.1f}%")

        except Exception as e:
            print(f"⚠️  Error comparando con plan mensual: {e}")
            import traceback
            traceback.print_exc()
            analisis_tonelaje = None

        # =================================================================
        # ANALISIS ADICIONAL 2: TOP EQUIPOS PROBLEMATICOS
        # =================================================================
        try:
            query_equipos = """
            SELECT equipment_id as equipo,
                tipo,
                COUNT(*) as horas_operadas,
                AVG(disponible * 100.0 / NULLIF(nominal, 0)) as dm_promedio,
                SUM(CASE WHEN (disponible * 100.0 / NULLIF(nominal, 0)) < 85 THEN 1 ELSE 0 END) as horas_bajo_meta
            FROM hexagon_by_kpi_hora
            WHERE timestamp >= ?
              AND timestamp < ?
              AND tipo IN ('Shovel', 'Truck')
              AND nominal > 0
              AND equipment_id NOT LIKE 'TE%'
            GROUP BY equipment_id, tipo
            HAVING COUNT(*) >= 10
            ORDER BY dm_promedio ASC
            LIMIT 15
            """

            df_equipos = pd.read_sql_query(query_equipos, conn, params=[fecha_inicio, fecha_fin])

            top_problematicos = []
            # LIMITAR A TOP 10 para evitar rate limits
            for _, row in df_equipos.head(10).iterrows():
                top_problematicos.append({
                    'equipo': row['equipo'],
                    'tipo': row['tipo'],
                    'dm_promedio': float(row['dm_promedio']),
                    'horas_operadas': int(row['horas_operadas']),
                    'horas_bajo_meta': int(row['horas_bajo_meta']),
                    'pct_bajo_meta': (float(row['horas_bajo_meta']) / float(row['horas_operadas']) * 100)
                })
        except Exception as e:
            print(f"Error calculando top equipos: {e}")
            top_problematicos = []

        # =================================================================
        # ANALISIS ADICIONAL 3: PATRON TEMPORAL
        # =================================================================
        try:
            query_patron = """
            SELECT
                turno,
                AVG(disponible * 100.0 / NULLIF(nominal, 0)) as dm_promedio
            FROM hexagon_by_kpi_hora
            WHERE timestamp >= ?
              AND timestamp < ?
              AND tipo = 'Truck'
              AND nominal > 0
              AND equipment_id NOT LIKE 'TE%'
            GROUP BY turno
            ORDER BY turno
            """

            df_patron = pd.read_sql_query(query_patron, conn, params=[fecha_inicio, fecha_fin])

            patron_turno = {}
            for _, row in df_patron.iterrows():
                patron_turno[row['turno']] = float(row['dm_promedio'])
        except Exception as e:
            print(f"Error calculando patron temporal: {e}")
            patron_turno = {}

        # =================================================================
        # RETORNO FINAL - SIN FINAL_ANSWER para que el LLM use system prompt
        # =================================================================

        # ================================================================
        # GENERAR FINAL_ANSWER PROFESIONAL DIRECTAMENTE
        # Esto evita que el LLM consuma 85k tokens procesando los datos
        # ================================================================
        print("[MATCH] USANDO CODIGO NUEVO CON FINAL_ANSWER v3.0")

        lineas = []
        lineas.append("📊 **ANÁLISIS MATCH PALA-CAMIÓN**")
        lineas.append("")
        lineas.append("═══════════════════════════════════════════════════════════════")
        lineas.append("")
        lineas.append(f"## 📅 Período Analizado")
        lineas.append("")
        lineas.append(f"**Fechas:** {fecha_inicio} a {fecha_fin}")
        lineas.append(f"**Horas totales:** {total_horas} hrs")
        lineas.append("")
        lineas.append("---")
        lineas.append("")
        lineas.append("## 📈 Disponibilidad Mecánica Promedio")
        lineas.append("")
        lineas.append("| Equipo | DM Real | DM Plan | Diferencia | Estado |")
        lineas.append("|--------|---------|---------|------------|--------|")

        dm_palas_prom = estadisticas.get('dm_palas_promedio', 0)
        dm_camiones_prom = estadisticas.get('dm_camiones_promedio', 0)

        diff_palas = dm_palas_prom - DM_PLAN_PALAS
        diff_camiones = dm_camiones_prom - DM_PLAN_CAMIONES

        estado_palas = "✅ Sobre plan" if diff_palas >= 0 else "❌ Bajo plan"
        estado_camiones = "✅ Sobre plan" if diff_camiones >= 0 else "❌ Bajo plan"

        lineas.append(f"| 🔧 Palas | {dm_palas_prom:.1f}% | {DM_PLAN_PALAS:.1f}% | {diff_palas:+.1f}% | {estado_palas} |")
        lineas.append(f"| 🚛 Camiones | {dm_camiones_prom:.1f}% | {DM_PLAN_CAMIONES:.1f}% | {diff_camiones:+.1f}% | {estado_camiones} |")
        lineas.append("")
        lineas.append("---")
        lineas.append("")
        lineas.append("## 🎯 Distribución de Cuadrantes")
        lineas.append("")
        lineas.append("| Cuadrante | Horas | % Total | Descripción |")
        lineas.append("|-----------|-------|---------|-------------|")

        for cuad_nombre, cuad_data in cuadrantes_dict.items():
            if isinstance(cuad_data, dict) and 'horas' in cuad_data:
                emoji = "✅" if cuad_nombre == "OPTIMO" else ("🔴" if "AMBOS" in cuad_nombre else "🟡")
                lineas.append(f"| {emoji} {cuad_nombre} | {cuad_data['horas']} | {cuad_data['porcentaje']:.1f}% | {cuad_data.get('descripcion', '')} |")

        lineas.append("")
        lineas.append("---")
        lineas.append("")
        lineas.append("## 🎯 Responsable Principal")
        lineas.append("")
        lineas.append(f"**Área:** {responsable.get('area', 'MANTENIMIENTO')}")
        lineas.append(f"**Equipos afectados:** {responsable.get('equipo', 'N/A')}")

        # Asegurar que porcentaje_impacto sea un número
        porcentaje_impacto = responsable.get('porcentaje_impacto', 0)
        if isinstance(porcentaje_impacto, (int, float)):
            lineas.append(f"**Impacto:** {porcentaje_impacto:.1f}% de las horas")
        else:
            lineas.append(f"**Impacto:** {porcentaje_impacto}")

        lineas.append(f"**Causa raíz:** {responsable.get('descripcion', 'N/A')}")
        lineas.append("")
        lineas.append(f"**Recomendación:** {responsable.get('recomendacion', 'N/A')}")
        lineas.append("")

        # Agregar Top 5 equipos problemáticos si el responsable es CAMIONES
        equipo_tipo = responsable.get('equipo', '')
        if top_problematicos and equipo_tipo in ['CAMIONES', 'AMBOS']:
            # Filtrar solo camiones si el problema es de camiones
            equipos_filtrados = [e for e in top_problematicos if e['tipo'] == 'Truck'][:5]

            if equipos_filtrados:
                lineas.append("### 🚛 Top 5 Camiones con Mayor Problema")
                lineas.append("")
                lineas.append("| # | Equipo | DM Promedio | % Horas Bajo Meta |")
                lineas.append("|---|--------|-------------|-------------------|")

                for idx, equipo in enumerate(equipos_filtrados, 1):
                    emoji_estado = "🔴" if equipo['dm_promedio'] < 50 else "🟡"
                    lineas.append(f"| {idx} | {emoji_estado} {equipo['equipo']} | {equipo['dm_promedio']:.1f}% | {equipo['pct_bajo_meta']:.1f}% |")

                lineas.append("")

        elif top_problematicos and equipo_tipo == 'PALAS':
            # Filtrar solo palas si el problema es de palas
            equipos_filtrados = [e for e in top_problematicos if e['tipo'] == 'Shovel'][:5]

            if equipos_filtrados:
                lineas.append("### 🔧 Top 5 Palas con Mayor Problema")
                lineas.append("")
                lineas.append("| # | Equipo | DM Promedio | % Horas Bajo Meta |")
                lineas.append("|---|--------|-------------|-------------------|")

                for idx, equipo in enumerate(equipos_filtrados, 1):
                    emoji_estado = "🔴" if equipo['dm_promedio'] < 50 else "🟡"
                    lineas.append(f"| {idx} | {emoji_estado} {equipo['equipo']} | {equipo['dm_promedio']:.1f}% | {equipo['pct_bajo_meta']:.1f}% |")

                lineas.append("")

        lineas.append("═══════════════════════════════════════════════════════════════")

        final_answer = "\n".join(lineas)

        return {
            'success': True,
            'FINAL_ANSWER': final_answer,
            'grafico_base64': grafico_base64
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }
    
    finally:
        conn.close()


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def identificar_responsable(cuadrantes: Dict) -> Dict[str, Any]:
    """
    Identifica el cuello de botella principal basado en distribución de cuadrantes.
    """
    
    dm_camiones = cuadrantes['DM_CAMIONES']['porcentaje']
    dm_palas = cuadrantes['DM_PALAS']['porcentaje']
    dm_ambos = cuadrantes['DM_AMBOS']['porcentaje']
    optimo = cuadrantes['OPTIMO']['porcentaje']
    
    # Cuello de botella es el problema que más tiempo genera
    problemas = [
        ('MANTENIMIENTO_CAMIONES', dm_camiones),
        ('MANTENIMIENTO_PALAS', dm_palas),
        ('MANTENIMIENTO_AMBOS', dm_ambos)
    ]
    
    problemas_sorted = sorted(problemas, key=lambda x: x[1], reverse=True)
    principal = problemas_sorted[0]
    
    if principal[1] < 10:
        # Si el problema principal es menor al 10%, el sistema está operando bien
        return {
            'area': 'OPERACIONES',
            'porcentaje_impacto': round(optimo, 2),
            'descripcion': 'Sistema operando cerca del óptimo',
            'recomendacion': 'Mantener estándares actuales'
        }
    
    descripciones = {
        'MANTENIMIENTO_CAMIONES': {
            'area': 'MANTENIMIENTO',
            'equipo': 'CAMIONES',
            'descripcion': 'Baja disponibilidad de camiones limita producción',
            'recomendacion': 'Priorizar mantención preventiva de flota de camiones'
        },
        'MANTENIMIENTO_PALAS': {
            'area': 'MANTENIMIENTO',
            'equipo': 'PALAS',
            'descripcion': 'Baja disponibilidad de palas limita producción',
            'recomendacion': 'Priorizar mantención preventiva de flota de palas'
        },
        'MANTENIMIENTO_AMBOS': {
            'area': 'MANTENIMIENTO',
            'equipo': 'AMBOS',
            'descripcion': 'Baja disponibilidad de ambos tipos de equipos',
            'recomendacion': 'Revisar estrategia integral de mantenimiento'
        }
    }
    
    detalle = descripciones[principal[0]]
    detalle['porcentaje_impacto'] = round(principal[1], 2)
    
    return detalle


def generar_scatter_plot(
    df: pd.DataFrame,
    dm_plan_palas: float,
    dm_plan_camiones: float,
    fecha_inicio: str,
    fecha_fin: str
) -> str:
    """
    Genera scatter plot del match pala-camión.
    Retorna imagen en base64 para mostrar en el chat.
    """
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Backend sin GUI
        import matplotlib.pyplot as plt
        
        # Configuración de estilo profesional con fondo blanco
        fig, ax = plt.subplots(figsize=(14, 10), facecolor='white')
        ax.set_facecolor('white')
        
        # =============================================================
        # PASO 1: Pintar regiones de cuadrantes
        # =============================================================
        
        # Cuadrante ÓPTIMO (superior derecho) - VERDE INTENSO
        ax.fill_between(
            [dm_plan_camiones, 100],
            dm_plan_palas,
            100,
            alpha=0.3,
            color='#4CAF50',  # Verde intenso profesional
            label='ÓPTIMO'
        )

        # Cuadrante DM CAMIONES (superior izquierdo) - ROJO INTENSO
        ax.fill_between(
            [0, dm_plan_camiones],
            dm_plan_palas,
            100,
            alpha=0.3,
            color='#F44336',  # Rojo intenso profesional
            label='Problema DM Camiones'
        )

        # Cuadrante DM PALAS (inferior derecho) - NARANJA INTENSO
        ax.fill_between(
            [dm_plan_camiones, 100],
            0,
            dm_plan_palas,
            alpha=0.3,
            color='#FF9800',  # Naranja intenso profesional
            label='Problema DM Palas'
        )

        # Cuadrante DM AMBOS (inferior izquierdo) - PÚRPURA INTENSO
        ax.fill_between(
            [0, dm_plan_camiones],
            0,
            dm_plan_palas,
            alpha=0.3,
            color='#9C27B0',  # Púrpura intenso profesional
            label='Problema DM Ambos'
        )
        
        # =============================================================
        # PASO 2: Dibujar puntos (cada hora = 1 punto)
        # =============================================================
        
        # Colorear puntos según cuadrante con COLORES PROFESIONALES INTENSOS
        colors = []
        for _, row in df.iterrows():
            if row['dm_palas'] >= dm_plan_palas and row['dm_camiones'] >= dm_plan_camiones:
                colors.append('#4CAF50')  # Verde intenso - ÓPTIMO
            elif row['dm_palas'] >= dm_plan_palas and row['dm_camiones'] < dm_plan_camiones:
                colors.append('#F44336')  # Rojo intenso - Problema Camiones
            elif row['dm_palas'] < dm_plan_palas and row['dm_camiones'] >= dm_plan_camiones:
                colors.append('#FF9800')  # Naranja intenso - Problema Palas
            else:
                colors.append('#9C27B0')  # Púrpura intenso - Problema Ambos

        ax.scatter(
            df['dm_camiones'],
            df['dm_palas'],
            c=colors,
            s=80,  # Puntos más grandes para visibilidad
            alpha=0.6,
            edgecolors='black',
            linewidths=0.5
        )
        
        # =============================================================
        # PASO 3: Líneas de referencia del plan
        # =============================================================
        
        # Línea vertical: DM Plan Camiones (ROJO INTENSO)
        ax.axvline(
            x=dm_plan_camiones,
            color='#D32F2F',  # Rojo oscuro profesional
            linestyle='--',
            linewidth=2.5,
            alpha=0.8,
            label=f'Plan Camiones: {dm_plan_camiones}%'
        )

        # Línea horizontal: DM Plan Palas (AZUL INTENSO)
        ax.axhline(
            y=dm_plan_palas,
            color='#1976D2',  # Azul oscuro profesional
            linestyle='--',
            linewidth=2.5,
            alpha=0.8,
            label=f'Plan Palas: {dm_plan_palas}%'
        )
        
        # =============================================================
        # PASO 4: Etiquetas de texto en cuadrantes
        # =============================================================

        # Etiqueta ÓPTIMO (superior derecho)
        ax.text(95, 95, 'ÓPTIMO', fontsize=14, ha='right', va='top', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#4CAF50', alpha=0.3, edgecolor='black'))

        # Etiqueta PROBLEMA DM CAMIONES (superior izquierdo)
        ax.text(5, 95, 'PROBLEMA:\nDM CAMIONES', fontsize=12, ha='left', va='top', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#F44336', alpha=0.3, edgecolor='black'))

        # Etiqueta PROBLEMA DM PALAS (inferior derecho)
        ax.text(95, 5, 'PROBLEMA:\nDM PALAS', fontsize=12, ha='right', va='bottom', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#FF9800', alpha=0.3, edgecolor='black'))

        # Etiqueta PROBLEMA AMBOS (inferior izquierdo)
        ax.text(5, 5, 'PROBLEMA:\nAMBOS EQUIPOS', fontsize=12, ha='left', va='bottom', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#9C27B0', alpha=0.3, edgecolor='black'))

        # =============================================================
        # PASO 5: Configurar ejes y títulos
        # =============================================================

        ax.set_xlabel('Disponibilidad Mecánica Camiones (%)', fontsize=14, fontweight='bold')
        ax.set_ylabel('Disponibilidad Mecánica Palas (%)', fontsize=14, fontweight='bold')
        ax.set_title(
            f'Match Pala-Camión - {fecha_inicio} a {fecha_fin}\n'
            f'Análisis de {len(df)} horas',
            fontsize=16,
            fontweight='bold',
            pad=20
        )

        # Limites de ejes
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)

        # Grid profesional
        ax.grid(True, alpha=0.3, linestyle=':', color='gray')

        # Leyenda mejorada
        ax.legend(loc='upper left', fontsize=11, framealpha=0.95, edgecolor='black')
        
        # Ajustar layout
        plt.tight_layout()
        
        # =============================================================
        # PASO 5: Convertir a base64
        # =============================================================
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close()

        # Guardar también como archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"match_pala_camion_{timestamp}.png"
        output_path = Path("outputs/charts") / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        buffer.seek(0)
        with open(output_path, 'wb') as f:
            f.write(buffer.read())

        print(f"OK Gráfico guardado: {output_path}")

        return image_base64
        
    except Exception as e:
        print(f"Error generando gráfico: {e}")
        return None


# ============================================================================
# FUNCIÓN PARA USO EN EL AGENTE
# ============================================================================

def ejecutar_analisis_match_pala_camion(
    fecha_inicio: str,
    fecha_fin: str
) -> str:
    """
    Función wrapper para llamar desde el agente.
    Retorna string formateado para mostrar al usuario.
    """
    
    resultado = analizar_match_pala_camion(fecha_inicio, fecha_fin)
    
    if not resultado['success']:
        return f"❌ Error: {resultado.get('error', 'Error desconocido')}"
    
    # Formatear respuesta
    output = []
    output.append("═" * 70)
    output.append("🎯 ANÁLISIS MATCH PALA-CAMIÓN")
    output.append("═" * 70)
    output.append("")
    
    # Período
    periodo = resultado['periodo']
    output.append(f"📅 PERÍODO: {periodo['fecha_inicio']} a {periodo['fecha_fin']}")
    output.append(f"📊 HORAS ANALIZADAS: {periodo['total_horas_analizadas']}")
    output.append("")
    
    # DM Promedio
    stats = resultado['estadisticas']
    output.append("📈 DISPONIBILIDAD PROMEDIO:")
    output.append(f"   • Palas:    {stats['dm_palas_promedio']:.1f}% (Plan: {resultado['dm_plan']['palas']:.1f}%)")
    output.append(f"   • Camiones: {stats['dm_camiones_promedio']:.1f}% (Plan: {resultado['dm_plan']['camiones']:.1f}%)")
    output.append(f"   • Match Score: {stats['match_score']:.1f}%")
    output.append("")
    
    # Cuadrantes
    output.append("🎯 DISTRIBUCIÓN DE CUADRANTES:")
    cuadrantes = resultado['cuadrantes']
    for nombre, datos in cuadrantes.items():
        icono = "OK" if nombre == "OPTIMO" else "🔴"
        output.append(f"   {icono} {nombre}: {datos['porcentaje']:.1f}% ({datos['horas']} hrs)")
        output.append(f"      → {datos['descripcion']}")
    output.append("")
    
    # Responsable principal
    resp = resultado['responsable_principal']
    output.append("🎯 RESPONSABLE PRINCIPAL:")
    output.append(f"   • Área: {resp['area']}")
    if 'equipo' in resp:
        output.append(f"   • Equipos: {resp['equipo']}")
    output.append(f"   • Impacto: {resp['porcentaje_impacto']:.1f}%")
    output.append(f"   • {resp['descripcion']}")
    output.append(f"   • Recomendación: {resp['recomendacion']}")
    output.append("")
    
    # Gráfico
    if resultado['grafico_base64']:
        output.append("📊 GRÁFICO SCATTER PLOT:")
        output.append(f"   Ver gráfico adjunto (imagen base64)")
        output.append("")
    
    output.append("═" * 70)
    
    return "\n".join(output)


# ============================================================================
# PARA TESTING
# ============================================================================

if __name__ == "__main__":
    # Test con enero 2025
    resultado = analizar_match_pala_camion(
        fecha_inicio="2025-01-01",
        fecha_fin="2025-02-01"
    )
    
    if resultado['success']:
        print(f"OK Análisis exitoso")
        print(f"Total horas: {resultado['periodo']['total_horas_analizadas']}")
        print(f"Match Score: {resultado['estadisticas']['match_score']:.1f}%")
        print(f"Responsable: {resultado['responsable_principal']['area']}")
    else:
        print(f"❌ Error: {resultado['error']}")
