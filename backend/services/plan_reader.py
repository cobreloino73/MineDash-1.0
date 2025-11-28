"""
Plan Reader - Lee planes mensuales directamente de Excel
No requiere ingesta previa a SQL
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional
import re

class PlanReader:
    """Lee planes mensuales directamente de archivos Excel"""

    def __init__(self, data_dir: str = "data/Planificacion"):
        self.data_dir = Path(data_dir)
        self._cache = {}

    def get_plan_mensual(self, mes: int, year: int = 2025) -> Optional[Dict]:
        """
        Obtiene el plan mensual de un mes específico

        Args:
            mes: Número de mes (1-12)
            year: Año (default 2025)

        Returns:
            Dict con datos del plan o None si no existe
        """
        # Nombre del mes en español
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        mes_nombre = meses.get(mes)
        if not mes_nombre:
            return None

        # Buscar archivo del plan mensual
        # Patrón: "01_Plan Mensual Enero Mina RI 2025 (7).xlsx"
        pattern = f"*Plan Mensual {mes_nombre}*{year}*.xlsx"

        archivos = list(self.data_dir.glob(pattern))

        if not archivos:
            print(f"[WARN] No se encontro plan mensual para {mes_nombre} {year}")
            return None

        archivo = archivos[0]  # Tomar el primero si hay múltiples
        print(f"[PLAN] Leyendo plan: {archivo.name}")

        try:
            return self._extract_plan_data(archivo, mes, year, mes_nombre)
        except Exception as e:
            print(f"[ERROR] Error leyendo plan: {e}")
            return None

    def _extract_plan_data(self, filepath: Path, mes: int, year: int, mes_nombre: str) -> Dict:
        """Extrae datos clave del plan mensual"""

        excel_file = pd.ExcelFile(filepath)

        result = {
            'mes': mes,
            'year': year,
            'mes_nombre': mes_nombre,
            'archivo': filepath.name,
            'movimiento_total': None,
            'extraccion_total': None,
            'disponibilidad_palas': None,
            'disponibilidad_camiones': None,
            'hojas_disponibles': excel_file.sheet_names,
            'fases_codelco': [],
            'fases_contratista': [],
            'requiere_confirmacion_usuario': False
        }

        # =====================================================================
        # DETECCIÓN DE FASES: Codelco vs Contratista
        # =====================================================================
        # Lógica según instrucciones del usuario:
        # - Si existe "CARGUIO Y TRANSPORTE FASE1" y NO existe "CARGUIO Y TRANSPORTE FASE2" ni "FASE3"
        #   entonces F1 es Codelco
        # - Si existen ambas hojas, F2/F3 son contratista (Tepsac)
        # - Solo queremos medir KPIs de equipos Codelco (no contratistas)

        # Buscar hojas con nombres variados
        tiene_fase1 = ('CARGUIO Y TRANSPORTE FASE1' in excel_file.sheet_names or
                       'C&T FASE1' in excel_file.sheet_names)
        tiene_fase2 = ('CARGUIO Y TRANSPORTE FASE2' in excel_file.sheet_names or
                       'C&T FASE2' in excel_file.sheet_names)
        tiene_fase3 = ('CARGUIO Y TRANSPORTE FASE3' in excel_file.sheet_names or
                       'C&T FASE3' in excel_file.sheet_names)
        tiene_tepsac = 'TEPSAC' in excel_file.sheet_names

        if tiene_fase1:
            # Si existe FASE1, asumimos que es Codelco
            result['fases_codelco'] = ['F01']
            if tiene_fase2:
                result['fases_contratista'].append('F02')
            if tiene_fase3:
                result['fases_contratista'].append('F03')

            if result['fases_contratista']:
                print(f"   [FASE] F01 es Codelco, {result['fases_contratista']} son contratista (Tepsac)")
            else:
                print(f"   [FASE] F01 es Codelco (no hay F02/F03)")
        else:
            # No hay FASE1 - caso incierto
            result['requiere_confirmacion_usuario'] = True
            print(f"   [WARN] No se puede determinar propiedad de fases - requiere confirmación del usuario")

        # =====================================================================
        # LEER PLAN TOTAL (TODAS LAS FASES: F01+F02+F03)
        # =====================================================================
        # CAMBIO: NO leer solo F01, leer desde RESUMEN DIARIO que tiene el TOTAL
        # Según IGM oficial, el plan debe incluir TODAS las fases, no solo Codelco
        sheet_name_fase1 = None
        if 'C&T FASE1' in excel_file.sheet_names:
            sheet_name_fase1 = 'C&T FASE1'
        elif 'CARGUIO Y TRANSPORTE FASE1' in excel_file.sheet_names:
            sheet_name_fase1 = 'CARGUIO Y TRANSPORTE FASE1'

        # DESHABILITADO: No leer solo F01, saltar directo a RESUMEN DIARIO (TOTAL)
        if False and 'F01' in result['fases_codelco'] and sheet_name_fase1:
            try:
                df = pd.read_excel(filepath, sheet_name=sheet_name_fase1, header=None)
                print(f"   [INFO] Leyendo desde hoja: {sheet_name_fase1}")

                # ============================================================
                # DETECTAR COLUMNA "TOTAL" DINÁMICAMENTE
                # ============================================================
                # Buscar la columna con "TOTAL" en las primeras 5 filas
                # Puede estar en fila 0, 1, 2, 3 o 4 dependiendo del formato
                col_total = None
                primera_fecha_col = None

                # Buscar en filas 0-4
                for row_idx in range(5):
                    for col_idx in range(4, min(50, len(df.columns))):
                        val = df.iloc[row_idx, col_idx]

                        # Detectar primera fecha (en fila 2 típicamente)
                        if row_idx == 2 and pd.notna(val) and isinstance(val, pd.Timestamp):
                            if primera_fecha_col is None:
                                primera_fecha_col = col_idx

                        # Detectar columna TOTAL
                        if pd.notna(val) and str(val).strip().upper() == 'TOTAL':
                            col_total = col_idx
                            print(f"   [OK] Columna TOTAL encontrada: {col_total} (fila {row_idx})")
                            break

                    if col_total is not None:
                        break

                # Si no se encuentra, calcular basándose en el número de días del mes
                if col_total is None:
                    import calendar
                    dias_mes = calendar.monthrange(year, mes)[1]
                    # Primera fecha en col 4, últimas fechas en col 4+dias_mes-1, TOTAL en col 4+dias_mes+1 o similar
                    col_total = 4 + dias_mes + 2  # Heurística: primera_fecha_col + días + separadores

                    print(f"   [INFO] Columna TOTAL no encontrada, calculada como col {col_total} (mes {mes} tiene {dias_mes} días)")

                    # Validar que no esté fuera de rango
                    if col_total >= len(df.columns):
                        col_total = 36  # Fallback final
                        print(f"   [WARN] Col calculada fuera de rango, usando col 36 por defecto")

                # ============================================================
                # LECTURA CORRECTA: Sumar TODAS las palas individuales
                # ============================================================
                # Estructura: PC 7000 205 en columna B (índice 1)
                # Tonelaje en fila "Tonelaje Cargado" ~26 filas después
                # Valor en columna TOTAL (detectada dinámicamente)

                palas_individuales = []

                for row_idx in range(len(df)):
                    equipo_nombre = str(df.iloc[row_idx, 1]).strip()

                    # Detectar palas PC 7000 o PC 5500
                    if ('PC 7000' in equipo_nombre or 'PC 5500' in equipo_nombre) and 'nan' not in equipo_nombre:
                        # ============================================================
                        # EXTRAER TODOS LOS PARÁMETROS IMPORTANTES DE LA PALA
                        # ============================================================
                        parametros = {
                            'equipo': equipo_nombre,
                            'tipo': 'pala'
                        }

                        # Mapeo de parámetros: concepto -> key en dict
                        parametros_buscar = {
                            'Días': ('dias', 'd'),
                            'Flota Nominal': ('flota_nominal', 'un'),
                            'Horas Nominales': ('horas_nominales', 'h'),
                            'Disponibilidad Física': ('disponibilidad_fisica', '%'),
                            'Horas Disponibles': ('horas_disponibles', 'h'),
                            'Demoras Programadas': ('demoras_programadas_pct', '%'),
                            'Demoras No Programadas': ('demoras_no_programadas_pct', '%'),
                            'Perdidas Operacionales': ('perdidas_operacionales_pct', '%'),
                            'Uso ef': ('uso_efectivo_pct', '%'),
                            'Horas Efectivas': ('horas_efectivas', 'h'),
                            'UEBD': ('uebd', '%'),
                            'Rendimiento Efectivo': ('rendimiento_efectivo', 't/hef')
                        }

                        # Buscar cada parámetro en las siguientes 35 filas
                        for offset in range(1, 36):
                            if row_idx + offset < len(df):
                                concepto = str(df.iloc[row_idx + offset, 2]).strip()
                                unidad_col = str(df.iloc[row_idx + offset, 3]).strip() if pd.notna(df.iloc[row_idx + offset, 3]) else ''
                                valor = df.iloc[row_idx + offset, col_total]

                                # CASO ESPECIAL: Tonelaje Cargado con unidad "th" (toneladas totales)
                                if 'Tonelaje Cargado' in concepto and unidad_col == 'th':
                                    if pd.notna(valor):
                                        parametros['tonelaje'] = float(valor)
                                    continue

                                # Verificar si este concepto está en nuestra lista
                                for concepto_buscar, (key, unidad) in parametros_buscar.items():
                                    if concepto_buscar in concepto:
                                        if pd.notna(valor):
                                            val_float = float(valor)

                                            # Convertir porcentajes decimales a %
                                            if unidad == '%' and val_float < 1:
                                                val_float = val_float * 100

                                            parametros[key] = val_float
                                        break

                        # Solo agregar si tiene tonelaje
                        if 'tonelaje' in parametros and parametros['tonelaje'] > 100000:
                            palas_individuales.append(parametros)
                            print(f"   [OK] {equipo_nombre:20s} -> {parametros['tonelaje']:>12,.0f} ton | UEBD: {parametros.get('uebd', 0):.1f}% | Horas Ef: {parametros.get('horas_efectivas', 0):.0f}h")

                # ============================================================
                # EXTRAER PARÁMETROS DE CAEX 930 (FLOTA DE CAMIONES)
                # ============================================================
                caex_params = {}
                for row_idx in range(len(df)):
                    equipo_nombre = str(df.iloc[row_idx, 1]).strip().upper()

                    if 'CAEX' in equipo_nombre:
                        # Mapeo de parámetros de CAEX
                        parametros_caex = {
                            'Horas Nominales': ('horas_nominales', 'h'),
                            'Flota nominal': ('flota_nominal', 'un'),
                            'Horas nominales flota': ('horas_nominales_flota', 'h'),
                            'Disponibilidad Física': ('disponibilidad_fisica', '%'),
                            'Horas Disponibles': ('horas_disponibles', 'h'),
                            'Camiones Disponibles': ('camiones_disponibles', 'un'),
                            'Demoras Programadas': ('demoras_programadas_pct', '%'),
                            'Demoras No Programadas': ('demoras_no_programadas_pct', '%'),
                            'Perdidas Operacionales': ('perdidas_operacionales_pct', '%'),
                            'Uso ef': ('uso_efectivo_pct', '%'),
                            'Horas Efectivas': ('horas_efectivas', 'h'),
                            'Camiones Efectivos': ('camiones_efectivos', 'un'),
                            'UEBD': ('uebd', '%'),
                            'Distancia media': ('distancia_media', 'mts'),
                            'Tiempo de ciclo': ('tiempo_ciclo', 'min'),
                            'Factor de Carga': ('factor_carga', 'th'),
                            'Rendimiento medio': ('rendimiento_medio', 'th-hef'),
                            'Tonelaje Transportado': ('tonelaje', 'th')
                        }

                        # Buscar cada parámetro
                        for offset in range(1, 51):
                            if row_idx + offset < len(df):
                                concepto = str(df.iloc[row_idx + offset, 2]).strip()
                                valor = df.iloc[row_idx + offset, col_total]

                                for concepto_buscar, (key, unidad) in parametros_caex.items():
                                    if concepto_buscar in concepto:
                                        if pd.notna(valor):
                                            val_float = float(valor)

                                            # Convertir porcentajes
                                            if unidad == '%' and val_float < 1:
                                                val_float = val_float * 100

                                            caex_params[key] = val_float
                                        break

                        if 'tonelaje' in caex_params:
                            print(f"   [OK] {equipo_nombre:20s} -> {caex_params['tonelaje']:>12,.0f} ton | UEBD: {caex_params.get('uebd', 0):.1f}% | Ciclo: {caex_params.get('tiempo_ciclo', 0):.1f}min")
                            result['caex_parametros'] = caex_params
                        break

                caex_total = caex_params.get('tonelaje', None)

                # ============================================================
                # LEER DISPONIBILIDADES (DF) DE PALAS Y CAEX
                # ============================================================
                # Buscar DF de cada pala (columna TOTAL, fila "Disponibilidad Física")
                df_palas = []
                for pala in palas_individuales:
                    equipo_nombre = pala['equipo']
                    # Buscar la fila del equipo
                    for row_idx in range(len(df)):
                        if str(df.iloc[row_idx, 1]).strip() == equipo_nombre:
                            # Buscar "Disponibilidad Física" ~7 filas después
                            for offset in range(1, 15):
                                if row_idx + offset < len(df):
                                    concepto = str(df.iloc[row_idx + offset, 2]).strip()
                                    if 'Disponibilidad F' in concepto or 'Disponibilidad Física' in concepto:
                                        val = df.iloc[row_idx + offset, col_total]
                                        if pd.notna(val):
                                            try:
                                                df_value = float(val)
                                                if df_value < 1:
                                                    df_value = df_value * 100
                                                df_palas.append(df_value)
                                                print(f"   [OK] {equipo_nombre:20s} -> DF: {df_value:.2f}%")
                                                break
                                            except:
                                                pass
                                        break
                            break

                # Calcular promedio DF palas
                if df_palas:
                    result['disponibilidad_palas'] = sum(df_palas) / len(df_palas)
                    print(f"   [OK] DF Promedio Palas: {result['disponibilidad_palas']:.2f}%")

                # Buscar DF de CAEX
                for row_idx in range(len(df)):
                    equipo_nombre = str(df.iloc[row_idx, 1]).strip().upper()
                    if 'CAEX' in equipo_nombre:
                        for offset in range(1, 20):
                            if row_idx + offset < len(df):
                                concepto = str(df.iloc[row_idx + offset, 2]).strip()
                                if 'Disponibilidad F' in concepto or 'Disponibilidad Física' in concepto:
                                    val = df.iloc[row_idx + offset, col_total]
                                    if pd.notna(val):
                                        try:
                                            df_value = float(val)
                                            if df_value < 1:
                                                df_value = df_value * 100
                                            result['disponibilidad_camiones'] = df_value
                                            print(f"   [OK] DF CAEX 930: {df_value:.2f}%")
                                            break
                                        except:
                                            pass
                                    break
                        break

                # Sumar todas las palas
                if palas_individuales:
                    total_palas = sum(p['tonelaje'] for p in palas_individuales)
                    result['movimiento_total'] = total_palas
                    result['equipos_carguio'] = palas_individuales

                    print(f"   " + "="*60)
                    print(f"   [OK] TOTAL PALAS F01 (Codelco): {total_palas:,.0f} ton")

                    # Validar con CAEX
                    if caex_total:
                        diferencia = abs(total_palas - caex_total)
                        if diferencia < 1000:
                            print(f"   [OK] Validacion OK: Palas ({total_palas:,.0f}) = CAEX ({caex_total:,.0f})")
                        else:
                            print(f"   [WARN] Diferencia: Palas ({total_palas:,.0f}) vs CAEX ({caex_total:,.0f}) = {diferencia:,.0f} ton")
                else:
                    print(f"   [WARN] No se encontraron palas individuales en columna TOTAL")

            except Exception as e:
                print(f"[WARN]  Error en CARGUIO Y TRANSPORTE FASE1: {e}")
                import traceback
                traceback.print_exc()

        # OPCIÓN 2 FALLBACK: Si no se pudo leer de FASE1, intentar RESUMEN MNTTO.
        if result['movimiento_total'] is None and 'RESUMEN MNTTO.' in excel_file.sheet_names:
            try:
                df = pd.read_excel(filepath, sheet_name='RESUMEN MNTTO.', header=None)

                # Buscar "Movimiento" o "Extracción" en la hoja
                for idx in range(len(df)):
                    for col_idx in range(min(5, len(df.columns))):
                        celda = str(df.iloc[idx, col_idx]).lower() if pd.notna(df.iloc[idx, col_idx]) else ""

                        if 'movimiento' in celda or 'extracción' in celda or 'extraccion' in celda:
                            # Buscar valor total en las siguientes columnas
                            for val_col in range(col_idx + 1, min(col_idx + 10, len(df.columns))):
                                val = df.iloc[idx, val_col]
                                if pd.notna(val) and isinstance(val, (int, float)) and val > 1_000_000:
                                    result['movimiento_total'] = float(val)
                                    print(f"   [OK] Movimiento Total: {result['movimiento_total']:,.0f} ton (desde RESUMEN MNTTO.)")
                                    break
                            if result['movimiento_total']:
                                break
                    if result['movimiento_total']:
                        break

            except Exception as e:
                print(f"[WARN]  Error en RESUMEN MNTTO.: {e}")

        # =================================================================
        # RESUMEN KPIS - Leer extraccion_total del plan mensual
        # =================================================================
        if 'RESUMEN KPIS' in excel_file.sheet_names:
            try:
                df = pd.read_excel(filepath, sheet_name='RESUMEN KPIS', header=None)

                # Buscar fila "Extracción Total" en columna 2 (índice 1)
                for row_idx in range(len(df)):
                    col2 = str(df.iloc[row_idx, 1]).strip() if pd.notna(df.iloc[row_idx, 1]) else ""

                    if 'Extracción Total' in col2 or 'Extraccion Total' in col2:
                        # Leer columna 5 (índice 4) = Plan Mensual
                        col3_unidad = str(df.iloc[row_idx, 2]).strip() if pd.notna(df.iloc[row_idx, 2]) else ""
                        val_col5 = df.iloc[row_idx, 4]  # Col 5 = Plan Mensual

                        if pd.notna(val_col5) and isinstance(val_col5, (int, float)):
                            # Si la unidad es 'kt', el valor ya está en kilotoneladas
                            if col3_unidad.lower() == 'kt':
                                result['extraccion_total'] = float(val_col5) * 1000  # Convertir kt a ton
                                print(f"   [OK] Extraccion Total (RESUMEN KPIS): {float(val_col5):,.2f} Kton = {result['extraccion_total']:,.0f} ton")
                            else:
                                result['extraccion_total'] = float(val_col5)
                                print(f"   [OK] Extraccion Total (RESUMEN KPIS): {result['extraccion_total']:,.0f} ton")
                        break

            except Exception as e:
                print(f"[WARN]  Error en RESUMEN KPIS: {e}")

        # HOJA 2: RESUMEN DIARIO (backup) - SOLO LEER F01 (CODELCO)
        if result['movimiento_total'] is None and 'RESUMEN DIARIO' in excel_file.sheet_names:
            try:
                df = pd.read_excel(filepath, sheet_name='RESUMEN DIARIO', header=None)

                # Buscar fila con TOTAL que suma todas las fases (F01+F02+F03)
                for idx in range(len(df)):
                    if idx >= 2 and idx <= 10:  # Filas 2-10 (donde están los totales por fase)
                        celda_fase_b = str(df.iloc[idx, 1]).strip().upper() if pd.notna(df.iloc[idx, 1]) else ""
                        celda_fase_c = str(df.iloc[idx, 2]).strip().upper() if pd.notna(df.iloc[idx, 2]) else ""

                        # Buscar fila que contenga "TOTAL" (suma de todas las fases)
                        if celda_fase_b == 'TOTAL' or 'TOTAL' in celda_fase_c:
                            # El valor total mensual está en la última columna
                            ultima_col = len(df.columns) - 1
                            val = df.iloc[idx, ultima_col]
                            if pd.notna(val) and isinstance(val, (int, float)) and val > 100_000:
                                result['movimiento_total'] = float(val)
                                print(f"   [OK] Movimiento TOTAL (todas las fases): {result['movimiento_total']:,.0f} ton (desde RESUMEN DIARIO)")
                                break

            except Exception as e:
                print(f"[WARN]  Error en RESUMEN DIARIO: {e}")

        # NOTA: Las disponibilidades (DF) ahora se leen directamente de CARGUIO Y TRANSPORTE FASE1
        # (código actualizado arriba, columna 36)

        # =================================================================
        # HOJA 4: RESUMEN DIARIO - Plan día por día
        # =================================================================
        if 'RESUMEN DIARIO' in excel_file.sheet_names:
            try:
                df = pd.read_excel(filepath, sheet_name='RESUMEN DIARIO', header=None)

                # PASO 1: Buscar fila con Fase="Total" de EXTRACCIÓN
                # Estructura esperada:
                # Fila 3: "Extracción total" [F01]
                # Fila 4: (vacío) [F02]
                # Fila 5: (vacío) [F03]
                # Fila 7: (vacío) [Total] <- ESTA ES LA QUE QUEREMOS
                fila_total_idx = None

                for row_idx in range(len(df)):
                    col2 = str(df.iloc[row_idx, 1]).strip() if pd.notna(df.iloc[row_idx, 1]) else ""
                    col3_fase = str(df.iloc[row_idx, 2]).strip() if pd.notna(df.iloc[row_idx, 2]) else ""
                    col4_unidad = str(df.iloc[row_idx, 3]).strip().lower() if pd.notna(df.iloc[row_idx, 3]) else ""

                    # Buscar fila donde:
                    # - col3 (índice 2) = "Total"
                    # - col4 (índice 3) = "tmh" (toneladas, no metros de perforación)
                    # - Cerca de una fila con "Extracción total" en col2
                    if col3_fase.lower() == 'total' and col4_unidad == 'tmh':
                        # Verificar que está cerca de "Extracción total"
                        es_extraccion = False
                        for check_row in range(max(0, row_idx - 5), min(row_idx + 2, len(df))):
                            check_col2 = str(df.iloc[check_row, 1]).strip().lower() if pd.notna(df.iloc[check_row, 1]) else ""
                            if 'extracción total' in check_col2 or 'extraccion total' in check_col2:
                                es_extraccion = True
                                break

                        if es_extraccion:
                            fila_total_idx = row_idx
                            print(f"   [OK] Fila Total de Extracción encontrada en fila {row_idx}")
                            break

                if fila_total_idx is None:
                    print(f"   [WARN]  No se encontró fila Total de Extracción en RESUMEN DIARIO")
                else:
                    # PASO 2: Detectar primera columna con fecha (columna E = índice 4)
                    primera_fecha_col = None
                    dias_mes = 0

                    for col_idx in range(4, len(df.columns)):
                        val = df.iloc[1, col_idx]
                        if pd.notna(val) and (isinstance(val, pd.Timestamp) or hasattr(val, 'day')):
                            if primera_fecha_col is None:
                                primera_fecha_col = col_idx
                            dias_mes += 1
                        elif primera_fecha_col is not None:
                            # Ya encontramos fechas y ahora llegó una celda sin fecha (probablemente "Total")
                            break

                    if primera_fecha_col is None:
                        print(f"   [WARN]  No se encontraron fechas en RESUMEN DIARIO")
                    else:
                        print(f"   [OK] Detectados {dias_mes} días (col {primera_fecha_col} a {primera_fecha_col + dias_mes - 1})")

                        # Columna TOTAL está después del último día
                        col_total_mes = primera_fecha_col + dias_mes
                        # PASO 3: Extraer tonelaje día por día
                        dias_plan = []

                        for i in range(dias_mes):
                            col_idx = primera_fecha_col + i

                            fecha = df.iloc[1, col_idx]
                            tonelaje = df.iloc[fila_total_idx, col_idx]

                            if pd.notna(fecha) and pd.notna(tonelaje):
                                try:
                                    dia = fecha.day if hasattr(fecha, 'day') else i + 1

                                    if isinstance(tonelaje, (int, float)) and tonelaje > 0:
                                        dias_plan.append({
                                            'dia': dia,
                                            'tonelaje': float(tonelaje)
                                        })
                                except Exception as e:
                                    print(f"   [WARN]  Error procesando día {i+1}: {e}")

                        result['plan_diario'] = dias_plan
                        print(f"   [OK] Plan diario extraído: {len(dias_plan)} días")

                        # PASO 4: Validar con columna TOTAL
                        if col_total_mes < len(df.columns):
                            total_mes_columna = df.iloc[fila_total_idx, col_total_mes]

                            if pd.notna(total_mes_columna) and isinstance(total_mes_columna, (int, float)):
                                suma_dias = sum(d['tonelaje'] for d in dias_plan)

                                print(f"   [OK] Columna TOTAL: {total_mes_columna:,.0f} ton")
                                print(f"   [OK] Suma días: {suma_dias:,.0f} ton")

                                diferencia = abs(suma_dias - total_mes_columna)
                                if diferencia < 1000:
                                    print(f"   [OK] Validación exitosa (diff: {diferencia:,.0f} ton)")
                                else:
                                    print(f"   [WARN]  Diferencia: {diferencia:,.0f} ton)")

                                result['plan_diario_total_validado'] = float(total_mes_columna)

                        # PASO 5: Extraer equipos por fase
                        equipos_por_fase = {'F01': [], 'F02': [], 'F03': [], 'F04': []}

                        for row_idx in range(len(df)):
                            col_b = str(df.iloc[row_idx, 1]).strip().upper() if pd.notna(df.iloc[row_idx, 1]) else ""
                            col_c = str(df.iloc[row_idx, 2]).strip() if pd.notna(df.iloc[row_idx, 2]) else ""
                            col_d = str(df.iloc[row_idx, 3]).strip().lower() if pd.notna(df.iloc[row_idx, 3]) else ""

                            # Solo equipos con unidad "tmh" (no perforación "m")
                            if col_b in ['F01', 'F02', 'F03', 'F04'] and col_d == 'tmh':
                                if col_c and col_c.lower() not in ['f01', 'f02', 'f03', 'f04', 'total', '']:
                                    equipos_por_fase[col_b].append({
                                        'nombre': col_c,
                                        'fase': col_b,
                                        'fila': row_idx
                                    })

                        result['equipos_por_fase'] = equipos_por_fase

                        total_equipos = sum(len(equipos) for equipos in equipos_por_fase.values())
                        if total_equipos > 0:
                            print(f"   [OK] Equipos: F01={len(equipos_por_fase['F01'])}, F02={len(equipos_por_fase['F02'])}, F03={len(equipos_por_fase['F03'])}, F04={len(equipos_por_fase['F04'])}")

            except Exception as e:
                print(f"   [WARN]  Error en RESUMEN DIARIO: {e}")
                import traceback
                traceback.print_exc()

        # =================================================================
        # HOJA EXTRACCIÓN POR FASE - Leer total mensual desde fila "Extracción total"
        # =================================================================
        if 'EXTRACCIÓN POR FASE' in excel_file.sheet_names:
            try:
                df = pd.read_excel(filepath, sheet_name='EXTRACCIÓN POR FASE', header=None)

                # Buscar fila que contiene "Extracción total" en columna A (índice 0)
                fila_total_idx = None
                for row_idx in range(len(df)):
                    val_a = str(df.iloc[row_idx, 0]).strip().lower() if pd.notna(df.iloc[row_idx, 0]) else ""
                    if 'extracción total' in val_a or 'extracci' in val_a:
                        # Verificar que sea la fila correcta (típicamente fila 31)
                        # Buscar valor en última columna con datos (típicamente col AK)
                        fila_total_idx = row_idx
                        print(f"   [OK] Fila 'Extracción total' encontrada en fila {row_idx}")
                        break

                if fila_total_idx is not None:
                    # Buscar columna TOTAL (típicamente la última con datos)
                    # Recorrer desde la derecha para encontrar la primera celda con número > 1M
                    total_mensual = None
                    for col_idx in range(len(df.columns) - 1, 3, -1):
                        val = df.iloc[fila_total_idx, col_idx]
                        if pd.notna(val) and isinstance(val, (int, float)) and val > 1000000:
                            total_mensual = float(val)
                            print(f"   [OK] Total mensual encontrado: {total_mensual:,.0f} ton (col {col_idx})")
                            result['extraccion_total'] = total_mensual
                            break

                    if total_mensual is None:
                        print(f"   [WARN] No se encontró total mensual en EXTRACCIÓN POR FASE")
                else:
                    print(f"   [WARN] No se encontró fila 'Extracción total' en EXTRACCIÓN POR FASE")

            except Exception as e:
                print(f"   [WARN] Error en EXTRACCIÓN POR FASE: {e}")

        return result

    def get_plan_p0(self, year: int = 2025) -> Optional[Dict]:
        """Obtiene el plan P0 anual"""

        # Buscar archivo P0
        archivos = []
        for ext in ['.xlsb', '.xlsx']:
            pattern = f"*P0*{year}*{ext}"
            found = list(self.data_dir.glob(pattern))
            if found:
                archivos = found
                break

        if not archivos:
            print(f"[WARN]  No se encontró plan P0 para {year}")
            return None

        archivo = archivos[0]
        print(f"[PLAN] Leyendo P0: {archivo.name}")

        try:
            df = pd.read_excel(archivo, header=None)

            result = {
                'year': year,
                'archivo': archivo.name,
                'planes_mensuales': {}
            }

            # Buscar fila "Movimiento Total - tmh"
            for idx in range(len(df)):
                celda = str(df.iloc[idx, 0]).lower() if pd.notna(df.iloc[idx, 0]) else ""

                if 'movimiento total' in celda and 'tmh' in celda:
                    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

                    for mes_idx, mes_nombre in enumerate(meses, start=1):
                        col_idx = mes_idx + 1
                        if col_idx < len(df.columns):
                            val = df.iloc[idx, col_idx]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                result['planes_mensuales'][mes_idx] = {
                                    'mes': mes_idx,
                                    'mes_nombre': mes_nombre,
                                    'movimiento_total': float(val)
                                }
                    break

            return result

        except Exception as e:
            print(f"[ERROR] Error leyendo P0: {e}")
            return None

    def get_plan_por_fase(self, mes: int, year: int = 2025) -> Optional[Dict]:
        """
        Obtiene el plan mensual separado por fase dinámicamente

        Lee la hoja RESUMEN DIARIO del plan mensual y extrae el tonelaje
        planificado para cada fase (F01, F02, F03, F04, etc.)

        Args:
            mes: Número de mes (1-12)
            year: Año (default 2025)

        Returns:
            {
                'plan_total': 9430808,
                'fases': {
                    'F01': 5169536,
                    'F02': 3500272,
                    'F03': 761000,
                    'F04': 0
                },
                'archivo': '09_Plan Mensual Septiembre Mina RI 2025.xlsx'
            }
        """
        # Primero obtener el archivo del plan mensual
        plan_mensual = self.get_plan_mensual(mes, year)
        if not plan_mensual:
            print(f"[PLAN_FASE] No se encontró plan mensual para {mes}/{year}")
            return None

        # Leer archivo Excel del plan
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }

        mes_nombre = meses.get(mes, '')

        # Buscar archivos
        possible_patterns = [
            f"{mes:02d}_Plan Mensual {mes_nombre} Mina RI {year}.xlsx",
            f"Plan Mensual {mes_nombre} Mina RI {year}.xlsx",
            f"{mes:02d}_Plan {mes_nombre} {year}.xlsx",
        ]

        filepath = None
        for pattern in possible_patterns:
            test_path = self.data_dir / pattern
            if test_path.exists():
                filepath = test_path
                break

        if not filepath:
            print(f"[PLAN_FASE] No se encontró archivo Excel para {mes_nombre} {year}")
            return None

        try:
            # Leer hoja RESUMEN DIARIO
            if 'RESUMEN DIARIO' not in pd.ExcelFile(filepath).sheet_names:
                print(f"[PLAN_FASE] No se encontró hoja RESUMEN DIARIO en {filepath.name}")
                return None

            df = pd.read_excel(filepath, sheet_name='RESUMEN DIARIO', header=None)

            # Estructura de fases
            fases = {}
            plan_total = 0

            # Buscar filas con fases (F01, F02, F03, etc.) en columna C (índice 2)
            # Las fases están en las primeras filas (típicamente 2-10)
            for row_idx in range(1, min(15, len(df))):
                col_b = str(df.iloc[row_idx, 1]).strip() if pd.notna(df.iloc[row_idx, 1]) else ""
                col_c = str(df.iloc[row_idx, 2]).strip().upper() if pd.notna(df.iloc[row_idx, 2]) else ""

                # Buscar patrón F\d+ (F01, F02, F03, etc.)
                fase_match = re.match(r'^(F\d+)', col_c)

                if fase_match:
                    fase_id = fase_match.group(1)

                    # El total mensual está en la última columna (columna 36 típicamente)
                    ultima_col = len(df.columns) - 1
                    val = df.iloc[row_idx, ultima_col]

                    if pd.notna(val) and isinstance(val, (int, float)) and val > 1000:
                        fases[fase_id] = float(val)
                        plan_total += float(val)
                        print(f"[PLAN_FASE] {fase_id}: {float(val):,.0f} ton")

                # También buscar fila "TOTAL" para validar
                if 'TOTAL' in col_c and col_b.strip() == '':
                    ultima_col = len(df.columns) - 1
                    val_total = df.iloc[row_idx, ultima_col]
                    if pd.notna(val_total) and isinstance(val_total, (int, float)):
                        # Validar que coincida con la suma
                        if abs(val_total - plan_total) / val_total < 0.01:  # 1% tolerancia
                            print(f"[PLAN_FASE] TOTAL validado: {val_total:,.0f} ton")
                            plan_total = float(val_total)
                        break

            if not fases:
                print(f"[PLAN_FASE] No se encontraron fases en RESUMEN DIARIO")
                return None

            result = {
                'plan_total': plan_total if plan_total > 0 else sum(fases.values()),
                'fases': fases,
                'archivo': filepath.name,
                'mes': mes,
                'year': year
            }

            print(f"[PLAN_FASE] Plan total: {result['plan_total']:,.0f} ton ({len(fases)} fases)")
            return result

        except Exception as e:
            print(f"[PLAN_FASE] Error leyendo fases: {e}")
            return None

    def get_plan_diario(self, fecha: str, year: int = 2025) -> Optional[Dict]:
        """
        Obtiene el plan de un día específico

        Args:
            fecha: Fecha en formato 'YYYY-MM-DD' (ej: '2025-01-15')
            year: Año (default 2025)

        Returns:
            Dict con plan del día o None
        """
        from datetime import datetime

        # Parsear fecha
        try:
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            print(f"[WARN]  Formato de fecha inválido: {fecha}")
            return None

        mes = fecha_obj.month
        dia = fecha_obj.day

        # Obtener plan mensual (incluye plan_diario)
        plan_mensual = self.get_plan_mensual(mes, year)
        if not plan_mensual or 'plan_diario' not in plan_mensual:
            print(f"[WARN]  No hay plan diario disponible para {fecha}")
            return None

        # Buscar el día específico
        for dia_info in plan_mensual['plan_diario']:
            if dia_info['dia'] == dia:
                result = {
                    'fecha': fecha,
                    'dia': dia,
                    'mes': mes,
                    'year': year,
                    'tonelaje_plan_dia': dia_info['tonelaje'],
                    'archivo': plan_mensual['archivo']
                }
                print(f"   [OK] Plan del {fecha}: {dia_info['tonelaje']:,.0f} ton")
                return result

        print(f"   [WARN]  No se encontró plan para día {dia}")
        return None


def get_plan_tonelaje(mes: int, year: int = 2025) -> Optional[Dict]:
    """
    Obtiene el tonelaje planificado para un mes específico (solo equipos Codelco)

    Returns:
        Dict con:
        - tonelaje: float con el tonelaje plan
        - requiere_confirmacion: bool si se necesita confirmar con el usuario
        - fases_codelco: list de fases operadas por Codelco
        - mes_nombre: str con nombre del mes
    """
    reader = PlanReader()

    # Intentar primero plan mensual
    plan = reader.get_plan_mensual(mes, year)
    if plan and plan.get('movimiento_total'):
        return {
            'tonelaje': plan['movimiento_total'],
            'requiere_confirmacion': plan.get('requiere_confirmacion_usuario', False),
            'fases_codelco': plan.get('fases_codelco', []),
            'fases_contratista': plan.get('fases_contratista', []),
            'mes_nombre': plan.get('mes_nombre', ''),
            'archivo': plan.get('archivo', '')
        }

    # Fallback a P0
    p0 = reader.get_plan_p0(year)
    if p0 and mes in p0.get('planes_mensuales', {}):
        return {
            'tonelaje': p0['planes_mensuales'][mes].get('movimiento_total'),
            'requiere_confirmacion': False,
            'fases_codelco': [],
            'fases_contratista': [],
            'mes_nombre': '',
            'archivo': p0.get('archivo', '')
        }

    return None


def get_plan_disponibilidades(mes: int, year: int = 2025) -> Dict[str, Optional[float]]:
    """Obtiene las disponibilidades planificadas de palas y camiones"""
    reader = PlanReader()
    plan = reader.get_plan_mensual(mes, year)

    if plan:
        return {
            'palas': plan.get('disponibilidad_palas'),
            'camiones': plan.get('disponibilidad_camiones')
        }

    return {'palas': None, 'camiones': None}


def get_plan_dia_especifico(fecha: str, year: int = 2025) -> Optional[float]:
    """
    Obtiene el tonelaje planificado para un día específico

    Args:
        fecha: Fecha en formato 'YYYY-MM-DD' (ej: '2025-09-15')
        year: Año (default 2025)

    Returns:
        Tonelaje en toneladas o None
    """
    reader = PlanReader()
    plan_dia = reader.get_plan_diario(fecha, year)

    if plan_dia:
        return plan_dia['tonelaje_plan_dia']

    return None
