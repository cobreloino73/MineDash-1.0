# -*- coding: utf-8 -*-
"""
Análisis de GAVIOTA - Comparación Real vs Teórico
Usa la fórmula exacta de gaviota teórica calibrada para División Salvador

CAMBIOS v3:
- Plan del día DIVIDIDO entre turnos (45% turno A, 55% turno C)
- Horas mostradas como hora real (08:00, 09:00) no relativa (0, 1, 2)
- Función generar_grafico_gaviota() para gráfico matplotlib
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import sqlite3
import pandas as pd
from pathlib import Path


# ============================================================================
# DISTRIBUCIÓN DE PLAN ENTRE TURNOS
# ============================================================================
# Basado en análisis histórico de División Salvador
PCT_TURNO_A = 0.45  # 45% del plan diario para turno A (día) - incluye tronadura
PCT_TURNO_C = 0.55  # 55% del plan diario para turno C (noche) - mejor rendimiento nocturno


# ============================================================================
# FACTORES CALIBRADOS DE GAVIOTA TEÓRICA
# ============================================================================
# Representan el % relativo de producción en cada hora basado en patrones reales

FACTORES_TURNO_A = {
    # Turno A: 08:00-20:00
    '08': 0.85,   # Arranque lento
    '09': 1.10,   # Peak post-arranque
    '10': 1.15,   # Peak máximo mañana
    '11': 1.10,   # Mantiene
    '12': 0.75,   # Colación
    '13': 0.70,   # Post-colación lento
    '14': 0.35,   # TRONADURA - paralización estándar 14:00-15:00
    '15': 0.35,   # TRONADURA - paralización continúa (o 1.10 si no hay)
    '16': 1.15,   # Peak tarde post-tronadura
    '17': 1.10,   # Mantiene alto
    '18': 1.05,   # Comienza descenso
    '19': 0.85,   # Cierre turno
}

FACTORES_TURNO_C = {
    # Turno C: 20:00-08:00
    '20': 0.85,   # Arranque turno noche
    '21': 1.10,   # Peak post-arranque
    '22': 1.15,   # Peak máximo noche
    '23': 1.10,   # Mantiene
    '00': 0.75,   # COLACIÓN NOCTURNA
    '01': 0.70,   # Post-colación lento
    '02': 1.05,   # Recuperación
    '03': 1.00,   # Estable madrugada
    '04': 0.95,   # Leve descenso
    '05': 1.00,   # Recuperación pre-cierre
    '06': 1.05,   # Último peak
    '07': 0.85,   # Cierre turno
}


# ============================================================================
# PASO 1: OBTENER PLAN DEL DÍA
# ============================================================================

def obtener_plan_diario(fecha: str) -> Optional[float]:
    """
    Obtiene el plan diario desde plan mensual Excel.

    Args:
        fecha: '2025-02-28'
    Returns:
        plan_dia_ton: 328744 (por ejemplo)
    """
    from services.plan_reader import PlanReader

    fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
    mes = fecha_obj.month
    year = fecha_obj.year
    dia = fecha_obj.day

    # Usar ruta absoluta
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data" / "Planificacion"

    reader = PlanReader(data_dir=str(data_dir))
    plan_info = reader.get_plan_mensual(mes, year)

    if plan_info and 'plan_diario' in plan_info:
        # Buscar el día específico
        for dia_plan in plan_info['plan_diario']:
            if dia_plan['dia'] == dia:
                return dia_plan['tonelaje']

    return None


# ============================================================================
# PASO 2: VERIFICAR TRONADURA REAL
# ============================================================================

def verificar_tronadura_real(fecha: str, conn: sqlite3.Connection) -> bool:
    """
    Verifica si hubo tronadura real en los datos.

    Heurística: Busca caída abrupta de producción en franja 14:00-16:00

    Returns:
        bool: True si detectó tronadura
    """
    cursor = conn.cursor()

    # Obtener producción en franjas horarias
    cursor.execute("""
        SELECT
            strftime('%H', timestamp) as hora,
            SUM(material_tonnage) as ton_hora
        FROM hexagon_by_kpi_hora
        WHERE DATE(timestamp) = ?
          AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 8 AND 19
        GROUP BY hora
        ORDER BY hora
    """, (fecha,))

    rows = cursor.fetchall()
    if not rows:
        return False

    # Calcular promedio del turno A (excluyendo colación 12:00)
    tonelajes = [ton for hora, ton in rows if hora != '12']
    if not tonelajes:
        return False

    promedio = sum(tonelajes) / len(tonelajes)
    umbral_tronadura = promedio * 0.30  # Si cae < 30% del promedio

    # Buscar caídas en franja 14:00-16:00
    for hora, ton_hora in rows:
        if hora in ['14', '15', '16']:
            if ton_hora < umbral_tronadura:
                print(f"   [TRONADURA] Detectada en hora {hora}:00 (ton={ton_hora:,.0f} < umbral={umbral_tronadura:,.0f})")
                return True

    return False


# ============================================================================
# PASO 3: CALCULAR GAVIOTA TEÓRICA (CORREGIDO: PLAN DIVIDIDO POR TURNO)
# ============================================================================

def calcular_gaviota_teorica(fecha: str, turno: str, plan_turno_ton: float, conn: sqlite3.Connection) -> Dict:
    """
    Calcula la curva de gaviota teórica hora por hora.

    LÓGICA CORREGIDA:
    1. plan_turno_ton ya viene dividido (45% o 55% del plan diario)
    2. ton_por_unidad = plan_turno / suma_factores_turno
    3. ton_hora = ton_por_unidad × factor_hora

    Args:
        fecha: '2025-02-28'
        turno: 'A' o 'C'
        plan_turno_ton: Plan SOLO para este turno (ya dividido)
        conn: Conexión a BD

    Returns:
        dict con ton_teorica por hora
    """

    # Seleccionar factores según turno
    if turno == 'A':
        factores = FACTORES_TURNO_A.copy()
    else:
        factores = FACTORES_TURNO_C.copy()

    # Detectar si hubo tronadura real
    # NOTA: Por defecto asumimos tronadura (14:00-15:00 = 0.35)
    # Si NO hubo tronadura, restauramos valores normales
    if turno == 'A':
        tronadura_detectada = verificar_tronadura_real(fecha, conn)
        if not tronadura_detectada:
            # Sin tronadura: restaurar producción normal
            factores['14'] = 1.05  # Recuperación normal
            factores['15'] = 1.10  # Producción normal
            print(f"   [AJUSTE] Sin tronadura detectada - factores 14:00-15:00 restaurados a normal")
        else:
            print(f"   [AJUSTE] Tronadura confirmada - factores 14:00-15:00 en 0.35")

    # Calcular ton_por_unidad usando PLAN DEL TURNO (no del día completo)
    suma_factores = sum(factores.values())
    ton_por_unidad = plan_turno_ton / suma_factores

    print(f"   [TEÓRICA] Turno {turno}: Plan turno: {plan_turno_ton:,.0f} ton")
    print(f"   [TEÓRICA] Suma factores: {suma_factores:.2f}")
    print(f"   [TEÓRICA] Ton por unidad: {ton_por_unidad:,.0f}")

    # Calcular ton por hora
    gaviota_teorica = {}
    for hora, factor in factores.items():
        gaviota_teorica[hora] = {
            'ton_teorica': ton_por_unidad * factor,
            'factor': factor
        }

    return gaviota_teorica


# ============================================================================
# PASO 4: OBTENER DATOS REALES
# ============================================================================

def obtener_datos_reales(fecha: str, conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Obtiene datos reales de producción por hora desde Excel o BD.

    PRIORIDAD:
    1. Excel: data/Hexagon/by_KPI_hora.xlsx (datos horarios reales)
    2. Fallback: Base de datos

    Returns:
        DataFrame con columnas: turno, hora, toneladas
    """
    import os

    # PRIORIDAD 1: Leer desde Excel (datos horarios correctos)
    base_dir = Path(__file__).parent.parent
    excel_path = base_dir / "data" / "Hexagon" / "by_KPI_hora.xlsx"

    if excel_path.exists():
        try:
            df_excel = pd.read_excel(excel_path, sheet_name=0)
            df_excel['fecha'] = pd.to_datetime(df_excel['fecha'])

            # Filtrar por fecha
            df_filtered = df_excel[df_excel['fecha'] == fecha]

            if len(df_filtered) > 0:
                # Agrupar por turno y hora
                df = df_filtered.groupby(['turno', 'hora']).agg({
                    'tonelaje': 'sum'
                }).reset_index()
                df.columns = ['turno', 'hora', 'toneladas']
                df = df.sort_values(['turno', 'hora'])

                print(f"   [EXCEL] Datos obtenidos desde by_KPI_hora.xlsx")
                print(f"   [EXCEL] {len(df)} registros horarios")
                return df
        except Exception as e:
            print(f"   [WARN] Error al leer Excel, usando BD: {e}")

    # PRIORIDAD 2: Fallback a base de datos
    query = """
        SELECT
            turno,
            hora,
            SUM(toneladas) as toneladas
        FROM hexagon_by_kpi_hora
        WHERE timestamp LIKE ?
        GROUP BY turno, hora
        ORDER BY turno, hora
    """

    df = pd.read_sql_query(query, conn, params=(f"{fecha}%",))
    print(f"   [DB] Datos obtenidos desde base de datos")
    return df


