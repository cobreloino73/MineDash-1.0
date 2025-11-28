"""
IGM Validator - Sistema de Validación Temporal
MineDash AI v2.0 - Codelco División Salvador
"""

import sqlite3
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import os

# Configuración
VALIDATION_ENABLED = True  # Cambiar a False post-calibración
ERROR_THRESHOLD = 5.0      # 5% error máximo

@dataclass
class ValidationResult:
    kpi_name: str
    minedash_value: float
    igm_value: float
    error_pct: float
    is_valid: bool
    recommendation: str

class IGMValidator:
    def __init__(self, db_path: str = None):
        # Buscar la base de datos
        if db_path is None:
            possible_paths = [
                "minedash.db",
                "data/minedash.db",
                "../minedash.db",
                os.path.join(os.path.dirname(__file__), "..", "..", "minedash.db")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _execute(self, query: str) -> Optional[float]:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(query)
            result = cur.fetchone()
            conn.close()
            return result[0] if result and result[0] else None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_igm_data(self, mes: int, ano: int) -> Optional[dict]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM igm_ground_truth WHERE mes=? AND ano=?", (mes, ano))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        cols = [d[0] for d in cur.description]
        conn.close()
        return dict(zip(cols, row))

    def get_minedash_extraccion(self, mes: int, ano: int) -> float:
        """Query calibrado con IGM (Error: 0.19%)"""
        query = f"""
        SELECT SUM(material_tonnage) / 1000.0 as kton
        FROM hexagon_by_detail_dumps_2025
        WHERE strftime('%m', timestamp) = '{mes:02d}'
          AND strftime('%Y', timestamp) = '{ano}'
          AND blast_type = 'Blast'
          AND dump_type != 'InpitDump'
          AND blast_region != 'STOCKS'
        """
        return self._execute(query) or 0

    def test_filtros_extraccion(self, mes: int, ano: int) -> dict:
        """Probar diferentes combinaciones de filtros"""

        igm = self.get_igm_data(mes, ano)
        if not igm:
            return {"error": "No hay datos IGM para ese mes"}

        target = igm['extraccion_real_kton']

        filtros = {
            "sin_filtro": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
            """,
            "excluir_stockpile": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND dump_type != 'Stockpile'
            """,
            "excluir_inpitdump": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND dump_type != 'InpitDump'
            """,
            "excluir_stocks_region": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND blast_region != 'STOCKS'
            """,
            "excluir_inpit_y_stocks": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND dump_type != 'InpitDump'
                  AND blast_region != 'STOCKS'
            """,
            "solo_dump_y_crusher": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND dump_type IN ('Dump', 'Crusher')
            """,
            "solo_fases_produccion": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND blast_region IN ('FASE01', 'FASE02', 'FASE03')
            """,
            "CALIBRADO_OPTIMO": f"""
                SELECT SUM(material_tonnage) / 1000.0
                FROM hexagon_by_detail_dumps_2025
                WHERE strftime('%m', timestamp) = '{mes:02d}'
                  AND strftime('%Y', timestamp) = '{ano}'
                  AND blast_type = 'Blast'
                  AND dump_type != 'InpitDump'
                  AND blast_region != 'STOCKS'
            """
        }

        resultados = {}
        mejor_error = 100
        mejor_filtro = None

        for nombre, query in filtros.items():
            valor = self._execute(query)
            if valor:
                error = abs(valor - target) / target * 100
                resultados[nombre] = {
                    "valor_kton": round(valor, 2),
                    "error_pct": round(error, 2),
                    "diferencia_kton": round(valor - target, 2)
                }
                if error < mejor_error:
                    mejor_error = error
                    mejor_filtro = nombre

        return {
            "target_igm_kton": target,
            "resultados": resultados,
            "mejor_filtro": mejor_filtro,
            "mejor_error_pct": round(mejor_error, 2),
            "calibrado": mejor_error <= ERROR_THRESHOLD
        }

    def validar_mes(self, mes: int, ano: int) -> List[ValidationResult]:
        """Validar todos los KPIs contra IGM"""

        igm = self.get_igm_data(mes, ano)
        if not igm:
            raise ValueError(f"No hay datos IGM para {mes:02d}/{ano}")

        results = []

        # Extracción
        md_ext = self.get_minedash_extraccion(mes, ano)
        igm_ext = igm['extraccion_real_kton']
        error = abs(md_ext - igm_ext) / igm_ext * 100 if igm_ext else 0
        results.append(ValidationResult(
            kpi_name="Extracción (Kton)",
            minedash_value=md_ext,
            igm_value=igm_ext,
            error_pct=error,
            is_valid=error <= ERROR_THRESHOLD,
            recommendation=self._get_recommendation(error)
        ))

        return results

    def _get_recommendation(self, error: float) -> str:
        if error <= 5:
            return "[OK] Dentro de tolerancia"
        elif error <= 10:
            return "[!] Ajuste menor en filtros SQL"
        elif error <= 20:
            return "[X] Revisar filtros load_location y destination"
        else:
            return "[ERROR] CRITICO: Query incorrecta"

    def generar_reporte(self, mes: int, ano: int) -> str:
        """Generar reporte de validación"""

        results = self.validar_mes(mes, ano)
        calibracion = self.test_filtros_extraccion(mes, ano)

        report = f"""
# REPORTE VALIDACION IGM - {mes:02d}/{ano}

## Estado Actual

| KPI | MineDash | IGM | Error | Estado |
|-----|----------|-----|-------|--------|
"""
        for r in results:
            status = "[OK]" if r.is_valid else "[X]"
            report += f"| {r.kpi_name} | {r.minedash_value:.2f} | {r.igm_value:.2f} | {r.error_pct:.1f}% | {status} |\n"

        report += f"""

## Calibracion de Filtros

**Target IGM:** {calibracion['target_igm_kton']} Kton

| Filtro | Valor (Kton) | Error | Diferencia |
|--------|--------------|-------|------------|
"""
        for nombre, data in calibracion['resultados'].items():
            status = "[OK]" if data['error_pct'] <= 5 else "[X]"
            report += f"| {nombre} | {data['valor_kton']} | {data['error_pct']}% | {data['diferencia_kton']:+.0f} | {status} |\n"

        report += f"""

## Recomendacion

**Mejor filtro:** `{calibracion['mejor_filtro']}`
**Error:** {calibracion['mejor_error_pct']}%
**Estado:** {'[OK] CALIBRADO' if calibracion['calibrado'] else '[X] REQUIERE AJUSTES'}
"""
        return report


def diagnostico():
    """Ejecutar diagnóstico completo"""
    print("=" * 60)
    print("DIAGNOSTICO IGM - MineDash AI v2.0")
    print("=" * 60)

    validator = IGMValidator()

    # Verificar que existe la tabla
    try:
        igm = validator.get_igm_data(1, 2025)
        if not igm:
            print("\n[!] No hay datos IGM cargados")
            print("Ejecuta primero el INSERT de datos IGM")
            return
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("Crea primero la tabla igm_ground_truth")
        return

    # Generar reporte
    reporte = validator.generar_reporte(1, 2025)
    print(reporte)


if __name__ == "__main__":
    diagnostico()
