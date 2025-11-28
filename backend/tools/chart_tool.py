"""
MineDash AI - Chart Generator Tool
Herramienta para generar gráficos profesionales
INCLUYE: line, bar, scatter, pie, heatmap, box, WATERFALL
"""

import matplotlib
matplotlib.use('Agg')  # Backend sin GUI
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

# Configurar estilo
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10


class ChartGenerator:
    """
    Generador de gráficos profesionales
    
    Tipos soportados:
    - line: Gráfico de líneas
    - bar: Gráfico de barras
    - scatter: Gráfico de dispersión
    - pie: Gráfico circular
    - heatmap: Mapa de calor
    - box: Diagrama de caja
    - waterfall: Gráfico de cascada (análisis causal)
    """
    
    def __init__(self, charts_dir: Path):
        """
        Inicializar Chart Generator
        
        Args:
            charts_dir: Directorio donde guardar gráficos
        """
        self.charts_dir = Path(charts_dir)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        
        # Paleta de colores corporativa Codelco
        self.codelco_colors = ['#E63946', '#F77F00', '#FCBF49', '#06A77D', '#118AB2']
    
    def generate(
        self,
        chart_type: str,
        data: Dict[str, Any],
        title: str,
        xlabel: str = '',
        ylabel: str = '',
        figsize: tuple = (12, 6)
    ) -> Path:
        """
        Generar gráfico
        
        Args:
            chart_type: Tipo de gráfico
            data: Datos para el gráfico
            title: Título del gráfico
            xlabel: Etiqueta eje X
            ylabel: Etiqueta eje Y
            figsize: Tamaño de figura (ancho, alto)
            
        Returns:
            Path al archivo del gráfico generado
        """
        # Crear figura
        fig, ax = plt.subplots(figsize=figsize)
        
        try:
            if chart_type == 'line':
                self._generate_line(ax, data, title, xlabel, ylabel)
            
            elif chart_type == 'bar':
                self._generate_bar(ax, data, title, xlabel, ylabel)
            
            elif chart_type == 'scatter':
                self._generate_scatter(ax, data, title, xlabel, ylabel)
            
            elif chart_type == 'pie':
                self._generate_pie(ax, data, title)
            
            elif chart_type == 'heatmap':
                self._generate_heatmap(ax, data, title)
            
            elif chart_type == 'box':
                self._generate_box(ax, data, title, xlabel, ylabel)
            
            elif chart_type == 'waterfall':
                # FIX: Usar Plotly en vez de matplotlib para waterfall
                from tools.waterfall_plotly import generate_waterfall_plotly
                plt.close()  # Cerrar la figura matplotlib
                return generate_waterfall_plotly(data, title, ylabel, self.charts_dir)
            
            else:
                raise ValueError(f"Tipo de gráfico no soportado: {chart_type}")
            
            # Ajustar layout
            plt.tight_layout()
            
            # Guardar
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"chart_{chart_type}_{timestamp}.png"
            filepath = self.charts_dir / filename
            
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            return filepath
            
        except Exception as e:
            plt.close()
            raise Exception(f"Error generando gráfico: {str(e)}")
    
    def _generate_line(
        self,
        ax,
        data: Dict[str, Any],
        title: str,
        xlabel: str,
        ylabel: str
    ):
        """Generar gráfico de líneas"""
        # Extraer datos
        x = data.get('x', [])
        y = data.get('y', [])
        
        if isinstance(y, dict):
            # Múltiples series
            for i, (label, values) in enumerate(y.items()):
                color = self.codelco_colors[i % len(self.codelco_colors)]
                ax.plot(x, values, marker='o', label=label, color=color, linewidth=2)
            ax.legend()
        else:
            # Serie única
            ax.plot(x, y, marker='o', color=self.codelco_colors[0], linewidth=2)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    
    def _generate_bar(
        self,
        ax,
        data: Dict[str, Any],
        title: str,
        xlabel: str,
        ylabel: str
    ):
        """Generar gráfico de barras"""
        # Buscar datos con múltiples posibles nombres de claves
        x = data.get('x') or data.get('labels') or data.get('equipment_ids') or data.get('categories') or []
        y = data.get('y') or data.get('values') or data.get('availability') or data.get('data') or []
        
        if isinstance(y, dict):
            # Barras agrupadas
            x_pos = np.arange(len(x))
            width = 0.8 / len(y)
            
            for i, (label, values) in enumerate(y.items()):
                offset = width * i - (width * len(y) / 2) + width / 2
                color = self.codelco_colors[i % len(self.codelco_colors)]
                ax.bar(x_pos + offset, values, width, label=label, color=color)
            
            ax.set_xticks(x_pos)
            ax.set_xticklabels(x, rotation=45, ha='right')
            ax.legend()
        else:
            # Barras simples
            colors = [self.codelco_colors[i % len(self.codelco_colors)] for i in range(len(x))]
            ax.bar(x, y, color=colors)
            ax.set_xticklabels(x, rotation=45, ha='right')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(axis='y', alpha=0.3)
    
    def _generate_scatter(
        self,
        ax,
        data: Dict[str, Any],
        title: str,
        xlabel: str,
        ylabel: str
    ):
        """Generar gráfico de dispersión"""
        x = data.get('x', [])
        y = data.get('y', [])
        sizes = data.get('sizes', [50] * len(x))
        
        ax.scatter(x, y, s=sizes, color=self.codelco_colors[0], alpha=0.6)
        
        # Línea de tendencia si hay suficientes puntos
        if len(x) > 2:
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            ax.plot(x, p(x), "--", color=self.codelco_colors[1], alpha=0.8, label='Tendencia')
            ax.legend()
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    
    def _generate_pie(
        self,
        ax,
        data: Dict[str, Any],
        title: str
    ):
        """Generar gráfico circular"""
        labels = data.get('labels', [])
        values = data.get('values', [])
        
        colors = self.codelco_colors[:len(labels)]
        
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90
        )
        
        # Mejorar texto
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
    
    def _generate_heatmap(
        self,
        ax,
        data: Dict[str, Any],
        title: str
    ):
        """Generar mapa de calor"""
        # Convertir data a matriz si es necesario
        if 'matrix' in data:
            matrix = np.array(data['matrix'])
        else:
            matrix = np.array(data.get('values', [[0]]))
        
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto')
        
        # Etiquetas
        if 'xlabels' in data:
            ax.set_xticks(np.arange(len(data['xlabels'])))
            ax.set_xticklabels(data['xlabels'], rotation=45, ha='right')
        
        if 'ylabels' in data:
            ax.set_yticks(np.arange(len(data['ylabels'])))
            ax.set_yticklabels(data['ylabels'])
        
        # Colorbar
        plt.colorbar(im, ax=ax)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
    
    def _generate_box(
        self,
        ax,
        data: Dict[str, Any],
        title: str,
        xlabel: str,
        ylabel: str
    ):
        """Generar diagrama de caja"""
        values = data.get('values', [])
        labels = data.get('labels', [])
        
        bp = ax.boxplot(
            values,
            labels=labels,
            patch_artist=True,
            notch=True
        )
        
        # Colorear cajas
        for i, patch in enumerate(bp['boxes']):
            patch.set_facecolor(self.codelco_colors[i % len(self.codelco_colors)])
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(axis='y', alpha=0.3)
    
    def _generate_waterfall(
        self,
        ax,
        data: Dict[str, Any],
        title: str,
        xlabel: str,
        ylabel: str
    ):
        """
        Generar gráfico de cascada (waterfall) para análisis causal
        
        Formato esperado:
        {
            "x": ["Target", "Factor1", "Factor2", ..., "Alcanzado"],
            "y": [100, -15, -8, ..., 70],
            "measures": ["absolute", "relative", "relative", ..., "total"]
        }
        
        measures:
        - "absolute": Punto de inicio (verde)
        - "relative": Factores que suman/restan (rojo si negativo, verde si positivo)
        - "total": Resultado final (azul)
        """
        x_labels = data.get('x', [])
        values = data.get('y', [])
        measures = data.get('measures', ['relative'] * len(values))
        
        if not x_labels or not values:
            raise ValueError("Se requieren 'x' e 'y' para waterfall chart")
        
        # Validar longitudes
        if len(x_labels) != len(values) or len(x_labels) != len(measures):
            raise ValueError("x, y, y measures deben tener la misma longitud")
        
        # Calcular posiciones acumuladas
        cumulative = []
        current = 0
        
        for i, (val, measure) in enumerate(zip(values, measures)):
            if measure == "absolute":
                cumulative.append(0)  # Comienza desde 0
                current = val
            elif measure == "total":
                cumulative.append(0)  # Total también desde 0
                current = val
            else:  # relative
                cumulative.append(current)
                current += val
        
        # Posiciones x
        x_pos = np.arange(len(x_labels))
        
        # Colores según medida y valor
        colors = []
        for val, measure in zip(values, measures):
            if measure == "absolute":
                colors.append('#06A77D')  # Verde (target)
            elif measure == "total":
                colors.append('#118AB2')  # Azul (alcanzado)
            else:  # relative
                if val < 0:
                    colors.append('#E63946')  # Rojo (negativo)
                else:
                    colors.append('#06A77D')  # Verde (positivo)
        
        # Generar barras
        bars = ax.bar(x_pos, values, bottom=cumulative, color=colors, width=0.6, edgecolor='black', linewidth=1)
        
        # Agregar líneas conectoras
        for i in range(len(x_pos) - 1):
            # Línea horizontal conectando barras
            y_start = cumulative[i] + values[i]
            y_end = cumulative[i + 1]
            
            # Solo dibujar línea si no es el mismo valor (evita líneas sobre sí mismas)
            if abs(y_start - y_end) > 0.01:
                ax.plot(
                    [x_pos[i] + 0.3, x_pos[i + 1] - 0.3],
                    [y_start, y_start],
                    color='gray',
                    linestyle='--',
                    linewidth=1,
                    alpha=0.5
                )
        
        # Etiquetas de valores sobre/bajo las barras
        for i, (bar, val, measure) in enumerate(zip(bars, values, measures)):
            height = bar.get_height()
            bottom = bar.get_y()
            
            # Posición de la etiqueta
            if measure in ["absolute", "total"]:
                # Para absolute y total, mostrar arriba
                label_y = bottom + height + max(values) * 0.02
                va = 'bottom'
            else:
                # Para relative, mostrar en medio de la barra
                label_y = bottom + height / 2
                va = 'center'
            
            # Formato del valor
            if abs(val) >= 1000:
                label_text = f'{val:,.0f}'
            else:
                label_text = f'{val:.1f}'
            
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                label_y,
                label_text,
                ha='center',
                va=va,
                fontweight='bold',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='none')
            )
        
        # Configurar ejes
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels, rotation=45, ha='right')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        
        # Grid horizontal
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        # Línea en y=0 si hay valores negativos
        if any(v < 0 for v in values):
            ax.axhline(y=0, color='black', linewidth=0.8, alpha=0.5)
        
        # Leyenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#06A77D', edgecolor='black', label='Target/Positivo'),
            Patch(facecolor='#E63946', edgecolor='black', label='Pérdida/Negativo'),
            Patch(facecolor='#118AB2', edgecolor='black', label='Alcanzado')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
    
    def create_dashboard(
        self,
        charts_data: List[Dict[str, Any]],
        dashboard_title: str
    ) -> Path:
        """
        Crear dashboard con múltiples gráficos
        
        Args:
            charts_data: Lista de configs de gráficos
            dashboard_title: Título del dashboard
            
        Returns:
            Path al dashboard generado
        """
        n_charts = len(charts_data)
        
        # Calcular layout
        if n_charts <= 2:
            rows, cols = 1, n_charts
        elif n_charts <= 4:
            rows, cols = 2, 2
        elif n_charts <= 6:
            rows, cols = 2, 3
        else:
            rows = (n_charts + 2) // 3
            cols = 3
        
        fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
        
        if n_charts == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        # Generar cada gráfico
        for i, chart_data in enumerate(charts_data):
            try:
                chart_type = chart_data['type']
                data = chart_data['data']
                title = chart_data['title']
                
                if chart_type == 'line':
                    self._generate_line(axes[i], data, title, '', '')
                elif chart_type == 'bar':
                    self._generate_bar(axes[i], data, title, '', '')
                elif chart_type == 'pie':
                    self._generate_pie(axes[i], data, title)
                elif chart_type == 'waterfall':
                    self._generate_waterfall(axes[i], data, title, '', '')
                # Agregar más tipos según necesidad
                
            except Exception as e:
                axes[i].text(0.5, 0.5, f'Error: {str(e)}', 
                           ha='center', va='center', transform=axes[i].transAxes)
        
        # Ocultar ejes sobrantes
        for i in range(n_charts, len(axes)):
            axes[i].set_visible(False)
        
        # Título general
        fig.suptitle(dashboard_title, fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Guardar
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dashboard_{timestamp}.png"
        filepath = self.charts_dir / filename
        
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return filepath


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    # Crear generator
    generator = ChartGenerator(Path("outputs/charts"))
    
    # Ejemplo 1: Gráfico de líneas
    print("\n=== GENERANDO GRÁFICO DE LÍNEAS ===")
    data_line = {
        'x': ['Ene', 'Feb', 'Mar', 'Abr', 'May'],
        'y': {
            'Producción': [8500, 9200, 8800, 9500, 9100],
            'Meta': [9000, 9000, 9000, 9000, 9000]
        }
    }
    
    path = generator.generate(
        chart_type='line',
        data=data_line,
        title='Producción Mensual vs Meta',
        xlabel='Mes',
        ylabel='Toneladas'
    )
    print(f"✅ Gráfico guardado: {path}")
    
    # Ejemplo 2: Gráfico de barras
    print("\n=== GENERANDO GRÁFICO DE BARRAS ===")
    data_bar = {
        'x': ['OP001', 'OP002', 'OP003', 'OP004', 'OP005'],
        'y': [85, 92, 78, 88, 95]
    }
    
    path = generator.generate(
        chart_type='bar',
        data=data_bar,
        title='Productividad por Operador',
        xlabel='Operador',
        ylabel='Productividad (%)'
    )
    print(f"✅ Gráfico guardado: {path}")
    
    # Ejemplo 3: Gráfico circular
    print("\n=== GENERANDO GRÁFICO CIRCULAR ===")
    data_pie = {
        'labels': ['Carguío', 'Transporte', 'Perforación', 'Servicios'],
        'values': [45, 30, 15, 10]
    }
    
    path = generator.generate(
        chart_type='pie',
        data=data_pie,
        title='Distribución de Recursos'
    )
    print(f"✅ Gráfico guardado: {path}")
    
    # Ejemplo 4: Gráfico de cascada (WATERFALL)
    print("\n=== GENERANDO GRÁFICO DE CASCADA ===")
    data_waterfall = {
        'x': ['Target', 'Delays', 'Mantención', 'Clima', 'Alcanzado'],
        'y': [100, -15, -8, -7, 70],
        'measures': ['absolute', 'relative', 'relative', 'relative', 'total']
    }
    
    path = generator.generate(
        chart_type='waterfall',
        data=data_waterfall,
        title='Análisis Causal - Cumplimiento Producción',
        xlabel='Factores',
        ylabel='Toneladas (%)'
    )
    print(f"✅ Gráfico guardado: {path}")