# ============================================================================
# PASO 5: IDENTIFICAR PATRÓN
# ============================================================================

def identificar_patron_gaviota(resultados: List[Dict]) -> str:
    """
    Identifica el patrón de la gaviota real.

    Patrones posibles:
    - M INVERTIDA: Peak mañana + valle colación + peak tarde (ideal)
    - VALLE EXTENDIDO: Producción baja por períodos largos
    - PLANO: Producción constante sin variación
    - ERRÁTICO: Variación sin patrón claro
    """

    # Extraer tonelajes por hora del turno A
    ton_turno_a = [r['real'] for r in resultados if r['turno'] == 'A']

    if not ton_turno_a or len(ton_turno_a) < 6:
        return "DATOS INSUFICIENTES"

    # Detectar valle extendido (> 5 horas consecutivas con ton < 30% del promedio)
    promedio = sum(ton_turno_a) / len(ton_turno_a)
    umbral_bajo = promedio * 0.30

    horas_bajas_consecutivas = 0
    max_consecutivas = 0

    for ton in ton_turno_a:
        if ton < umbral_bajo:
            horas_bajas_consecutivas += 1
            max_consecutivas = max(max_consecutivas, horas_bajas_consecutivas)
        else:
            horas_bajas_consecutivas = 0

    if max_consecutivas >= 5:
        return "VALLE EXTENDIDO"

    # Detectar M invertida (picos en índices 1-3 y 8-10)
    if len(ton_turno_a) >= 10:
        peak_manana = max(ton_turno_a[1:4]) if len(ton_turno_a) > 3 else 0
        peak_tarde = max(ton_turno_a[8:11]) if len(ton_turno_a) > 10 else 0
        valle_colacion = ton_turno_a[4] if len(ton_turno_a) > 4 else 0

        if peak_manana > promedio * 1.2 and peak_tarde > promedio * 1.2 and valle_colacion < promedio * 0.8:
            return "M INVERTIDA - EFICIENTE"

    # Detectar plano
    if max(ton_turno_a) - min(ton_turno_a) < promedio * 0.3:
        return "PLANO"

    return "ERRATICO"


