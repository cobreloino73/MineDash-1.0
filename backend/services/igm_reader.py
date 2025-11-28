"""
IGM READER - Informes de Gestión Mensual
Lector de PDFs oficiales para obtener tonelaje real por fase/empresa

Este módulo extrae datos validados de los IGM mensuales generados por
División Salvador, que contienen tonelajes oficiales por fase/empresa.
"""
import re
from pathlib import Path
from typing import Dict, Optional
import pdfplumber


def leer_igm_mes(mes: int, year: int = 2025) -> Optional[Dict]:
    """
    Busca y lee el IGM PDF del mes especificado

    Busca en los siguientes patrones:
    1. data/Control de Gestion/{mes:02d}. IGM {nombre_mes} {year}.pdf
    2. data/Control de Gestion/{year}/IGM_{mes:02d}_{year}.pdf
    3. data/Control de Gestion/IGM {nombre_mes} {year}.pdf

    Args:
        mes: Mes (1-12)
        year: Año (default 2025)

    Returns:
        {
            'extraccion_codelco': 2666207,  # F01
            'extraccion_tepsac': 5904637,   # F02
            'extraccion_f03': 0,
            'extraccion_f04': 0,
            'source': 'IGM'
        }
        O None si no encuentra el archivo
    """
    # Mapeo de meses
    meses = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    nombre_mes = meses.get(mes)
    if not nombre_mes:
        print(f"[IGM] Mes inválido: {mes}")
        return None

    # Base path
    base_path = Path(__file__).parent.parent / 'data' / 'Control de Gestion'

    # Patrones de búsqueda (orden de preferencia)
    patrones = [
        base_path / f"{mes:02d}. IGM {nombre_mes} {year}.pdf",
        base_path / f"{year}" / f"IGM_{mes:02d}_{year}.pdf",
        base_path / f"IGM {nombre_mes} {year}.pdf",
        base_path / f"{mes}. IGM {nombre_mes} {year}.pdf",  # Sin cero inicial
    ]

    # Buscar archivo
    igm_file = None
    for path in patrones:
        if path.exists():
            igm_file = path
            print(f"[IGM] Archivo encontrado: {path.name}")
            break

    if not igm_file:
        print(f"[IGM] No se encontró IGM para {nombre_mes} {year}")
        print(f"[IGM] Patrones buscados:")
        for p in patrones:
            print(f"  - {p}")
        return None

    # Leer PDF con pdfplumber
    try:
        with pdfplumber.open(igm_file) as pdf:
            # Extraer texto de todas las páginas
            texto_completo = ""
            for page in pdf.pages:
                texto_completo += page.extract_text() + "\n"

            if not texto_completo.strip():
                print(f"[IGM] PDF vacío o sin texto extraíble: {igm_file.name}")
                return None

            # Parsear tonelajes
            tonelajes = extraer_tonelajes_igm(texto_completo)

            if tonelajes:
                tonelajes['source'] = 'IGM'
                tonelajes['file'] = igm_file.name
                print(f"[IGM] Datos extraídos exitosamente de {igm_file.name}")
                return tonelajes
            else:
                print(f"[IGM] No se pudieron extraer tonelajes de {igm_file.name}")
                return None

    except Exception as e:
        print(f"[IGM] Error leyendo PDF {igm_file.name}: {e}")
        return None


def extraer_tonelajes_igm(text: str) -> Optional[Dict]:
    """
    Extrae tonelajes por fase del texto del IGM

    Busca el patrón de la tabla de resumen:
    "Fase Real (Kton) PAM (Kton) Cumplimiento
     Fase 1 5.002 5.170 97%
     Fase 2 1.826 2.373 77%
     Fase 3 1.331 1.888 70%"

    NOTA: Valores están en Kton (miles de toneladas), se multiplican por 1000

    Args:
        text: Texto completo del IGM

    Returns:
        {
            'extraccion_codelco': 5002000,  # Fase 1 * 1000
            'extraccion_tepsac': 1826000,   # Fase 2 * 1000
            'extraccion_f03': 1331000,      # Fase 3 * 1000
            'extraccion_f04': 0
        }
    """
    result = {
        'extraccion_codelco': 0,  # Fase 1
        'extraccion_tepsac': 0,   # Fase 2
        'extraccion_f03': 0,      # Fase 3
        'extraccion_f04': 0
    }

    # Normalizar texto (reemplazar saltos de línea múltiples con espacio)
    text = re.sub(r'\s+', ' ', text)

    # Buscar tabla de fases
    # Patrón: "Fase 1" seguido de número real en Kton
    # Ejemplo: "Fase 1 5.002 5.170 97%"
    # Capturamos el primer número después de "Fase X"

    patrones = {
        'fase_1': r'Fase\s+1\s+([0-9.]+)',
        'fase_2': r'Fase\s+2\s+([0-9.]+)',
        'fase_3': r'Fase\s+3\s+([0-9.]+)',
        'fase_4': r'Fase\s+4\s+([0-9.]+)'
    }

    def extraer_kton(patron, texto):
        """Extrae valor en Kton y convierte a toneladas"""
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            try:
                # Valor en Kton con formato español (ejemplo: "5.002")
                # El punto es separador de miles, NO decimal
                # "5.002" = cinco mil dos
                kton_str = match.group(1)
                # Remover punto (separador de miles)
                kton_str = kton_str.replace('.', '')
                kton_value = int(kton_str)
                # Convertir de Kton a toneladas: 5002 Kton = 5,002,000 tons
                tons = kton_value * 1000
                return tons
            except:
                return 0
        return 0

    # Extraer valores (Fase 1 = Codelco, Fase 2 = Tepsac, etc.)
    result['extraccion_codelco'] = extraer_kton(patrones['fase_1'], text)
    result['extraccion_tepsac'] = extraer_kton(patrones['fase_2'], text)
    result['extraccion_f03'] = extraer_kton(patrones['fase_3'], text)
    result['extraccion_f04'] = extraer_kton(patrones['fase_4'], text)

    # Validar que se extrajo al menos una fase
    total = sum(result.values())
    if total == 0:
        print("[IGM] No se encontraron valores de fases en el texto")
        return None

    print(f"[IGM] Tonelajes extraídos (convertidos de Kton a ton):")
    print(f"  - Fase 1 (Codelco): {result['extraccion_codelco']:,} ton")
    print(f"  - Fase 2 (Tepsac): {result['extraccion_tepsac']:,} ton")
    print(f"  - Fase 3: {result['extraccion_f03']:,} ton")
    print(f"  - Fase 4: {result['extraccion_f04']:,} ton")
    print(f"  - TOTAL: {total:,} ton")

    return result


