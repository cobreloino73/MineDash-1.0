"""
Servicio de visualización automática para rankings y análisis
División Salvador - Codelco Chile

Genera gráficos automáticos para rankings de operadores
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class RankingVisualizer:
    """Genera visualizaciones automáticas para rankings"""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('outputs')
        self.output_dir.mkdir(exist_ok=True)

    def generate_ranking_chart(self, ranking_data: List[Dict[str, Any]],
                              year: int, tipo: str = "CAEX") -> Path:
        """
        Genera gráfico de barras horizontales con 3 métricas clave

        Args:
            ranking_data: Lista de diccionarios con datos del ranking
            year: Año del ranking
            tipo: Tipo de equipo (CAEX, PALA, etc)

        Returns:
            Path al archivo PNG generado
        """
        # Extraer top 10
        top10 = ranking_data[:10]

        # Preparar datos
        operadores = [' '.join(item['operador'].split()[:2]) for item in top10]
        toneladas = [item['toneladas_total'] for item in top10]
        uebd = [item['uebd'] for item in top10]
        ton_hr = [item['ton_por_hr_efectiva'] for item in top10]

        # Crear figura con 3 subplots
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f'TOP 10 OPERADORES {tipo} {year}', fontsize=16, fontweight='bold')

        # Gráfico 1: Toneladas totales
        colors1 = plt.cm.Blues([(10-i)/10 for i in range(10)])
        bars1 = ax1.barh(operadores, toneladas, color=colors1)
        ax1.set_xlabel('Toneladas', fontweight='bold')
        ax1.set_title('Producción Total', fontweight='bold')
        ax1.invert_yaxis()
        for bar, val in zip(bars1, toneladas):
            ax1.text(val + max(toneladas)*0.02, bar.get_y() + bar.get_height()/2,
                    f'{val:,.0f}', va='center', fontsize=9)

        # Gráfico 2: UEBD
        colors2 = plt.cm.Greens([(10-i)/10 for i in range(10)])
        bars2 = ax2.barh(operadores, uebd, color=colors2)
        ax2.set_xlabel('UEBD (%)', fontweight='bold')
        ax2.set_title('Utilización Efectiva', fontweight='bold')
        ax2.invert_yaxis()
        ax2.set_xlim(0, 100)
        for bar, val in zip(bars2, uebd):
            ax2.text(val + 2, bar.get_y() + bar.get_height()/2,
                    f'{val:.1f}%', va='center', fontsize=9)

        # Gráfico 3: Ton/hr efectiva
        colors3 = plt.cm.Oranges([(10-i)/10 for i in range(10)])
        bars3 = ax3.barh(operadores, ton_hr, color=colors3)
        ax3.set_xlabel('Ton/hr efectiva', fontweight='bold')
        ax3.set_title('Productividad', fontweight='bold')
        ax3.invert_yaxis()
        for bar, val in zip(bars3, ton_hr):
            ax3.text(val + max(ton_hr)*0.02, bar.get_y() + bar.get_height()/2,
                    f'{val:.1f}', va='center', fontsize=9)

        plt.tight_layout()

        # Guardar con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'ranking_{tipo.lower()}_{year}_{timestamp}.png'
        output_path = self.output_dir / filename

        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return output_path

    def format_ranking_table(self, ranking_data: List[Dict[str, Any]],
                            year: int, stats: Dict[str, Any]) -> str:
        """
        Genera tabla formateada en texto para ranking

        Args:
            ranking_data: Lista de diccionarios con datos del ranking
            year: Año del ranking
            stats: Estadísticas generales

        Returns:
            String con tabla formateada
        """
        lines = []
        lines.append('=' * 120)
        lines.append(f'RANKING TOP 10 OPERADORES CAEX {year}'.center(120))
        lines.append('=' * 120)

        # Header
        header = f"{'#':<4} {'OPERADOR':<35} {'GRP':<5} {'TONELADAS':>12} {'TON/HR':>8} {'UEBD%':>7} {'HRS EF':>8} {'DÍAS':>6} {'DUMPS':>7}"
        lines.append(header)
        lines.append('-' * 120)

        # Filas
        for item in ranking_data[:10]:
            nombre = item['operador'][:33] if len(item['operador']) > 33 else item['operador']
            row = (f"{item['posicion']:<4} {nombre:<35} {item['grupo']:<5} "
                  f"{item['toneladas_total']:>12,} {item['ton_por_hr_efectiva']:>8.1f} "
                  f"{item['uebd']:>7.1f} {item['horas_efectivas']:>8.1f} "
                  f"{item['dias_trabajados']:>6} {item['dumps']:>7}")
            lines.append(row)

        lines.append('=' * 120)

        # Footer con estadísticas
        footer = (f"Total operadores: {stats.get('total_operadores', 'N/A')} | "
                 f"Período: {year} | "
                 f"Total toneladas: {stats.get('total_toneladas_formatted', 'N/A')}")
        lines.append(footer)
        lines.append('=' * 120)

        return '\n'.join(lines)

    def generate_comparison_chart(self, data_2024: List[Dict], data_2025: List[Dict]) -> Path:
        """
        Genera gráfico comparativo entre dos años

        Args:
            data_2024: Datos del ranking 2024
            data_2025: Datos del ranking 2025

        Returns:
            Path al archivo PNG generado
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle('COMPARACIÓN RANKINGS 2024 vs 2025', fontsize=16, fontweight='bold')

        # Top 5 de cada año
        top5_2024 = data_2024[:5]
        top5_2025 = data_2025[:5]

        ops_2024 = [' '.join(item['operador'].split()[:2]) for item in top5_2024]
        ops_2025 = [' '.join(item['operador'].split()[:2]) for item in top5_2025]

        tons_2024 = [item['toneladas_total'] for item in top5_2024]
        tons_2025 = [item['toneladas_total'] for item in top5_2025]

        uebd_2024 = [item['uebd'] for item in top5_2024]
        uebd_2025 = [item['uebd'] for item in top5_2025]

        # Gráfico 1: Toneladas 2024
        axes[0, 0].barh(ops_2024, tons_2024, color=plt.cm.Blues(0.7))
        axes[0, 0].set_title('Top 5 Producción 2024', fontweight='bold')
        axes[0, 0].set_xlabel('Toneladas')
        axes[0, 0].invert_yaxis()

        # Gráfico 2: Toneladas 2025
        axes[0, 1].barh(ops_2025, tons_2025, color=plt.cm.Oranges(0.7))
        axes[0, 1].set_title('Top 5 Producción 2025 (Ene-Jul)', fontweight='bold')
        axes[0, 1].set_xlabel('Toneladas')
        axes[0, 1].invert_yaxis()

        # Gráfico 3: UEBD 2024
        axes[1, 0].barh(ops_2024, uebd_2024, color=plt.cm.Greens(0.7))
        axes[1, 0].set_title('Top 5 UEBD 2024', fontweight='bold')
        axes[1, 0].set_xlabel('UEBD (%)')
        axes[1, 0].set_xlim(0, 100)
        axes[1, 0].invert_yaxis()

        # Gráfico 4: UEBD 2025
        axes[1, 1].barh(ops_2025, uebd_2025, color=plt.cm.Reds(0.7))
        axes[1, 1].set_title('Top 5 UEBD 2025 (Ene-Jul)', fontweight='bold')
        axes[1, 1].set_xlabel('UEBD (%)')
        axes[1, 1].set_xlim(0, 100)
        axes[1, 1].invert_yaxis()

        plt.tight_layout()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'comparacion_2024_vs_2025_{timestamp}.png'
        output_path = self.output_dir / filename

        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return output_path