# ============================================================================
# PASO 6: GENERAR GRÁFICO MATPLOTLIB
# ============================================================================

def generar_grafico_gaviota(fecha: str, resultados: List[Dict], plan_dia: float) -> Optional[Dict]:
    """
    Genera gráfico INTERACTIVO con Plotly de gaviota con 3 curvas:
    - TA Real (azul) - Producción real Turno A
    - TC Real (magenta) - Producción real Turno C
    - Teórico (naranja punteado) - Curva teórica ideal

    Returns:
        Dict con:
        - plotly_json: str (JSON spec para renderizar con plotly.js en frontend)
        - html: str (HTML embebible con gráfico interactivo)
        O None si falla
    """
    try:
        import plotly.graph_objects as go

        # Separar por turno
        turno_a = [r for r in resultados if r['turno'] == 'A']
        turno_c = [r for r in resultados if r['turno'] == 'C']

        # Calcular totales
        total_real = sum(r['real'] for r in resultados)
        cumpl_dia = (total_real / plan_dia * 100) if plan_dia > 0 else 0

        # Colores según especificación
        COLOR_TA = '#2E86AB'     # Azul - Turno A
        COLOR_TC = '#A23B72'     # Magenta - Turno C
        COLOR_TEORICO = '#F18F01' # Naranja - Teórico

        # Crear figura única
        fig = go.Figure()

        # Horas del turno (0-11 interna, mostrar como hora real)
        horas_labels = list(range(12))  # 0, 1, 2, ..., 11

        # ===== CURVA TA REAL (Turno A - Día) =====
        if turno_a:
            # Ordenar por hora
            turno_a_sorted = sorted(turno_a, key=lambda x: x.get('hora', 0))
            real_a = [r['real'] for r in turno_a_sorted]
            cumpl_a_list = [r.get('cumplimiento', 0) for r in turno_a_sorted]
            horas_a_labels = [f"H{r.get('hora', i)}" for i, r in enumerate(turno_a_sorted)]

            total_a = sum(real_a)

            fig.add_trace(go.Scatter(
                x=horas_labels[:len(real_a)],
                y=real_a,
                mode='lines+markers',
                name=f'TA Real ({total_a:,.0f} ton)',
                line=dict(color=COLOR_TA, width=3),
                marker=dict(size=10, symbol='circle'),
                hovertemplate='<b>Turno A - Hora %{x}</b><br>Real: %{y:,.0f} ton<br>Cumpl: %{customdata:.1f}%<extra></extra>',
                customdata=cumpl_a_list
            ))

        # ===== CURVA TC REAL (Turno C - Noche) =====
        if turno_c:
            # Ordenar por hora
            turno_c_sorted = sorted(turno_c, key=lambda x: x.get('hora', 0))
            real_c = [r['real'] for r in turno_c_sorted]
            cumpl_c_list = [r.get('cumplimiento', 0) for r in turno_c_sorted]

            total_c = sum(real_c)

            fig.add_trace(go.Scatter(
                x=horas_labels[:len(real_c)],
                y=real_c,
                mode='lines+markers',
                name=f'TC Real ({total_c:,.0f} ton)',
                line=dict(color=COLOR_TC, width=3),
                marker=dict(size=10, symbol='diamond'),
                hovertemplate='<b>Turno C - Hora %{x}</b><br>Real: %{y:,.0f} ton<br>Cumpl: %{customdata:.1f}%<extra></extra>',
                customdata=cumpl_c_list
            ))

        # ===== CURVA TEÓRICA =====
        # Factores por hora para curva teórica (patrón gaviota ideal)
        FACTORES_HORA = {
            0: 0.07,   # Post-relevo
            1: 0.08,   # Ajuste
            2: 0.09,   # Operación media
            3: 0.10,   # Pico operación
            4: 0.10,   # Pico operación
            5: 0.08,   # Pre-colación
            6: 0.06,   # Colación
            7: 0.08,   # Post-colación
            8: 0.09,   # Operación tarde
            9: 0.10,   # Pico tarde
            10: 0.09,  # Cierre
            11: 0.06   # Pre-relevo
        }

        # Plan por turno (mitad del día para cada uno)
        plan_turno = plan_dia / 2.0

        teorica_vals = [plan_turno * FACTORES_HORA[h] for h in range(12)]
        total_teorico = sum(teorica_vals)

        fig.add_trace(go.Scatter(
            x=horas_labels,
            y=teorica_vals,
            mode='lines+markers',
            name=f'Teórico ({total_teorico:,.0f} ton)',
            line=dict(color=COLOR_TEORICO, width=2, dash='dash'),
            marker=dict(size=8, symbol='square'),
            hovertemplate='<b>Hora %{x}</b><br>Teórico: %{y:,.0f} ton<extra></extra>'
        ))

        # Layout
        fig.update_layout(
            title=dict(
                text=f'<b>ANÁLISIS GAVIOTA - {fecha}</b><br><sub>Cumplimiento Día: {cumpl_dia:.1f}% | Plan: {plan_dia:,.0f} ton | Real: {total_real:,.0f} ton</sub>',
                x=0.5,
                font=dict(size=18)
            ),
            height=550,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5,
                font=dict(size=12)
            ),
            hovermode='x unified',
            template='plotly_white',
            xaxis=dict(
                title='Hora del Turno',
                tickmode='array',
                tickvals=list(range(12)),
                ticktext=['H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10', 'H11'],
                gridcolor='rgba(0,0,0,0.1)'
            ),
            yaxis=dict(
                title='Toneladas',
                tickformat=',',
                gridcolor='rgba(0,0,0,0.1)'
            )
        )

        # Generar JSON para frontend (plotly.js)
        plotly_json = fig.to_json()

        # Generar HTML embebible
        html_content = fig.to_html(
            full_html=False,
            include_plotlyjs='cdn',
            config={
                'displayModeBar': True,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                'displaylogo': False,
                'responsive': True
            }
        )

        print(f"   [CHART] Gráfico interactivo Plotly generado")
        return {
            "plotly_json": plotly_json,
            "html": html_content,
            "type": "plotly"
        }

    except ImportError:
        print("   [WARN] Plotly no instalado, usando fallback matplotlib")
        return _generar_grafico_matplotlib_fallback(fecha, resultados, plan_dia)
    except Exception as e:
        print(f"   [ERROR] Error generando gráfico: {e}")
        import traceback
        traceback.print_exc()
        return None