def obtener_real_por_fase_con_fallback(mes: int, year: int = 2025, db_path: str = None) -> Dict:
    """
    Obtiene real por fase usando IGM primero, BD como fallback

    Args:
        mes: Mes (1-12)
        year: Año
        db_path: Path a la base de datos SQLite (opcional)

    Returns:
        {
            'F01': 2666207,
            'F02': 5904637,
            'F03': 0,
            'F04': 0,
            'source': 'IGM' | 'BD'
        }
    """
    # Intentar leer IGM primero
    igm_data = leer_igm_mes(mes, year)

    if igm_data:
        # Convertir formato IGM a formato por fase
        return {
            'F01': igm_data.get('extraccion_codelco', 0),
            'F02': igm_data.get('extraccion_tepsac', 0),
            'F03': igm_data.get('extraccion_f03', 0),
            'F04': igm_data.get('extraccion_f04', 0),
            'source': 'IGM',
            'file': igm_data.get('file', '')
        }

    # Fallback a BD
    print(f"[IGM] Usando fallback a BD para {mes}/{year}")

    if not db_path:
        db_path = Path(__file__).parent.parent / 'minedash.db'

    try:
        import sqlite3
        from datetime import datetime

        # Calcular rango de fechas
        fecha_inicio = f"{year}-{mes:02d}-01"
        if mes == 12:
            fecha_fin = f"{year+1}-01-01"
        else:
            fecha_fin = f"{year}-{mes+1:02d}-01"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query para obtener tonelaje por empresa
        query = f"""
        SELECT
            COALESCE(empresa, 'SIN_EMPRESA') as empresa,
            SUM(material_tonnage) as total
        FROM hexagon_by_detail_dumps_{year}
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY empresa
        """

        cursor.execute(query, (fecha_inicio, fecha_fin))
        rows = cursor.fetchall()
        conn.close()

        result = {
            'F01': 0,  # CODELCO
            'F02': 0,  # TEPSAC
            'F03': 0,
            'F04': 0,
            'source': 'BD'
        }

        for empresa, total in rows:
            if empresa == 'CODELCO':
                result['F01'] = int(total)
            elif empresa == 'TEPSAC':
                result['F02'] = int(total)

        print(f"[BD] Tonelajes extraídos de BD:")
        print(f"  - F01 (CODELCO): {result['F01']:,} ton")
        print(f"  - F02 (TEPSAC): {result['F02']:,} ton")

        return result

    except Exception as e:
        print(f"[BD] Error consultando base de datos: {e}")
        return {
            'F01': 0,
            'F02': 0,
            'F03': 0,
            'F04': 0,
            'source': 'ERROR'
        }


# Test si se ejecuta directamente
if __name__ == "__main__":
    print("=== TEST IGM READER ===\n")

    # Test Enero 2025
    print("1. Probando lectura IGM Enero 2025...")
    data = leer_igm_mes(1, 2025)

    if data:
        print("\n[OK] IGM leído exitosamente:")
        print(f"  Codelco: {data['extraccion_codelco']:,} ton")
        print(f"  Tepsac: {data['extraccion_tepsac']:,} ton")
        print(f"  Source: {data.get('source')}")
        print(f"  File: {data.get('file')}")
    else:
        print("\n[FAIL] No se pudo leer IGM")

    print("\n" + "="*50)
    print("2. Probando función con fallback...")
    data_fallback = obtener_real_por_fase_con_fallback(1, 2025)

    print("\n[RESULT] Datos finales:")
    print(f"  F01: {data_fallback['F01']:,} ton")
    print(f"  F02: {data_fallback['F02']:,} ton")
    print(f"  Source: {data_fallback.get('source')}")