def _generar_grafico_matplotlib_fallback(fecha: str, resultados: List[Dict], _plan_dia: float) -> Optional[Dict]:
    """Fallback a matplotlib si Plotly no está disponible."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import base64
        from io import BytesIO

        turno_a = [r for r in resultados if r['turno'] == 'A']
        turno_c = [r for r in resultados if r['turno'] == 'C']

        _, axes = plt.subplots(1, 2, figsize=(16, 6))

        for turno_data, ax, titulo in [
            (turno_a, axes[0], f'TURNO A - {fecha}'),
            (turno_c, axes[1], f'TURNO C - {fecha}')
        ]:
            if turno_data:
                horas = [f"{r['hora_absoluta']}:00" for r in turno_data]
                real = [r['real'] for r in turno_data]
                teorica = [r['teorica'] for r in turno_data]

                ax.plot(horas, real, 'o-', color='#2563eb', linewidth=2.5, label='Real')
                ax.plot(horas, teorica, 's--', color='#f59e0b', linewidth=2, label='Teórica')
                ax.fill_between(range(len(horas)), real, teorica, alpha=0.2, color='#93c5fd')
                ax.set_title(titulo, fontweight='bold')
                ax.set_xlabel('Hora')
                ax.set_ylabel('Toneladas')
                ax.legend()
                ax.grid(True, alpha=0.3)
                ax.set_xticks(range(len(horas)))
                ax.set_xticklabels(horas, rotation=45)

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        buffer.close()
        plt.close()

        return {
            "base64": f"data:image/png;base64,{img_base64}",
            "type": "image"
        }
    except Exception as e:
        print(f"   [ERROR] Fallback matplotlib falló: {e}")
        return None


# ============================================================================
# PASO 7: GENERAR INFORME
# ============================================================================

def generar_informe_gaviota(fecha: str, plan_dia: float, resultados: List[Dict], patron: str) -> str:
    """
    Genera informe markdown del análisis de gaviota.
    CORREGIDO: Usa hora absoluta (08:00, 09:00) en lugar de relativa (0, 1, 2)
    """

    # Calcular totales
    total_real = sum(r['real'] for r in resultados)
    cumplimiento_dia = (total_real / plan_dia * 100) if plan_dia > 0 else 0
    desviacion_dia = total_real - plan_dia

    # Calcular totales por turno
    real_turno_a = sum(r['real'] for r in resultados if r['turno'] == 'A')
    real_turno_c = sum(r['real'] for r in resultados if r['turno'] == 'C')
    plan_turno_a = plan_dia * PCT_TURNO_A
    plan_turno_c = plan_dia * PCT_TURNO_C
    cumpl_a = (real_turno_a / plan_turno_a * 100) if plan_turno_a > 0 else 0
    cumpl_c = (real_turno_c / plan_turno_c * 100) if plan_turno_c > 0 else 0

    informe = f"""# ANALISIS GAVIOTA - {fecha}

## RESUMEN DEL DIA

| Metrica | Plan | Real | Cumpl. |
|---------|------|------|--------|
| **Dia Completo** | {plan_dia:,.0f} ton | {total_real:,.0f} ton | {cumplimiento_dia:.1f}% |
| Turno A (Dia) | {plan_turno_a:,.0f} ton | {real_turno_a:,.0f} ton | {cumpl_a:.1f}% |
| Turno C (Noche) | {plan_turno_c:,.0f} ton | {real_turno_c:,.0f} ton | {cumpl_c:.1f}% |

**Desviacion del dia:** {desviacion_dia:+,.0f} ton

## PATRON IDENTIFICADO

**{patron}**

---

## COMPARACION HORARIA: REAL vs TEORICA

### TURNO A (08:00 - 20:00)

| Hora | Real (ton) | Teorica (ton) | Cumpl. | Desv. | Estado |
|------|------------|---------------|--------|-------|--------|
"""

    # Turno A
    for r in [r for r in resultados if r['turno'] == 'A']:
        estado = 'OK' if r['cumplimiento'] >= 95 else 'ALERTA' if r['cumplimiento'] >= 80 else 'CRITICO'
        hora_display = r.get('hora_absoluta', f"{r['hora']:02d}")
        informe += f"| {hora_display}:00 | {r['real']:,.0f} | {r['teorica']:,.0f} | {r['cumplimiento']:.1f}% | {r['desviacion']:+,.0f} | {estado} |\n"

    informe += """

### TURNO C (20:00 - 08:00)

| Hora | Real (ton) | Teorica (ton) | Cumpl. | Desv. | Estado |
|------|------------|---------------|--------|-------|--------|
"""

    # Turno C
    for r in [r for r in resultados if r['turno'] == 'C']:
        estado = 'OK' if r['cumplimiento'] >= 95 else 'ALERTA' if r['cumplimiento'] >= 80 else 'CRITICO'
        hora_display = r.get('hora_absoluta', f"{r['hora']:02d}")
        informe += f"| {hora_display}:00 | {r['real']:,.0f} | {r['teorica']:,.0f} | {r['cumplimiento']:.1f}% | {r['desviacion']:+,.0f} | {estado} |\n"

    # Diagnóstico
    horas_criticas = [r for r in resultados if r['cumplimiento'] < 80 and r['teorica'] > 0]
    horas_eficientes = [r for r in resultados if r['cumplimiento'] >= 100]

    informe += """

---

## DIAGNOSTICO

### FORTALEZAS

"""

    if horas_eficientes:
        informe += f"- **{len(horas_eficientes)} horas sobre el plan teorico**\n"
        top_3 = sorted(horas_eficientes, key=lambda x: x['cumplimiento'], reverse=True)[:3]
        for h in top_3:
            hora_display = h.get('hora_absoluta', f"{h['hora']:02d}")
            informe += f"  - Hora {hora_display}:00 ({h['turno']}) - {h['cumplimiento']:.1f}% ({h['real']:,.0f} ton)\n"
    else:
        informe += "- Ninguna hora supero el plan teorico\n"

    informe += """

### PROBLEMAS CRITICOS

"""

    if horas_criticas:
        informe += f"- **{len(horas_criticas)} horas criticas (< 80% cumplimiento)**\n"
        for h in sorted(horas_criticas, key=lambda x: x['cumplimiento'])[:5]:
            hora_display = h.get('hora_absoluta', f"{h['hora']:02d}")
            informe += f"  - Hora {hora_display}:00 ({h['turno']}) - {h['cumplimiento']:.1f}% (perdida: {-h['desviacion']:,.0f} ton)\n"

        perdida_total = sum(-h['desviacion'] for h in horas_criticas if h['desviacion'] < 0)
        informe += f"\n- **Perdida total estimada:** {perdida_total:,.0f} ton\n"
    else:
        informe += "- Ninguna hora critica detectada\n"

    # Recomendaciones
    informe += """

---

## RECOMENDACIONES

"""

    if patron == "VALLE EXTENDIDO":
        informe += """
1. **Investigar causa de detencion prolongada**
   - Revisar logs de sistemas
   - Validar si fue mantencion programada
   - Verificar incidentes de seguridad

2. **Implementar alertas tempranas**
   - Sistema de deteccion de valles > 3 horas
   - Notificacion automatica a supervisores

3. **Mejorar planificacion**
   - Coordinar mantenciones en horarios de menor impacto
   - Optimizar ventanas de tronadura
"""
    elif "EFICIENTE" in patron:
        informe += """
1. **Mantener patron actual** - El rendimiento es optimo
2. **Documentar mejores practicas** para replicar en otros turnos
3. **Reforzar disciplina operacional** en horas de peak
"""
    else:
        informe += """
1. Analizar causas de variabilidad horaria
2. Estandarizar procedimientos operacionales
3. Revisar asignaciones de equipos por hora
"""

    return informe


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def analizar_gaviota_completo(fecha: str) -> Dict:
    """
    Análisis COMPLETO de gaviota con curva teórica usando fórmula exacta.

    CORREGIDO v2:
    - Plan del día DIVIDIDO entre turnos (45% A, 55% C)
    - Horas mostradas como hora real (08:00) no relativa (0)
    - Genera gráfico matplotlib automáticamente

    Args:
        fecha: '2025-02-28'

    Returns:
        Dict con:
        - informe: str (markdown)
        - resultados: list
        - patron: str
        - plan_dia: float
        - total_real: float
        - chart_path: str (path al gráfico PNG)
    """

    print(f"[GAVIOTA] Iniciando analisis para {fecha}")

    # PASO 1: Obtener plan del día
    plan_dia = obtener_plan_diario(fecha)
    if not plan_dia:
        return {"error": f"No se encontro plan diario para {fecha}"}

    # NUEVO: Calcular plan por turno
    plan_turno_a = plan_dia * PCT_TURNO_A
    plan_turno_c = plan_dia * PCT_TURNO_C

    print(f"[GAVIOTA] Plan del dia: {plan_dia:,.0f} ton")
    print(f"[GAVIOTA] Plan Turno A (45%): {plan_turno_a:,.0f} ton")
    print(f"[GAVIOTA] Plan Turno C (55%): {plan_turno_c:,.0f} ton")

    # PASO 2: Conectar a BD
    db_path = Path(__file__).parent.parent / "minedash.db"
    conn = sqlite3.connect(str(db_path))

    try:
        # PASO 3: Obtener datos reales
        df = obtener_datos_reales(fecha, conn)

        if df.empty:
            conn.close()
            return {"error": f"No hay datos reales de produccion para {fecha}"}

        print(f"[GAVIOTA] Datos reales obtenidos: {len(df)} horas")

        # PASO 4: Calcular gaviota teórica para ambos turnos
        # CORREGIDO: Usar plan_turno en lugar de plan_dia
        teorica_a = calcular_gaviota_teorica(fecha, 'A', plan_turno_a, conn)
        teorica_c = calcular_gaviota_teorica(fecha, 'C', plan_turno_c, conn)

        # PASO 5: Comparar hora por hora
        resultados = []
        for _, row in df.iterrows():
            hora_relativa = int(row['hora'])  # 0-11
            turno = row['turno']
            real = row['toneladas']

            # Convertir hora relativa (0-11) a hora absoluta ('08'-'19' o '20'-'07')
            if turno == 'A':
                hora_absoluta = f"{(hora_relativa + 8):02d}"  # 0 -> '08', 1 -> '09', ..., 11 -> '19'
            else:  # Turno C
                hora_absoluta = f"{(hora_relativa + 20) % 24:02d}"  # 0 -> '20', 1 -> '21', ..., 11 -> '07'

            # Obtener teórica según turno
            teorica_dict = teorica_a if turno == 'A' else teorica_c
            teorica_info = teorica_dict.get(hora_absoluta, {'ton_teorica': 0})
            teorica = teorica_info['ton_teorica']

            cumplimiento = (real / teorica * 100) if teorica > 0 else 0
            desviacion = real - teorica

            resultados.append({
                'hora': hora_relativa,
                'hora_absoluta': hora_absoluta,  # NUEVO: Guardar hora absoluta para display
                'turno': turno,
                'real': real,
                'teorica': teorica,
                'cumplimiento': cumplimiento,
                'desviacion': desviacion
            })

        # PASO 6: Identificar patrón
        patron = identificar_patron_gaviota(resultados)
        print(f"[GAVIOTA] Patron identificado: {patron}")

        # PASO 7: Generar gráfico matplotlib
        chart_result = generar_grafico_gaviota(fecha, resultados, plan_dia)

        # PASO 8: Generar informe
        informe = generar_informe_gaviota(fecha, plan_dia, resultados, patron)

        total_real = sum(r['real'] for r in resultados)

        return {
            "informe": informe,
            "resultados": resultados,
            "patron": patron,
            "plan_dia": plan_dia,
            "plan_turno_a": plan_turno_a,
            "plan_turno_c": plan_turno_c,
            "total_real": total_real,
            "cumplimiento": (total_real / plan_dia * 100) if plan_dia > 0 else 0,
            # Gráfico interactivo (Plotly) o estático (matplotlib fallback)
            "chart": chart_result  # Contiene: plotly_json, html, type="plotly" o base64, type="image"
        }

    finally:
        conn.close()
